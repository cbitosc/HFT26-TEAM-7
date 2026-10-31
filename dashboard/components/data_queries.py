"""
data_queries.py - the single data layer for the SmallWorld dashboard.

Built against the real pipeline schema (pipeline/ingest.py):
  media(image_id, file_path, location_id, datetime, sequence_id, blur_score, status, gt_label)
  detections(id, image_id, category, confidence, bbox_x..bbox_h, crop_path, needs_review)
  classifications(id, detection_id, species_common, species_sci, family, conf_top1..3,
                  rolled_up_to, human_label, status)
  encounters(...)   <- written by pipeline/encounter.py; here encounters are recomputed live
                       with the same 30-min rule so they respond to the confidence filter.

Species label for each animal detection, in priority order:
  1. human_label            (scientist-verified in the Review page)
  2. SpeciesNet prediction  (classifications table, after `--step classify`)
  3. Caltech ground truth   (media.gt_label from the COCO annotations)
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from config import DB_PATH

GAP_MINUTES = 30            # independence window, same as pipeline/encounter.py
BLUR_THRESHOLD = 100.0      # same default as pipeline/quality.py
NON_ANIMAL_LABELS = {"", "empty", "car", "vehicle", "person", "human", "none", "blank"}

# ── Species reference for the Caltech Camera Traps classes ─────
# key: (display name, scientific name, family, ecological group)
SPECIES = {
    "opossum":       ("Virginia Opossum",   "Didelphis virginiana",     "Didelphidae", "herbivore"),
    "raccoon":       ("Raccoon",            "Procyon lotor",            "Procyonidae", "carnivore"),
    "squirrel":      ("Squirrel",           "Sciurus sp.",              "Sciuridae",   "herbivore"),
    "bobcat":        ("Bobcat",             "Lynx rufus",               "Felidae",     "carnivore"),
    "skunk":         ("Striped Skunk",      "Mephitis mephitis",        "Mephitidae",  "carnivore"),
    "dog":           ("Domestic Dog",       "Canis familiaris",         "Canidae",     "carnivore"),
    "coyote":        ("Coyote",             "Canis latrans",            "Canidae",     "carnivore"),
    "rabbit":        ("Cottontail Rabbit",  "Sylvilagus sp.",           "Leporidae",   "herbivore"),
    "bird":          ("Bird",               "Aves",                     "—",           "avian"),
    "cat":           ("Domestic Cat",       "Felis catus",              "Felidae",     "carnivore"),
    "badger":        ("American Badger",    "Taxidea taxus",            "Mustelidae",  "carnivore"),
    "fox":           ("Gray Fox",           "Urocyon cinereoargenteus", "Canidae",     "carnivore"),
    "rodent":        ("Rodent",             "Rodentia",                 "—",           "herbivore"),
    "deer":          ("Mule Deer",          "Odocoileus hemionus",      "Cervidae",    "herbivore"),
    "mountain_lion": ("Mountain Lion",      "Puma concolor",            "Felidae",     "carnivore"),
    "pig":           ("Wild Boar",          "Sus scrofa",               "Suidae",      "herbivore"),
    "cow":           ("Cattle",             "Bos taurus",               "Bovidae",     "herbivore"),
    "lizard":        ("Lizard",             "Squamata",                 "—",           "herbivore"),
    "insect":        ("Insect",             "Insecta",                  "—",           "herbivore"),
}
# words that map free-text SpeciesNet names onto the keys above
ALIASES = [
    ("opossum", "opossum"), ("raccoon", "raccoon"), ("squirrel", "squirrel"), ("bobcat", "bobcat"),
    ("lynx", "bobcat"), ("skunk", "skunk"), ("coyote", "coyote"), ("dog", "dog"), ("rabbit", "rabbit"),
    ("cottontail", "rabbit"), ("hare", "rabbit"), ("badger", "badger"), ("fox", "fox"),
    ("deer", "deer"), ("puma", "mountain_lion"), ("mountain lion", "mountain_lion"), ("cougar", "mountain_lion"),
    ("boar", "pig"), ("pig", "pig"), ("cattle", "cow"), ("cow", "cow"), ("lizard", "lizard"),
    ("cat", "cat"), ("mouse", "rodent"), ("rat", "rodent"), ("rodent", "rodent"), ("woodrat", "rodent"),
    ("bird", "bird"), ("aves", "bird"), ("owl", "bird"), ("hawk", "bird"), ("quail", "bird"),
    ("crow", "bird"), ("raven", "bird"), ("jay", "bird"), ("turkey", "bird"),
]
GROUP_LABELS = {"carnivore": "Carnivora", "herbivore": "Herbivores & Omnivores", "avian": "Avian"}


def species_key(name) -> str:
    """Normalise any label (ground truth, SpeciesNet common name, human label) to a key."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    n = str(name).strip().lower().replace("-", " ")
    if n.replace(" ", "_") in SPECIES:
        return n.replace(" ", "_")
    for word, key in ALIASES:
        if f" {word} " in f" {n} " or n.endswith(word):
            return key
    return n


