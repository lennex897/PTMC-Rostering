from pathlib import Path

import streamlit as st


APP_ROOT = Path(__file__).resolve().parents[1]
ASSUMPTIONS_PATH = APP_ROOT / "config" / "assumptions.md"


st.set_page_config(
    page_title="Assumptions",
    page_icon="📝",
    layout="wide",
)

st.title("Assumptions")

if not ASSUMPTIONS_PATH.exists():
    st.error("The assumptions file could not be found.")
    st.stop()

assumptions = ASSUMPTIONS_PATH.read_text(encoding="utf-8")

edited_assumptions = st.text_area(
    "Assumptions Markdown",
    value=assumptions,
    height=650,
)

st.caption(
    "Saving to permanent storage will be enabled after Supabase is connected."
)

preview, raw = st.tabs(["Preview", "Raw Markdown"])

with preview:
    st.markdown(edited_assumptions)

with raw:
    st.code(edited_assumptions, language="markdown")