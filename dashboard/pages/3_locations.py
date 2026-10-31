"""Site Activity - full site scorecard and per-station drill-down."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from dashboard.components import data_queries as q
from dashboard.components import charts
from dashboard.components.ui import (html, chip, sci, esc, page_header, section, empty_state, confidence_gate,
                                     media_card, footer, GROUP_DOT)

if not q.db_exists():
    empty_state("Observatory offline", "No database found.", "python run_pipeline.py --limit 100"); st.stop()

media, det, n_cls = q.load()
ov = q.overview(media, det)
page_header("Site Activity",
            "Camera-station effort, independent encounter rates per 100 trap-nights and species composition for every node "
            "in the array.",
            tiles=[("Stations", ov["stations"], f"/ {ov['operational']} reporting", None),
                   ("Effort", f"{ov['trap_nights']:,}", "trap-nights", "var(--primary)")])

with st.container(key="panel_gate_loc"):
    min_conf = confidence_gate()
obs = q.species_obs(det, min_conf)
ev = q.encounters(obs)
loc = q.location_scorecard(media, obs, ev)
html('<div style="height:16px"></div>')
if loc.empty:
    empty_state("No stations yet", "Ingest images first.", "python run_pipeline.py --limit 100"); st.stop()

status_kind = {"HIGH ACTIVITY": "tertiary", "VERIFIED": "secondary", "STABLE": "ghost", "LOW DATA": "error"}
with st.container(key="panel_allloc"):
    section("Site Comparative Scorecard", f"All {len(loc)} stations ranked by encounter rate (/100 TN)",
            "".join(chip(f"{k} {int((loc['status'] == k).sum())}", v) for k, v in status_kind.items() if (loc["status"] == k).any()))
    mx = max(loc["rate"].max(), 1)
    body = ""
    for r in loc.itertuples():
        taxon = (f'{sci(r.dominant_sci, 13)} <span class="sw-sub">({esc(r.dominant)})</span>' if r.dominant_sci else '<span class="sw-sub">—</span>')
        body += (f'<tr><td class="m">loc_{esc(r.location_id)}</td><td class="r m">{r.trap_nights}</td><td class="r m">{r.detections}</td>'
                 f'<td class="r m"><b>{r.encounters}</b></td><td style="min-width:170px"><div style="display:flex;gap:10px;align-items:center">'
                 f'<div class="sw-bar" style="flex:1"><div style="width:{r.rate / mx * 100:.0f}%;background:var(--tertiary)"></div></div>'
                 f'<span class="sw-mono" style="color:var(--tertiary);width:44px;text-align:right">{r.rate}</span></div></td>'
                 f'<td class="r m">{r.n_species}</td><td>{taxon}</td><td class="r m">{r.avg_conf:.1%}</td>'
                 f'<td class="c">{chip(r.status, status_kind.get(r.status, "ghost"))}</td></tr>')
    html(f"""<div class="sw-table-wrap"><table class="sw-table"><thead><tr><th>Station</th><th class="r">Trap-nights</th>
        <th class="r">Detections</th><th class="r">Encounters</th><th>Rate / 100 TN</th><th class="r">Taxa</th><th>Dominant species</th>
        <th class="r">Mean conf.</th><th class="c">Status</th></tr></thead><tbody>{body}</tbody></table></div>""")
    html('<div class="sw-sub" style="margin-top:8px">Trap-nights = distinct camera-days with at least one capture in the database. '
         'Rates from small samples are indicative only.</div>')

html('<div style="height:18px"></div>')

with st.container(key="panel_station"):
    ids = loc["location_id"].tolist()
    pick = st.selectbox("Station drill-down", ids, format_func=lambda s: f"loc_{s}")
    r = loc[loc["location_id"] == pick].iloc[0]
    o = obs[obs["location_id"] == pick]
    e = ev[ev["location_id"] == pick]
    m = media[media["location_id"] == pick]
    tiles = [("Images", len(m)), ("Trap-nights", int(r.trap_nights)), ("Encounters", int(r.encounters)),
             ("Rate /100 TN", r.rate), ("Empty frames", int((m["status"] == "empty").sum())),
             ("Active", f"{m['ts'].min():%b %Y} – {m['ts'].max():%b %Y}" if m["ts"].notna().any() else "—")]
    html('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:6px 0 18px 0">' + "".join(
        f'<div class="sw-card" style="padding:10px 12px"><div class="sw-label">{t}</div><div class="sw-mono" style="font-size:16px;margin-top:3px">{v}</div></div>'
        for t, v in tiles) + "</div>")
    a, b = st.columns([1, 1.25], gap="large")
    with a:
        comp = o.groupby(["species", "common", "group"]).size().sort_values(ascending=False)
        html('<div class="sw-label" style="margin-bottom:4px">Species composition · detections</div>')
        if len(comp):
            html(charts.hbars([(f'{esc(c)}', int(v), str(int(v)), GROUP_DOT.get(g)) for (k, c, g), v in comp.items()]))
        else:
            html('<div class="sw-sub">No animal detections at this gate.</div>')
        html('<div class="sw-label" style="margin:16px 0 6px 0">Encounters by hour</div>')
        html(charts.columns([(f"{h:02d}", int((e["hour"] == h).sum())) for h in range(24)], 100))
    with b:
        caps = o[o["bbox_x"].notna()].sort_values("conf", ascending=False).drop_duplicates("image_id").head(4)
        html('<div class="sw-label" style="margin-bottom:6px">Highest-confidence captures</div>')
        if caps.empty:
            html('<div class="sw-sub">No framed captures yet.</div>')
        cc = st.columns(2, gap="small")
        for i, c in enumerate(caps.itertuples()):
            with cc[i % 2]:
                media_card(c.file_path, (c.bbox_x, c.bbox_y, c.bbox_w, c.bbox_h), c.common, c.sci, c.conf, c.location_id,
                           f"{c.ts:%Y-%m-%d %H:%M}" if str(c.ts) != "NaT" else "")

footer()
