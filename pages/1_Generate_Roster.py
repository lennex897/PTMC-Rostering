from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import openpyxl
import streamlit as st

from roster_engine.documents import get_current_document
from roster_engine.generator import (
    GenerationRequest,
    generate_roster,
)


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

# Define this before the upload block so it always exists.
selected_sheet = None

if uploaded_leave is not None:
    try:
        workbook = openpyxl.load_workbook(
            uploaded_leave,
            read_only=True,
            data_only=True,
        )

        sheet_names = workbook.sheetnames

        # Example expected value:
        # July 2026 becomes "Jul 26".
        expected_sheet = selected_month.strftime("%b %y")

        # Keep only worksheet names that look like month sheets.
        # strip() also handles accidental leading/trailing spaces.
        valid_month_names = {
            date(2000, month_number, 1).strftime("%b")
            for month_number in range(1, 13)
        }

        valid_sheets = []

        for sheet_name in sheet_names:
            cleaned_name = sheet_name.strip()
            parts = cleaned_name.split()

            if (
                len(parts) == 2
                and parts[0] in valid_month_names
                and parts[1].isdigit()
                and len(parts[1]) == 2
            ):
                valid_sheets.append(sheet_name)

        if not valid_sheets:
            st.error(
                "No monthly worksheets were found. "
                "Expected worksheet names such as 'Jul 26' or 'Aug 26'."
            )
        else:
            # Match using stripped names while preserving the workbook's
            # original worksheet name.
            matching_sheet = next(
                (
                    sheet_name
                    for sheet_name in valid_sheets
                    if sheet_name.strip() == expected_sheet
                ),
                None,
            )

            default_index = (
                valid_sheets.index(matching_sheet)
                if matching_sheet is not None
                else 0
            )

            selected_sheet = st.selectbox(
                "Select the worksheet containing the month",
                valid_sheets,
                index=default_index,
            )

            if selected_sheet.strip() == expected_sheet:
                st.success(
                    "Workbook loaded successfully. "
                    f"Selected worksheet: {selected_sheet}"
                )
            else:
                st.warning(
                    f"The worksheet '{expected_sheet}' was not found. "
                    f"Using '{selected_sheet}' instead."
                )

        with st.expander("Available worksheets"):
            st.write(sheet_names)

        workbook.close()

    except Exception as exc:
        st.error(f"Unable to read workbook: {exc}")

else:
    st.info("Upload a leave workbook to continue.")

generate_disabled = (
    uploaded_leave is None
    or selected_sheet is None
)

if st.button(
    "Generate roster",
    type="primary",
    disabled=generate_disabled,
):
    if uploaded_leave is None:
        st.error("Upload a leave workbook first.")
        st.stop()

    if selected_sheet is None:
        st.error("Select a leave worksheet.")
        st.stop()

    try:
        rulebook = get_current_document("rulebook")
        assumptions = get_current_document("assumptions")
    except Exception as exc:
        st.error(f"Unable to load documents from Supabase: {exc}")
        st.stop()

    with TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory)

        leave_path = temp_path / "leave_forecast.xlsx"
        leave_path.write_bytes(uploaded_leave.getvalue())

        output_path = (
            temp_path
            / f"{selected_month:%B_%Y}_Roster.xlsx"
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

        if result.statistics:
            st.subheader("Input validation")
            st.json(result.statistics)

        for error in result.errors:
            st.error(error)

        for warning in result.warnings:
            st.warning(warning)

        if result.success:
            st.success("Roster generated successfully.")