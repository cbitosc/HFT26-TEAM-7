"""Create a stratified, downloadable Caltech Camera Traps subset and CSV skeleton."""
from __future__ import annotations

import argparse
import json
import random
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

MASTER_COLUMNS = [
    "image_id", "path", "location", "datetime", "blur_score", "status",
    "md_conf", "bbox", "species", "species_conf",
]
EXTRA_COLUMNS = ["seq_id", "frame_num", "gt_species"]
METADATA_URL = "https://storage.googleapis.com/public-datasets-lila/caltechcameratraps/labels/caltech_camera_traps.json.zip"
IMAGE_BASE = "https://storage.googleapis.com/public-datasets-lila/caltech-unzipped/cct_images/"


def read_metadata(path: Path) -> dict:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            candidates = [n for n in archive.namelist() if n.lower().endswith(".json")]
            if not candidates:
                raise ValueError("Metadata ZIP contains no JSON file")
            with archive.open(candidates[0]) as f:
                return json.load(f)
    return json.loads(path.read_text())


def is_day(value: str) -> bool:
    try:
        hour = datetime.fromisoformat(value.replace("Z", "+00:00")).hour
        return 6 <= hour < 18
    except (ValueError, TypeError):
        return False


def image_url(file_name: str) -> str:
    normalized = str(file_name).lstrip("/")
    if "cct_images/" in normalized:
        normalized = normalized.split("cct_images/", 1)[1]
    return IMAGE_BASE + normalized


def build_subset(metadata: dict, count: int, seed: int) -> pd.DataFrame:
    images = metadata.get("images", [])
    annotations: dict[str, list[dict]] = {}
    categories = {str(c["id"]): c["name"] for c in metadata.get("categories", [])}
    for ann in metadata.get("annotations", []):
        annotations.setdefault(str(ann["image_id"]), []).append(ann)
    rows = []
    for im in images:
        iid = str(im.get("id", im.get("file_name", "")))
        anns = annotations.get(iid, [])
        # Dataset categories include an explicit "empty" class; annotations can
        # also be absent for images that should be treated as empty.
        labels = [categories.get(str(a.get("category_id")), "") for a in anns]
        animal_labels = [label for label in labels if label.lower() not in {"", "empty", "blank"}]
        animal = bool(animal_labels)
        stamp = im.get("datetime", "")
        rows.append({
            "image_id": iid,
            "path": image_url(im.get("file_name", "")),
            "location": str(im.get("location", "unknown")),
            "datetime": stamp,
            "seq_id": im.get("seq_id", ""),
            "frame_num": im.get("frame_num", ""),
            "gt_species": animal_labels[0] if animal else "empty",
            "_day": "day" if is_day(stamp) else "night",
            "_label": "animal" if animal else "empty",
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("Metadata has no images")
    # Balance day/night and empty/animal where available, then spread over
    # locations. This is a demonstration subset, not a representative sample.
    rng = random.Random(seed)
    frame["_rand"] = [rng.random() for _ in range(len(frame))]
    frame = frame.sort_values("_rand")
    groups = [g for _, g in frame.groupby(["_day", "_label", "location"], sort=True)]
    chosen = []
    while groups and len(chosen) < count:
        next_groups = []
        for group in groups:
            if len(chosen) < count:
                chosen.append(group.iloc[0])
                group = group.iloc[1:]
            if not group.empty:
                next_groups.append(group)
        groups = next_groups
    out = pd.DataFrame(chosen).drop(columns=["_day", "_label", "_rand"], errors="ignore")
    for col in MASTER_COLUMNS + EXTRA_COLUMNS:
        if col not in out:
            out[col] = ""
    out["status"] = "Pending"
    return out[MASTER_COLUMNS + EXTRA_COLUMNS].reset_index(drop=True)


def download_images(master: pd.DataFrame, destination: Path, workers: int) -> None:
    from concurrent.futures import ThreadPoolExecutor
    import urllib.error

    destination.mkdir(parents=True, exist_ok=True)
    def fetch(row: dict) -> None:
        url = row["path"]
        relative = url.split("/cct_images/", 1)[-1]
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return
        try:
            urllib.request.urlretrieve(url, target)
        except (urllib.error.URLError, OSError) as exc:
            print(f"Download failed: {url}: {exc}")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(fetch, master.to_dict("records")))
    # Store local file paths for the image pipeline and gallery.
    master["path"] = master["path"].map(lambda url: str(destination / url.split("/cct_images/", 1)[-1]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, default=Path("data/caltech_camera_traps.json.zip"))
    parser.add_argument("--count", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--download-images", action="store_true")
    parser.add_argument("--image-dir", type=Path, default=Path("data/images"))
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    if not args.metadata.exists():
        print(f"Downloading metadata to {args.metadata} (not the image archive)...")
        urllib.request.urlretrieve(METADATA_URL, args.metadata)
    master = build_subset(read_metadata(args.metadata), args.count, args.seed)
    if args.download_images:
        download_images(master, args.image_dir, args.workers)
    output = Path("data/master.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(output, index=False)
    print(f"Wrote {len(master)} rows to {output}")


if __name__ == "__main__":
    main()
