"""
ui.py - shared SmallWorld building blocks used by every page.
"""

import base64
import html as _html
from io import BytesIO
from pathlib import Path

import streamlit as st

from config import find_image
from dashboard.components.charts import AMBER, TEAL, SAGE

esc = _html.escape


def html(s: str):
    """Render raw HTML. Lines are de-indented so Markdown never turns them into code blocks."""
    st.markdown(" ".join(line.strip() for line in s.splitlines() if line.strip()), unsafe_allow_html=True)


def chip(text, kind="primary", dot=None):
    d = f'<span class="sw-dot" style="background:{dot}"></span>' if dot else ""
    return f'<span class="sw-chip {kind}">{d}{esc(str(text))}</span>'


def sci(name, size=13):
    return f'<span class="sw-sci" style="font-size:{size}px">{esc(name)}</span>' if name else ""


def page_header(title, lead, tiles=()):
    """Editorial page title with a ribbon of metric tiles on the right (tiles = [(label, value, suffix, color)])."""
    t = "".join(
        f'<div class="sw-tile"><div class="sw-label">{esc(lbl)}</div><div style="display:flex;align-items:baseline;gap:6px;margin-top:2px">'
        f'<span class="v" style="color:{col or "var(--on)"}">{val}</span><span class="sw-sub" style="color:var(--secondary)">{suf}</span></div></div>'
        for lbl, val, suf, col in tiles)
    html(f"""
    <div style="display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:16px;margin:4px 0 22px 0">
      <div style="flex:1 1 520px"><h1 class="sw-h1">{esc(title)}</h1><p class="sw-lead">{lead}</p></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">{t}</div>
    </div>""")


def section(title, sub="", right=""):
    html(f"""<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:14px">
      <div><div class="sw-h2">{title}</div>{f'<div class="sw-sub" style="margin-top:2px">{sub}</div>' if sub else ''}</div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">{right}</div></div>""")


def empty_state(title, body, command=None):
    cmd = f'<div style="margin-top:12px"><span class="sw-code" style="font-size:12px;padding:4px 10px">{esc(command)}</span></div>' if command else ""
    html(f"""<div class="sw-inset" style="padding:28px;text-align:center">
      <div class="sw-h2" style="font-size:16px">{esc(title)}</div>
      <div class="sw-body" style="color:var(--on-var);margin-top:4px">{body}</div>{cmd}</div>""")


def confidence_gate(default=50, help_text="Detections and predictions below this score are excluded from every figure on this page."):
    """Shared confidence slider. Its value persists across pages."""
    if "min_conf" not in st.session_state:
        st.session_state["min_conf"] = default
    def _sync():
        st.session_state["min_conf"] = st.session_state["_min_conf_widget"]
    st.session_state["_min_conf_widget"] = st.session_state["min_conf"]
    st.slider("Minimum AI prediction confidence", 20, 95, step=5, key="_min_conf_widget",
              on_change=_sync, format="%d%%", help=help_text)
    return st.session_state["min_conf"] / 100


def filter_bar_specs(stats, tn, n_in, n_out, min_conf, ground_truth_mode):
    """The methodology strip under the confidence slider."""
    src = ('<span style="color:var(--tertiary)">Species labels from Caltech ground truth until SpeciesNet runs</span>'
           if ground_truth_mode else '<span style="color:var(--secondary)">Species labels from SpeciesNet + scientist review</span>')
    pct = n_out / (n_in + n_out) * 100 if (n_in + n_out) else 0
    html(f"""
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin:2px 0 10px 0">
      <div class="sw-pill"><span class="sw-dot" style="background:var(--secondary)"></span><div>
        <div class="sw-label">Independence separation</div><div class="sw-mono" style="font-size:11px">30 minutes (same species + site)</div></div></div>
      <div class="sw-pill"><span class="sw-dot" style="background:var(--tertiary)"></span><div>
        <div class="sw-label">Active effort baseline</div><div class="sw-mono" style="font-size:11px">{tn:,} trap-nights · {stats} stations</div></div></div>
    </div>
    <div class="sw-inset" style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;padding:8px 14px">
      <span class="sw-mono" style="font-size:11px;color:var(--on)">Sample coverage: <b>{n_in:,} animal detections included</b>
        <span style="color:var(--outline);margin:0 6px">|</span><span style="color:var(--tertiary)">{n_out:,} below {min_conf:.0%} excluded</span> ({pct:.1f}%)</span>
      <span class="sw-mono" style="font-size:11px">{src}</span>
    </div>""")


def _thumb_b64(path, max_w=720):
    from PIL import Image
    try:
        im = Image.open(path).convert("RGB")
        im.thumbnail((max_w, max_w))
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=82)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


@st.cache_data(show_spinner=False, max_entries=400)
def thumb(file_path: str, max_w: int = 720):
    p = find_image(file_path) if file_path else None
    return _thumb_b64(p, max_w) if p else None


def media_card(file_path, bbox, label_common, label_sci, conf, loc, when, footer_right="", height=None):
    """Camera-trap frame with the amber AI bounding box + reticle tag (DESIGN.md: Bounding Boxes & AI Overlays)."""
    b64 = thumb(file_path)
    style = f' style="aspect-ratio:auto;height:{height}px"' if height else ""
    if b64:
        img = f'<img src="data:image/jpeg;base64,{b64}"/>'
    else:
        img = ('<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">'
               '<span class="sw-sub">image file not found on disk</span></div>')
    box = ""
    if bbox and all(v is not None for v in bbox) and b64:
        x, y, w, h = bbox
        box = (f'<div class="sw-box" style="left:{x*100:.2f}%;top:{y*100:.2f}%;width:{w*100:.2f}%;height:{h*100:.2f}%">'
               f'<div class="sw-tag" style="left:-1px;top:0"><i>{esc(label_sci or label_common)}</i>· {conf:.1%} conf</div></div>')
    stamp = f'<div class="sw-stamp">loc_{esc(str(loc))} · {esc(when)}</div>'
    html(f"""<div><div class="sw-media"{style}>{img}<div class="vig"></div>{box}{stamp}</div>
      <div class="sw-meta"><span class="sw-body" style="font-size:13px">{esc(label_common)}</span>{footer_right}</div></div>""")


def footer():
    html("""<div class="sw-footer">
      <div><span style="font-family:'Newsreader',serif;font-size:22px;color:var(--on)">SmallWorld</span>
        <span class="sw-label" style="margin-left:8px">AI biotelemetry &amp; ecological observatory</span>
        <div class="sw-body" style="color:var(--on-var);margin-top:6px;max-width:640px">Pipeline orchestration: OpenCV Laplacian clarity filtering,
        MegaDetector v5 localisation, SpeciesNet taxonomic inference, and Featherless LLM ecological synthesis.</div></div>
      <div style="text-align:right"><div class="sw-label">Dataset provenance</div>
        <div class="sw-mono" style="color:var(--tertiary);margin-top:4px">Caltech Camera Traps (CCT-20)</div></div></div>""")


GROUP_DOT = {"carnivore": AMBER, "herbivore": TEAL, "avian": SAGE}
SOURCE_CHIP = {"Ground truth": ("Ground truth", "ghost"), "SpeciesNet": ("SpeciesNet", "primary"),
               "Verified": ("Verified", "secondary"), "Unidentified": ("Unidentified", "error")}
