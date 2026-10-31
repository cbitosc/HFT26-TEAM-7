"""
run_pipeline.py - master script.
  python run_pipeline.py --limit 100
  python run_pipeline.py --step detect
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

STEPS = ["ingest", "extract", "quality", "detect", "classify", "encounter"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="number of images to ingest")
    ap.add_argument("--step", default="all", choices=["all"] + STEPS)
    ap.add_argument("--threshold", type=float, default=100.0, help="blur threshold")
    a = ap.parse_args()
    for step in (STEPS if a.step == "all" else [a.step]):
        print(f"\n{'=' * 50}\n  STEP: {step.upper()}\n{'=' * 50}")
        if step == "ingest":
            from pipeline.ingest import ingest; ingest(limit=a.limit)
        elif step == "extract":
            from pipeline.extract_images import run; run()
        elif step == "quality":
            from pipeline.quality import run; run(threshold=a.threshold)
        elif step == "detect":
            from pipeline.detect import run; run()
        elif step == "classify":
            from pipeline.classify import run; run()
        elif step == "encounter":
            from pipeline.encounter import run; run()
    print("\nPipeline complete. Launch the dashboard with:\n  python -m streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
