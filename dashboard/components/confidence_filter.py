"""confidence_filter.py - shared confidence slider + unverified toggle."""
import streamlit as st


def render(key_prefix: str = ""):
    min_conf = st.slider("Minimum confidence", 0.0, 1.0, 0.5, 0.05, key=f"{key_prefix}_conf")
    unverified = st.checkbox("Include unverified predictions", value=True, key=f"{key_prefix}_unv")
    return min_conf, unverified
