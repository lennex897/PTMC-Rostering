from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from roster_engine.exporter import export_schedule
from roster_engine.generator import GenerationSettings
from roster_engine.planning_generation import generate_roster_from_planning
from roster_engine.planning_loader import load_planning_context
from roster_engine.database import get_supabase
from roster_engine.validator import validate_schedule


APP_ROOT = Path(__file__).resolve().parents[1]

ROSTER_TEMPLATE_PATH = (
    APP_ROOT
    / "reference"
    / "Scheduling Roster 2026.xlsx"
)


st.set_page_config(
    page_title="Generate Roster",
    page_icon="⚙️",
    layout="wide",
)

st.title("Generate Roster")
st.caption(
    "Generate the selected roster month from Supabase planning data, "
    "including availability, locked assignments, covers, FC reserves, "
    "and PTMC overnight interests."
)


@st.cache_data(ttl=30)
def load_roster_months() -> list[dict]:
    response = (
        get_supabase()
        .table("roster_months")
        .select("id,month_start,status")
        .order("month_start", desc=True)
        .execute()
    )

    rows: list[dict] = []

    for row in response.data or []:
        raw_month = row.get("month_start")

        if not raw_month:
            continue

        parsed = (
            raw_month
            if isinstance(raw_month, date)
            else date.fromisoformat(str(raw_month))
        )

        rows.append(
            {
                "id": str(row["id"]),
                "month_start": parsed.replace(day=1),
                "status": str(row.get("status") or "draft"),
            }
        )

    return rows


def assignment_key(assignment) -> tuple:
    return (
        assignment.duty_date,
        assignment.role,
        assignment.person_name,
    )


def render_preflight(planning) -> None:
    st.subheader("Planning inputs")

    cover_fit_count = sum(
        1
        for person in planning.personnel
        if person.is_cover_fit is True
    )

    locked_duties = sum(
        1
        for assignment in planning.manual_assignments
        if (
            assignment.is_locked
            and assignment.assignment_kind == "DUTY"
        )
    )

    locked_covers = sum(
        1
        for assignment in planning.manual_assignments
        if (
            assignment.is_locked
            and assignment.assignment_kind
            in {"COVER", "COVER_RESERVE"}
        )
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Active personnel",
        len(planning.personnel),
    )
    c2.metric(
        "Availability blocks",
        len(planning.availability_entries),
    )
    c3.metric(
        "Cover Fit personnel",
        cover_fit_count,
    )
    c4.metric(
        "PTMC interests",
        len(planning.duty_interests),
    )

    d1, d2, d3, d4 = st.columns(4)

    d1.metric(
        "Cover requirements",
        len(planning.cover_requirements),
    )
    d2.metric(
        "Expanded cover slots",
        len(planning.cover_slots),
    )
    d3.metric(
        "Locked duties",
        locked_duties,
    )
    d4.metric(
        "Locked covers / reserves",
        locked_covers,
    )


def render_duty_results(result, *, year: int, month: int) -> None:
    st.subheader("Duty roster")

    locked_keys = {
        assignment_key(assignment)
        for assignment in result.locked_duty_assignments
    }

    assignments = [
        assignment
        for assignment in result.schedule.assignments
        if (
            assignment.duty_date.year == year
            and assignment.duty_date.month == month
        )
    ]

    rows = [
        {
            "Date": assignment.duty_date,
            "Centre": assignment.centre,
            "Role": assignment.role,
            "Personnel": assignment.person_name,
            "Points": assignment.points,
            "Overnight": assignment.is_overnight,
            "Locked": (
                assignment_key(assignment)
                in locked_keys
            ),
        }
        for assignment in sorted(
            assignments,
            key=lambda item: (
                item.duty_date,
                item.centre,
                item.role,
            ),
        )
    ]

    if not rows:
        st.info(
            "No duty assignments were generated."
        )
        return

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        height=min(
            750,
            90 + len(rows) * 35,
        ),
        column_config={
            "Date": st.column_config.DateColumn(
                "Date",
                format="DD MMM",
            ),
            "Points": st.column_config.NumberColumn(
                "Points",
                format="%.2f",
            ),
            "Overnight": st.column_config.CheckboxColumn(
                "Overnight"
            ),
            "Locked": st.column_config.CheckboxColumn(
                "Locked"
            ),
        },
    )


