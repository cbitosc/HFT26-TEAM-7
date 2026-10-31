"""config.py - single source of truth for paths and settings."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")


def _resolve(p: str) -> Path:
    p = Path(p)
    return p if p.is_absolute() else BASE / p


DB_PATH = _resolve(os.getenv("DB_PATH", "data/db/wildlife.db"))
RAW_DIR = BASE / "data" / "raw"
IMAGES_DIR = RAW_DIR / "images"
PROCESSED_DIR = BASE / "data" / "processed"
CROPS_DIR = PROCESSED_DIR / "crops"
MODELS_DIR = BASE / "models"
ANNOTATION_ARCHIVE = RAW_DIR / "caltech_coco.json"      # actually a tar of 5 JSON files
IMAGES_ARCHIVE = IMAGES_DIR / "eccv_18_all_images_sm.tar.gz"

for _d in (DB_PATH.parent, IMAGES_DIR, CROPS_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def find_image(file_path: str):
    """Locate an image under data/raw/images (flat or in a subfolder)."""
    name = Path(file_path).name
    for c in (IMAGES_DIR / file_path, IMAGES_DIR / name):
        if c.exists():
            return c
    for sub in IMAGES_DIR.iterdir():
        if sub.is_dir() and (sub / name).exists():
            return sub / name
    return None
