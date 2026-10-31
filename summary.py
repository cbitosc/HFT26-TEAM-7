"""Create a short, uncertainty-aware wildlife activity summary.

This file intentionally uses only aggregated tables from analytics.py. It does
not send images or raw image rows anywhere.
"""

from pathlib import Path

import analytics


DATA_DIR = Path(__file__).resolve().parent / "data"


def make_summary(df):
    """Return a plain-English summary for the Insights dashboard tab."""
    metrics = analytics.dashboard_metrics(df)
    species = analytics.sightings_by_species(df)
    locations = analytics.sightings_by_location(df)
    encounters = analytics.build_encounters(df)

    sentences = [
        f"This subset contains {metrics['total_images']:,} images.",
        f"The pipeline marked {metrics['empty']:,} images as empty, "
        f"identified {metrics['identified']:,} animal images, and flagged "
        f"{metrics['needs_review']:,} images for review.",
    ]

    if metrics["identified"]:
        sentences.append(
            f"Confident detections span {len(species):,} predicted species and "
            f"form {len(encounters):,} encounter groups when sightings of the "
            f"same species at one location occur within 30 minutes."
        )

    if not species.empty:
        top_species = species.iloc[0]
        sentences.append(
            f"The most frequent confident prediction is {top_species['species']} "
            f"with {top_species['sightings']:,} sightings."
        )

    if not locations.empty:
        top_location = locations.iloc[0]
        sentences.append(
            f"Location {top_location['location']} has the most confident sightings "
            f"({top_location['sightings']:,})."
        )

    if metrics["uncertain"]:
        sentences.append(
            f"{metrics['uncertain']:,} detections are uncertain, representing "
            f"{metrics['uncertain_share_of_detections']:.1f}% of all animal "
            f"detections; review them before drawing firm conclusions."
        )

    sentences.append(
        "Interpret activity patterns as results from this limited subset; model "
        "predictions and camera coverage can affect the apparent pattern."
    )
    return " ".join(sentences)


if __name__ == "__main__":
    demo_data = analytics.load_analytics_data(DATA_DIR / "fake_master.csv")
    print(make_summary(demo_data))