def render_cover_results(result) -> None:
    st.subheader("Cover roster")

    if not result.cover_assignments:
        st.info(
            "No cover assignments were required for this month."
        )
        return

    rows = [
        {
            "Date": assignment.duty_date,
            "Personnel": assignment.person_name,
            "Unit": assignment.requesting_unit,
            "Category": assignment.cover_category,
            "Cover": assignment.cover_type,
            "Session": assignment.session,
            "Points": assignment.points,
            "Reserve": assignment.is_reserve,
            "Locked": assignment.is_locked,
        }
        for assignment in sorted(
            result.cover_assignments,
            key=lambda item: (
                item.duty_date,
                item.is_reserve,
                item.requesting_unit,
                item.cover_type,
            ),
        )
    ]

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        height=min(
            750,
            90 + len(rows) * 35,
        ),
        column_config={
            "Date": st.column_config.DateColumn(
                "Date",
                format="DD MMM",
            ),
            "Points": st.column_config.NumberColumn(
                "Points",
                format="%.2f",
            ),
            "Reserve": st.column_config.CheckboxColumn(
                "Reserve"
            ),
            "Locked": st.column_config.CheckboxColumn(
                "Locked"
            ),
        },
    )


def render_unfilled(result) -> None:
    unfilled_duties = (
        result
        .roster_result
        .scheduler_result
        .unfilled_requirements
    )

    unfilled_covers = (
        result.unfilled_cover_slots
    )

    if (
        not unfilled_duties
        and not unfilled_covers
    ):
        st.success(
            "All duty and cover requirements were filled."
        )
        return

    st.error(
        "The roster is incomplete. Review the unfilled "
        "requirements below before using the result."
    )

    if unfilled_duties:
        st.markdown("#### Unfilled duties")

        st.dataframe(
            [
                {
                    "Date": item.duty_date,
                    "Centre": item.centre,
                    "Role": item.role,
                    "Overnight": item.is_overnight,
                    "Points": item.points,
                }
                for item in unfilled_duties
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn(
                    "Date",
                    format="DD MMM",
                ),
                "Overnight": (
                    st.column_config.CheckboxColumn(
                        "Overnight"
                    )
                ),
            },
        )

    if unfilled_covers:
        st.markdown(
            "#### Unfilled mandatory covers / reserves"
        )

        st.dataframe(
            [
                {
                    "Date": item.duty_date,
                    "Unit": item.requesting_unit,
                    "Category": item.cover_category,
                    "Cover": item.cover_type,
                    "Session": item.session,
                    "Reserve": item.is_reserve,
                    "Mandatory": item.mandatory,
                }
                for item in unfilled_covers
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn(
                    "Date",
                    format="DD MMM",
                ),
                "Reserve": (
                    st.column_config.CheckboxColumn(
                        "Reserve"
                    )
                ),
                "Mandatory": (
                    st.column_config.CheckboxColumn(
                        "Mandatory"
                    )
                ),
            },
        )


try:
    roster_months = load_roster_months()
except Exception as exc:
    st.error(
        f"Unable to load roster months: {exc}"
    )
    st.stop()

if not roster_months:
    st.warning(
        "No roster months exist yet. Create one from the "
        "Availability page first."
    )
    st.stop()


stored_month = st.session_state.get(
    "selected_roster_month"
)

default_index = 0

if stored_month:
    for index, record in enumerate(
        roster_months
    ):
        if (
            record["month_start"].isoformat()
            == str(stored_month)
        ):
            default_index = index
            break


selected_month_record = st.selectbox(
    "Roster month",
    options=roster_months,
    index=default_index,
    format_func=lambda record: (
        f"{record['month_start']:%b %y} "
        f"— {record['status'].title()}"
    ),
)

selected_month = (
    selected_month_record["month_start"]
)

st.session_state[
    "selected_roster_month"
] = selected_month.isoformat()


try:
    planning = load_planning_context(
        year=selected_month.year,
        month=selected_month.month,
    )
except Exception as exc:
    st.error(
        "Unable to load planning data for "
        f"{selected_month:%B %Y}: {exc}"
    )
    st.exception(exc)
    st.stop()


render_preflight(planning)

st.divider()

st.info(
    "Generation order: locked duties → locked covers/reserves → "
    "remaining mandatory covers → remaining duties. "
    "PTMC overnight interest is applied as a soft duty preference."
)


if st.button(
    "Generate roster",
    type="primary",
    use_container_width=True,
    key="generate_planning_roster",
):
    try:
        result = generate_roster_from_planning(
            planning=planning,
            settings=GenerationSettings(
                year=selected_month.year,
                month=selected_month.month,
            ),
        )
    except Exception as exc:
        st.error(
            f"Roster generation failed: {exc}"
        )
        st.exception(exc)
    else:
        st.session_state[
            "latest_planning_generation"
        ] = result


