from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import openpyxl
import streamlit as st

from roster_engine.availability import load_availability
from roster_engine.documents import get_current_document
from roster_engine.exporter import export_schedule
from roster_engine.generator import (
    GenerationSettings,
    generate_roster,
)
from roster_engine.personnel import load_personnel

from roster_engine.validator import validate_schedule


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

        # Example:
        # August 2026 becomes "Aug 26".
        expected_sheet = selected_month.strftime("%b %y")

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
                "Expected worksheet names such as "
                "'Jul 26' or 'Aug 26'."
            )

        else:
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
        st.error(
            f"Unable to load documents from Supabase: {exc}"
        )
        st.stop()

    with TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory)

        leave_path = (
            temp_path
            / "leave_forecast.xlsx"
        )

        leave_path.write_bytes(
            uploaded_leave.getvalue()
        )

        output_path = (
            temp_path
            / f"{selected_month:%B_%Y}_Roster.xlsx"
        )

        scheduling_roster_path = (
            APP_ROOT
            / "reference"
            / "Scheduling Roster 2026.xlsx"
        )

        try:
            personnel = load_personnel(
                scheduling_roster_path
            )

            availability_entries = load_availability(
                workbook_path=leave_path,
                worksheet_name=selected_sheet,
            )

            result = generate_roster(
                personnel=personnel,
                availability_entries=availability_entries,
                settings=GenerationSettings(
                    year=selected_month.year,
                    month=selected_month.month,
                ),
            )

            validation_report = validate_schedule(
                schedule=result.schedule,
                personnel=personnel,
                availability_entries=availability_entries,
                requirements=result.requirements,
                year=selected_month.year,
                month=selected_month.month,
                maximum_weekly_overnights=3,
            )

            if not validation_report.is_valid:
                issue_lines = [
                    issue.message
                    for issue in validation_report.errors
                ]

                raise ValueError(
                    "Generated roster failed validation:\n"
                    + "\n".join(issue_lines)
                )

            export_schedule(
                template_path=scheduling_roster_path,
                output_path=output_path,
                schedule=result.schedule,
                year=selected_month.year,
                month=selected_month.month,
            )

        except Exception as exc:
            st.error(
                f"Roster generation failed: {exc}"
            )
            st.exception(exc)
            st.stop()

        report = result.report

        st.success("Roster scheduling completed.")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Personnel",
            report.personnel_count,
        )

        col2.metric(
            "Availability blocks",
            report.availability_entry_count,
        )

        col3.metric(
            "Assignments generated",
            report.generated_assignment_count,
        )

        col4.metric(
            "Unfilled duties",
            report.unfilled_requirement_count,
        )

        completion_rate = min(
            max(report.completion_rate, 0.0),
            1.0,
        )

        st.progress(completion_rate)

        st.caption(
            f"Completion rate: "
            f"{report.completion_rate:.1%}"
        )

        for warning in report.warnings:
            st.warning(warning)

        if result.unfilled_requirements:
            st.subheader("Unfilled requirements")

            unfilled_rows = [
                {
                    "Date": requirement.duty_date,
                    "Role": requirement.role,
                    "Centre": requirement.centre,
                    "Overnight": requirement.is_overnight,
                    "Points": requirement.points,
                }
                for requirement
                in result.unfilled_requirements
            ]

            st.dataframe(
                unfilled_rows,
                use_container_width=True,
                hide_index=True,
            )

        output_bytes = output_path.read_bytes()

        st.download_button(
            label="Download generated roster",
            data=output_bytes,
            file_name=output_path.name,
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            type="primary",
        )