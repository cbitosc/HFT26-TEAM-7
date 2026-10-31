import json, csv, random, tarfile, shutil, re, math
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from PIL import Image
import pandas as pd

ROOT = Path(__file__).resolve().parent
ANNOTATIONS = ROOT / 'eccv_18_annotations' / 'eccv_18_annotation_files'
ARCHIVE = ROOT / 'eccv_18_all_images_sm.tar.gz'
OUT = ROOT / 'data'
SUBSET = OUT / 'subset'
SEED = 42
TARGET = 2500
random.seed(SEED)

# Read each split and preserve its name for reference.
records = []
categories = {}
for jf in sorted(ANNOTATIONS.glob('*.json')):
    data = json.loads(jf.read_text(encoding='utf-8'))
    print(f"JSON {jf.name}: top-level keys={list(data)}; images={len(data.get('images', []))}; annotations={len(data.get('annotations', []))}; categories={len(data.get('categories', []))}")
    categories.update({c['id']: c['name'] for c in data.get('categories', [])})
    anns = defaultdict(list)
    for ann in data.get('annotations', []):
        anns[str(ann.get('image_id'))].append(ann)
    split = jf.stem.replace('_annotations', '')
    for im in data.get('images', []):
        row = dict(im)
        row['_split'] = split
        row['_anns'] = anns.get(str(im.get('id')), [])
        cats = [categories.get(a.get('category_id'), 'unknown') for a in row['_anns']]
        animals = [c for c in cats if c.lower() != 'empty']
        row['_empty'] = len(animals) == 0
        row['_species'] = animals[0] if animals else 'empty'
        records.append(row)

# Build one image record per unique filename across splits.
unique = {}
for r in records:
    unique.setdefault(r['file_name'], r)
records = list(unique.values())
print('Unique images:', len(records), 'Categories:', categories)

# Stratified, capped selection. Fill empty target first, then animal images with species caps,
# while spreading choices across locations. Sequence is retained for downstream grouping.
locs = defaultdict(list)
for r in records:
    locs[str(r.get('location', 'unknown'))].append(r)
empty_target = round(TARGET * 0.25)
selected = []
used = set()
# Rotate through locations so every available location is represented.
location_names = sorted(locs)
random.shuffle(location_names)
for want_empty, limit in [(True, empty_target), (False, TARGET-empty_target)]:
    buckets = {}
    for loc in location_names:
        bucket = [r for r in locs[loc] if r['_empty'] == want_empty and r['file_name'] not in used]
        random.shuffle(bucket)
        buckets[loc] = bucket
    species_counts = Counter()
    per_species_cap = max(1, math.ceil((TARGET-empty_target) / max(1, len([c for c in categories.values() if c.lower() != 'empty']))))
    while len([r for r in selected if r['_empty'] == want_empty]) < limit:
        moved = False
        for loc in location_names:
            bucket = buckets[loc]
            while bucket:
                r = bucket.pop()
                sp = r['_species']
                if not want_empty and species_counts[sp] >= per_species_cap:
                    continue
                selected.append(r); used.add(r['file_name']); species_counts[sp] += 1
                moved = True
                break
            if len([x for x in selected if x['_empty'] == want_empty]) >= limit:
                break
        if not moved:
            break
if len(selected) < TARGET:
    remaining = [r for r in records if r['file_name'] not in used]
    random.shuffle(remaining)
    selected.extend(remaining[:TARGET-len(selected)])
selected = selected[:TARGET]

# Extract only selected files from the tar archive; never unpack the full image collection.
OUT.mkdir(exist_ok=True); SUBSET.mkdir(parents=True, exist_ok=True)
name_to_record = {r['file_name']: r for r in selected}
archive_prefix = 'eccv_18_all_images_sm/'
missing = set(name_to_record)
with tarfile.open(ARCHIVE, 'r:gz') as tf:
    for member in tf:
        if not member.isfile() or not member.name.lower().endswith(('.jpg','.jpeg','.png')):
            continue
        name = Path(member.name).name
        if name not in missing:
            continue
        src = tf.extractfile(member)
        if src:
            with (SUBSET / name).open('wb') as dst:
                shutil.copyfileobj(src, dst)
            missing.remove(name)
        if not missing:
            break
