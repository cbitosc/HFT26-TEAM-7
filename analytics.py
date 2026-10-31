"""Small pandas analytics helpers for the camera-trap dashboard.

The functions work with either data/fake_master.csv during UI development or
data/master.csv after the detection and species pipelines have filled it.
"""

from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data"
DETECTION_STATUSES = {"Identified", "Uncertain"}


def load_analytics_data(csv_path=DATA_DIR / "fake_master.csv"):
    """Load a master-format CSV and add an integer capture-hour column."""
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["location"] = df["location"].astype("string")
    df["status"] = df["status"].fillna("").astype("string")
    df["species"] = df["species"].fillna("").astype("string")
    df["species_conf"] = pd.to_numeric(df["species_conf"], errors="coerce")
    df["hour"] = df["datetime"].dt.hour
    return df


def status_counts(df):
    """Return every status count, including blank/unprocessed rows."""
    return df["status"].replace("", "Unprocessed").value_counts().rename_axis("status").reset_index(name="images")


def confident_detections(df):
    """Keep only high-confidence model results used in primary totals."""
    return df[(df["status"] == "Identified") & df["species"].ne("")].copy()


def uncertain_detections(df):
    """Return low-confidence detections for the review tab and caveats."""
    return df[(df["status"] == "Uncertain") & df["species"].ne("")].copy()


def sightings_by_species(df, include_uncertain=False):
    """Count model sightings by species; uncertain predictions are optional."""
    valid = df[df["status"].isin(DETECTION_STATUSES)] if include_uncertain else confident_detections(df)
    return valid.groupby("species").size().sort_values(ascending=False).rename("sightings").reset_index()


def sightings_by_location(df, include_uncertain=False):
    """Count model sightings at each camera location."""
    valid = df[df["status"].isin(DETECTION_STATUSES)] if include_uncertain else confident_detections(df)
    return valid.groupby("location").size().sort_values(ascending=False).rename("sightings").reset_index()


def activity_by_hour(df, include_uncertain=False):
    """Count model sightings by species and capture hour (0 through 23)."""
    valid = df[df["status"].isin(DETECTION_STATUSES)] if include_uncertain else confident_detections(df)
    result = valid.dropna(subset=["hour"]).groupby(["hour", "species"]).size().rename("sightings").reset_index()
    return result.sort_values(["hour", "species"]).reset_index(drop=True)


def build_encounters(df, minutes=30, include_uncertain=False):
    """Group nearby sightings of one species at one location into encounters.

    A new encounter begins when the time since the previous qualifying sighting
    exceeds ``minutes``. Primary reporting includes only ``Identified`` rows;
    set ``include_uncertain=True`` for a sensitivity view.
    """
    valid = df[df["status"].isin(DETECTION_STATUSES)] if include_uncertain else confident_detections(df)
    valid = valid.dropna(subset=["datetime"]).copy()
    valid = valid.sort_values(["location", "species", "datetime"])
    gap = valid.groupby(["location", "species"])["datetime"].diff()
    valid["new_encounter"] = gap.isna() | gap.gt(pd.Timedelta(minutes=minutes))
    valid["encounter_number"] = valid.groupby(["location", "species"])["new_encounter"].cumsum()
    grouped = valid.groupby(["location", "species", "encounter_number"], as_index=False).agg(
        encounter_start=("datetime", "min"),
        encounter_end=("datetime", "max"),
        image_count=("image_id", "size"),
        mean_species_conf=("species_conf", "mean"),
        representative_image=("path", "first"),
    )
    grouped.insert(0, "encounter_id", range(1, len(grouped) + 1))
    return grouped.drop(columns="encounter_number")


def dashboard_metrics(df):
    """Return the small KPI dictionary used by the Overview tab."""
    counts = df["status"].replace("", "Unprocessed").value_counts()
    detections = int(df["status"].isin(DETECTION_STATUSES).sum())
    return {
        "total_images": len(df),
        "empty": int(counts.get("Empty", 0)),
        "identified": int(counts.get("Identified", 0)),
        "uncertain": int(counts.get("Uncertain", 0)),
        "needs_review": int(counts.get("Needs Review", 0)),
        "uncertain_share_of_detections": round(100 * int(counts.get("Uncertain", 0)) / detections, 1) if detections else 0.0,
    }


if __name__ == "__main__":
    data = load_analytics_data()
    print("Dashboard metrics:", dashboard_metrics(data))
    print("\nSightings by species:")
    print(sightings_by_species(data).to_string(index=False))
    print("\nEncounters:")
    print(build_encounters(data).to_string(index=False))