def species_info(key: str) -> dict:
    if key in SPECIES:
        common, sci, fam, grp = SPECIES[key]
    else:
        common, sci, fam, grp = (key.title() if key else "Unidentified"), "", "—", "herbivore"
    return {"common": common, "sci": sci, "family": fam, "group": grp}


# ── Connection / cache plumbing ────────────────────────────────
def db_exists() -> bool:
    return Path(DB_PATH).exists()


def _db_version() -> float:
    """Cache key: changes whenever the pipeline or the Review page writes to the DB."""
    p = Path(DB_PATH)
    return p.stat().st_mtime if p.exists() else 0.0


def connect():
    return sqlite3.connect(str(DB_PATH))


def _cols(conn, table):
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


@st.cache_data(show_spinner=False)
def _load(version: float):
    conn = connect()
    mcols = _cols(conn, "media")
    gt = "m.gt_label" if "gt_label" in mcols else "NULL"
    media = pd.read_sql(f"""SELECT image_id, file_path, location_id, datetime, sequence_id,
                                   blur_score, status, {gt.replace('m.', '')} AS gt_label
                            FROM media m""", conn)

    has_cls = bool(_cols(conn, "classifications"))
    cls_sel = ("c.id AS cls_id, c.species_common AS cls_species, c.species_sci AS cls_sci, "
               "c.family AS cls_family, c.conf_top1, c.rolled_up_to, c.human_label, c.status AS cls_status")
    cls_join = "LEFT JOIN classifications c ON c.detection_id = d.id"
    if not has_cls:
        cls_sel = ("NULL AS cls_id, NULL AS cls_species, NULL AS cls_sci, NULL AS cls_family, "
                   "NULL AS conf_top1, NULL AS rolled_up_to, NULL AS human_label, NULL AS cls_status")
        cls_join = ""
    reviewed = "d.reviewed" if "reviewed" in _cols(conn, "detections") else "0"
    det = pd.read_sql(f"""
        SELECT d.id AS det_id, {reviewed} AS reviewed, d.image_id, d.category, d.confidence AS det_conf,
               d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h, d.crop_path, d.needs_review,
               m.file_path, m.location_id, m.datetime, m.status AS media_status,
               {gt} AS gt_label, {cls_sel}
        FROM detections d JOIN media m ON m.image_id = d.image_id
        {cls_join}""", conn)
    n_cls = conn.execute("SELECT COUNT(*) FROM classifications WHERE human_label IS NULL").fetchone()[0] if has_cls else 0
    conn.close()

    media["ts"] = pd.to_datetime(media["datetime"], errors="coerce")
    media["location_id"] = media["location_id"].astype(str)

    det["location_id"] = det["location_id"].astype(str)
    det["ts"] = pd.to_datetime(det["datetime"], errors="coerce")
    det["hour"] = det["ts"].dt.hour
    det["month"] = det["ts"].dt.to_period("M").astype(str)

    # Resolve species label + its provenance
    keys, sources, confs = [], [], []
    for r in det.itertuples():
        if r.cls_status == "rejected":
            keys.append(""); sources.append("Rejected"); confs.append(0.0); continue
        if isinstance(r.human_label, str) and r.human_label.strip():
            keys.append(species_key(r.human_label)); sources.append("Verified"); confs.append(1.0)
        elif isinstance(r.cls_species, str) and r.cls_species.strip():
            src = "Verified" if r.cls_status == "human_verified" else "SpeciesNet"
            keys.append(species_key(r.cls_species)); sources.append(src)
            confs.append(1.0 if src == "Verified" else float(r.conf_top1 or 0))
        elif isinstance(r.gt_label, str) and r.gt_label.strip().lower() not in NON_ANIMAL_LABELS:
            keys.append(species_key(r.gt_label)); sources.append("Ground truth")
            confs.append(float(r.det_conf or 0))
        else:
            keys.append(""); sources.append("Unidentified"); confs.append(float(r.det_conf or 0))
    det["species"] = keys
    det["label_source"] = sources
    det["conf"] = confs
    info = det["species"].map(species_info)
    det["common"] = [i["common"] for i in info]
    det["sci"] = [i["sci"] for i in info]
    det["family"] = [i["family"] for i in info]
    det["group"] = [i["group"] for i in info]
    det["unverified"] = (det["cls_status"] == "needs_review") | (det["needs_review"] == 1)
    return media, det, n_cls


