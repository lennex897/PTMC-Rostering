from __future__ import annotations

from datetime import date

import streamlit as st

from roster_engine.database import get_supabase
from roster_engine.generated_roster_repository import (
    GeneratedRosterRepository,
)


st.set_page_config(
    page_title="Saved Rosters",
    page_icon="📋",
    layout="wide",
)

st.title("Saved Rosters")
st.caption(
    "Review current and historical generated roster versions saved in Supabase."
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
                "status": str(
                    row.get("status")
                    or "draft"
                ),
            }
        )

    return rows


@st.cache_data(ttl=15)
def load_generations(
    roster_month_id: str,
):
    return GeneratedRosterRepository(
        get_supabase()
    ).list_generations(
        roster_month_id
    )


@st.cache_data(ttl=15)
def load_assignments(
    generation_id: str,
):
    return GeneratedRosterRepository(
        get_supabase()
    ).list_assignments(
        generation_id
    )


try:
    roster_months = load_roster_months()
except Exception as exc:
    st.error(
        f"Unable to load roster months: {exc}"
    )
    st.stop()

if not roster_months:
    st.info(
        "No roster months exist yet."
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
        record["month_start"].strftime(
            "%b %y"
        )
    ),
)

selected_month = (
    selected_month_record["month_start"]
)

roster_month_id = (
    selected_month_record["id"]
)

st.session_state[
    "selected_roster_month"
] = selected_month.isoformat()


try:
    generations = load_generations(
        roster_month_id
    )
except Exception as exc:
    st.error(
        f"Unable to load saved roster versions: {exc}"
    )
    st.stop()


if not generations:
    st.info(
        f"No saved generations exist for "
        f"{selected_month:%B %Y} yet."
    )
    st.stop()


generation_by_id = {
    item.id: item
    for item in generations
}

selected_generation_id = st.selectbox(
    "Roster version",
    options=list(generation_by_id),
    format_func=lambda generation_id: (
        f"Version "
        f"{generation_by_id[generation_id].version}"
        f"{' — Current' if generation_by_id[generation_id].is_current else ''}"
        f" — {generation_by_id[generation_id].status.title()}"
    ),
)

generation = generation_by_id[
    selected_generation_id
]


try:
    assignments = load_assignments(
        generation.id
    )
except Exception as exc:
    st.error(
        f"Unable to load saved assignments: {exc}"
    )
    st.stop()


m1, m2, m3, m4, m5 = st.columns(5)

m1.metric(
    "Personnel",
    generation.personnel_count,
)

m2.metric(
    "Duties",
    generation.duty_assignment_count,
)

m3.metric(
    "Covers",
    generation.cover_assignment_count,
)

m4.metric(
    "Unfilled duties",
    generation.unfilled_duty_count,
)

m5.metric(
    "Unfilled covers",
    generation.unfilled_cover_count,
)


if generation.is_current:
    st.success(
        f"Version {generation.version} is the current saved roster."
    )
else:
    st.info(
        f"Viewing historical version {generation.version}."
    )


duty_assignments = [
    item
    for item in assignments
    if item.assignment_kind == "DUTY"
]

cover_assignments = [
    item
    for item in assignments
    if item.assignment_kind in {
        "COVER",
        "COVER_RESERVE",
    }
]


duty_tab, cover_tab, matrix_tab, workload_tab = st.tabs(
    [
        "Duties",
        "Covers",
        "Monthly Matrix",
        "Workload",
    ]
)


with duty_tab:
    st.subheader("Saved duty assignments")

    if not duty_assignments:
        st.info(
            "This generation has no saved duties."
        )
    else:
        duty_rows = [
            {
                "Date": item.assignment_date,
                "Centre": item.centre or "",
                "Role": item.role_name or "",
                "Personnel": item.person_name,
                "Points": item.points,
                "Overnight": item.is_overnight,
                "Locked": item.is_locked,
            }
            for item in duty_assignments
        ]

        st.dataframe(
            duty_rows,
            use_container_width=True,
            hide_index=True,
            height=min(
                750,
                90 + len(duty_rows) * 35,
            ),
            column_config={
                "Date": (
                    st.column_config.DateColumn(
                        "Date",
                        format="DD MMM",
                    )
                ),
                "Points": (
                    st.column_config.NumberColumn(
                        "Points",
                        format="%.2f",
                    )
                ),
                "Overnight": (
                    st.column_config.CheckboxColumn(
                        "Overnight"
                    )
                ),
                "Locked": (
                    st.column_config.CheckboxColumn(
                        "Locked"
                    )
                ),
            },
        )


