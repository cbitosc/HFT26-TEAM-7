"""
classify.py - SpeciesNet species ID on MegaDetector crops.
The SpeciesNet ensemble already rolls low-confidence predictions up the taxonomy
(species -> genus -> family -> order -> class); we record the level reached and
flag anything below CONF_MIN, or not resolved to species, for human review.
"""
import os
import sqlite3
from pathlib import Path
from config import DB_PATH

CONF_MIN = 0.5
BATCH = 32
LEVELS = ["class", "order", "family", "genus", "species"]   # label parts 1..5


def _norm(p) -> str:
    """Normalise a path for matching: resolves '..'/'.' segments and
    case-folds on Windows (where paths are case-insensitive), without
    touching the filesystem. Path.resolve() is avoided here because it
    can mint a different string for the same file (e.g. an extended-length
    \\\\?\\ prefix, or a differently-cased drive letter) than what
    SpeciesNet echoes back, which silently drops every match."""
    return os.path.normcase(os.path.normpath(str(p)))


def parse_label(label: str):
    """'uuid;class;order;family;genus;species;common' -> (common, scientific, family, level)."""
    parts = (label.split(";") + [""] * 7)[:7]
    common = parts[6] or parts[5] or parts[4] or parts[3] or parts[2] or parts[1] or label
    sci = f"{parts[4]} {parts[5]}".strip()
    level = "none"
    for i, lv in enumerate(LEVELS, start=1):
        if parts[i]:
            level = lv
    return common, sci, parts[3], level


def run():
    try:
        from speciesnet import SpeciesNet, DEFAULT_MODEL
    except ImportError as e:
        raise SystemExit(f"speciesnet not importable ({e}). Run: pip install speciesnet")

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT d.id, d.crop_path FROM detections d
        WHERE d.category='animal' AND d.crop_path IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM classifications c WHERE c.detection_id=d.id)""").fetchall()
    rows = [(i, p) for i, p in rows if Path(p).exists()]
    print(f"Classifying {len(rows)} crops ...")
    if not rows:
        return

    print("Loading SpeciesNet (first run downloads model weights) ...")
    model = SpeciesNet(DEFAULT_MODEL, geofence=False)

    total_skipped = 0
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        out = model.predict(filepaths=[p for _, p in chunk], run_mode="single_thread", progress_bars=False)
        preds = out.get("predictions", [])
        by_path = {_norm(p["filepath"]): p for p in preds if "filepath" in p}
        chunk_skipped = 0
        for det_id, crop in chunk:
            pr = by_path.get(_norm(crop))
            if not pr:
                chunk_skipped += 1
                continue
            # SpeciesNet >= 4.0 nests the classification under
            # predictions[i]["detections"][j]["processed_classification"]
            # rather than the old flat "prediction"/"prediction_score"/
            # "classifications" keys. Pick the highest-confidence detection
            # (crops are already localised, so there's normally just one).
            dets = pr.get("detections") or []
            d0 = max(dets, key=lambda d: d.get("conf", 0)) if dets else None
            pc = (d0 or {}).get("processed_classification")
            if not pc or "class" not in pc:
                chunk_skipped += 1
                continue
            common, sci, family, level = parse_label(pc["class"])
            conf1 = float(pc.get("score") or 0.0)
            scores = (d0.get("raw_classifications") or {}).get("scores", [])
            c2 = float(scores[1]) if len(scores) > 1 else None
            c3 = float(scores[2]) if len(scores) > 2 else None
            review = conf1 < CONF_MIN or level != "species"
            rolled = None if level == "species" else f"{level}: {common}"
            conn.execute("""INSERT INTO classifications
                (detection_id, species_common, species_sci, family, conf_top1, conf_top2, conf_top3,
                 rolled_up_to, status) VALUES (?,?,?,?,?,?,?,?,?)""",
                (det_id, common, sci, family, conf1, c2, c3, rolled,
                 "needs_review" if review else "auto"))
            if review:
                conn.execute("UPDATE detections SET needs_review=1 WHERE id=?", (det_id,))
        conn.commit()
        total_skipped += chunk_skipped
        status = f"  {min(start + BATCH, len(rows))}/{len(rows)}"
        if chunk_skipped:
            status += f"  ({chunk_skipped} skipped - no detections/classification for that crop)"
        print(status)
    conn.close()
    if total_skipped:
        print(f"NOTE: {total_skipped}/{len(rows)} crops had no SpeciesNet detection/classification result "
              f"(e.g. the crop was too ambiguous for SpeciesNet's own internal detector) and were left "
              f"unclassified. They'll be retried on the next classify run.")
    print("Classification complete.")


if __name__ == "__main__":
    run()
