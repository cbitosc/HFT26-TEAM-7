# SmallWorld: project audit and team handoff

Last updated: 2026-10-31 (pipeline + dashboard track added. See section 12)

This document explains the hackathon project, the files in this repository,
what has been completed, and the next steps for every role.

## 1. Project goal

Build a beginner-friendly wildlife camera-trap dashboard that helps researchers:

1. Separate empty frames from frames containing animals.
2. Identify animals where possible and show confidence scores.
3. Explore sightings by species, camera location, and time of day.
4. Review blurry or uncertain predictions.
5. Summarize activity while stating uncertainty and limits of the sample.

The source is the Caltech Camera Traps CCT20 benchmark subset from LILA.
The dashboard is a hackathon demo, not a validated ecological study.

## 2. Current project status

### Completed

- The CCT annotation JSON files were inspected and parsed.
- A reproducible 2,500-image subset was created with seed `42`.
- The subset contains all 20 dataset locations and approximately 25% empty frames.
- The selected images were copied into `data/subset/`.
- `data/master.csv` was created with real metadata and blank pipeline-output fields.
- `data/fake_master.csv` was created for dashboard development with synthetic model outputs.
- `data_utils.py` was created to load the master CSV and resolve image paths.
- `analytics.py` was created for dashboard totals, species/location/hour counts, and encounter grouping.
- `summary.py` was created to generate a cautious plain-English Insights summary.
- The project is committed and pushed to the `main` branch at
  `https://github.com/ntw-1/SmallWorld`.
- Local checks passed: 2,500 CSV rows loaded, 2,500 image paths existed, all
  datetimes parsed, analytics ran, and the summary text generated.

### Completed on the pipeline + dashboard track (Nikita, 2026-10-31)

Full details are in section 12.

- Blur scoring (`pipeline/quality.py`, Laplacian variance, threshold 100).
- MegaDetector v5 detection with animal/person/vehicle confidences, bounding boxes and
  saved crops (`pipeline/detect.py`). It was run on a 100-image sample.
- SpeciesNet classification code with taxonomic roll-up (`pipeline/classify.py`). Written but
  **not yet run** on the sample.
- 30-minute encounter grouping in R with a Python fallback (`pipeline/encounter.py`), plus a
  live pandas version inside the dashboard.
- Featherless LLM field-report summariser (`llm/summariser.py`).
- A five-page Streamlit dashboard in the SmallWorld design (`dashboard/`).

### Not completed yet

- SpeciesNet run on the sample (`python run_pipeline.py --step classify`).
- Pipeline run beyond the first 100 images.
- Writing pipeline results back into the shared `data/master.csv` (the two tracks use
  different storage; see section 12.5).
- Final dashboard review and demo preparation.

## 3. Dataset facts and limits

The downloaded image archive is `eccv_18_all_images_sm.tar.gz` (about 6.5 GB).
It stays out of Git. The selected subset images are in GitHub and total about
289 MB.

The extracted annotation package contains five COCO Camera Traps JSON files:

| Split file | Images |
| --- | ---: |
| `train_annotations.json` | 13,553 |
| `cis_val_annotations.json` | 3,484 |
| `trans_val_annotations.json` | 1,725 |
| `cis_test_annotations.json` | 15,827 |
| `trans_test_annotations.json` | 23,275 |
| Total | 57,864 |

JSON top-level keys: `info`, `categories`, `images`, `annotations`.

Useful image keys: `id`, `file_name`, `location`, `date_captured`, `seq_id`,
`frame_num`, `seq_num_frames`, `height`, and `width`. Annotation records use
`image_id` and `category_id`. This dataset's annotations do not supply bounding
boxes in the files inspected.

The original categories are: `bobcat`, `opossum`, `empty`, `coyote`, `raccoon`,
`bird`, `dog`, `cat`, `squirrel`, `rabbit`, `skunk`, `rodent`, `badger`, `deer`,
`car`, and `fox`.

The current 2,500-image subset has:

- 20 locations.
- 640 empty images (25.6%).
- 1,365 day images and 1,135 night images. Day is defined as capture time from
  06:00 through 17:59.
- No missing or unparseable capture datetimes.
- Capture dates in the full source data from 2010-05-25 through 2015-04-22.