print('Selected:', len(selected), 'Copied:', TARGET-len(missing), 'Missing from archive:', len(missing))

# Make the requested master schema and append ground-truth/debug columns.
rows = []
for r in selected:
    name = r['file_name']
    try:
        dt = pd.to_datetime(r.get('date_captured'), errors='coerce')
        dtout = dt.isoformat() if not pd.isna(dt) else ''
    except Exception:
        dtout = ''
    rows.append({
        'image_id': r.get('id', Path(name).stem), 'path': f'subset/{name}',
        'location': r.get('location', ''), 'datetime': dtout,
        'blur_score': '', 'status': '', 'md_conf': '', 'bbox': '',
        'species': '', 'species_conf': '', 'seq_id': r.get('seq_id', ''),
        'frame_num': r.get('frame_num', ''), 'gt_species': r['_species'],
        '_split': r['_split'],
    })
master = pd.DataFrame(rows)
columns = ['image_id','path','location','datetime','blur_score','status','md_conf','bbox','species','species_conf','seq_id','frame_num','gt_species']
master[columns].to_csv(OUT/'master.csv', index=False)

# Synthetic dashboard starter data; values are fake and are tagged in README.
# Select a dashboard-friendly mix rather than taking the first 50 subset rows,
# which may all belong to the empty-image portion of the selection.
fake_empty = master[master["gt_species"].eq("empty")].sample(n=12, random_state=SEED)
animal_pool = master[~master["gt_species"].eq("empty")]
one_per_species = animal_pool.groupby("gt_species", group_keys=False).sample(n=1, random_state=SEED)
remaining_animals = animal_pool.drop(index=one_per_species.index).sample(
    n=38 - len(one_per_species), random_state=SEED
)
fake = pd.concat([fake_empty, one_per_species, remaining_animals], ignore_index=True)[columns].copy().astype(object)
rng = random.Random(SEED)
for i in range(len(fake)):
    label = fake.iloc[i]['gt_species']
    empty = label == 'empty'
    status = 'Empty' if empty else rng.choices(['Identified','Uncertain','Needs Review'], [0.68,0.22,0.10])[0]
    fake.loc[fake.index[i], 'blur_score'] = round(rng.uniform(18, 240), 2)
    fake.loc[fake.index[i], 'status'] = status
    fake.loc[fake.index[i], 'md_conf'] = '' if empty else round(rng.uniform(.55,.99),3)
    fake.loc[fake.index[i], 'bbox'] = '' if empty else json.dumps([round(rng.uniform(0,.5),3),round(rng.uniform(0,.4),3),round(rng.uniform(.3,.5),3),round(rng.uniform(.3,.5),3)])
    fake.loc[fake.index[i], 'species'] = 'empty' if empty else label
    fake.loc[fake.index[i], 'species_conf'] = '' if empty else round(rng.uniform(.45,.99),3)
fake.to_csv(OUT/'fake_master.csv', index=False)

# Validate copied images and inspect 20 reproducible random files.
problems = []
for r in selected:
    p = SUBSET / r['file_name']
    if not p.exists(): problems.append(f'missing file: {p.name}')
    try:
        with Image.open(p) as im: im.verify()
    except Exception as e: problems.append(f'bad image {p.name}: {e}')
check = random.sample([r for r in selected if (SUBSET/r['file_name']).exists()], min(20, len(selected)))
for r in check:
    try:
        with Image.open(SUBSET/r['file_name']) as im: im.load()
    except Exception as e: problems.append(f'random open failed {r["file_name"]}: {e}')

