"""Blur scoring plus optional merge of precomputed MegaDetector JSON results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


def blur_score(path: str) -> float:
    image_path = Path(path)
    if not image_path.exists() and (Path("data") / image_path).exists():
        image_path = Path("data") / image_path
    image = cv2.imread(str(image_path))
    if image is None:
        return float("nan")
    height, width = image.shape[:2]
    scale = min(1.0, 640 / max(height, width))
    if scale < 1:
        image = cv2.resize(image, (int(width * scale), int(height * scale)))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def md_index(path: Path) -> dict[str, list[dict]]:
    data = json.loads(path.read_text())
    result = {}
    for image in data.get("images", []):
        key = Path(image.get("file", image.get("file_name", ""))).name
        result[key] = image.get("detections", [])
    return result


def run(master: pd.DataFrame, threshold: float, md_file: Path | None) -> pd.DataFrame:
    for column in ("md_conf", "bbox"):
        master[column] = master[column].astype(object)
    scores = master["path"].fillna("").map(blur_score)
    master["blur_score"] = scores
    md = md_index(md_file) if md_file else {}
    for index, row in master.iterrows():
        if pd.isna(scores.iloc[index]) or scores.iloc[index] < threshold:
            master.at[index, "status"] = "Needs Review"
            continue
        detections = md.get(Path(str(row["path"])).name, [])
        # MegaDetector category 1 = animal. Preserve the highest animal score
        # and all animal boxes in COCO [x,y,w,h] relative coordinates.
        animals = [d for d in detections if str(d.get("category", "")) == "1"]
        master.at[index, "md_conf"] = max((d.get("conf", 0.0) for d in animals), default="")
        master.at[index, "bbox"] = json.dumps([d.get("bbox") for d in animals]) if animals else ""
        master.at[index, "status"] = "Pending Species" if animals else "Empty"
    return master


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=Path("data/master.csv"))
    parser.add_argument("--threshold", type=float, default=50.0, help="Tune visually on ~30 day/night frames")
    parser.add_argument("--md-json", type=Path, help="Optional precomputed MegaDetector results JSON")
    parser.add_argument("--output", type=Path, default=Path("data/master.csv"))
    args = parser.parse_args()
    frame = pd.read_csv(args.master, keep_default_na=False)
    run(frame, args.threshold, args.md_json)
    frame.to_csv(args.output, index=False)
    print(f"Updated {len(frame)} rows in {args.output}")


if __name__ == "__main__":
    main()