### Important evaluation warning

The 2,500-image subset samples across all five official splits. It is suitable
for a hackathon demo and pipeline development, but it must not be used to claim
benchmark accuracy because train, validation, and test data are mixed.

## 4. Repository layout

```text
SmallWorld/
├── AUDIT_LOG.md                 # this handoff document
├── README.md                    # original repository README
├── build_subset.py              # reproducibly creates the subset and CSVs
├── data_utils.py                # load_master() and get_image_path()
├── analytics.py                 # tables and encounter grouping
├── summary.py                   # plain-English Insights summary
├── config.py / run_pipeline.py / requirements.txt   # pipeline + dashboard (section 12)
├── pipeline/                    # ingest, extract, quality, detect, classify, encounter
├── llm/                         # Featherless summariser
├── r_scripts/                   # R encounter counting
├── dashboard/                   # Streamlit app, components, pages, assets
├── .streamlit/                  # dashboard theme config
└── data/
    ├── README.md                # data-specific documentation and stats
    ├── master.csv               # real metadata; model columns are blank
    ├── fake_master.csv          # 50 real images with synthetic predictions
    └── subset/                  # 2,500 selected JPG images
```

## 5. Shared CSV contract

`data/master.csv` has these columns in this order:

```text
image_id, path, location, datetime, blur_score, status, md_conf, bbox,
species, species_conf, seq_id, frame_num, gt_species
```

| Column | Owner / meaning |
| --- | --- |
| `image_id` | Dataset image ID. Do not change. |
| `path` | Path relative to `data/`, for example `subset/example.jpg`. Do not change. |
| `location` | Numeric camera location ID from CCT. Do not change. |
| `datetime` | Capture timestamp. Do not change. |
| `blur_score` | Quality role fills this numeric score. |
| `status` | Pipeline result: `Identified`, `Uncertain`, `Needs Review`, or `Empty`. |
| `md_conf` | Detector confidence from 0 to 1. |
| `bbox` | Detector bounding box, preferably JSON `[x, y, width, height]`. |
| `species` | Species role's predicted class. |
| `species_conf` | Species confidence from 0 to 1. |
| `seq_id` | Dataset sequence ID; supports grouping. Do not change. |
| `frame_num` | Position within a sequence. Do not change. |
| `gt_species` | Dataset ground-truth helper label. Use for internal checks only. |

`fake_master.csv` has the same columns and 50 rows. Its paths, timestamps,
locations, sequences, and ground-truth labels are real. Its blur scores,
statuses, confidences, boxes, and species predictions are fake placeholders for
dashboard development. Never present them as real model results.

## 6. How the pipeline should work

```text
image
  -> blur score
      -> blurry: Needs Review; retain image; skip models
      -> sharp: animal detector
          -> no animal: Empty
          -> animal: crop detection -> species classifier
              -> confidence >= 0.60: Identified
              -> confidence < 0.60: Uncertain
  -> master.csv -> analytics.py -> summary.py -> Streamlit dashboard
```

Tune the blur cutoff by looking at about 30 images. Night infrared images can
have low blur scores despite being usable, so do not blindly use a default
threshold.

If SpeciesNet is unavailable or slow, show the detector class
(`animal`, `person`, or `vehicle`) and state that species identification was
not available for that run.

## 7. Analytics rules already implemented

`analytics.py` uses `Identified` rows for primary wildlife totals. It keeps
`Uncertain` rows available for review and reports their share separately.
`Empty` and `Needs Review` rows are excluded from encounter and confident
sighting totals.

An encounter is one or more detections of the same predicted species at the
same location where each consecutive detection is no more than 30 minutes
after the last. Example: raccoon at 20:00, 20:08, and 20:20 is one encounter.

This mirrors the purpose of camtraptor and camtrapR workflows but is written in
pandas so the team does not need R.

`summary.py` only uses aggregated counts. It mentions uncertain detections and
the fact that the results come from a limited subset.

## 8. Current Git history

| Commit | Purpose |
| --- | --- |
| `c83ac04` | Initial camera-trap subset, CSVs, helper, annotation files. |
| `8e2def6` | Merged the pre-existing repository `main` history. |
| `0946270` | Added `analytics.py` and fixed the fake dashboard data mix. |
| `300e588` | Added `summary.py`. |
| `acd29e5` | Added this audit and team handoff. |
| _next_ | Added the pipeline + SmallWorld dashboard track, README and section 12 of this log. |

