# SmallWorld — Camera Trap Explorer

CBIT Hacktoberfest '26 submission for Team 7. SmallWorld turns a Caltech Camera Traps sample into a reviewable wildlife-monitoring dashboard.

## Team

| Attribute | Details |
| --- | --- |
| Team | SmallWorld — Team 7 (`HFT26-TEAM-7`) |
| Registration ID | `HFEST26-44VLBLBP` |
| Team leader | Nishita Chintalapati |
| Members | Advaith Reddy Vemula, Aditya Konduru, Manjeswara Sai Aishwarya, Nirek Tiwari |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The dashboard uses `data/fake_master.csv` for its Overview and Activity tabs. The master CSV begins with the fixed contract:

`image_id, path, location, datetime, blur_score, status, md_conf, bbox, species, species_conf`

## Pipeline

```bash
python quality_detect.py --master data/master.csv --output data/master.csv --threshold 50 --md-json path/to/caltech-megadetector.json
python species.py --master data/master.csv --predictions data/species_predictions.csv --threshold 0.6
python analytics.py --master data/master.csv
```

The quality stage computes a resized grayscale Laplacian blur score and records MegaDetector animal boxes. Species confidence at least 0.6 becomes `Identified`; lower confidence becomes `Uncertain`. Analytics groups detections of the same species at the same location within 30 minutes into one encounter, mirroring workflows commonly handled with camtraptor and camtrapR.

For an optional aggregate-only Featherless summary:

```bash
export FEATHERLESS_API_KEY="your_key"
export FEATHERLESS_MODEL="your_model_id"
python summary.py --input data/summary.json
```

The included sample metadata covers 2,500 images; the source image files are available from [LILA](https://lila.science/datasets/caltech-camera-traps). The sample is for a demo and not a population estimate.

## Submission

Open a pull request from this fork's `main` branch to `cbitosc/HFT26-TEAM-7:main` with title:

`[SUBMISSION] TEAM-7 - SmallWorld - Camera Trap Explorer`

Include the approach, architecture, local setup, demo URL or recording, and screenshots.
