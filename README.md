# SmallWorld

cbit ke don

**SmallWorld Wildlife Intelligence** is an AI camera-trap analytics project built on the
[Caltech Camera Traps (CCT20)](https://lila.science/datasets/caltech-camera-traps) dataset.
It filters blurry frames, finds animals with MegaDetector, identifies species with SpeciesNet,
groups detections into independent 30-minute encounters, and presents everything in a dark
"field observatory" Streamlit dashboard with an LLM-written field report.

> This is a hackathon demo on a small sample, not a validated ecological study. See
> [`AUDIT_LOG.md`](AUDIT_LOG.md) for status, verified numbers and known limitations.

## What's in this repository

The repository holds two tracks that share the same dataset:

| Track | Files | Storage | Owner |
| --- | --- | --- | --- |
| Data subset + analytics | `build_subset.py`, `data_utils.py`, `analytics.py`, `summary.py`, `data/` | `data/master.csv` (2,500 images) | Advaith |
| AI pipeline + dashboard | `pipeline/`, `dashboard/`, `llm/`, `r_scripts/`, `config.py`, `run_pipeline.py` | SQLite `data/db/wildlife.db` | Nikita |

```text
SmallWorld/
├── AUDIT_LOG.md               # project status, change log and team handoff
├── README.md
├── requirements.txt           # pipeline + dashboard dependencies
├── config.py                  # paths (DB, images, crops, models); loads .env
├── run_pipeline.py            # runs the pipeline steps in order
├── pipeline/
│   ├── ingest.py              # COCO JSON (tar / gzip / plain) -> SQLite tables
│   ├── extract_images.py      # pulls the selected images out of the image archive
│   ├── quality.py             # Laplacian-variance blur gate (sharp / blurry)
│   ├── detect.py              # MegaDetector v5: animal / person / vehicle boxes + crops
│   ├── classify.py            # SpeciesNet on animal crops, with taxonomic roll-up
│   └── encounter.py           # 30-min independent encounters (R, Python fallback)
├── r_scripts/encounter_count.R
├── llm/summariser.py          # Featherless (OpenAI-compatible) field-report writer
├── dashboard/
│   ├── app.py                 # entry point: theme, logo, ☰ sidebar navigation
│   ├── assets/                # SmallWorld logo + icon
│   ├── components/
│   │   ├── data_queries.py    # single data layer over the SQLite schema
│   │   ├── charts.py          # inline SVG charts (no plotting library needed)
│   │   ├── theme.py           # design-system CSS (colours, fonts, nav drawer)
│   │   └── ui.py              # shared page header, chips, image cards, filters
│   └── pages/                 # one file per dashboard page (see below)
├── .streamlit/config.toml     # dark theme + toolbar settings
├── build_subset.py            # reproducible 2,500-image subset (seed 42)
├── data_utils.py / analytics.py / summary.py
├── eccv_18_annotations/       # CCT20 COCO annotation files
└── data/                      # master.csv, fake_master.csv, subset/ images
```

## Dashboard

Open the ☰ menu left of the SmallWorld logo to switch pages:

| Page | What it shows |
| --- | --- |
| **Activity Timeline** (home) | Encounters per month, species × hour heat-map, seasonal signal, day/night split per species |
| **Sightings** | Every detection with its amber bounding box and ID tag. Filter by class, species and station |
| **Review Queue** | Accept, relabel or reject uncertain SpeciesNet predictions and low-confidence MegaDetector boxes. Decisions are saved to the database |
| **AI Summary** | Streams a three-paragraph Featherless report from live statistics and lets you download it as `.md` |
| **Site Activity** | Per-camera effort, encounter rate per 100 trap-nights, species mix and best captures |

A shared **confidence gate** (20–95%) at the top of each page filters every figure. Its value
carries over between pages.

**Species label priority:** scientist label from the Review Queue, then the SpeciesNet
prediction, then the Caltech ground-truth label. Until `--step classify` has been run, species
names come from ground truth and are marked **GROUND TRUTH** in the interface.

## Quick start (pipeline + dashboard)

Requires Python 3.12 and **Streamlit 1.46 or newer** (the sidebar navigation uses
`st.navigation`).

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
2. **Create `.env`** in the project root. It is ignored by Git and must never be committed:
   ```text
   FEATHERLESS_API_KEY=your-key-here
   ```
3. **Add the data.** Put the CCT annotation archive at `data/raw/caltech_coco.json` and the
   images in `data/raw/images/`. MegaDetector downloads its weights (MDV5A) automatically on
   first run, or you can place `md_v5a.0.0.pt` in `models/`.
4. **Run the pipeline.** Start small:
   ```bash
   python run_pipeline.py --limit 100              # ingest -> extract -> quality -> detect -> classify -> encounter
   python run_pipeline.py --step classify          # run a single step
   ```
5. **Launch the dashboard** from the project root:
   ```bash
   python -m streamlit run dashboard/app.py
   ```
   Then open http://localhost:8501.

## Pipeline thresholds

| Step | Rule |
| --- | --- |
| Quality | Laplacian variance < 100 is `blurry` and skipped (`--threshold` to change) |
| Detect | Best animal confidence < 0.10 is `empty`, 0.10–0.20 is `needs_review`, ≥ 0.20 is `animal_detected` (crop saved) |
| Classify | Confidence < 0.50, or not resolved to species level, goes to `needs_review` |
| Encounters | Same species at the same site, gap ≤ 30 minutes, counts as one encounter |

## Data-subset track (analytics.py / summary.py)

See [`data/README.md`](data/README.md) and sections 3–10 of [`AUDIT_LOG.md`](AUDIT_LOG.md):

```bash
python analytics.py
python summary.py
```

## Notes

- Large archives (`eccv_18_all_images_sm.tar.gz`), local databases, crops, model weights and
  `.env` are all ignored by Git.
- Benchmark figures in the dashboard are computed against CCT ground truth for the frames in
  your local database only. They are not official benchmark results.
