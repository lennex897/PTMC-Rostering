from datetime import date
from pathlib import Path

import openpyxl
import streamlit as st


APP_ROOT = Path(__file__).resolve().parents[1]


st.set_page_config(
    page_title="Generate Roster",
    page_icon="⚙️",
    layout="wide",
)

st.title("Generate Roster")

selected_month = st.date_input(
    "Roster month",
    value=date.today().replace(day=1),
)

uploaded_leave = st.file_uploader(
    "Upload Leave / Off / Important Dates Forecast",
    type=["xlsx"],
    help="Upload the latest monthly availability workbook.",
)

if uploaded_leave is not None:
    try:
        workbook = openpyxl.load_workbook(
            uploaded_leave,
            read_only=True,
            data_only=True,
        )

        sheet_names = workbook.sheetnames

        selected_sheet = st.selectbox(
            "Select the worksheet containing the month",
            options=sheet_names,
        )

        st.success(
            f"Workbook loaded successfully. "
            f"Selected worksheet: {selected_sheet}"
        )

        st.write("Available worksheets:", sheet_names)

    except Exception as exc:
        st.error(f"Unable to read workbook: {exc}")
else:
    st.info("Upload a leave workbook to continue.")

generate_disabled = uploaded_leave is None

if st.button(
    "Validate inputs",
    type="primary",
    disabled=generate_disabled,
):
    st.warning(
        "The validation engine will be connected in the next phase."
    )