with cover_tab:
    st.subheader("Saved cover assignments")

    if not cover_assignments:
        st.info(
            "This generation has no saved covers."
        )
    else:
        cover_rows = [
            {
                "Date": item.assignment_date,
                "Personnel": item.person_name,
                "Unit": item.requesting_unit or "",
                "Category": item.cover_category or "",
                "Cover": item.cover_type or "",
                "Session": item.session or "",
                "Points": item.points,
                "Reserve": item.is_reserve,
                "Locked": item.is_locked,
            }
            for item in cover_assignments
        ]

        st.dataframe(
            cover_rows,
            use_container_width=True,
            hide_index=True,
            height=min(
                750,
                90 + len(cover_rows) * 35,
            ),
            column_config={
                "Date": (
                    st.column_config.DateColumn(
                        "Date",
                        format="DD MMM",
                    )
                ),
                "Points": (
                    st.column_config.NumberColumn(
                        "Points",
                        format="%.2f",
                    )
                ),
                "Reserve": (
                    st.column_config.CheckboxColumn(
                        "Reserve"
                    )
                ),
                "Locked": (
                    st.column_config.CheckboxColumn(
                        "Locked"
                    )
                ),
            },
        )


with matrix_tab:
    st.subheader("Monthly assignment matrix")
    st.caption(
        "One row per person. Each date shows their saved duty or cover."
    )

    all_people = sorted(
        {
            item.person_name
            for item in assignments
        }
    )

    all_dates = sorted(
        {
            item.assignment_date
            for item in assignments
        }
    )

    matrix_rows = []

    for person_name in all_people:
        row = {
            "Personnel": person_name,
        }

        for current_date in all_dates:
            values = []

            for item in assignments:
                if (
                    item.person_name == person_name
                    and item.assignment_date == current_date
                ):
                    if item.assignment_kind == "DUTY":
                        values.append(
                            item.role_name or "DUTY"
                        )
                    elif item.assignment_kind == "COVER_RESERVE":
                        values.append("FC RESERVE")
                    else:
                        values.append(
                            item.cover_type or "COVER"
                        )

            row[
                current_date.strftime("%d %b")
            ] = " / ".join(values)

        matrix_rows.append(row)

    if matrix_rows:
        st.dataframe(
            matrix_rows,
            use_container_width=True,
            hide_index=True,
            height=min(
                800,
                90 + len(matrix_rows) * 35,
            ),
        )
    else:
        st.info(
            "No saved assignments exist."
        )


with workload_tab:
    st.subheader("Saved workload summary")

    workload: dict[str, dict] = {}

    for item in assignments:
        person = workload.setdefault(
            item.person_name,
            {
                "Personnel": item.person_name,
                "Duty points": 0.0,
                "Cover points": 0.0,
                "Total points": 0.0,
                "Duties": 0,
                "Covers": 0,
            },
        )

        if item.assignment_kind == "DUTY":
            person["Duty points"] += item.points
            person["Duties"] += 1
        else:
            person["Cover points"] += item.points
            person["Covers"] += 1

        person["Total points"] += item.points

    workload_rows = sorted(
        workload.values(),
        key=lambda row: (
            row["Total points"],
            row["Personnel"],
        ),
        reverse=True,
    )

    if workload_rows:
        st.dataframe(
            workload_rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Duty points": (
                    st.column_config.NumberColumn(
                        "Duty points",
                        format="%.2f",
                    )
                ),
                "Cover points": (
                    st.column_config.NumberColumn(
                        "Cover points",
                        format="%.2f",
                    )
                ),
                "Total points": (
                    st.column_config.NumberColumn(
                        "Total points",
                        format="%.2f",
                    )
                ),
            },
        )
    else:
        st.info(
            "No workload data exists for this generation."
        )
