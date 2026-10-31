"""AI Summary - Featherless uncertainty-aware ecological narrative with feedback loop."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
import os
from datetime import datetime

import streamlit as st

import config  # noqa: F401  (loads .env)
from dashboard.components import data_queries as q
from dashboard.components.ui import (html, chip, esc, page_header, section, empty_state, confidence_gate, footer)

try:
    from pipeline.feedback import feedback_context_for_llm, compute_accuracy_drift, export_training_jsonl
    _feedback_available = True
except Exception:
    _feedback_available = False

if not q.db_exists():
    empty_state("Observatory offline", "No database found.", "python run_pipeline.py --limit 100"); st.stop()

try:
    from llm.summariser import summarise, MODEL
except Exception as e:          # openai not installed etc.
    summarise, MODEL = None, "mistralai/Mistral-7B-Instruct-v0.2"
    import_error = str(e)
else:
    import_error = None

media, det, n_cls = q.load()
has_key = bool(os.getenv("FEATHERLESS_API_KEY"))
page_header("AI Summary",
            "A natural-language field report written by an LLM from the survey statistics below. The prompt instructs "
            "the model to state unverified counts, low-confidence species and data limitations instead of overstating certainty.",
            tiles=[("Model", MODEL.split("/")[-1].replace("-Instruct", ""), "", None),
                   ("API key", "Ready" if has_key else "Missing", ".env", "var(--secondary)" if has_key else "var(--error)")])

with st.container(key="panel_gate_ai"):
    min_conf = confidence_gate()
snap = q.llm_snapshot(media, det, n_cls, min_conf)
html('<div style="height:16px"></div>')

left, right = st.columns([1.6, 1], gap="medium")
with right:
    with st.container(key="panel_snapshot"):
        section("Data snapshot sent to the model", "Recomputed live at the current confidence gate")
        s = snap["survey"]
        rows = [("Images", s["images"]), ("Stations", s["stations"]), ("Trap-nights", s["trap_nights"]),
                ("Independent encounters", snap["independent_encounters"]),
                ("Nocturnal share", f"{snap['diel_activity_pct']['nocturnal']}%"),
                ("Unverified detections", snap["unverified_detections"]),
                ("SpeciesNet classifications", snap["species_classified_by_speciesnet"]),
                ("Label provenance", ", ".join(f"{k}: {v}" for k, v in snap["label_provenance"].items()) or "—")]
        html("".join(f'<div style="display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid '
                     f'rgba(120,148,119,.08)"><span class="sw-label">{k}</span><span class="sw-mono" style="text-align:right">{esc(str(v))}</span></div>'
                     for k, v in rows))
        with st.expander("Full JSON payload"):
            st.json(snap)

with left:
    with st.container(key="panel_story"):
        section("Field report", f"Gate ≥ {min_conf:.0%} · 30-min independence window",
                chip("Featherless API", "primary") + chip("Uncertainty-aware", "tertiary"))
        if import_error:
            st.error(f"LLM client unavailable ({import_error}). Run: pip install openai")
        elif not has_key:
            st.warning("FEATHERLESS_API_KEY is missing from your .env file, so the report can't be generated yet.")
        go = st.button("Generate field report", type="primary", disabled=bool(import_error) or not has_key)
        if go:
            try:
                text = st.write_stream(summarise(snap))
                st.session_state["ai_report"] = {"text": text, "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "gate": min_conf}
            except Exception as e:
                st.error(f"Featherless call failed: {e}")
        elif st.session_state.get("ai_report"):
            r = st.session_state["ai_report"]
            html(f'<div class="sw-sub" style="margin-bottom:8px">Generated {r["at"]} at gate ≥ {r["gate"]:.0%}</div>')
            st.markdown(r["text"])
        else:
            empty_state("No report yet", "Press Generate to stream a three-paragraph summary: activity & dominant species, "
                        "temporal and spatial patterns, and data limitations.")
        if st.session_state.get("ai_report"):
            r = st.session_state["ai_report"]
            md = (f"# SmallWorld field report\n\nGenerated {r['at']} · model {MODEL} · confidence gate ≥ {r['gate']:.0%}\n\n"
                  f"{r['text']}\n\n## Data snapshot\n\n```json\n{json.dumps(snap, indent=2, default=str)}\n```\n")
            st.download_button("Download report (.md)", md, file_name="smallworld_field_report.md", mime="text/markdown")

# ── Model Learning / Feedback Loop ────────────────────────────────
html('<div style="height:32px"></div>')
section("Model Learning", "Human-in-the-loop feedback drives continuous improvement",
        chip("Active Learning", "tertiary") + chip("Feedback Loop", "secondary"))

if not _feedback_available:
    st.info("Feedback module not available. Ensure `pipeline/feedback.py` is present.")
else:
    fb_stats = q.feedback_stats()
    if fb_stats["total_decisions"] == 0:
        empty_state("No feedback yet",
                    "Review predictions in the Review Queue page. Every accept / relabel / reject decision "
                    "trains the AI to produce better reports and adjust confidence thresholds.")
    else:
        # Feedback summary tiles
        fb_cols = st.columns(4)
        with fb_cols[0]:
            html(f'<div style="text-align:center;padding:16px;background:rgba(166,207,197,.06);'
                 f'border-radius:12px;border:1px solid rgba(166,207,197,.12)">'
                 f'<div class="sw-mono" style="font-size:28px;color:var(--primary)">{fb_stats["total_decisions"]}</div>'
                 f'<div class="sw-sub">Total Decisions</div></div>')
        with fb_cols[1]:
            acc_pct = f"{fb_stats['accuracy']:.0%}" if fb_stats["accuracy"] is not None else "—"
            acc_color = "var(--secondary)" if fb_stats["accuracy"] and fb_stats["accuracy"] >= 0.7 else "var(--tertiary)"
            html(f'<div style="text-align:center;padding:16px;background:rgba(166,207,197,.06);'
                 f'border-radius:12px;border:1px solid rgba(166,207,197,.12)">'
                 f'<div class="sw-mono" style="font-size:28px;color:{acc_color}">{acc_pct}</div>'
                 f'<div class="sw-sub">Model Accuracy</div></div>')
        with fb_cols[2]:
            html(f'<div style="text-align:center;padding:16px;background:rgba(166,207,197,.06);'
                 f'border-radius:12px;border:1px solid rgba(166,207,197,.12)">'
                 f'<div class="sw-mono" style="font-size:28px;color:var(--secondary)">{fb_stats.get("accepted", 0)}</div>'
                 f'<div class="sw-sub">Accepted</div></div>')
        with fb_cols[3]:
            html(f'<div style="text-align:center;padding:16px;background:rgba(166,207,197,.06);'
                 f'border-radius:12px;border:1px solid rgba(166,207,197,.12)">'
                 f'<div class="sw-mono" style="font-size:28px;color:var(--tertiary)">{fb_stats.get("corrected", 0)}</div>'
                 f'<div class="sw-sub">Corrected</div></div>')

        html('<div style="height:16px"></div>')

        fb_left, fb_right = st.columns([1, 1], gap="medium")

        with fb_left:
            with st.container(key="panel_corrections"):
                section("Common Corrections", "Species the model frequently misidentifies")
                if fb_stats["corrections"]:
                    for corr in fb_stats["corrections"][:5]:
                        html(f'<div style="display:flex;justify-content:space-between;gap:12px;padding:8px 0;'
                             f'border-bottom:1px solid rgba(120,148,119,.08)">'
                             f'<span class="sw-body">{esc(str(corr["predicted"]))} → {esc(str(corr["corrected_to"]))}</span>'
                             f'<span class="sw-mono" style="color:var(--tertiary)">{corr["count"]}×</span></div>')
                else:
                    html('<div class="sw-sub">No corrections recorded yet.</div>')

        with fb_right:
            with st.container(key="panel_species_acc"):
                section("Per-Species Accuracy", "How well the AI identifies each species")
                if fb_stats["by_species"]:
                    for sp in fb_stats["by_species"][:8]:
                        pct = f"{sp['accuracy']:.0%}"
                        bar_w = max(5, sp["accuracy"] * 100)
                        bar_color = "var(--secondary)" if sp["accuracy"] >= 0.7 else "var(--tertiary)" if sp["accuracy"] >= 0.4 else "var(--error)"
                        html(f'<div style="padding:6px 0;border-bottom:1px solid rgba(120,148,119,.08)">'
                             f'<div style="display:flex;justify-content:space-between;margin-bottom:4px">'
                             f'<span class="sw-label">{esc(str(sp["species"]))}</span>'
                             f'<span class="sw-mono">{pct} ({sp["correct"]}/{sp["total"]})</span></div>'
                             f'<div style="height:4px;background:rgba(120,148,119,.1);border-radius:2px">'
                             f'<div style="height:4px;width:{bar_w}%;background:{bar_color};border-radius:2px"></div>'
                             f'</div></div>')
                else:
                    html('<div class="sw-sub">Review more predictions to see per-species accuracy.</div>')

        # Feedback-aware LLM context preview
        html('<div style="height:16px"></div>')
        fb_context = feedback_context_for_llm()
        if fb_context:
            with st.expander("Feedback context injected into AI prompt"):
                st.json(fb_context)

        # Export training data
        html('<div style="height:12px"></div>')
        exp_cols = st.columns([1, 2])
        with exp_cols[0]:
            if st.button("Export training data (JSONL)", type="secondary"):
                try:
                    path = export_training_jsonl()
                    st.success(f"Exported to `{path}`")
                except Exception as e:
                    st.error(f"Export failed: {e}")

footer()