def load():
    """Returns (media_df, detections_df, n_classifications). Cached until the DB changes."""
    return _load(_db_version())


def animal_obs(det: pd.DataFrame, min_conf: float = 0.0) -> pd.DataFrame:
    """Animal detections that pass the confidence gate and have a usable species label."""
    a = det[(det["category"] == "animal") & (det["label_source"] != "Rejected")]
    return a[a["conf"] >= min_conf]


def species_obs(det, min_conf=0.0):
    a = animal_obs(det, min_conf)
    return a[a["species"] != ""]


def ensure_review_schema(conn):
    """Adds detections.reviewed (0/1) the first time the Review page saves a decision. Idempotent."""
    if "reviewed" not in _cols(conn, "detections"):
        conn.execute("ALTER TABLE detections ADD COLUMN reviewed INTEGER DEFAULT 0")
        conn.commit()


def ensure_feedback_schema(conn):
    """Creates the feedback_log table for human-in-the-loop learning. Idempotent."""
    conn.execute("""CREATE TABLE IF NOT EXISTS feedback_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
        detection_id INTEGER NOT NULL,
        image_id    TEXT,
        location_id TEXT,
        action      TEXT    NOT NULL,   -- accept, relabel, reject, confirm, false_positive
        model_prediction TEXT,          -- what the AI predicted
        model_confidence REAL,          -- AI's confidence score
        human_label TEXT,               -- what the human decided
        previous_label TEXT,            -- label before human intervention
        label_source TEXT,              -- SpeciesNet / Ground truth / Unidentified
        FOREIGN KEY (detection_id) REFERENCES detections(id)
    )""")
    conn.commit()


