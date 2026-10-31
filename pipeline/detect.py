"""
detect.py - MegaDetector on 'sharp' images.
  best animal conf < 0.1 -> empty | 0.1-0.2 -> needs_review | >= 0.2 -> animal_detected (crops saved)
Uses models/md_v*.pt if present, otherwise auto-downloads MDV5A (as in test_megadetector.py).
"""
import sqlite3
from pathlib import Path
from PIL import Image
from config import DB_PATH, CROPS_DIR, MODELS_DIR, find_image

LOW_THRESH, HIGH_THRESH = 0.1, 0.2
CATS = {"1": "animal", "2": "person", "3": "vehicle"}


def _load_detector():
    from megadetector.detection.run_detector import load_detector, try_download_known_detector
    local = next(MODELS_DIR.glob("md_v*.pt"), None)
    model_file = str(local) if local else try_download_known_detector("MDV5A")
    print(f"Loading MegaDetector: {model_file}")
    return load_detector(model_file)


def save_crop(img, bbox, image_id, idx):
    w, h = img.size
    x, y, bw, bh = bbox
    box = (max(0, int(x * w)), max(0, int(y * h)), min(w, int((x + bw) * w)), min(h, int((y + bh) * h)))
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    out = CROPS_DIR / f"{image_id}_{idx}.jpg"
    img.crop(box).save(out, quality=92)
    return str(out)


def run():
    detector = _load_detector()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT image_id, file_path FROM media WHERE status='sharp'").fetchall()
    print(f"Running detection on {len(rows)} images ...")
    for n, (image_id, fp) in enumerate(rows, 1):
        p = find_image(fp)
        if p is None:
            continue
        try:
            img = Image.open(p).convert("RGB")
            res = detector.generate_detections_one_image(img, str(p), detection_threshold=LOW_THRESH)
        except Exception as e:
            print(f"  skip {Path(fp).name}: {e}")
            continue
        if res.get("failure"):
            print(f"  skip {Path(fp).name}: {res['failure']}")
            continue
        dets = res.get("detections", [])
        best = max((d["conf"] for d in dets if str(d["category"]) == "1"), default=0.0)
        status = "empty" if best < LOW_THRESH else "needs_review" if best < HIGH_THRESH else "animal_detected"
        conn.execute("DELETE FROM detections WHERE image_id=?", (image_id,))
        for i, d in enumerate(dets):
            cat = CATS.get(str(d["category"]), "unknown")
            crop, nr = None, 0
            if cat == "animal":
                if d["conf"] >= HIGH_THRESH:
                    crop = save_crop(img, d["bbox"], image_id, i)
                else:
                    nr = 1
            conn.execute("""INSERT INTO detections
                (image_id, category, confidence, bbox_x, bbox_y, bbox_w, bbox_h, crop_path, needs_review)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (image_id, cat, d["conf"], *d["bbox"], crop, nr))
        conn.execute("UPDATE media SET status=? WHERE image_id=?", (status, image_id))
        if n % 25 == 0:
            conn.commit(); print(f"  {n}/{len(rows)}")
    conn.commit(); conn.close()
    print("Detection complete.")


if __name__ == "__main__":
    run()
