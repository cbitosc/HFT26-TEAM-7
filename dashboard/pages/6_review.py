"""Review Queue - scientist verification of uncertain predictions and detections."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from dashboard.components import data_queries as q
from dashboard.components.ui import (html, chip, sci, esc, page_header, section, empty_state, media_card, footer, SOURCE_CHIP)

if not q.db_exists():
    empty_state("Observatory offline", "No database found.", "python run_pipeline.py --limit 100"); st.stop()

media, det, n_cls = q.load()
animals = det[det["category"] == "animal"]
cls_queue = animals[(animals["cls_status"] == "needs_review")].sort_values("conf")
low_conf = animals[(animals["cls_id"].isna()) & (animals["det_conf"] < 0.5) & (animals["reviewed"] != 1)].sort_values("det_conf")
unclassified = animals[(animals["cls_id"].isna()) & (animals["reviewed"] != 1)].sort_values("det_conf")
verified = int((animals["label_source"] == "Verified").sum())

page_header("Review Queue",
            "Scientist-in-the-loop verification. Decisions are written straight back to the pipeline database and "
            "flow into every chart, encounter count and AI summary.",
            tiles=[("SpeciesNet flags", len(cls_queue), "predictions", "var(--tertiary)"),
                   ("Low-conf. boxes", len(low_conf), "MD < 50%", None),
                   ("Verified", verified, "by scientists", "var(--secondary)")])

SPECIES_CHOICES = sorted(q.SPECIES, key=lambda k: q.SPECIES[k][0])
fmt = lambda k: f"{q.SPECIES[k][0]} ({q.SPECIES[k][1]})"


def save(fn, feedback_entry=None):
    conn = q.connect()
    try:
        q.ensure_review_schema(conn)
        q.ensure_feedback_schema(conn)
        fn(conn)
        if feedback_entry:
            q.log_feedback(conn, **feedback_entry)
        conn.commit()
    finally:
        conn.close()
    st.toast("Decision saved — feedback logged for model learning")
    st.rerun()


def item(r, mode, n):
    with st.container(key=f"panel_rev_{mode}_{n}"):
        a, b = st.columns([1.15, 1.4], gap="large")
        with a:
            media_card(r.file_path, (r.bbox_x, r.bbox_y, r.bbox_w, r.bbox_h), r.common, r.sci,
                       r.conf if mode == "cls" else r.det_conf, r.location_id,
                       f"{r.ts:%Y-%m-%d %H:%M}" if str(r.ts) != "NaT" else "")
        with b:
            gt = q.species_info(q.species_key(r.gt_label)) if isinstance(r.gt_label, str) and r.gt_label.lower() not in q.NON_ANIMAL_LABELS else None
            lines = []
            if mode == "cls":
                lines.append(("SpeciesNet prediction", f"{esc(str(r.cls_species))} · {r.conf_top1:.1%}"))
                if isinstance(r.rolled_up_to, str):
                    lines.append(("Rolled up to", esc(r.rolled_up_to)))
            lines.append(("MegaDetector box", f"{r.det_conf:.1%} confidence"))
            if gt:
                lines.append(("Caltech ground truth", f"{esc(gt['common'])} {sci(gt['sci'], 12)}"))
            lines.append(("Station · time", f"loc_{esc(r.location_id)} · {esc(str(r.datetime))}"))
            html("".join(f'<div style="display:flex;justify-content:space-between;gap:12px;padding:7px 0;'
                         f'border-bottom:1px solid rgba(120,148,119,.08)"><span class="sw-label">{k}</span>'
                         f'<span class="sw-body" style="text-align:right">{v}</span></div>' for k, v in lines))
            with st.form(f"f_{mode}_{r.det_id}", border=False):
                options = (["Accept prediction", "Relabel", "Reject (wrong / unidentifiable)"] if mode == "cls"
                           else ["Confirm animal + label", "False trigger (no animal)"])
                action = st.radio("Decision", options, horizontal=True, key=f"a_{mode}_{r.det_id}")
                default = SPECIES_CHOICES.index(r.species) if r.species in SPECIES_CHOICES else 0
                label = st.selectbox("Species (used for Relabel / Confirm)", SPECIES_CHOICES, index=default,
                                     format_func=fmt, key=f"s_{mode}_{r.det_id}")
                if st.form_submit_button("Save decision", type="primary"):
                    common = q.SPECIES[label][0]
                    fb_base = dict(detection_id=int(r.det_id), image_id=r.image_id,
                                   location_id=r.location_id,
                                   model_prediction=str(r.cls_species) if hasattr(r, "cls_species") and r.cls_species else str(r.common),
                                   model_confidence=float(r.conf if mode == "cls" else r.det_conf),
                                   previous_label=str(r.common),
                                   label_source=str(r.label_source) if hasattr(r, "label_source") else "unknown")
                    if mode == "cls":
                        if action.startswith("Accept"):
                            fb = {**fb_base, "action": "accept", "human_label": str(r.cls_species)}
                            save(lambda c: c.execute("UPDATE classifications SET status='human_verified' WHERE id=?", (int(r.cls_id),)),
                                 feedback_entry=fb)
                        elif action == "Relabel":
                            fb = {**fb_base, "action": "relabel", "human_label": label}
                            save(lambda c: c.execute("UPDATE classifications SET status='human_verified', human_label=?, "
                                                     "species_common=?, species_sci=? WHERE id=?",
                                                     (label, common, q.SPECIES[label][1], int(r.cls_id))),
                                 feedback_entry=fb)
                        else:
                            fb = {**fb_base, "action": "reject", "human_label": None}
                            save(lambda c: c.execute("UPDATE classifications SET status='rejected' WHERE id=?", (int(r.cls_id),)),
                                 feedback_entry=fb)
                    else:
                        if action.startswith("Confirm"):
                            fb = {**fb_base, "action": "confirm", "human_label": label}
                            def confirm(c):
                                c.execute("UPDATE detections SET reviewed=1, needs_review=0 WHERE id=?", (int(r.det_id),))
                                c.execute("INSERT INTO classifications (detection_id, species_common, species_sci, family, conf_top1, "
                                          "human_label, status) VALUES (?,?,?,?,1.0,?, 'human_verified')",
                                          (int(r.det_id), common, q.SPECIES[label][1], q.SPECIES[label][2], label))
                            save(confirm, feedback_entry=fb)
                        else:
                            fb = {**fb_base, "action": "false_positive", "human_label": "empty"}
                            def reject(c):
                                c.execute("UPDATE detections SET category='false_positive', reviewed=1 WHERE id=?", (int(r.det_id),))
                                left = c.execute("SELECT COUNT(*) FROM detections WHERE image_id=? AND category='animal'",
                                                 (r.image_id,)).fetchone()[0]
                                if left == 0:
                                    c.execute("UPDATE media SET status='empty' WHERE image_id=?", (r.image_id,))
                            save(reject, feedback_entry=fb)
    html('<div style="height:14px"></div>')


tab1, tab2 = st.tabs([f"SpeciesNet predictions ({len(cls_queue)})", f"Detection audit ({len(low_conf)})"])

with tab1:
    section("Flagged species predictions", "Confidence below 50% or not resolved to species level · lowest confidence first")
    if n_cls == 0:
        empty_state("SpeciesNet hasn't run yet", "Predictions appear here once the classify step has run.",
                    "python run_pipeline.py --step classify")
    elif cls_queue.empty:
        empty_state("Queue clear", "Every SpeciesNet prediction is above threshold or already reviewed.")
    else:
        for n, r in enumerate(cls_queue.head(10).itertuples()):
            item(r, "cls", n)
        if len(cls_queue) > 10:
            html(f'<div class="sw-sub">Showing 10 of {len(cls_queue)}. Save decisions to load more.</div>')

with tab2:
    show_all = st.toggle("Also verify detections that only have ground-truth labels", value=False,
                         help="Confirming a detection records a scientist-verified label, which counts toward station verification %.")
    queue = unclassified if show_all else low_conf
    section("MegaDetector boxes awaiting a human decision",
            "All unclassified animal boxes" if show_all else "Animal boxes with MegaDetector confidence below 50% · lowest first")
    if queue.empty:
        empty_state("Queue clear", "No low-confidence animal boxes. Turn on the toggle above to verify ground-truth-labelled detections.")
    else:
        for n, r in enumerate(queue.head(10).itertuples()):
            item(r, "det", n)
        if len(queue) > 10:
            html(f'<div class="sw-sub">Showing 10 of {len(queue)}. Save decisions to load more.</div>')

footer()
