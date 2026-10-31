"""
extract_images.py - pulls ONLY the images listed in the DB out of the big
eccv_18_all_images_sm.tar.gz (6.5 GB) into data/raw/images/. Streams the archive
once and stops as soon as every wanted image is found.
"""
import sqlite3, tarfile
from pathlib import Path
from config import DB_PATH, IMAGES_DIR, IMAGES_ARCHIVE, find_image


def run():
    conn = sqlite3.connect(DB_PATH)
    wanted = {Path(r[0]).name for r in conn.execute("SELECT file_path FROM media")}
    conn.close()
    missing = {n for n in wanted if find_image(n) is None}
    print(f"{len(wanted)} images needed, {len(wanted) - len(missing)} already extracted")
    if not missing:
        return
    if not IMAGES_ARCHIVE.exists():
        print(f"  !! {IMAGES_ARCHIVE.name} not found - put the images in {IMAGES_DIR}")
        return
    print(f"Scanning {IMAGES_ARCHIVE.name} for {len(missing)} images (a few minutes) ...")
    found = 0
    with tarfile.open(IMAGES_ARCHIVE, "r|gz") as tf:          # streaming mode
        for m in tf:
            if not m.isfile():
                continue
            name = Path(m.name).name
            if name in missing:
                (IMAGES_DIR / name).write_bytes(tf.extractfile(m).read())
                missing.discard(name)
                found += 1
                if not missing:
                    break
    print(f"Extracted {found} images; {len(missing)} not found in archive")


if __name__ == "__main__":
    run()