def log_feedback(conn, detection_id: int, image_id: str, location_id: str,
                 action: str, model_prediction: str, model_confidence: float,
                 human_label: str, previous_label: str, label_source: str):
    """Record a human review decision into the feedback_log for model retraining."""
    ensure_feedback_schema(conn)
    conn.execute("""INSERT INTO feedback_log
        (detection_id, image_id, location_id, action, model_prediction,
         model_confidence, human_label, previous_label, label_source)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (detection_id, image_id, location_id, action, model_prediction,
         model_confidence, human_label, previous_label, label_source))


def feedback_stats(conn=None) -> dict:
    """Aggregate feedback statistics for model learning analytics."""
    close = False
    if conn is None:
        conn = connect()
        close = True
    try:
        ensure_feedback_schema(conn)
        total = conn.execute("SELECT COUNT(*) FROM feedback_log").fetchone()[0]
        if total == 0:
            return {"total_decisions": 0, "accuracy": None, "corrections": [],
                    "by_action": {}, "by_species": [], "recent": []}

        by_action = dict(conn.execute(
            "SELECT action, COUNT(*) FROM feedback_log GROUP BY action").fetchall())

        # Model accuracy: how often the human accepted the AI's prediction
        accepted = by_action.get("accept", 0) + by_action.get("confirm", 0)
        corrected = by_action.get("relabel", 0)
        rejected = by_action.get("reject", 0) + by_action.get("false_positive", 0)
        accuracy = accepted / total if total else 0.0

        # Most common corrections (what the AI got wrong)
        corrections = conn.execute("""
            SELECT model_prediction, human_label, COUNT(*) as cnt
            FROM feedback_log WHERE action='relabel' AND human_label IS NOT NULL
            GROUP BY model_prediction, human_label ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        # Per-species accuracy
        by_species = conn.execute("""
            SELECT model_prediction,
                   SUM(CASE WHEN action IN ('accept','confirm') THEN 1 ELSE 0 END) as correct,
                   COUNT(*) as total
            FROM feedback_log WHERE model_prediction IS NOT NULL AND model_prediction != ''
            GROUP BY model_prediction ORDER BY total DESC LIMIT 15
        """).fetchall()

        # Recent decisions for timeline
        recent = conn.execute("""
            SELECT timestamp, action, model_prediction, human_label, model_confidence
            FROM feedback_log ORDER BY timestamp DESC LIMIT 20
        """).fetchall()

        return {
            "total_decisions": total,
            "accepted": accepted,
            "corrected": corrected,
            "rejected": rejected,
            "accuracy": round(accuracy, 3),
            "by_action": by_action,
            "corrections": [{"predicted": r[0], "corrected_to": r[1], "count": r[2]} for r in corrections],
            "by_species": [{"species": r[0], "correct": r[1], "total": r[2],
                            "accuracy": round(r[1] / r[2], 3) if r[2] else 0} for r in by_species],
            "recent": [{"time": r[0], "action": r[1], "predicted": r[2],
                        "human": r[3], "confidence": r[4]} for r in recent],
        }
    finally:
        if close:
            conn.close()


# ── Independent encounters (30-min rule, same species + site) ──
def encounters(obs: pd.DataFrame) -> pd.DataFrame:
    o = obs.dropna(subset=["ts"]).sort_values(["location_id", "species", "ts"])
    if o.empty:
        return pd.DataFrame(columns=["location_id", "species", "common", "sci", "group",
                                     "start", "end", "images", "hour", "month"])
    gap = o.groupby(["location_id", "species"])["ts"].diff() > pd.Timedelta(minutes=GAP_MINUTES)
    first = o.groupby(["location_id", "species"]).cumcount() == 0
    o = o.assign(event=(gap | first).cumsum())
    ev = o.groupby("event").agg(location_id=("location_id", "first"), species=("species", "first"),
                                common=("common", "first"), sci=("sci", "first"), group=("group", "first"),
                                start=("ts", "min"), end=("ts", "max"), images=("det_id", "count"))
    ev["hour"] = ev["start"].dt.hour
    ev["month"] = ev["start"].dt.to_period("M").astype(str)
    return ev.reset_index(drop=True)


# ── Effort ─────────────────────────────────────────────────────
def trap_nights(media: pd.DataFrame) -> pd.Series:
    """Camera-days with at least one capture, per location (effort proxy)."""
    m = media.dropna(subset=["ts"])
    return m.groupby("location_id")["ts"].apply(lambda s: s.dt.date.nunique())


def overview(media, det):
    tn = trap_nights(media)
    status = media["status"].value_counts()
    processed = media[media["status"].isin(["animal_detected", "empty", "needs_review", "sharp"])]
    return {
        "images": len(media),
        "stations": media["location_id"].nunique(),
        "operational": processed["location_id"].nunique(),
        "trap_nights": int(tn.sum()),
        "animal_dets": int((det["category"] == "animal").sum()),
        "person_dets": int((det["category"] == "person").sum()),
        "vehicle_dets": int((det["category"] == "vehicle").sum()),
        "status": status.to_dict(),
        "blurry": int(status.get("blurry", 0)),
        "empty": int(status.get("empty", 0)),
        "review_imgs": int(status.get("needs_review", 0)),
        "date_min": media["ts"].min(),
        "date_max": media["ts"].max(),
    }


# ── Temporal ───────────────────────────────────────────────────
def diel_bucket(h):
    if h >= 20 or h < 5:
        return "nocturnal"
    if 5 <= h < 8 or 17 <= h < 20:
        return "crepuscular"
    return "diurnal"


def diel(ev: pd.DataFrame) -> dict:
    n = len(ev)
    counts = ev["hour"].map(diel_bucket).value_counts() if n else pd.Series(dtype=int)
    out = {"total": n}
    for k in ("nocturnal", "crepuscular", "diurnal"):
        c = int(counts.get(k, 0))
        out[k] = c
        out[k + "_pct"] = round(c / n * 100, 1) if n else 0.0
    return out


def hourly_by_group(ev: pd.DataFrame) -> list[dict]:
    rows = []
    for h in range(24):
        e = ev[ev["hour"] == h]
        rows.append({"hour": h, **{g: int((e["group"] == g).sum()) for g in ("carnivore", "herbivore", "avian")}})
    return rows


def monthly(ev: pd.DataFrame) -> list[dict]:
    if ev.empty:
        return []
    s = ev.groupby("month").size()
    idx = pd.period_range(min(s.index), max(s.index), freq="M").astype(str)
    s = s.reindex(idx, fill_value=0)
    return [{"month": m, "count": int(c)} for m, c in s.items()]


# ── Spatial ────────────────────────────────────────────────────
def location_scorecard(media, obs, ev) -> pd.DataFrame:
    tn = trap_nights(media)
    rows = []
    for loc in sorted(media["location_id"].unique(), key=lambda s: (len(s), s)):
        o = obs[obs["location_id"] == loc]
        e = ev[ev["location_id"] == loc]
        t = int(tn.get(loc, 0))
        dom = o[o["species"] != ""]["species"].value_counts()
        dk = dom.index[0] if len(dom) else ""
        di = species_info(dk)
        classified = o[o["label_source"].isin(["SpeciesNet", "Verified"])]
        verified = classified[(classified["label_source"] == "Verified") | (classified["cls_status"] == "auto")]
        rows.append({
            "location_id": loc, "trap_nights": t, "detections": len(o), "encounters": len(e),
            "rate": round(len(e) / t * 100, 1) if t else 0.0,
            "dominant_key": dk, "dominant": di["common"] if dk else "—", "dominant_sci": di["sci"],
            "n_species": int(o["species"].replace("", pd.NA).nunique()),
            "avg_conf": round(float(o["conf"].mean()), 3) if len(o) else 0.0,
            "verified_pct": round(len(verified) / len(classified) * 100, 1) if len(classified) else None,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    hi = df["rate"].quantile(0.75)
    def status(r):
        if r["encounters"] < 2:
            return "LOW DATA"
        if r["verified_pct"] is not None and r["verified_pct"] >= 90:
            return "VERIFIED"
        if r["rate"] >= hi:
            return "HIGH ACTIVITY"
        return "STABLE"
    df["status"] = df.apply(status, axis=1)
    return df.sort_values(["rate", "encounters"], ascending=False).reset_index(drop=True)


# ── Species registry ───────────────────────────────────────────
def species_table(obs, ev) -> pd.DataFrame:
    o = obs[obs["species"] != ""]
    if o.empty:
        return pd.DataFrame()
    g = o.groupby("species").agg(detections=("det_id", "count"), avg_conf=("conf", "mean"),
                                 locations=("location_id", "nunique"), unverified=("unverified", "sum"),
                                 source=("label_source", lambda s: s.value_counts().index[0]))
    e = ev.groupby("species").size().rename("encounters")
    noct = ev.assign(n=ev["hour"].map(diel_bucket) == "nocturnal").groupby("species")["n"].mean().rename("nocturnal")
    g = g.join(e).join(noct).fillna({"encounters": 0, "nocturnal": 0})
    g["peak_hour"] = o.dropna(subset=["hour"]).groupby("species")["hour"].agg(
        lambda s: int(s.value_counts().index[0]) if len(s) else None)
    for col in ("common", "sci", "family", "group"):
        g[col] = [species_info(k)[col] for k in g.index]
    return g.sort_values("detections", ascending=False).reset_index()


# ── Model benchmarks (computed against Caltech ground truth) ───
def benchmarks(media, det, n_cls) -> dict:
    out = {}
    m = media[media["gt_label"].notna()]
    processed = m[m["status"].isin(["animal_detected", "empty", "needs_review"])]
    if len(processed):
        truth = ~processed["gt_label"].str.lower().isin(NON_ANIMAL_LABELS)
        pred = processed["status"].isin(["animal_detected", "needs_review"])
        tp = int((truth & pred).sum()); fp = int((~truth & pred).sum()); fn = int((truth & ~pred).sum())
        tn_ = int((~truth & ~pred).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        out["md"] = {"n": len(processed), "precision": prec, "recall": rec,
                     "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
                     "tp": tp, "fp": fp, "fn": fn, "tn": tn_,
                     "mean_conf": float(det.loc[det["category"] == "animal", "det_conf"].mean() or 0)}
    cls = det[det["cls_species"].notna() & det["human_label"].isna() & det["gt_label"].notna()]
    if n_cls and len(cls):
        match = cls["cls_species"].map(species_key) == cls["gt_label"].map(species_key)
        out["sn"] = {"n": len(cls), "top1": float(match.mean()),
                     "rolled": float(cls["rolled_up_to"].notna().mean()),
                     "review": float((cls["cls_status"] == "needs_review").mean()),
                     "taxa": int(det["cls_species"].dropna().nunique())}
    scored = media[media["blur_score"].notna()]
    out["blur"] = {"scored": len(scored),
                   "blurry_pct": float((media["status"] == "blurry").sum() / len(scored)) if len(scored) else 0.0,
                   "mean_score": float(scored["blur_score"].mean()) if len(scored) else 0.0,
                   "empty_pct": float((media["status"] == "empty").sum() / len(media)) if len(media) else 0.0,
                   "threshold": BLUR_THRESHOLD}
    return out


# ── Snapshot for the Featherless LLM ───────────────────────────
def llm_snapshot(media, det, n_cls, min_conf) -> dict:
    obs = species_obs(det, min_conf)
    ev = encounters(obs)
    sp = species_table(obs, ev)
    loc = location_scorecard(media, obs, ev)
    d = diel(ev)
    ov = overview(media, det)
    return {
        "survey": {"images": ov["images"], "stations": ov["stations"], "trap_nights": ov["trap_nights"],
                   "date_range": f"{ov['date_min']:%Y-%m-%d} to {ov['date_max']:%Y-%m-%d}" if pd.notna(ov["date_min"]) else None,
                   "confidence_threshold": min_conf, "independence_window_min": GAP_MINUTES},
        "label_provenance": obs["label_source"].value_counts().to_dict(),
        "species_classified_by_speciesnet": n_cls,
        "unverified_detections": int(obs["unverified"].sum()),
        "blurry_images_rejected": ov["blurry"], "empty_frames": ov["empty"],
        "independent_encounters": len(ev),
        "diel_activity_pct": {k: d[k + "_pct"] for k in ("nocturnal", "crepuscular", "diurnal")},
        "top_species": [{"species": r.common, "detections": int(r.detections), "encounters": int(r.encounters),
                         "avg_confidence": round(float(r.avg_conf), 2), "nocturnal_share": round(float(r.nocturnal), 2)}
                        for r in sp.head(8).itertuples()] if len(sp) else [],
        "top_locations": [{"location": r.location_id, "encounters": int(r.encounters),
                           "rate_per_100_trap_nights": r.rate, "dominant": r.dominant}
                          for r in loc.head(5).itertuples()] if len(loc) else [],
        "person_detections": ov["person_dets"], "vehicle_detections": ov["vehicle_dets"],
    }
