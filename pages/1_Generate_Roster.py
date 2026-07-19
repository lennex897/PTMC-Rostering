from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from roster_engine.documents import get_current_document
from roster_engine.generator import (
    GenerationRequest,
    generate_roster,
)

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
    "Generate roster",
    type="primary",
    disabled=generate_disabled,
):
    if uploaded_leave is None:
        st.error("Upload a leave workbook first.")
        st.stop()

    if not selected_sheet:
        st.error("Select a leave worksheet.")
        st.stop()

    rulebook = get_current_document("rulebook")
    assumptions = get_current_document("assumptions")

    with TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory)

        leave_path = temp_path / "leave_forecast.xlsx"
        leave_path.write_bytes(uploaded_leave.getvalue())

        output_path = temp_path / (
            f"{selected_month:%B_%Y}_Roster.xlsx"
        )

        scheduling_roster_path = (
            APP_ROOT
            / "reference"
            / "Scheduling_Roster_2026.xlsx"
        )

        request = GenerationRequest(
            roster_month=selected_month.replace(day=1),
            scheduling_roster_path=scheduling_roster_path,
            leave_workbook_path=leave_path,
            leave_sheet=selected_sheet,
            rulebook_text=rulebook.content,
            assumptions_text=assumptions.content,
            output_path=output_path,
        )

        result = generate_roster(request)

        if result.errors:
            for error in result.errors:
                st.error(error)

        for warning in result.warnings:
            st.warning(warning)

        if result.success:
            st.success("Roster generated successfully.")