The current shared branch is `main`. Before starting work, run:

```bash
git pull --rebase origin main
```

After editing only your assigned files:

```bash
git add path/to/your-file
git commit -m "Short description of change"
git pull --rebase origin main
git push origin main
```

Do not have multiple people edit `data/master.csv` at the same time. Designate
one person to integrate model outputs into that CSV.

## 9. Step-by-step plan from here

### Step 1: Dashboard developer — build a working UI now

1. Pull the latest `main` branch.
2. Install UI dependencies if needed:
   ```bash
   python -m pip install streamlit plotly
   ```
3. Create `app.py` only. Start with `data/fake_master.csv`.
4. Import `analytics` and `make_summary` from `summary.py`; do not recreate
   their calculations inside `app.py`.
5. Create five tabs:
   - Overview: totals for total images, empty, identified, uncertain, and
     needs-review images.
   - Species: species bar chart, confidence distribution, representative image.
   - Activity: sightings by hour and sightings by location.
   - Review: gallery of `Uncertain` and `Needs Review` rows, showing score and
     prediction.
   - Insights: display `make_summary(df)`.
6. Run locally:
   ```bash
   streamlit run app.py
   ```
7. Commit and push `app.py`.

### Step 2: Quality + detection developer — validate a 20-image run first

1. Pull `main` and create `quality_detect.py`.
2. Add a blur score based on grayscale Laplacian variance after resizing.
3. Inspect roughly 30 day and night frames to choose a review threshold.
4. Test on 20 images before starting the whole subset.
5. For sharp images, run MegaDetector or use the official precomputed results
   if local inference is too slow.
6. Populate only `blur_score`, `status`, `md_conf`, and `bbox`.
7. Mark blurry images `Needs Review`; mark sharp frames without an animal
   detection `Empty`.
8. Store the 20-image output separately while testing. Do not overwrite the
   shared full `master.csv` until the test is reviewed.
9. Commit `quality_detect.py` and its small test artifact.

### Step 3: Species developer — validate a 20-crop run first

1. Pull `main` and create `species.py`.
2. Take animal crops from detector boxes, then run SpeciesNet if available.
3. Test on 20 crops and check a few predictions visually.
4. Set `species` and `species_conf`.
5. Set `Identified` for confidence at least `0.60`; otherwise set `Uncertain`.
6. If species classification fails, document the fallback and keep detector
   categories instead of inventing species labels.
7. Commit `species.py` and its small test artifact.

### Step 4: One integrator — create real master data

1. Pull the latest model scripts and test outputs.
2. Run quality detection and species classification in batches.
3. Write results into a copy of `data/master.csv` first.
4. Check that all 2,500 rows remain present and the original metadata columns
   still match.
5. Check status counts, missing confidence values, and a random set of image
   paths/crops.
6. Replace `data/master.csv` only after these checks.
7. Commit and push the updated CSV.

### Step 5: Analytics owner — switch from fake to real results

1. Pull the integrated `master.csv`.
2. Run:
   ```bash
   python -c "import analytics; from summary import make_summary; df = analytics.load_analytics_data('data/master.csv'); print(analytics.dashboard_metrics(df)); print(make_summary(df))"
   ```
3. Confirm counts add up to 2,500 and inspect the most common species and
   locations for obvious errors.
4. Check that uncertain detections are reported separately.
5. Confirm the 30-minute encounter logic creates plausible groups.
6. Give the dashboard developer the final summary text and any caveats.

### Step 6: Integration and demo

1. Change the dashboard input from `fake_master.csv` to `master.csv`.
2. Test all five tabs with the real data.
3. Open representative images and review uncertain/blurry cases.
4. Confirm every displayed number comes from real data rather than fake rows.
5. Rehearse a 2-minute demo:
   - problem: manual review of camera-trap images is slow;
   - workflow: quality check -> animal detection -> species confidence ->
     encounter grouping;
   - value: dashboard shows activity and flags uncertainty for human review;
   - limitation: this is a 2,500-image mixed-split demo subset.
6. Record a backup screen recording before the presentation.

