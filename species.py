"""Apply species predictions supplied by a SpeciesNet adapter/export.

SpeciesNet interfaces can vary by runtime/version. Keep inference behind a CSV
boundary: predictions.csv must contain image_id, species, species_conf.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def apply_predictions(master: pd.DataFrame, predictions: pd.DataFrame, threshold: float = 0.6) -> pd.DataFrame:
    required = {"image_id", "species", "species_conf"}
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Prediction file is missing columns: {sorted(missing)}")
    out = master.merge(predictions[list(required)], on="image_id", how="left", suffixes=("", "_pred"))
    for col in ("species", "species_conf"):
        pred = f"{col}_pred"
        if pred in out:
            out[col] = out[pred].combine_first(out[col] if col in out else pd.Series(index=out.index, dtype=object))
            out.drop(columns=pred, inplace=True)
    has_prediction = out["species"].astype(str).str.len().gt(0)
    confidence = pd.to_numeric(out["species_conf"], errors="coerce")
    out.loc[has_prediction & (confidence >= threshold), "status"] = "Identified"
    out.loc[has_prediction & (confidence < threshold), "status"] = "Uncertain"
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=Path("data/master.csv"))
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--output", type=Path, default=Path("data/master.csv"))
    args = parser.parse_args()
    master = pd.read_csv(args.master, keep_default_na=False)
    predictions = pd.read_csv(args.predictions)
    apply_predictions(master, predictions, args.threshold).to_csv(args.output, index=False)
    print(f"Wrote species labels to {args.output}")


if __name__ == "__main__":
    main()