result = st.session_state.get(
    "latest_planning_generation"
)

if result is None:
    st.stop()


# Prevent showing a stale result after changing month.
if (
    result.roster_result.report.year
    != selected_month.year
    or result.roster_result.report.month
    != selected_month.month
):
    st.warning(
        "The displayed generation result belongs to another month. "
        "Click Generate roster for the selected month."
    )
    st.stop()


st.divider()
st.header(
    f"Generated roster — {selected_month:%B %Y}"
)


report = result.roster_result.report

unfilled_duties = (
    result
    .roster_result
    .scheduler_result
    .unfilled_requirements
)

unfilled_covers = (
    result.unfilled_cover_slots
)


c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Duty assignments",
    report.generated_assignment_count,
)

c2.metric(
    "Cover assignments",
    len(result.cover_assignments),
)

c3.metric(
    "Locked duties",
    len(result.locked_duty_assignments),
)

c4.metric(
    "Unfilled duties",
    len(unfilled_duties),
)

c5.metric(
    "Unfilled covers",
    len(unfilled_covers),
)


tabs = st.tabs(
    [
        "Duty roster",
        "Cover roster",
        "Unfilled / warnings",
    ]
)

with tabs[0]:
    render_duty_results(
        result,
        year=selected_month.year,
        month=selected_month.month,
    )

with tabs[1]:
    render_cover_results(result)

with tabs[2]:
    render_unfilled(result)

    warnings = [
        *result.planning_warnings,
        *report.warnings,
    ]

    # Preserve order while removing duplicates.
    seen: set[str] = set()
    unique_warnings: list[str] = []

    for warning in warnings:
        if warning in seen:
            continue

        seen.add(warning)
        unique_warnings.append(warning)

    if unique_warnings:
        st.markdown("#### Generator warnings")

        for warning in unique_warnings:
            st.warning(warning)


roster_complete = (
    not unfilled_duties
    and not unfilled_covers
)


st.divider()
st.subheader("Validation & export")

try:
    validation_report = validate_schedule(
        schedule=result.schedule,
        personnel=planning.personnel,
        availability_entries=(
            planning.availability_entries
        ),
        requirements=(
            result.roster_result.requirements
        ),
        year=selected_month.year,
        month=selected_month.month,
        maximum_weekly_overnights=3,
    )
except Exception as exc:
    st.error(
        f"Unable to validate duty roster: {exc}"
    )
    validation_report = None


if validation_report is not None:
    if validation_report.is_valid:
        st.success(
            "Duty roster passed validation."
        )
    else:
        st.error(
            f"Duty roster validation found "
            f"{validation_report.error_count} error(s)."
        )

        validation_rows = [
            {
                "Code": issue.code,
                "Message": issue.message,
            }
            for issue in validation_report.errors
        ]

        st.dataframe(
            validation_rows,
            use_container_width=True,
            hide_index=True,
        )


can_export = (
    roster_complete
    and validation_report is not None
    and validation_report.is_valid
)


if not can_export:
    st.caption(
        "Excel export is disabled until all duty and cover slots "
        "are filled and the duty roster passes validation."
    )
else:
    if not ROSTER_TEMPLATE_PATH.exists():
        st.error(
            "Roster template was not found at "
            f"{ROSTER_TEMPLATE_PATH}."
        )
    else:
        with TemporaryDirectory() as temp_directory:
            output_path = (
                Path(temp_directory)
                / (
                    f"{selected_month:%B_%Y}_Roster.xlsx"
                )
            )

            try:
                export_schedule(
                    template_path=ROSTER_TEMPLATE_PATH,
                    output_path=output_path,
                    schedule=result.schedule,
                    year=selected_month.year,
                    month=selected_month.month,
                )

                output_bytes = (
                    output_path.read_bytes()
                )
            except Exception as exc:
                st.error(
                    f"Unable to create Excel export: {exc}"
                )
            else:
                st.download_button(
                    label="Download generated duty roster",
                    data=output_bytes,
                    file_name=output_path.name,
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    type="primary",
                    use_container_width=True,
                )

                st.caption(
                    "This first planning-aware export writes the duty "
                    "schedule into the existing roster workbook. "
                    "Cover assignments are visible in the Cover roster "
                    "tab; writing covers into Excel will be the next "
                    "export enhancement."
                )
