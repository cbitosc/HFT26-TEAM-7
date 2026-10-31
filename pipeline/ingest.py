"""
ingest.py - loads Caltech Camera Traps (CCT20) annotation files into SQLite.

caltech_coco.json may be: a plain COCO json, a gzip'd json, or (as downloaded
from LILA) a tar / tar.gz holding several *_annotations.json files. All handled.
Images are sampled across locations (fixed seed) so --limit gives variety.
"""
import gzip, io, json, random, sqlite3, tarfile
from collections import defaultdict
from config import DB_PATH, ANNOTATION_ARCHIVE


def get_db():
    return sqlite3.connect(DB_PATH)


def create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS media (
            image_id TEXT PRIMARY KEY, file_path TEXT NOT NULL, location_id TEXT,
            datetime TEXT, sequence_id TEXT, blur_score REAL,
            status TEXT DEFAULT 'pending', gt_label TEXT);
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT, image_id TEXT, category TEXT,
            confidence REAL, bbox_x REAL, bbox_y REAL, bbox_w REAL, bbox_h REAL,
            crop_path TEXT, needs_review INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, detection_id INTEGER,
            species_common TEXT, species_sci TEXT, family TEXT,
            conf_top1 REAL, conf_top2 REAL, conf_top3 REAL,
            rolled_up_to TEXT, human_label TEXT, status TEXT DEFAULT 'auto');
        CREATE TABLE IF NOT EXISTS encounters (
            id INTEGER PRIMARY KEY AUTOINCREMENT, location_id TEXT, species_common TEXT,
            event_start TEXT, event_end TEXT, image_count INTEGER, trap_nights REAL);
    """)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(media)")]
    if "gt_label" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN gt_label TEXT")
    conn.commit()


def _decode(raw: bytes) -> bytes:
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def _json_docs(raw: bytes):
    """Yield (name, dict) for every COCO json inside the file, whatever its wrapping."""
    raw = _decode(raw)
    if len(raw) > 512 and raw[257:262] == b"ustar":          # tar archive
        with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
            for m in tf.getmembers():
                if m.isfile() and m.name.endswith(".json"):
                    yield m.name, json.loads(tf.extractfile(m).read().decode("utf-8"))
    else:
        yield "caltech_coco.json", json.loads(raw.decode("utf-8-sig"))


def load_annotations():
    if not ANNOTATION_ARCHIVE.exists():
        raise FileNotFoundError(f"Missing {ANNOTATION_ARCHIVE}")
    images, labels = {}, defaultdict(set)
    for name, doc in _json_docs(ANNOTATION_ARCHIVE.read_bytes()):
        print(f"  read {name}: {len(doc.get('images', []))} images")
        cats = {c["id"]: c["name"] for c in doc.get("categories", [])}
        for im in doc.get("images", []):
            images.setdefault(im["id"], im)
        for a in doc.get("annotations", []):
            labels[a["image_id"]].add(cats.get(a["category_id"], str(a["category_id"])))
    return images, labels


def ingest(limit=None):
    print("Loading annotations ...")
    images, labels = load_annotations()
    items = sorted(images.values(), key=lambda i: i["id"])
    if limit and limit < len(items):
        by_loc = defaultdict(list)
        for im in items:
            by_loc[im.get("location")].append(im)
        rng = random.Random(42)
        for v in by_loc.values():
            rng.shuffle(v)
        picked, locs = [], list(by_loc)
        while len(picked) < limit and locs:          # round-robin across locations
            for loc in list(locs):
                if by_loc[loc]:
                    picked.append(by_loc[loc].pop())
                    if len(picked) == limit:
                        break
                else:
                    locs.remove(loc)
        items = picked

    conn = get_db()
    create_tables(conn)
    for im in items:
        gt = ",".join(sorted(labels.get(im["id"], []))) or None
        conn.execute("""INSERT OR IGNORE INTO media
            (image_id, file_path, location_id, datetime, sequence_id, status, gt_label)
            VALUES (?,?,?,?,?,'pending',?)""",
            (str(im["id"]), im.get("file_name", ""), str(im.get("location", "")),
             im.get("date_captured", ""), im.get("seq_id", ""), gt))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    conn.close()
    print(f"Ingested {len(items)} images ({n} total in DB) -> {DB_PATH}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int)
    ingest(ap.parse_args().limit)
