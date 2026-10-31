"""
feedback.py - Human-in-the-loop feedback pipeline for model retraining.

This module closes the loop between human review decisions (approve / relabel /
reject) captured in the dashboard's Review Queue page and the AI classification
models (MegaDetector + SpeciesNet).  It does three things:

  1. **Export training data** - converts human-verified labels into JSONL
     fine-tuning format that can be used to retrain or fine-tune SpeciesNet.
  2. **Compute model drift** - tracks how well the AI agrees with humans over
     time, so the team can see whether additional training is needed.
  3. **Adaptive thresholds** - adjusts the confidence threshold for auto-accept
     vs. needs-review based on per-species accuracy from feedback, so species
     the model is good at are auto-accepted and uncertain ones are flagged.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH, BASE


TRAINING_DIR = BASE / "data" / "training"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)


def connect():
    return sqlite3.connect(str(DB_PATH))


# ── 1. Training data export ──────────────────────────────────────

def export_training_jsonl(output_path: str | None = None) -> Path:
    """Export human-verified labels as JSONL for SpeciesNet fine-tuning.

    Each line contains:
      {"image_path": "...", "crop_path": "...", "species": "...",
       "scientific_name": "...", "confidence": 1.0, "source": "human_verified",
       "original_prediction": "...", "original_confidence": 0.xx,
       "action": "accept|relabel|confirm", "timestamp": "..."}
    """
    conn = connect()
    rows = conn.execute("""
        SELECT f.timestamp, f.detection_id, f.action, f.model_prediction,
               f.model_confidence, f.human_label, f.previous_label,
               d.crop_path, m.file_path, m.location_id
        FROM feedback_log f
        JOIN detections d ON d.id = f.detection_id
        JOIN media m ON m.image_id = d.image_id
        WHERE f.action IN ('accept', 'relabel', 'confirm')
          AND (f.human_label IS NOT NULL AND f.human_label != '')
    """).fetchall()
    conn.close()

    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(TRAINING_DIR / f"training_data_{ts}.jsonl")

    out = Path(output_path)
    with out.open("w") as fh:
        for r in rows:
            entry = {
                "timestamp": r[0],
                "detection_id": r[1],
                "action": r[2],
                "original_prediction": r[3],
                "original_confidence": r[4],
                "species": r[5],
                "crop_path": r[7],
                "image_path": r[8],
                "location_id": r[9],
                "source": "human_verified",
                "confidence": 1.0,
            }
            fh.write(json.dumps(entry) + "\n")

    print(f"Exported {len(rows)} training samples to {out}")
    return out


# ── 2. Model accuracy drift ─────────────────────────────────────

def compute_accuracy_drift() -> dict:
    """Compute model accuracy trends from the feedback log.

    Returns a dict with overall accuracy, per-species accuracy,
    and a time series of rolling accuracy.
    """
    conn = connect()

    # Check if feedback_log exists
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "feedback_log" not in tables:
        conn.close()
        return {"total": 0, "overall_accuracy": None, "per_species": {}, "timeline": []}

    total = conn.execute("SELECT COUNT(*) FROM feedback_log").fetchone()[0]
    if total == 0:
        conn.close()
        return {"total": 0, "overall_accuracy": None, "per_species": {}, "timeline": []}

    # Overall accuracy (accept + confirm = model was right)
    correct = conn.execute("""
        SELECT COUNT(*) FROM feedback_log WHERE action IN ('accept', 'confirm')
    """).fetchone()[0]
    overall = correct / total if total else 0.0

    # Per-species accuracy
    species_rows = conn.execute("""
        SELECT model_prediction,
               SUM(CASE WHEN action IN ('accept','confirm') THEN 1 ELSE 0 END) as correct,
               COUNT(*) as total,
               AVG(model_confidence) as avg_conf
        FROM feedback_log
        WHERE model_prediction IS NOT NULL AND model_prediction != ''
        GROUP BY model_prediction ORDER BY total DESC
    """).fetchall()

    per_species = {}
    for sp, corr, tot, avg_c in species_rows:
        per_species[sp] = {
            "correct": corr, "total": tot,
            "accuracy": round(corr / tot, 3) if tot else 0.0,
            "avg_model_confidence": round(avg_c, 3) if avg_c else 0.0,
        }

    # Timeline: accuracy by day
    timeline = conn.execute("""
        SELECT DATE(timestamp) as day,
               SUM(CASE WHEN action IN ('accept','confirm') THEN 1 ELSE 0 END) as correct,
               COUNT(*) as total
        FROM feedback_log GROUP BY DATE(timestamp) ORDER BY day
    """).fetchall()

    conn.close()

    return {
        "total": total,
        "overall_accuracy": round(overall, 3),
        "per_species": per_species,
        "timeline": [{"date": r[0], "correct": r[1], "total": r[2],
                       "accuracy": round(r[1] / r[2], 3) if r[2] else 0}
                      for r in timeline],
    }


# ── 3. Adaptive confidence thresholds ────────────────────────────

def adaptive_thresholds(base_threshold: float = 0.5,
                        min_samples: int = 5) -> dict:
    """Compute per-species confidence thresholds based on feedback.

    Species the model handles well get a LOWER threshold (more auto-accepts);
    species it struggles with get a HIGHER threshold (more human review).

    Returns {species_key: adjusted_threshold}.
    """
    drift = compute_accuracy_drift()
    thresholds = {}

    for species, stats in drift.get("per_species", {}).items():
        if stats["total"] < min_samples:
            thresholds[species] = base_threshold  # not enough data
            continue

        acc = stats["accuracy"]
        if acc >= 0.9:
            # Model is great at this species: lower threshold → auto-accept more
            thresholds[species] = max(0.2, base_threshold - 0.2)
        elif acc >= 0.7:
            # Decent: slight reduction
            thresholds[species] = max(0.3, base_threshold - 0.1)
        elif acc >= 0.5:
            # Mediocre: keep default
            thresholds[species] = base_threshold
        else:
            # Poor: raise threshold → flag more for review
            thresholds[species] = min(0.9, base_threshold + 0.2)

    return thresholds


# ── 4. Feedback summary for LLM prompt injection ────────────────

def feedback_context_for_llm() -> dict | None:
    """Build a compact feedback summary to inject into the AI Summary prompt.

    This tells the LLM which species predictions are trustworthy
    and which have been frequently corrected by humans.
    """
    drift = compute_accuracy_drift()
    if drift["total"] == 0:
        return None

    reliable = []
    unreliable = []
    common_corrections = []

    for sp, stats in drift["per_species"].items():
        if stats["total"] < 3:
            continue
        if stats["accuracy"] >= 0.8:
            reliable.append(sp)
        elif stats["accuracy"] < 0.5:
            unreliable.append(sp)

    conn = connect()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "feedback_log" in tables:
        corrections = conn.execute("""
            SELECT model_prediction, human_label, COUNT(*) as cnt
            FROM feedback_log WHERE action='relabel'
            GROUP BY model_prediction, human_label ORDER BY cnt DESC LIMIT 5
        """).fetchall()
        common_corrections = [{"from": r[0], "to": r[1], "count": r[2]} for r in corrections]
    conn.close()

    return {
        "total_human_decisions": drift["total"],
        "overall_model_accuracy": drift["overall_accuracy"],
        "reliable_species": reliable,
        "unreliable_species": unreliable,
        "common_misclassifications": common_corrections,
        "note": ("Human reviewers have verified these predictions. "
                 "Species marked reliable have >80% accuracy; unreliable <50%. "
                 "Adjust your confidence language accordingly.")
    }


# ── CLI ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Feedback loop utilities")
    parser.add_argument("--export", action="store_true", help="Export training data JSONL")
    parser.add_argument("--drift", action="store_true", help="Show model accuracy drift")
    parser.add_argument("--thresholds", action="store_true", help="Show adaptive thresholds")
    args = parser.parse_args()

    if args.export:
        export_training_jsonl()
    elif args.drift:
        d = compute_accuracy_drift()
        print(json.dumps(d, indent=2))
    elif args.thresholds:
        t = adaptive_thresholds()
        print(json.dumps(t, indent=2))
    else:
        # Show everything
        print("=== Accuracy Drift ===")
        print(json.dumps(compute_accuracy_drift(), indent=2))
        print("\n=== Adaptive Thresholds ===")
        print(json.dumps(adaptive_thresholds(), indent=2))
        print("\n=== LLM Context ===")
        ctx = feedback_context_for_llm()
        print(json.dumps(ctx, indent=2) if ctx else "No feedback yet.")
