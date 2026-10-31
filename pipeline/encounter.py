"""
encounter.py - groups classified detections into independent encounter events
(30-min gap rule). Uses R (Rscript) when available, else an equivalent Python fallback.
"""
import csv, shutil, sqlite3, subprocess
from datetime import datetime, timedelta
from itertools import groupby
from config import BASE, DB_PATH, PROCESSED_DIR

R_SCRIPT = BASE / "r_scripts" / "encounter_count.R"
IN_CSV = PROCESSED_DIR / "detections_for_r.csv"
OUT_CSV = PROCESSED_DIR / "encounters.csv"
FIELDS = ["location_id", "species_common", "event_start", "event_end", "image_count", "trap_nights"]


def export_detections_csv():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT m.image_id, m.location_id, m.datetime, c.species_common, c.conf_top1
        FROM media m JOIN detections d ON m.image_id=d.image_id
        JOIN classifications c ON c.detection_id=d.id
        WHERE d.category='animal' AND c.status IN ('auto','human_verified')
          AND m.datetime IS NOT NULL AND m.datetime != ''""").fetchall()
    conn.close()
    with open(IN_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image_id", "location_id", "datetime", "species_common", "confidence"])
        w.writerows(rows)
    print(f"Exported {len(rows)} detections -> {IN_CSV.name}")
    return len(rows)


def _parse(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            pass
    return None


def python_encounters():
    print("  (Rscript not found - using Python 30-min gap rule)")
    recs = []
    with open(IN_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            dt = _parse(r["datetime"])
            if dt:
                recs.append((r["location_id"], r["species_common"], dt))
    recs.sort()
    span = {}
    for loc, _, dt in recs:
        lo, hi = span.get(loc, (dt, dt))
        span[loc] = (min(lo, dt), max(hi, dt))
    events = []
    for (loc, sp), grp in groupby(recs, key=lambda r: (r[0], r[1])):
        times = [t for _, _, t in grp]
        start = prev = times[0]; n = 1
        def close():
            lo, hi = span[loc]
            events.append(dict(location_id=loc, species_common=sp, event_start=start, event_end=prev,
                               image_count=n, trap_nights=round((hi - lo).total_seconds() / 86400, 2)))
        for t in times[1:]:
            if t - prev > timedelta(minutes=30):
                close(); start = t; n = 0
            prev = t; n += 1
        close()
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(events)


def load_encounters():
    if not OUT_CSV.exists():
        print("No encounters.csv produced."); return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM encounters")
    n = 0
    with open(OUT_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            conn.execute("""INSERT INTO encounters (location_id, species_common, event_start, event_end,
                image_count, trap_nights) VALUES (?,?,?,?,?,?)""",
                (r["location_id"], r["species_common"], r["event_start"], r["event_end"],
                 int(float(r["image_count"] or 0)), float(r["trap_nights"] or 0)))
            n += 1
    conn.commit(); conn.close()
    print(f"Loaded {n} encounter events.")


def run():
    if export_detections_csv() == 0:
        print("No classified detections yet - skipping encounters."); return
    OUT_CSV.unlink(missing_ok=True)
    rscript = shutil.which("Rscript")
    if rscript:
        res = subprocess.run([rscript, str(R_SCRIPT)], capture_output=True, text=True, cwd=str(BASE))
        if res.returncode == 0:
            print(res.stdout.strip())
        else:
            print("R failed, falling back to Python:\n", res.stderr[-500:])
            python_encounters()
    else:
        python_encounters()
    load_encounters()


if __name__ == "__main__":
    run()
