"""Helpers for loading the camera-trap master CSV."""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"

def load_master(csv_path=DATA_DIR / "master.csv"):
    """Load master.csv with stable text IDs and parsed capture datetimes."""
    df = pd.read_csv(csv_path, dtype={"image_id": "string", "location": "string", "seq_id": "string", "gt_species": "string"})
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    return df

def get_image_path(row):
    """Return an absolute Path for an image row from master.csv."""
    path = Path(str(row["path"]))
    return path if path.is_absolute() else DATA_DIR / path
