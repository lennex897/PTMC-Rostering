from pathlib import Path

import streamlit as st


APP_ROOT = Path(__file__).parent


st.set_page_config(
    page_title="Roster Generator",
    page_icon="📅",
    layout="wide",
)

st.title("Roster Generator")

st.write(
    """
    Generate monthly duty rosters using the scheduling roster,
    Rulebook, assumptions and monthly leave forecast.
    """
)

reference_path = APP_ROOT / "reference" / "Scheduling_Roster_2026.xlsx"
rulebook_path = APP_ROOT / "config" / "rulebook.md"
assumptions_path = APP_ROOT / "config" / "assumptions.md"

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Scheduling roster",
        "Available" if reference_path.exists() else "Missing",
    )

with col2:
    st.metric(
        "Rulebook",
        "Available" if rulebook_path.exists() else "Missing",
    )

with col3:
    st.metric(
        "Assumptions",
        "Available" if assumptions_path.exists() else "Missing",
    )

st.info(
    "Use the pages in the sidebar to edit settings and generate a roster."
)