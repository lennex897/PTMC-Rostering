from __future__ import annotations

from collections import defaultdict
from datetime import date

import streamlit as st

from roster_engine.availability_repository import (
    AvailabilityRepository,
)
from roster_engine.database import get_supabase
from roster_engine.eligibility import (
    BLOCKING_REASONS,
    is_eligible_for_role,
)
from roster_engine.generated_roster_repository import (
    GeneratedRosterRepository,
    StoredGeneratedAssignment,
)
from roster_engine.models import (
    Assignment,
    DutyRequirement,
    Schedule,
)
from roster_engine.personnel_repository import (
    load_personnel_records,
)
from roster_engine.roster_rules_repository import (
    RosterRulesRepository,
)
from roster_engine.validator import validate_schedule


st.set_page_config(
    page_title="Saved Rosters",
    page_icon="📋",
    layout="wide",
)

st.title("Saved Rosters")
st.caption(
    "Review and edit a saved draft roster before publishing and export."
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
        raw = row.get("month_start")

        if not raw:
            continue

        parsed = (
            raw
            if isinstance(raw, date)
            else date.fromisoformat(str(raw))
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


@st.cache_data(ttl=15)
def load_personnel():
    return load_personnel_records(
        include_inactive=False
    )


@st.cache_data(ttl=15)
def load_availability(
    year: int,
    month: int,
):
    return AvailabilityRepository(
        get_supabase()
    ).load_month_availability(
        year=year,
        month=month,
    )


@st.cache_data(ttl=15)
def load_rules():
    return RosterRulesRepository(
        get_supabase()
    ).load_rules()


def clear_saved_roster_cache() -> None:
    load_generations.clear()
    load_assignments.clear()


def normalise(value: str) -> str:
    return " ".join(
        str(value or "").strip().upper().split()
    )


def sessions_conflict(
    first: str | None,
    second: str | None,
) -> bool:
    a = normalise(first or "FULL_DAY")
    b = normalise(second or "FULL_DAY")

    if "FULL_DAY" in {a, b}:
        return True

    return a == b


def person_available_for_cover(
    person,
    *,
    duty_date: date,
    availability_entries,
) -> bool:
    if not person.is_active:
        return False

    if person.is_cover_fit is not True:
        return False

    if (
        person.leaving_date is not None
        and duty_date >= person.leaving_date
    ):
        return False

    person_name = normalise(
        person.name
    )

    return not any(
        normalise(entry.person_name)
        == person_name
        and entry.unavailable_date
        == duty_date
        and normalise(entry.reason)
        in BLOCKING_REASONS
        for entry in availability_entries
    )


def assignment_conflicts(
    *,
    candidate_name: str,
    target: StoredGeneratedAssignment,
    assignments: list[StoredGeneratedAssignment],
) -> list[str]:
    candidate = normalise(
        candidate_name
    )

    conflicts: list[str] = []

    for other in assignments:
        if other.id == target.id:
            continue

        if (
            other.assignment_date
            != target.assignment_date
        ):
            continue

        if normalise(
            other.person_name
        ) != candidate:
            continue

        if (
            target.assignment_kind == "DUTY"
            or other.assignment_kind == "DUTY"
            or sessions_conflict(
                target.session,
                other.session,
            )
        ):
            label = (
                other.role_name
                if other.assignment_kind
                == "DUTY"
                else other.cover_type
                or other.assignment_kind
            )

            conflicts.append(
                str(label)
            )

    return conflicts


def eligible_replacements(
    *,
    target: StoredGeneratedAssignment,
    personnel_records,
    availability_entries,
    assignments,
):
    candidates = []

    for record in personnel_records:
        person = record.person

        if target.assignment_kind == "DUTY":
            role = normalise(
                target.role_name or ""
            )

            if role in {
                "PT RESERVE",
                "RH RESERVE",
            }:
                if normalise(
                    person.centre
                ) != role.split()[0]:
                    continue
            elif not is_eligible_for_role(
                person=person,
                role=role,
                duty_date=target.assignment_date,
                availability_entries=(
                    availability_entries
                ),
            ):
                continue
        else:
            if not person_available_for_cover(
                person,
                duty_date=target.assignment_date,
                availability_entries=(
                    availability_entries
                ),
            ):
                continue

        conflicts = assignment_conflicts(
            candidate_name=person.name,
            target=target,
            assignments=assignments,
        )

        if conflicts:
            continue

        candidates.append(record)

    return candidates


def validate_saved_roster(
    *,
    assignments,
    personnel_records,
    availability_entries,
    generation,
    rules,
    year: int,
    month: int,
) -> list[str]:
    errors: list[str] = []

    personnel = [
        record.person
        for record in personnel_records
    ]

    duty_rows = [
        item
        for item in assignments
        if item.assignment_kind
        == "DUTY"
    ]

    schedule = Schedule(
        assignments=[
            Assignment(
                duty_date=item.assignment_date,
                role=item.role_name or "",
                centre=item.centre or "",
                person_name=item.person_name,
                points=item.points,
                is_overnight=item.is_overnight,
            )
            for item in duty_rows
        ]
    )

    # Each existing non-reserve duty row represents a requirement already
    # fulfilled by this generation. Edits only swap personnel, so validation
    # focuses on eligibility, spacing and double-booking rather than rebuilding
    # the original requirement settings.
    requirements = [
        DutyRequirement(
            duty_date=item.assignment_date,
            role=item.role_name or "",
            centre=item.centre or "",
            is_overnight=item.is_overnight,
            points=item.points,
        )
        for item in duty_rows
        if normalise(
            item.role_name or ""
        ) not in {
            "PT RESERVE",
            "RH RESERVE",
        }
    ]

    report = validate_schedule(
        schedule=schedule,
        personnel=personnel,
        availability_entries=(
            availability_entries
        ),
        requirements=requirements,
        year=year,
        month=month,
        maximum_weekly_overnights=(
            rules.maximum_weekly_overnights
        ),
        overnight_min_break_days=(
            rules.overnight_min_break_days
        ),
        manual_only_personnel=(
            rules.manual_only_personnel
        ),
    )

    errors.extend(
        issue.message
        for issue in report.errors
    )

    # Cross-check duties and covers together.
    by_person_date: dict[
        tuple[str, date],
        list[StoredGeneratedAssignment],
    ] = defaultdict(list)

    for item in assignments:
        by_person_date[
            (
                normalise(item.person_name),
                item.assignment_date,
            )
        ].append(item)

    for (_, duty_date), items in by_person_date.items():
        if len(items) < 2:
            continue

        for index, first in enumerate(items):
            for second in items[
                index + 1:
            ]:
                if (
                    first.assignment_kind
                    == "DUTY"
                    or second.assignment_kind
                    == "DUTY"
                    or sessions_conflict(
                        first.session,
                        second.session,
                    )
                ):
                    errors.append(
                        f"{first.person_name} has conflicting "
                        f"assignments on {duty_date:%d %b %Y}."
                    )
                    break

    if generation.unfilled_duty_count:
        errors.append(
            f"Generation still records "
            f"{generation.unfilled_duty_count} "
            "unfilled duty slot(s)."
        )

    if generation.unfilled_cover_count:
        errors.append(
            f"Generation still records "
            f"{generation.unfilled_cover_count} "
            "unfilled cover slot(s)."
        )

    # Preserve first occurrence only.
    return list(
        dict.fromkeys(errors)
    )


try:
    roster_months = load_roster_months()
except Exception as exc:
    st.error(
        f"Unable to load roster months: {exc}"
    )
    st.stop()

if not roster_months:
    st.info("No roster months exist yet.")
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


generations = load_generations(
    roster_month_id
)

if not generations:
    st.info(
        f"No saved generations exist for "
        f"{selected_month:%B %Y}."
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

assignments = load_assignments(
    generation.id
)

personnel_records = load_personnel()
availability_entries = load_availability(
    selected_month.year,
    selected_month.month,
)
rules = load_rules()


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


is_editable = (
    generation.status == "draft"
)

if is_editable:
    st.info(
        "This roster is a draft. You may edit personnel assignments "
        "before publishing."
    )
else:
    st.success(
        f"This roster is {generation.status}. Editing is locked."
    )


edit_tab, duty_tab, cover_tab, matrix_tab, workload_tab, validation_tab = st.tabs(
    [
        "Edit Roster",
        "Duties",
        "Covers",
        "Monthly Matrix",
        "Workload",
        "Validate & Publish",
    ]
)


with edit_tab:
    st.subheader("Roster plotter")
    st.caption(
        "Use the matrix as a live visual overview, then select a person and date "
        "below to edit the assignment for that cell. Changes are applied immediately "
        "to the saved draft roster."
    )

    if not is_editable:
        st.info(
            "Only draft generations can be edited."
        )
    elif not assignments:
        st.info(
            "This generation has no assignments."
        )
    else:
        import calendar
        import pandas as pd

        days_in_month = calendar.monthrange(
            selected_month.year,
            selected_month.month,
        )[1]

        month_dates = [
            date(
                selected_month.year,
                selected_month.month,
                day_number,
            )
            for day_number in range(
                1,
                days_in_month + 1,
            )
        ]

        ordered_records = sorted(
            personnel_records,
            key=lambda record: (
                normalise(
                    record.person.centre
                ),
                getattr(
                    record,
                    "display_order",
                    0,
                ),
                normalise(
                    record.person.name
                ),
            ),
        )

        person_record_by_name = {
            normalise(
                record.person.name
            ): record
            for record in ordered_records
        }

        def assignment_display(
            item: StoredGeneratedAssignment,
        ) -> str:
            if item.assignment_kind == "DUTY":
                return item.role_name or "DUTY"

            unit = (
                item.requesting_unit
                or ""
            ).strip()

            cover = (
                item.cover_type
                or item.assignment_kind
            )

            return (
                f"{unit} — {cover}"
                if unit
                else cover
            )

        assignments_by_person_date: dict[
            tuple[str, date],
            list[StoredGeneratedAssignment],
        ] = defaultdict(list)

        for item in assignments:
            assignments_by_person_date[
                (
                    normalise(
                        item.person_name
                    ),
                    item.assignment_date,
                )
            ].append(item)

        # Clean visual matrix: personnel down the left, dates across the top.
        matrix_rows = []

        for record in ordered_records:
            person = record.person
            person_key = normalise(
                person.name
            )

            row = {
                "Personnel": person.name,
                "Centre": person.centre,
            }

            for duty_date in month_dates:
                items = (
                    assignments_by_person_date.get(
                        (
                            person_key,
                            duty_date,
                        ),
                        [],
                    )
                )

                row[
                    duty_date.strftime(
                        "%d %b"
                    )
                ] = "\n".join(
                    assignment_display(
                        item
                    )
                    for item in sorted(
                        items,
                        key=lambda item: (
                            item.assignment_kind,
                            item.role_name or "",
                            item.cover_type or "",
                        ),
                    )
                )

            matrix_rows.append(row)

        matrix_df = pd.DataFrame(
            matrix_rows
        )

        st.dataframe(
            matrix_df,
            use_container_width=True,
            hide_index=True,
            height=min(
                850,
                90
                + max(
                    1,
                    len(matrix_rows),
                )
                * 35,
            ),
            column_config={
                "Personnel": (
                    st.column_config.TextColumn(
                        "Personnel",
                        width="medium",
                    )
                ),
                "Centre": (
                    st.column_config.TextColumn(
                        "Centre",
                        width="small",
                    )
                ),
            },
        )

        st.divider()
        st.markdown(
            "#### Edit selected cell"
        )

        selector_cols = st.columns(
            [2, 1.2]
        )

        with selector_cols[0]:
            selected_person_name = (
                st.selectbox(
                    "Personnel",
                    options=[
                        record.person.name
                        for record in ordered_records
                    ],
                    key=(
                        "roster_plotter_person_"
                        + generation.id
                    ),
                )
            )

        with selector_cols[1]:
            selected_date = st.date_input(
                "Date",
                value=selected_month,
                min_value=selected_month,
                max_value=date(
                    selected_month.year,
                    selected_month.month,
                    days_in_month,
                ),
                format="DD/MM/YYYY",
                key=(
                    "roster_plotter_date_"
                    + generation.id
                ),
            )

        selected_person_key = normalise(
            selected_person_name
        )

        selected_items = list(
            assignments_by_person_date.get(
                (
                    selected_person_key,
                    selected_date,
                ),
                [],
            )
        )

        if not selected_items:
            st.info(
                f"{selected_person_name} currently has no saved assignment "
                f"on {selected_date:%d %b %Y}."
            )
        else:
            st.caption(
                f"Current assignments for {selected_person_name} "
                f"on {selected_date:%d %b %Y}"
            )

            for item in selected_items:
                st.write(
                    "• "
                    + assignment_display(
                        item
                    )
                )

            assignment_by_id = {
                item.id: item
                for item in selected_items
            }

            selected_assignment_id = (
                st.selectbox(
                    "Assignment to edit",
                    options=list(
                        assignment_by_id
                    ),
                    format_func=lambda assignment_id: (
                        assignment_display(
                            assignment_by_id[
                                assignment_id
                            ]
                        )
                    ),
                    key=(
                        "roster_plotter_assignment_"
                        + generation.id
                        + "_"
                        + selected_person_key
                        + "_"
                        + selected_date.isoformat()
                    ),
                )
            )

            target = assignment_by_id[
                selected_assignment_id
            ]

            replacements = eligible_replacements(
                target=target,
                personnel_records=(
                    personnel_records
                ),
                availability_entries=(
                    availability_entries
                ),
                assignments=assignments,
            )

            replacement_by_id = {
                record.id: record
                for record in replacements
            }

            if not replacements:
                st.warning(
                    "No eligible conflict-free replacement is available "
                    "for this assignment."
                )
            else:
                current_record = next(
                    (
                        record
                        for record
                        in replacements
                        if normalise(
                            record.person.name
                        )
                        == normalise(
                            target.person_name
                        )
                    ),
                    None,
                )

                replacement_ids = list(
                    replacement_by_id
                )

                default_index = (
                    replacement_ids.index(
                        current_record.id
                    )
                    if (
                        current_record
                        and current_record.id
                        in replacement_ids
                    )
                    else 0
                )

                replacement_id = (
                    st.selectbox(
                        "Reassign to",
                        options=(
                            replacement_ids
                        ),
                        index=default_index,
                        format_func=lambda personnel_id: (
                            replacement_by_id[
                                personnel_id
                            ].person.name
                        ),
                        key=(
                            "roster_plotter_replacement_"
                            + generation.id
                            + "_"
                            + target.id
                        ),
                    )
                )

                replacement_record = (
                    replacement_by_id[
                        replacement_id
                    ]
                )

                preview_cols = st.columns(
                    3
                )

                preview_cols[0].metric(
                    "Current",
                    target.person_name,
                )

                preview_cols[1].metric(
                    "Assignment",
                    assignment_display(
                        target
                    ),
                )

                preview_cols[2].metric(
                    "New",
                    replacement_record.person.name,
                )

                if st.button(
                    "Apply reassignment",
                    type="primary",
                    use_container_width=True,
                    disabled=(
                        normalise(
                            replacement_record.person.name
                        )
                        == normalise(
                            target.person_name
                        )
                    ),
                    key=(
                        "apply_roster_plotter_change_"
                        + generation.id
                        + "_"
                        + target.id
                    ),
                ):
                    try:
                        GeneratedRosterRepository(
                            get_supabase()
                        ).update_assignment_person(
                            assignment_id=(
                                target.id
                            ),
                            personnel_id=(
                                replacement_record.id
                            ),
                            person_name=(
                                replacement_record.person.name
                            ),
                        )
                    except Exception as exc:
                        st.error(
                            f"Unable to update assignment: {exc}"
                        )
                    else:
                        clear_saved_roster_cache()
                        st.success(
                            "Assignment updated."
                        )
                        st.rerun()

        st.caption(
            "This editor currently moves existing saved duties/covers only. "
            "DM Shadow will be added here next as an additional post-generation "
            "plotting action without consuming the real DM slot."
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


with duty_tab:
    rows = [
        {
            "Date": item.assignment_date,
            "Centre": item.centre or "",
            "Role": item.role_name or "",
            "Personnel": item.person_name,
            "Points": item.points,
            "Locked": item.is_locked,
        }
        for item in duty_assignments
    ]

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


with cover_tab:
    rows = [
        {
            "Date": item.assignment_date,
            "Personnel": item.person_name,
            "Unit": item.requesting_unit or "",
            "Cover": item.cover_type or "",
            "Session": item.session or "",
            "Points": item.points,
            "Reserve": item.is_reserve,
        }
        for item in cover_assignments
    ]

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


with matrix_tab:
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
            "Personnel": person_name
        }

        for current_date in all_dates:
            values = []

            for item in assignments:
                if (
                    item.person_name
                    == person_name
                    and item.assignment_date
                    == current_date
                ):
                    values.append(
                        item.role_name
                        if item.assignment_kind
                        == "DUTY"
                        else item.cover_type
                        or item.assignment_kind
                    )

            row[
                current_date.strftime(
                    "%d %b"
                )
            ] = " / ".join(values)

        matrix_rows.append(row)

    st.dataframe(
        matrix_rows,
        use_container_width=True,
        hide_index=True,
    )


with workload_tab:
    workload: dict[str, dict] = {}

    for item in assignments:
        row = workload.setdefault(
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
            row["Duty points"] += item.points
            row["Duties"] += 1
        else:
            row["Cover points"] += item.points
            row["Covers"] += 1

        row["Total points"] += item.points

    workload_rows = sorted(
        workload.values(),
        key=lambda row: (
            row["Total points"],
            row["Personnel"],
        ),
        reverse=True,
    )

    st.dataframe(
        workload_rows,
        use_container_width=True,
        hide_index=True,
    )


with validation_tab:
    st.subheader(
        "Validate and publish"
    )

    validation_errors = (
        validate_saved_roster(
            assignments=assignments,
            personnel_records=(
                personnel_records
            ),
            availability_entries=(
                availability_entries
            ),
            generation=generation,
            rules=rules,
            year=selected_month.year,
            month=selected_month.month,
        )
    )

    if validation_errors:
        st.error(
            f"{len(validation_errors)} validation issue(s) remain."
        )

        for message in validation_errors:
            st.write(
                f"• {message}"
            )
    else:
        st.success(
            "Roster passes post-generation validation."
        )

    if generation.status == "draft":
        if st.button(
            "Publish roster",
            type="primary",
            use_container_width=True,
            disabled=bool(
                validation_errors
            ),
        ):
            try:
                GeneratedRosterRepository(
                    get_supabase()
                ).set_generation_status(
                    generation_id=(
                        generation.id
                    ),
                    status="published",
                )
            except Exception as exc:
                st.error(
                    f"Unable to publish roster: {exc}"
                )
            else:
                clear_saved_roster_cache()
                st.success(
                    "Roster published. Editing is now locked."
                )
                st.rerun()
    else:
        st.info(
            "Published/superseded rosters are read-only."
        )
