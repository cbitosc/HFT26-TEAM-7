"""quality.py - Laplacian-variance blur check. status: pending -> sharp | blurry | missing."""
import sqlite3
import cv2
from config import DB_PATH, find_image

THRESHOLD = 100.0


def blur_score(path):
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return None if img is None else float(cv2.Laplacian(img, cv2.CV_64F).var())


def run(threshold=THRESHOLD):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT image_id, file_path FROM media WHERE status IN ('pending','missing')").fetchall()
    print(f"Checking quality of {len(rows)} images (threshold={threshold}) ...")
    sharp = blurry = missing = 0
    for image_id, fp in rows:
        p = find_image(fp)
        score = blur_score(p) if p else None
        if score is None:
            conn.execute("UPDATE media SET status='missing' WHERE image_id=?", (image_id,))
            missing += 1
            continue
        status = "sharp" if score >= threshold else "blurry"
        conn.execute("UPDATE media SET blur_score=?, status=? WHERE image_id=?", (score, status, image_id))
        sharp += status == "sharp"; blurry += status == "blurry"
    conn.commit(); conn.close()
    print(f"  Sharp: {sharp} | Blurry: {blurry} | Missing/unreadable: {missing}")


if __name__ == "__main__":
    run()