## 10. Quick test commands

Use the installed Python executable if `python` points somewhere else:

```powershell
& 'C:\Users\Advaith\AppData\Local\Python\bin\python.exe' analytics.py
& 'C:\Users\Advaith\AppData\Local\Python\bin\python.exe' summary.py
```

Basic data check:

```powershell
& 'C:\Users\Advaith\AppData\Local\Python\bin\python.exe' -c "from data_utils import load_master, get_image_path; df=load_master(); print(len(df), get_image_path(df.iloc[0]).exists())"
```

Expected output is `2500 True`.

## 11. Ownership summary

| Role | Own files / responsibilities |
| --- | --- |
| Data lead | `build_subset.py`, `data/README.md`, CSV contract, data integration coordination. |
| Quality + detection | `quality_detect.py`, blur score, detector fields, crop handling. |
| Species ID | `species.py`, predicted species and confidence. |
| Analytics + insights | `analytics.py`, `summary.py`, encounter logic, caveats. |
| Dashboard + demo | `app.py`, dashboard behavior, slides, presentation. |

Keep changes small, commit often, and pull before each work session.

## 12. Pipeline + dashboard track (Nikita): change log and audit

This track is a separate, end-to-end implementation. It stores results in SQLite
(`data/db/wildlife.db`, created locally and not committed) and serves them through a
Streamlit dashboard. It does not modify `data/master.csv` or any of the files in sections 4–10.

### 12.1 Database schema (`pipeline/ingest.py`)

| Table | Key columns |
| --- | --- |
| `media` | `image_id`, `file_path`, `location_id`, `datetime`, `sequence_id`, `blur_score`, `status`, `gt_label` |
| `detections` | `id`, `image_id`, `category`, `confidence`, `bbox_x/y/w/h` (normalised), `crop_path`, `needs_review`, `reviewed`* |
| `classifications` | `id`, `detection_id`, `species_common`, `species_sci`, `family`, `conf_top1..3`, `rolled_up_to`, `human_label`, `status` |
| `encounters` | `location_id`, `species_common`, `event_start`, `event_end`, `image_count`, `trap_nights` |

\* `detections.reviewed` is added automatically (idempotent `ALTER TABLE`) the first time a
decision is saved in the Review Queue.

`media.status` moves through `pending` → `sharp` / `blurry` / `missing` → `animal_detected` /
`needs_review` / `empty`. `classifications.status` is `auto`, `needs_review`, `human_verified`
or `rejected`.

### 12.2 Change log

| # | Change | Why / outcome |
| --- | --- | --- |
| 1 | Built `pipeline/` (ingest, extract, quality, detect, classify, encounter), `run_pipeline.py`, `config.py`, `llm/summariser.py`, `r_scripts/encounter_count.R` and a basic 7-page dashboard. | First end-to-end version. |
| 2 | Ingest handles the CCT annotation file being a **tar of 5 JSONs** (as well as gzip or plain JSON). | The downloaded `caltech_coco.json` turned out to be a tar. |
| 3 | Rewrote `classify.py` against the real SpeciesNet API (`SpeciesNet(DEFAULT_MODEL).predict(filepaths=…)`) and its label format `uuid;class;order;family;genus;species;common`. | The first version guessed the API. |
| 4 | `detect.py` uses the `megadetector` package (`load_detector`, auto-download of MDV5A). | Fixed `No module named utils` from the old YOLOv5 path. |
| 5 | Ran ingest → quality → detect on a 100-image sample. | Produced the verified numbers in 12.3. |
| 6 | **Redesign v1 (SmallWorld design system)** shipped a single-page `app.py`. It crashed with `sqlite3.OperationalError: no such column: m.seq_id`. | Root cause: the queries were written against an assumed schema, not the real one (the column is `sequence_id`). The rewrite also hid the other pages. |
| 7 | Rewrote `dashboard/components/data_queries.py` against the real schema with column checks (`PRAGMA table_info`), a cache keyed on the database's modified time, and a species-label priority of human, then SpeciesNet, then ground truth. | Fixes the crash and keeps the dashboard useful before SpeciesNet has been run. |
| 8 | Encounters are recomputed live in pandas with the same 30-minute rule, so they respond to the confidence gate. Trap-nights are distinct camera-days with a capture. | Matches `pipeline/encounter.py` and the rule in section 7. |
| 9 | Benchmarks computed against CCT ground truth: MegaDetector image-level precision, recall, F1 and confusion counts; SpeciesNet top-1 accuracy and roll-up rate (excluding human labels); blur and empty-frame rates. | Replaces placeholder metrics with real ones. |
| 10 | Multipage dashboard using `st.navigation`, inline SVG charts, and amber bounding-box overlays on the images. | Implements the SmallWorld design. |
| 11 | Review Queue writes decisions back. Accept, relabel or reject a prediction; or confirm a box and its label (inserts a `human_verified` classification) or mark a false trigger (`category='false_positive'`, image set to `empty` if no animal boxes are left). | Scientist-in-the-loop verification. |
| 12 | Removed the **Bio-Analytics** and **Fauna Classifiers** pages. Renamed Grid Viewport to **Sightings**, AI Synthesis to **AI Summary** and Station Network to **Site Activity**. Activity Timeline is now the home page. | Requested scope change. |
| 13 | Replaced the top nav bar with a **☰ sidebar drawer** to the left of the SmallWorld logo; the button and logo stay in the same place whether the drawer is open or closed. | Requested navigation change. |

