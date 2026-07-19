import streamlit as st

from roster_engine.documents import (
    get_current_document,
    save_document,
)


st.set_page_config(
    page_title="Rulebook",
    page_icon="📘",
    layout="wide",
)

st.title("Rulebook")

current = get_current_document("rulebook")

edited = st.text_area(
    f"Rulebook Markdown — Version {current.version}",
    value=current.content,
    height=650,
)

preview, history = st.tabs(["Preview", "Save"])

with preview:
    st.markdown(edited)

with history:
    st.warning(
        "Saving creates a new version and retains the previous version."
    )

    if st.button("Save new Rulebook version", type="primary"):
        if not edited.strip():
            st.error("The Rulebook cannot be empty.")
        elif edited == current.content:
            st.info("No changes were detected.")
        else:
            saved = save_document(
                document_type="rulebook",
                content=edited,
            )

            st.success(
                f"Rulebook version {saved.version} saved."
            )

            st.rerun()