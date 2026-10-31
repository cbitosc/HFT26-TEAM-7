"""
SmallWorld Wildlife Intelligence - Streamlit entry point.
Run from the project folder:   python -m streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from dashboard.components.theme import inject_theme

ASSETS = Path(__file__).resolve().parent / "assets"
PAGES = Path(__file__).resolve().parent / "pages"

st.set_page_config(page_title="SmallWorld · Wildlife Intelligence", page_icon=str(ASSETS / "mark.svg"),
                   layout="wide", initial_sidebar_state="collapsed")
inject_theme()
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "logo.svg"))

nav = st.navigation(
    [
        st.Page(str(PAGES / "4_timeline.py"), title="Activity Timeline", url_path="timeline", default=True),
        st.Page(str(PAGES / "5_gallery.py"), title="Sightings", url_path="sightings"),
        st.Page(str(PAGES / "6_review.py"), title="Review Queue", url_path="review"),
        st.Page(str(PAGES / "7_ai_summary.py"), title="AI Summary", url_path="ai-summary"),
        st.Page(str(PAGES / "3_locations.py"), title="Site Activity", url_path="site-activity"),
    ],
    position="sidebar",
)
nav.run()
