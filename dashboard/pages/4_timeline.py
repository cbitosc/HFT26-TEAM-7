"""Activity Timeline - monthly effort, species × hour activity matrix, diel partitioning."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import calendar
import streamlit as st

from dashboard.components import data_queries as q
from dashboard.components import charts
from dashboard.components.ui import (html, chip, sci, esc, page_header, section, empty_state, confidence_gate,
                                     footer, GROUP_DOT)

if not q.db_exists():
    empty_state("Observatory offline", "No database found.", "python run_pipeline.py --limit 100"); st.stop()

media, det, n_cls = q.load()
ov = q.overview(media, det)
span = f"{ov['date_min']:%d %b %Y} → {ov['date_max']:%d %b %Y}" if str(ov["date_min"]) != "NaT" else "—"
page_header("Activity Timeline",
            "When animals are active: encounter volume through the survey, hour-of-day partitioning by taxon, "
            "and seasonal signal across months of the year.",
            tiles=[("Survey window", span, "", None)])

with st.container(key="panel_gate_tl"):
    min_conf = confidence_gate()
obs = q.species_obs(det, min_conf)
ev = q.encounters(obs)
html('<div style="height:16px"></div>')
if ev.empty:
    empty_state("No encounters at this gate", "Lower the confidence gate or run the detect step."); footer(); st.stop()

with st.container(key="panel_month"):
    mon = q.monthly(ev)
    section("Encounter Volume Through the Survey", f"Independent encounters per calendar month · {len(mon)} months",
            chip(f"N = {len(ev)}", "ghost"))
    html(charts.columns([(charts._fmt_month(d["month"]), d["count"]) for d in mon], 150))

html('<div style="height:18px"></div>')
a, b = st.columns([1.7, 1], gap="medium")
with a:
    with st.container(key="panel_heat"):
        top = ev["species"].value_counts().head(12)
        section("Species × Hour Activity Matrix", "Independent encounters per taxon per hour · amber = peak density",
                chip(f"Top {len(top)} taxa", "ghost"))
        matrix = {k: [int(((ev["species"] == k) & (ev["hour"] == h)).sum()) for h in range(24)] for k in top.index}
        labels = [(k, f'<span class="sw-dot" style="background:{GROUP_DOT.get(q.species_info(k)["group"])};margin-right:7px"></span>'
                      f'{esc(q.species_info(k)["common"])}') for k in top.index]
        html(charts.heatmap(matrix, labels))
with b:
    with st.container(key="panel_seasonal"):
        section("Seasonal Signal", "All years pooled, by month of year")
        moy = ev["start"].dt.month.value_counts()
        html(charts.columns([(calendar.month_abbr[m][:1], int(moy.get(m, 0))) for m in range(1, 13)], 120, charts.SAGE))
        html('<div class="sw-sub" style="margin-top:8px">Detection frequency at active stations, not abundance.</div>')
    with st.container(key="panel_diel_tbl"):
        section("Diel Partitioning by Taxon", "Share of encounters in each photoperiod")
        rows = ""
        for k in top.index[:8]:
            d = q.diel(ev[ev["species"] == k])
            bar = (f'<div style="display:flex;height:8px;border-radius:3px;overflow:hidden;background:var(--highest)">'
                   f'<div style="width:{d["nocturnal_pct"]}%;background:{charts.AMBER}"></div>'
                   f'<div style="width:{d["crepuscular_pct"]}%;background:{charts.TEAL}"></div>'
                   f'<div style="width:{d["diurnal_pct"]}%;background:{charts.SAGE}"></div></div>')
            rows += (f'<div style="display:grid;grid-template-columns:120px 1fr 40px;gap:10px;align-items:center;margin:8px 0">'
                     f'<span style="font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{esc(q.species_info(k)["common"])}</span>'
                     f'{bar}<span class="sw-mono" style="text-align:right;color:var(--tertiary)">{d["nocturnal_pct"]:.0f}%</span></div>')
        html(rows + '<div class="sw-sub" style="margin-top:6px">Amber nocturnal · teal crepuscular · sage diurnal. Value = nocturnal share.</div>')

footer()
