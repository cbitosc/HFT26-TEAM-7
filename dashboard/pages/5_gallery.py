"""Sightings - every detection framed with its AI bounding box."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import math
import streamlit as st

from dashboard.components import data_queries as q
from dashboard.components.ui import (html, chip, page_header, empty_state, confidence_gate, media_card, footer, SOURCE_CHIP)

if not q.db_exists():
    empty_state("Observatory offline", "No database found.", "python run_pipeline.py --limit 100"); st.stop()

media, det, n_cls = q.load()
page_header("Sightings",
            "Every MegaDetector detection, framed with its bounding box and identification tag. Person and vehicle "
            "detections are available here for perimeter audits but never enter wildlife statistics.",
            tiles=[("Detections", f"{len(det):,}", "boxes", None),
                   ("Framed images", f"{det['image_id'].nunique():,}", "frames", "var(--primary)")])

with st.container(key="panel_gate_gal"):
    min_conf = confidence_gate()
    f1, f2, f3, f4 = st.columns([1, 1.3, 1, 1])
    kind = f1.selectbox("Detection class", ["Animals", "People", "Vehicles"])
    cat = {"Animals": "animal", "People": "person", "Vehicles": "vehicle"}[kind]
    pool = det[(det["category"] == cat) & (det["label_source"] != "Rejected")]
    pool = pool[pool["conf"] >= min_conf] if cat == "animal" else pool[pool["det_conf"] >= min_conf]
    sp_keys = sorted(k for k in pool["species"].unique() if k) if cat == "animal" else []
    species = f2.selectbox("Species", ["All"] + sp_keys, format_func=lambda k: k if k == "All" else q.species_info(k)["common"],
                           disabled=cat != "animal")
    locs = sorted(pool["location_id"].unique(), key=lambda s: (len(s), s))
    station = f3.selectbox("Station", ["All"] + locs, format_func=lambda s: s if s == "All" else f"loc_{s}")
    order = f4.selectbox("Sort", ["Confidence ↓", "Confidence ↑", "Newest", "Oldest"])

view = pool
if species != "All":
    view = view[view["species"] == species]
if station != "All":
    view = view[view["location_id"] == station]
sort_col, asc = {"Confidence ↓": ("conf", False), "Confidence ↑": ("conf", True),
                 "Newest": ("ts", False), "Oldest": ("ts", True)}[order]
if cat != "animal" and sort_col == "conf":
    sort_col = "det_conf"
view = view.sort_values(sort_col, ascending=asc)

html('<div style="height:16px"></div>')
if view.empty:
    empty_state("Nothing matches these filters", "Widen the filters or lower the confidence gate."); footer(); st.stop()

PER = 12
pages = math.ceil(len(view) / PER)
c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
with c2:
    page = st.number_input("Page", 1, pages, 1) if pages > 1 else 1
with c1:
    html(f'<div class="sw-sub">{len(view):,} detections · page {page} of {pages}</div>')

cols = st.columns(3, gap="medium")
for i, r in enumerate(view.iloc[(page - 1) * PER: page * PER].itertuples()):
    with cols[i % 3]:
        if cat == "animal":
            label, latin, conf = r.common, r.sci, r.conf
            src, k = SOURCE_CHIP.get(r.label_source, (r.label_source, "ghost"))
            right = chip(src, k) + (" " + chip("review", "tertiary") if r.unverified else "")
        else:
            label, latin, conf, right = kind[:-1].title(), kind[:-1].title(), r.det_conf, chip("Perimeter", "error")
        media_card(r.file_path, (r.bbox_x, r.bbox_y, r.bbox_w, r.bbox_h), label, latin, conf, r.location_id,
                   f"{r.ts:%Y-%m-%d %H:%M}" if str(r.ts) != "NaT" else "", right)
        html('<div style="height:10px"></div>')

footer()
