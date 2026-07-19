from pathlib import Path

import streamlit as st


APP_ROOT = Path(__file__).resolve().parents[1]
RULEBOOK_PATH = APP_ROOT / "config" / "rulebook.md"


st.set_page_config(
    page_title="Rulebook",
    page_icon="📘",
    layout="wide",
)

st.title("Rulebook")

if not RULEBOOK_PATH.exists():
    st.error("The Rulebook file could not be found.")
    st.stop()

rulebook = RULEBOOK_PATH.read_text(encoding="utf-8")

edited_rulebook = st.text_area(
    "Rulebook Markdown",
    value=rulebook,
    height=650,
)

st.caption(
    "Saving to permanent storage will be enabled after Supabase is connected."
)

preview, raw = st.tabs(["Preview", "Raw Markdown"])

with preview:
    st.markdown(edited_rulebook)

with raw:
    st.code(edited_rulebook, language="markdown")