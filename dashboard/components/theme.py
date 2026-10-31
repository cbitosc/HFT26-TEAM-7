"""
theme.py - SmallWorld "Field BioTelemetry & Observatory" design system for Streamlit.
"""

import streamlit as st

COLORS = {
    "surface": "#0b1513",
    "surface_container_lowest": "#06100e",
    "surface_container_low": "#131d1b",
    "surface_container": "#17221f",
    "surface_container_high": "#222c2a",
    "surface_container_highest": "#2d3734",
    "on_surface": "#dae5e1",
    "on_surface_variant": "#c0c8c5",
    "outline": "#8b928f",
    "outline_variant": "#414846",
    "primary": "#a6cfc5",
    "primary_container": "#153c35",
    "on_primary_container": "#7fa69d",
    "secondary": "#b1ceae",
    "secondary_container": "#334d34",
    "tertiary": "#fbbb5b",
    "tertiary_container": "#4c3000",
    "error": "#ffb4ab",
    "bone": "#F4F5EF",
}

FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700"
    "&family=Geist:wght@300..700"
    "&family=JetBrains+Mono:wght@400..700"
    "&display=swap"
)

_CSS = """
@import url('__FONTS__');

:root {
  --surface:#0b1513; --lowest:#06100e; --low:#131d1b; --cont:#17221f; --high:#222c2a; --highest:#2d3734;
  --on:#dae5e1; --on-var:#c0c8c5; --outline:#8b928f; --outline-var:#414846;
  --primary:#a6cfc5; --primary-c:#153c35; --on-primary-c:#7fa69d;
  --secondary:#b1ceae; --secondary-c:#334d34; --tertiary:#fbbb5b; --tertiary-c:#4c3000;
  --error:#ffb4ab; --bone:#F4F5EF; --hair:rgba(120,148,119,0.15);
}

/* ── Canvas ─────────────────────────────────────────── */
.stApp { background: var(--surface) !important; color: var(--on); }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stMarkdown, [data-testid="stWidgetLabel"] { font-family: 'Geist', sans-serif !important; }
.block-container { max-width: 1720px !important; padding: 5.2rem 2rem 2rem 2rem !important; }
.stApp h1, .stApp h2, .stApp h3 { font-family: 'Newsreader', serif !important; color: var(--on) !important;
  font-weight: 500 !important; letter-spacing: -0.01em; }
[data-testid="stHeaderActionElements"], .stApp a.anchor-link { display: none !important; }

/* ── Header: ☰ hamburger + SmallWorld logo ─────────── */
header[data-testid="stHeader"] { background: rgba(11,21,19,0.92) !important; backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--hair); height: 3.75rem; }
[data-testid="stAppDeployButton"], [data-testid="stDecoration"], #MainMenu { display: none !important; }
[data-testid="stHeaderLogo"], [data-testid="stSidebarLogo"] { height: 2.4rem !important; max-width: 15rem !important; }
/* put the menu button to the LEFT of the logo (header when closed, sidebar header when open) */
[data-testid="stToolbar"] div:has(> div [data-testid="stHeaderLogo"]):has(> div [data-testid="stExpandSidebarButton"]) {
  display: flex !important; flex-direction: row-reverse !important; justify-content: flex-end !important;
  align-items: center !important; gap: 12px !important; }
[data-testid="stSidebarHeader"] { display: flex !important; flex-direction: row-reverse !important;
  justify-content: flex-end !important; align-items: center !important; gap: 12px !important;
  padding: 0.9rem 1rem 0.9rem 19px !important; height: 3.75rem; border-bottom: 1px solid var(--hair); margin-bottom: 14px; }
/* swap the » / « chevrons for a hamburger icon */
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] button {
  width: 36px !important; height: 36px !important; border-radius: 4px !important;
  border: 1px solid rgba(120,148,119,0.25) !important; background: rgba(21,60,53,0.35) !important;
  display: flex !important; align-items: center !important; justify-content: center !important; }
[data-testid="stExpandSidebarButton"]:hover, [data-testid="stSidebarCollapseButton"] button:hover {
  border-color: var(--tertiary) !important; background: var(--primary-c) !important; }
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"] { font-size: 0 !important; width: 18px; height: 18px;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'%3E%3Cpath d='M2 4.5h14M2 9h14M2 13.5h14' stroke='%23dae5e1' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E") center/18px no-repeat; }
[data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; opacity: 1 !important; }
/* identical ☰ + logo position whether the drawer is closed or open */
[data-testid="stToolbar"] div:has(> div > [data-testid="stHeaderLogo"]) { margin-left: 0 !important; }
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] button { margin: 0 !important; }
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-left: 0 !important; padding-right: 0 !important; }
[data-testid="stSidebarHeader"] { width: 100% !important; box-sizing: border-box !important; padding-left: 7px !important; }

/* ── Side navigation drawer ─────────────────────────── */
section[data-testid="stSidebar"] { background: var(--low) !important; border-right: 1px solid var(--hair) !important;
  box-shadow: 8px 0 40px rgba(0,0,0,0.35); }
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { background: transparent !important; }
[data-testid="stSidebarNav"] { padding: 0 1rem !important; }
[data-testid="stSidebarNavItems"] { gap: 2px; padding-top: 4px !important; }
[data-testid="stSidebarNavLink"] { border-radius: 4px !important; padding: 4px 14px !important; margin: 1px 0 !important; min-height: 2.5rem !important;
  border-left: 2px solid transparent !important; transition: background .15s; }
[data-testid="stSidebarNavLink"] p, [data-testid="stSidebarNavLink"] span { font-family: 'Newsreader', serif !important;
  font-size: 17px !important; color: var(--on-var) !important; }
[data-testid="stSidebarNavLink"]:hover { background: var(--high) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: var(--primary-c) !important;
  border-left-color: var(--tertiary) !important; box-shadow: 0 0 24px -8px rgba(166,207,197,0.35); }
[data-testid="stSidebarNavLink"][aria-current="page"] p { color: var(--bone) !important; }
[data-testid="stSidebarNavSeparator"] { display: none !important; }
footer { display: none !important; }

/* ── Widgets ───────────────────────────────────────── */
[data-testid="stWidgetLabel"] p { font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important;
  letter-spacing: .06em; text-transform: uppercase; color: var(--outline) !important; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  background: var(--primary-c) !important; color: var(--bone) !important;
  border: 1px solid rgba(120,148,119,0.4) !important; border-radius: 4px !important;
  font-family: 'JetBrains Mono', monospace !important; font-size: 12px !important; letter-spacing: .04em; }
.stButton > button:hover { background: #1B4A41 !important; border-color: var(--tertiary) !important; }
.stButton > button[kind="primary"] { background: #E7A94B !important; color: #111B19 !important; font-weight: 600 !important;
  border-color: #E7A94B !important; }
.stButton > button[kind="primary"]:hover { box-shadow: 0 0 24px -4px rgba(231,169,75,0.45); }
[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input, .stTextArea textarea {
  background: rgba(17,27,25,0.75) !important; border: 1px solid rgba(120,148,119,0.25) !important;
  color: var(--on) !important; border-radius: 4px !important; }
[data-baseweb="select"] > div:focus-within { border-color: var(--tertiary) !important; }
[data-baseweb="popover"] ul, [data-baseweb="menu"] { background: var(--high) !important; }
[data-testid="stSlider"] [role="slider"] { background: var(--tertiary) !important; border: 2px solid #0b1513 !important;
  box-shadow: 0 0 0 4px rgba(231,169,75,0.18) !important; }
[data-testid="stSliderThumbValue"], [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {
  font-family: 'JetBrains Mono', monospace !important; color: var(--tertiary) !important; font-size: 11px !important; }
[data-testid="stExpander"] details { background: var(--low) !important; border: 1px solid var(--hair) !important; border-radius: 6px !important; }
[data-testid="stExpander"] summary p { font-family: 'Geist', sans-serif !important; color: var(--on) !important; }
[data-testid="stRadio"] label p, [data-testid="stCheckbox"] label p { color: var(--on-var) !important; font-size: 13px !important;
  text-transform: none !important; font-family: 'Geist', sans-serif !important; letter-spacing: 0 !important; }
.stAlert { border-radius: 4px !important; }
[data-testid="stImage"] img { border-radius: 4px; }

/* ── Bordered containers become instrument panels ── */
[class*="st-key-panel"] { background: var(--low); border-radius: 8px;
  padding: 20px 22px; box-shadow: 0 8px 30px rgba(0,0,0,0.25); }

/* ── Typography helpers ────────────────────────────── */
.sw-h1 { font-family:'Newsreader',serif; font-size:34px; line-height:42px; font-weight:400; color:var(--on);
  letter-spacing:-0.015em; margin:0; }
.sw-h2 { font-family:'Geist',sans-serif; font-size:20px; line-height:28px; font-weight:600; color:var(--on); letter-spacing:-0.01em; }
.sw-lead { font-family:'Geist',sans-serif; font-size:16px; line-height:24px; color:var(--on-var); margin:6px 0 0 0; max-width:880px; }
.sw-label { font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:500; letter-spacing:.06em;
  text-transform:uppercase; color:var(--outline); }
.sw-mono { font-family:'JetBrains Mono',monospace; font-size:12px; font-weight:500; letter-spacing:.02em; }
.sw-sub { font-family:'JetBrains Mono',monospace; font-size:10.5px; color:var(--outline); letter-spacing:.02em; }
.sw-body { font-family:'Geist',sans-serif; font-size:14px; line-height:21px; color:var(--on); }
.sw-sci { font-family:'Newsreader',serif; font-style:italic; color:var(--primary); }
.sw-code { font-family:'JetBrains Mono',monospace; font-size:11px; background:var(--lowest); color:var(--primary);
  padding:1px 6px; border-radius:3px; }

/* ── Surfaces ───────────────────────────────────────── */
.sw-panel { background:var(--low); border-radius:8px; padding:20px 22px; box-shadow:0 8px 30px rgba(0,0,0,0.25);
  position:relative; overflow:hidden; margin-bottom:22px; }
.sw-glow::before { content:''; position:absolute; right:-80px; top:-80px; width:320px; height:320px; border-radius:50%;
  background:rgba(21,60,53,0.45); filter:blur(60px); pointer-events:none; }
.sw-card { background:var(--cont); border-radius:4px; padding:16px; transition:background .2s; height:100%; }
.sw-card:hover { background:var(--high); }
.sw-inset { background:var(--lowest); border-radius:4px; padding:10px 14px; }
.sw-tile { background:var(--low); border-radius:4px; padding:10px 16px; min-width:140px; box-shadow:0 4px 14px rgba(0,0,0,.25); }
.sw-tile .v { font-family:'Geist',sans-serif; font-size:22px; font-weight:600; color:var(--on); }
.sw-pill { display:inline-flex; align-items:center; gap:8px; background:var(--cont); border-radius:4px; padding:6px 10px; }

/* ── Chips ──────────────────────────────────────────── */
.sw-chip { display:inline-flex; align-items:center; gap:5px; padding:2px 8px; border-radius:4px;
  font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:500; letter-spacing:.06em; text-transform:uppercase;
  white-space:nowrap; }
.sw-chip.primary { background:var(--primary-c); color:var(--on-primary-c); }
.sw-chip.tertiary { background:var(--tertiary-c); color:var(--tertiary); }
.sw-chip.secondary { background:var(--highest); color:var(--secondary); }
.sw-chip.ghost { background:var(--lowest); color:var(--on-var); }
.sw-chip.error { background:#3b0d0a; color:var(--error); }
.sw-taxon { display:inline-block; background:rgba(21,60,53,0.6); border:1px solid #789477; border-radius:4px;
  padding:1px 8px; font-family:'Newsreader',serif; font-style:italic; color:var(--bone); font-size:14px; }
.sw-dot { display:inline-block; width:7px; height:7px; border-radius:50%; }

/* ── Tables ─────────────────────────────────────────── */
.sw-table-wrap { overflow-x:auto; border-radius:4px; }
.sw-table { width:100%; border-collapse:collapse; font-family:'Geist',sans-serif; font-size:14px; }
.sw-table thead th { background:var(--cont); padding:10px 14px; font-family:'JetBrains Mono',monospace; font-size:10px;
  font-weight:500; letter-spacing:.06em; text-transform:uppercase; color:var(--outline); text-align:left; vertical-align:bottom; }
.sw-table tbody tr { background:var(--lowest); }
.sw-table tbody tr:nth-child(even) { background:rgba(6,16,14,0.6); }
.sw-table tbody tr:hover { background:var(--high); }
.sw-table td { padding:12px 14px; color:var(--on); border-bottom:1px solid rgba(120,148,119,0.06); vertical-align:middle; }
.sw-table .r { text-align:right; } .sw-table .c { text-align:center; }
.sw-table .m { font-family:'JetBrains Mono',monospace; font-size:12px; }

/* ── Bars ───────────────────────────────────────────── */
.sw-bar { width:100%; height:6px; background:var(--highest); border-radius:3px; overflow:hidden; }
.sw-bar > div { height:100%; border-radius:3px; }

/* ── Media vignettes with AI overlay ───────────────── */
.sw-media { position:relative; border-radius:4px; overflow:hidden; background:var(--lowest); aspect-ratio:16/10; }
.sw-media img { width:100%; height:100%; object-fit:cover; display:block; filter:saturate(.9) contrast(1.05); }
.sw-media .vig { position:absolute; inset:0; background:radial-gradient(ellipse at center, transparent 55%, rgba(6,16,14,.75)); }
.sw-box { position:absolute; border:1px solid #E7A94B; box-shadow:0 0 24px -4px rgba(231,169,75,0.35); }
.sw-box::before, .sw-box::after { content:''; position:absolute; width:8px; height:8px; border-color:#E7A94B; border-style:solid; }
.sw-box::before { left:-3px; top:-3px; border-width:2px 0 0 2px; }
.sw-box::after { right:-3px; bottom:-3px; border-width:0 2px 2px 0; }
.sw-tag { position:absolute; background:rgba(17,27,25,0.9); border-radius:4px; padding:2px 7px; white-space:nowrap;
  font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--tertiary); transform:translateY(-120%); }
.sw-tag i { font-family:'Newsreader',serif; color:var(--bone); font-size:12px; margin-right:4px; }
.sw-stamp { position:absolute; right:8px; bottom:6px; font-family:'JetBrains Mono',monospace; font-size:10px;
  color:var(--on-var); background:rgba(6,16,14,.7); padding:1px 6px; border-radius:3px; }
.sw-meta { display:flex; justify-content:space-between; align-items:center; padding:8px 2px 2px 2px; gap:8px; }

/* ── Footer ─────────────────────────────────────────── */
.sw-footer { margin-top:40px; padding:26px 0 8px 0; border-top:1px solid var(--hair); display:flex;
  justify-content:space-between; gap:20px; flex-wrap:wrap; }

::-webkit-scrollbar { width:8px; height:8px; } ::-webkit-scrollbar-track { background:var(--lowest); }
::-webkit-scrollbar-thumb { background:var(--outline-var); border-radius:4px; }

@media (max-width: 768px) { .block-container { padding: 4.6rem 1rem 1rem 1rem !important; } .sw-h1 { font-size:26px; line-height:34px; } }
"""


def inject_theme():
    st.markdown(f"<style>{_CSS.replace('__FONTS__', FONT_IMPORT)}</style>", unsafe_allow_html=True)