### 12.3 Verified results (local 100-image sample, 2026-10-31)

Checked by running the dashboard against a copy of the real database:

- 100 images, 20 locations, dated 2010-07-30 to 2014-10-12. All 100 passed the blur gate (mean
  Laplacian variance 779).
- MegaDetector: 95 boxes (86 animal, 5 person, 4 vehicle). 80 images `animal_detected`, 20 `empty`.
- **MegaDetector against ground truth (image level): precision 98.8%, recall 89.8%, F1 0.940**
  (TP 79, FP 1, FN 9, TN 11).
- At the 50% confidence gate: 76 animal detections, 72 independent encounters, 11 taxa, 54.2%
  nocturnal.
- SpeciesNet: 0 classifications so far. The dashboard shows ground-truth labels marked as such.
- Tests: all five pages load with no exceptions on the real database copy and on a simulated
  database containing classifications. Review Queue saves were confirmed in SQLite. Every
  sidebar link was click-tested.

### 12.4 Known limitations

- Encounter rates per station rest on 2–5 encounters each and are indicative only.
- These benchmark numbers come from 100 frames drawn across the official splits and must not
  be quoted as CCT benchmark accuracy (same warning as section 3).
- `requirements.txt` does not pin versions. The dashboard needs Streamlit 1.46 or newer and was
  tested on 1.66.1.
- `dashboard/components/bbox_draw.py` and `confidence_filter.py` are no longer used and can be
  removed.
- The dashboard loads fonts from Google Fonts. Without internet access it falls back to
  system fonts.

### 12.5 Integration items for the team

1. **Two stores.** The analytics track reads `data/master.csv`; this track writes SQLite. Agree
   on one. The simplest option is an export from SQLite into the `master.csv` columns in section 5
   (`blur_score`, `status`, `md_conf`, `bbox`, `species`, `species_conf`).
2. **Threshold mismatch.** Section 6 uses `Identified` at species confidence ≥ 0.60. `classify.py`
   flags below 0.50. Pick one value.
3. **Status vocabulary.** `Identified/Uncertain/Needs Review/Empty` (CSV) versus
   `animal_detected/needs_review/empty/blurry` (SQLite) needs a mapping.
4. **Day/night definition.** The CSV track uses day = 06:00–17:59. The dashboard uses nocturnal
   20–05, crepuscular 05–08 and 17–20, diurnal 08–17.
5. **Images.** The pipeline reads images from `data/raw/images/`. To use the committed 2,500-image
   subset, point `IMAGES_DIR` in `config.py` at `data/subset`, or copy the images across.

### 12.6 Next steps

1. `python run_pipeline.py --step classify`, then `--step encounter`. The SpeciesNet benchmark
   card and Review Queue will fill in automatically.
2. Increase the sample size (`python run_pipeline.py --limit 2500`), ideally using `data/subset`.
3. Resolve the integration items in 12.5.
4. Rehearse the demo on the dashboard (Activity Timeline → Sightings → Review Queue → AI Summary).