# Stats and README.
df = master[columns].copy()
df['location'] = df['location'].astype(str)
df['dt'] = pd.to_datetime(df['datetime'], errors='coerce')
df['period'] = df['dt'].dt.hour.map(lambda h: 'day' if pd.notna(h) and 6 <= h < 18 else ('night' if pd.notna(h) else 'unknown'))
loc_stats = df.groupby('location').size().sort_values(ascending=False)
species_stats = df['gt_species'].value_counts()
empty_pct = (df['gt_species'].eq('empty').mean()*100) if len(df) else 0
day_night = df['period'].value_counts()
missing_dt = int(df['dt'].isna().sum())
readme = f'''# Camera-trap dashboard data\n\nSubset generated with seed {SEED} from the provided CCT annotation files. It contains {len(df)} images. This is a convenience subset across all provided split files; split membership is not exported to the master contract. Sequences are retained as metadata but may be partially sampled.\n\n## Subset summary\n\n- Images: {len(df)}\n- Empty: {int(df['gt_species'].eq('empty').sum())} ({empty_pct:.1f}%)\n- Day / night / unknown (day defined as 06:00–17:59 local capture time): {int(day_night.get('day',0))} / {int(day_night.get('night',0))} / {int(day_night.get('unknown',0))}\n- Missing/unparsed datetimes: {missing_dt}\n\n### Images per location\n\n{chr(10).join(f'- {k}: {v}' for k,v in loc_stats.items())}\n\n### Ground-truth species counts\n\n{chr(10).join(f'- {k}: {v}' for k,v in species_stats.items())}\n\n## CSV columns\n\n`image_id` is the dataset image ID. `path` is relative to this data folder. `location` is the dataset location ID (not a human-readable site name). `datetime` is the dataset capture time in ISO format. `blur_score`, `status`, `md_conf`, `bbox`, `species`, and `species_conf` are pipeline-owned fields left blank in `master.csv`. `seq_id` and `frame_num` support encounter grouping. `gt_species` is the benchmark ground-truth class, or `empty` when no animal annotation exists.\n\nAllowed `status` values: `Identified`, `Uncertain`, `Needs Review`, `Empty`. Data lead owns image ID, path, location, datetime and ground-truth helper fields; quality/detection fills blur score, status, detector confidence and bounding box; species role fills predicted species and confidence.\n\n`fake_master.csv` contains 50 rows with synthetic model outputs for dashboard development. Its model values are fake; paths, metadata, and ground-truth labels refer to selected real images.\n\n## Limitations and assumptions\n\nThe annotation package contains five split JSONs (`train`, `cis_val`, `trans_val`, `cis_test`, `trans_test`). The subset samples across these files and does not preserve benchmark evaluation split isolation. Location is a numeric dataset ID. A frame with no non-empty category annotation is labeled `empty`. Day/night uses capture hour only; unknown timestamps remain unknown. Sequence integrity is not guaranteed because the target size and balancing can select only part of a sequence.\n\nEncounter counting can follow the blueprint: group detections of the same predicted species at the same location when successive detections are within 30 minutes. This is a pandas implementation inspired by the standard workflows in camtraptor and camtrapR; the project does not depend on either R package.\n'''
(OUT/'README.md').write_text(readme, encoding='utf-8')

# Simple helper module for dashboard teammates.
(OUT.parent/'data_utils.py').write_text('''"""Helpers for loading the camera-trap master CSV."""\nfrom pathlib import Path\nimport pandas as pd\n\nDATA_DIR = Path(__file__).resolve().parent / "data"\n\ndef load_master(csv_path=DATA_DIR / "master.csv"):\n    """Load master.csv with stable text IDs and parsed capture datetimes."""\n    df = pd.read_csv(csv_path, dtype={"image_id": "string", "location": "string", "seq_id": "string", "gt_species": "string"})\n    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")\n    return df\n\ndef get_image_path(row):\n    """Return an absolute Path for an image row from master.csv."""\n    path = Path(str(row["path"]))\n    return path if path.is_absolute() else DATA_DIR / path\n''', encoding='utf-8')

print('Locations:', loc_stats.to_dict())
print('Species:', species_stats.to_dict())
print(f'Empty fraction: {empty_pct:.1f}% | Day/night: {day_night.to_dict()} | Missing datetimes: {missing_dt}')
print('First 5 master rows:')
print(master[columns].head().to_string(index=False))
print('Problems:', problems[:20] if problems else 'none')
