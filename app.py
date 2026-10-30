"""Streamlit dashboard for the shared fake-data fixture."""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from analytics import analyze


DATA_PATH = Path("data/fake_master.csv")
STATUS_ORDER = ["Empty", "Identified", "Uncertain", "Needs Review"]
STATUS_COLORS = ["#94A3B8", "#16A34A", "#F59E0B", "#DC2626"]


@st.cache_data
def load_fixture(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=False)
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce", utc=True)
    frame["species_conf"] = pd.to_numeric(frame["species_conf"], errors="coerce")
    frame["blur_score"] = pd.to_numeric(frame["blur_score"], errors="coerce")
    return frame


def status_chart(frame: pd.DataFrame) -> alt.Chart:
    counts = (
        frame["status"].value_counts().reindex(STATUS_ORDER, fill_value=0)
        .rename_axis("status").reset_index(name="images")
    )
    return (
        alt.Chart(counts, title="Image status")
        .mark_bar(cornerRadiusEnd=5)
        .encode(
            x=alt.X("images:Q", title="Images"),
            y=alt.Y("status:N", sort=STATUS_ORDER, title=None),
            color=alt.Color("status:N", scale=alt.Scale(domain=STATUS_ORDER, range=STATUS_COLORS), legend=None),
            tooltip=[alt.Tooltip("status:N", title="Status"), alt.Tooltip("images:Q", title="Images")],
        )
        .properties(height=230)
    )


def quality_chart(frame: pd.DataFrame) -> alt.Chart:
    eligible = frame.dropna(subset=["blur_score"])
    return (
        alt.Chart(eligible, title="Blur-score distribution")
        .mark_bar()
        .encode(
            x=alt.X("blur_score:Q", bin=alt.Bin(maxbins=12), title="Laplacian variance"),
            y=alt.Y("count():Q", title="Images"),
            color=alt.Color("status:N", scale=alt.Scale(domain=STATUS_ORDER, range=STATUS_COLORS), title="Status"),
            tooltip=[alt.Tooltip("count():Q", title="Images")],
        )
        .properties(height=230)
    )


def hourly_chart(frame: pd.DataFrame) -> alt.Chart:
    activity = frame[frame["status"].isin(["Identified", "Uncertain"]) & frame["species"].ne("")].copy()
    activity["hour"] = activity["datetime"].dt.hour
    return (
        alt.Chart(activity, title="Detection activity by hour")
        .mark_line(point=True)
        .encode(
            x=alt.X("hour:O", title="Hour of day"),
            y=alt.Y("count():Q", title="Images"),
            color=alt.Color("species:N", title="Species"),
            tooltip=[alt.Tooltip("hour:O", title="Hour"), alt.Tooltip("species:N", title="Species"), alt.Tooltip("count():Q", title="Images")],
        )
        .properties(height=310)
    )


def location_chart(frame: pd.DataFrame) -> alt.Chart:
    sightings = frame[frame["status"].isin(["Identified", "Uncertain"]) & frame["species"].ne("")].copy()
    counts = sightings.groupby("location", as_index=False).size().rename(columns={"size": "detections"})
    return (
        alt.Chart(counts, title="Animal detections by camera location")
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("detections:Q", title="Detections"),
            y=alt.Y("location:N", sort="-x", title="Location"),
            tooltip=[alt.Tooltip("location:N", title="Location"), alt.Tooltip("detections:Q", title="Detections")],
        )
        .properties(height=310)
    )


st.set_page_config(page_title="SmallWorld | Camera Trap Explorer", page_icon="🦝", layout="wide")
st.title("SmallWorld Camera Trap Explorer")
st.caption("Dashboard preview using `data/fake_master.csv`. Model values are synthetic; image metadata comes from the selected Caltech Camera Traps subset.")

if not DATA_PATH.exists():
    st.error("Missing data/fake_master.csv. Run `python make_fake_data.py` to regenerate the fixture.")
    st.stop()

df = load_fixture(str(DATA_PATH))
encounters, stats = analyze(df)
tabs = st.tabs(["Overview", "Activity", "Species", "Review", "Insights"])

with tabs[0]:
    metrics = st.columns(5)
    values = {
        "Total images": len(df),
        "Empty": stats["status_counts"].get("Empty", 0),
        "Identified": stats["status_counts"].get("Identified", 0),
        "Uncertain": stats["status_counts"].get("Uncertain", 0),
        "Needs review": stats["status_counts"].get("Needs Review", 0),
    }
    for column, (label, value) in zip(metrics, values.items()):
        column.metric(label, value)

    left, right = st.columns(2)
    left.altair_chart(status_chart(df), use_container_width=True)
    right.altair_chart(quality_chart(df), use_container_width=True)

    st.info(f"{len(encounters)} identified encounters in this fixture. Uncertain predictions account for {stats['uncertain_share']:.1%} of all images and remain in the review queue.")

with tabs[1]:
    identified = df[df["status"].eq("Identified")]
    activity_metrics = st.columns(3)
    activity_metrics[0].metric("Identified encounters", len(encounters))
    activity_metrics[1].metric("Locations with detections", identified["location"].nunique())
    activity_metrics[2].metric("Active hours observed", identified["datetime"].dt.hour.dropna().nunique())

    left, right = st.columns(2)
    left.altair_chart(hourly_chart(df), use_container_width=True)
    right.altair_chart(location_chart(df), use_container_width=True)

    with st.expander("Encounter table"):
        st.dataframe(encounters.sort_values("start_time"), use_container_width=True, hide_index=True)

with tabs[2]:
    identified = df[df["status"].isin(["Identified", "Uncertain"]) & df["species"].ne("")]
    species_counts = identified["species"].value_counts().rename_axis("species").reset_index(name="images")
    st.altair_chart(
        alt.Chart(species_counts, title="Predicted species").mark_bar(cornerRadiusEnd=5).encode(
            x=alt.X("images:Q", title="Images"), y=alt.Y("species:N", sort="-x", title=None), tooltip=["species:N", "images:Q"],
        ),
        use_container_width=True,
    )
    st.dataframe(identified[["image_id", "species", "species_conf", "location", "status"]], use_container_width=True, hide_index=True)

with tabs[3]:
    review = df[df["status"].isin(["Needs Review", "Uncertain"])].copy()
    st.write(f"{len(review)} images need a human decision.")
    for _, row in review.iterrows():
        image_path = Path("data") / str(row["path"])
        with st.container(border=True):
            confidence = row["species_conf"] if pd.notna(row["species_conf"]) else "—"
            st.write(f"{row['image_id']} · {row['status']} · guess: {row['species'] or '—'} · confidence: {confidence}")
            if image_path.exists():
                st.image(str(image_path), width=320)

with tabs[4]:
    st.write("Insights will use aggregate statistics only after the pipeline produces real model outputs.")
    st.json({"image_count": stats["image_count"], "encounter_count": stats["encounter_count"], "uncertain_share": stats["uncertain_share"], "species_counts": stats["species_counts"]})
