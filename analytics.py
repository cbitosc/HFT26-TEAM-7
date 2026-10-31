"""Encounter and summary statistics for the camera-trap master table."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def analyze(master: pd.DataFrame, gap_minutes: int = 30) -> tuple[pd.DataFrame, dict]:
    df = master.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
    df["species_conf"] = pd.to_numeric(df["species_conf"], errors="coerce")
    identified = df[df["status"].eq("Identified") & df["species"].notna()].copy()
    identified = identified.sort_values(["location", "species", "datetime"])
    delta = identified.groupby(["location", "species"])["datetime"].diff().dt.total_seconds().div(60)
    identified["encounter_id"] = (delta.isna() | delta.gt(gap_minutes)).groupby(
        [identified["location"], identified["species"]]
    ).cumsum().astype(str)
    identified["encounter_id"] = identified["location"].astype(str) + "-" + identified["species"].astype(str) + "-" + identified["encounter_id"]
    encounters = identified.groupby(["encounter_id", "location", "species"], as_index=False).agg(
        start_time=("datetime", "min"), end_time=("datetime", "max"), image_count=("image_id", "count"),
        mean_confidence=("species_conf", "mean"),
    )
    identified["hour"] = identified["datetime"].dt.hour
    confidence = pd.to_numeric(df.loc[df["status"].isin(["Identified", "Uncertain"]), "species_conf"], errors="coerce")
    summary = {
        "image_count": int(len(df)),
        "status_counts": df["status"].fillna("Unknown").value_counts().to_dict(),
        "encounter_count": int(len(encounters)),
        "uncertain_share": float(df["status"].eq("Uncertain").mean()) if len(df) else 0.0,
        "mean_prediction_confidence": float(confidence.mean()) if confidence.notna().any() else None,
        "species_counts": encounters["species"].value_counts().to_dict(),
        "location_counts": encounters["location"].value_counts().to_dict(),
        "hourly_counts": identified.groupby(["hour", "species"], dropna=False).size().rename("images").reset_index().to_dict("records"),
    }
    return encounters, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=Path("data/master.csv"))
    parser.add_argument("--encounters", type=Path, default=Path("data/encounters.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/summary.json"))
    args = parser.parse_args()
    encounters, summary = analyze(pd.read_csv(args.master, keep_default_na=False))
    args.encounters.parent.mkdir(parents=True, exist_ok=True)
    encounters.to_csv(args.encounters, index=False)
    args.summary.write_text(pd.Series(summary).to_json(indent=2))
    print(f"Wrote {len(encounters)} encounters to {args.encounters}")


if __name__ == "__main__":
    main()
