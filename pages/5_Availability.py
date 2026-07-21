from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from collections import Counter, defaultdict

import streamlit as st

from roster_engine.availability_repository import (
    AvailabilityRepository,
)
from roster_engine.database import get_supabase
from roster_engine.personnel_repository import (
    PersonnelRecord,
    load_personnel_records,
)


AVAILABILITY_CODES = [
    "AL",
    "ORD",
    "HL",
    "MC",
    "CCL",
    "OIL",
    "OFF",
    "MA",
    "AM",
    "PM",
]


st.set_page_config(
    page_title="Availability",
    page_icon="📅",
    layout="wide",
)

st.title("Personnel Availability")

st.caption(
    "Plot and manage personnel availability stored in Supabase."
)


def month_start(value: date) -> date:
    return value.replace(day=1)


def dates_between(
    start_date: date,
    end_date: date,
) -> list[date]:
    if end_date < start_date:
        return []

    number_of_days = (
        end_date - start_date
    ).days

    return [
        start_date + timedelta(days=offset)
        for offset in range(number_of_days + 1)
    ]


def personnel_label(
    record: PersonnelRecord,
) -> str:
    person = record.person

    rank_prefix = (
        f"{person.rank} "
        if person.rank
        else ""
    )

    return (
        f"{rank_prefix}{person.name}"
        f" — {person.centre}"
    )

def full_personnel_name(
    record: PersonnelRecord,
) -> str:
    person = record.person

    if person.rank:
        return f"{person.rank} {person.name}"

    return person.name

@st.cache_data(ttl=30)
def load_cached_personnel() -> list[PersonnelRecord]:
    return load_personnel_records()


def clear_page_cache() -> None:
    load_cached_personnel.clear()


repository = AvailabilityRepository(
    get_supabase()
)

today = date.today()

selected_month = st.date_input(
    "Roster month",
    value=today.replace(day=1),
    format="DD/MM/YYYY",
)

selected_month = month_start(
    selected_month
)

year = selected_month.year
month = selected_month.month

month_last_day = date(
    year,
    month,
    monthrange(year, month)[1],
)

try:
    personnel_records = load_cached_personnel()
except Exception as exc:
    st.error(
        f"Unable to load personnel: {exc}"
    )
    st.stop()

if not personnel_records:
    st.warning(
        "No active personnel were found."
    )
    st.stop()


centre_filter = st.segmented_control(
    "Centre",
    options=[
        "All",
        "PT",
        "RH",
    ],
    default="All",
)

if centre_filter == "All":
    filtered_records = personnel_records
else:
    filtered_records = [
        record
        for record in personnel_records
        if record.person.centre == centre_filter
    ]


try:
    stored_entries = (
        repository.list_month_availability(
            year=year,
            month=month,
        )
    )
except Exception as exc:
    st.error(
        f"Unable to load availability: {exc}"
    )
    st.stop()


total_people = len(
    {
        entry.personnel_id
        for entry in stored_entries
    }
)

metric_1, metric_2, metric_3 = st.columns(3)

metric_1.metric(
    "Availability entries",
    len(stored_entries),
)

metric_2.metric(
    "Personnel affected",
    total_people,
)

metric_3.metric(
    "Roster month",
    selected_month.strftime("%B %Y"),
)


st.divider()

dashboard_tab, entry_tab, review_tab = st.tabs(
    [
        "Dashboard",
        "Plot availability",
        "Review entries",
    ]
)

with dashboard_tab:
    st.subheader(
        f"Availability dashboard — "
        f"{selected_month:%B %Y}"
    )

    personnel_by_id = {
        record.id: record
        for record in personnel_records
    }

    total_active_personnel = len(
        personnel_records
    )

    pt_personnel = [
        record
        for record in personnel_records
        if record.person.centre == "PT"
    ]

    rh_personnel = [
        record
        for record in personnel_records
        if record.person.centre == "RH"
    ]

    affected_personnel_ids = {
        entry.personnel_id
        for entry in stored_entries
    }

    code_counts = Counter(
        entry.reason
        for entry in stored_entries
    )

    centre_counts = Counter(
        entry.centre
        for entry in stored_entries
    )

    daily_entries = defaultdict(list)

    for entry in stored_entries:
        daily_entries[
            entry.unavailable_date
        ].append(entry)

    dashboard_metric_1, dashboard_metric_2, \
        dashboard_metric_3, dashboard_metric_4 = (
            st.columns(4)
        )

    dashboard_metric_1.metric(
        "Active personnel",
        total_active_personnel,
    )

    dashboard_metric_2.metric(
        "Personnel affected",
        len(affected_personnel_ids),
    )

    dashboard_metric_3.metric(
        "Availability entries",
        len(stored_entries),
    )

    busiest_date = None
    busiest_count = 0

    if daily_entries:
        busiest_date, busiest_entries = max(
            daily_entries.items(),
            key=lambda item: len(item[1]),
        )

        busiest_count = len(
            busiest_entries
        )

    dashboard_metric_4.metric(
        "Busiest unavailable day",
        (
            busiest_date.strftime("%d %b")
            if busiest_date
            else "None"
        ),
        (
            f"{busiest_count} unavailable"
            if busiest_date
            else None
        ),
    )

    st.divider()

    left_column, right_column = st.columns(2)

    with left_column:
        st.subheader("Availability by code")

        if not code_counts:
            st.info(
                "No availability has been plotted "
                "for this month."
            )

        else:
            code_table = [
                {
                    "Code": code,
                    "Entries": count,
                }
                for code, count in sorted(
                    code_counts.items(),
                    key=lambda item: (
                        -item[1],
                        item[0],
                    ),
                )
            ]

            st.dataframe(
                code_table,
                use_container_width=True,
                hide_index=True,
            )

            st.bar_chart(
                {
                    code: count
                    for code, count in sorted(
                        code_counts.items()
                    )
                },
                horizontal=True,
            )

    with right_column:
        st.subheader("Availability by centre")

        centre_table = [
            {
                "Centre": "PT",
                "Active personnel": len(
                    pt_personnel
                ),
                "Availability entries": (
                    centre_counts.get(
                        "PT",
                        0,
                    )
                ),
                "Personnel affected": len(
                    {
                        entry.personnel_id
                        for entry in stored_entries
                        if entry.centre == "PT"
                    }
                ),
            },
            {
                "Centre": "RH",
                "Active personnel": len(
                    rh_personnel
                ),
                "Availability entries": (
                    centre_counts.get(
                        "RH",
                        0,
                    )
                ),
                "Personnel affected": len(
                    {
                        entry.personnel_id
                        for entry in stored_entries
                        if entry.centre == "RH"
                    }
                ),
            },
        ]

        st.dataframe(
            centre_table,
            use_container_width=True,
            hide_index=True,
        )

        st.bar_chart(
            {
                "PT": centre_counts.get(
                    "PT",
                    0,
                ),
                "RH": centre_counts.get(
                    "RH",
                    0,
                ),
            },
            horizontal=True,
        )

    st.divider()

    st.subheader("Daily unavailable personnel")

    all_month_dates = dates_between(
        selected_month,
        month_last_day,
    )

    daily_summary_rows = []

    for current_date in all_month_dates:
        entries_for_date = daily_entries.get(
            current_date,
            [],
        )

        unavailable_ids = {
            entry.personnel_id
            for entry in entries_for_date
        }

        unavailable_pt_ids = {
            entry.personnel_id
            for entry in entries_for_date
            if entry.centre == "PT"
        }

        unavailable_rh_ids = {
            entry.personnel_id
            for entry in entries_for_date
            if entry.centre == "RH"
        }

        daily_summary_rows.append(
            {
                "Date": current_date,
                "Day": current_date.strftime(
                    "%a"
                ),
                "Unavailable": len(
                    unavailable_ids
                ),
                "Available": (
                    total_active_personnel
                    - len(unavailable_ids)
                ),
                "PT unavailable": len(
                    unavailable_pt_ids
                ),
                "PT available": (
                    len(pt_personnel)
                    - len(unavailable_pt_ids)
                ),
                "RH unavailable": len(
                    unavailable_rh_ids
                ),
                "RH available": (
                    len(rh_personnel)
                    - len(unavailable_rh_ids)
                ),
            }
        )

    st.line_chart(
        daily_summary_rows,
        x="Date",
        y=[
            "Unavailable",
            "PT unavailable",
            "RH unavailable",
        ],
    )

    st.dataframe(
        daily_summary_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn(
                "Date",
                format="DD/MM/YYYY",
            ),
        },
    )

    st.divider()

    st.subheader("Daily manpower detail")

    selected_dashboard_date = st.date_input(
        "View date",
        value=selected_month,
        min_value=selected_month,
        max_value=month_last_day,
        format="DD/MM/YYYY",
        key="dashboard_selected_date",
    )

    selected_date_entries = daily_entries.get(
        selected_dashboard_date,
        [],
    )

    selected_unavailable_ids = {
        entry.personnel_id
        for entry in selected_date_entries
    }

    selected_pt_unavailable = [
        entry
        for entry in selected_date_entries
        if entry.centre == "PT"
    ]

    selected_rh_unavailable = [
        entry
        for entry in selected_date_entries
        if entry.centre == "RH"
    ]

    selected_date_metric_1, \
        selected_date_metric_2, \
        selected_date_metric_3 = st.columns(3)

    selected_date_metric_1.metric(
        "Total available",
        (
            total_active_personnel
            - len(selected_unavailable_ids)
        ),
        f"{len(selected_unavailable_ids)} unavailable",
    )

    selected_date_metric_2.metric(
        "PT available",
        (
            len(pt_personnel)
            - len(
                {
                    entry.personnel_id
                    for entry
                    in selected_pt_unavailable
                }
            )
        ),
        (
            f"{len(selected_pt_unavailable)} "
            "unavailable"
        ),
    )

    selected_date_metric_3.metric(
        "RH available",
        (
            len(rh_personnel)
            - len(
                {
                    entry.personnel_id
                    for entry
                    in selected_rh_unavailable
                }
            )
        ),
        (
            f"{len(selected_rh_unavailable)} "
            "unavailable"
        ),
    )

    if not selected_date_entries:
        st.success(
            "No personnel are marked unavailable "
            f"on {selected_dashboard_date:%d %B %Y}."
        )

    else:
        day_detail_rows = [
            {
                "Centre": entry.centre,
                "Rank": entry.rank,
                "Personnel": entry.person_name,
                "Code": entry.reason,
                "Notes": entry.notes or "",
            }
            for entry in sorted(
                selected_date_entries,
                key=lambda entry: (
                    entry.centre,
                    entry.person_name,
                ),
            )
        ]

        st.dataframe(
            day_detail_rows,
            use_container_width=True,
            hide_index=True,
        )

with entry_tab:
    st.subheader("Add or update availability")

    st.info(
        "Saving the same person and date again updates the "
        "existing availability code."
    )

    personnel_options = {
        personnel_label(record): record
        for record in filtered_records
    }

    selected_labels = st.multiselect(
        "Personnel",
        options=list(
            personnel_options.keys()
        ),
        placeholder=(
            "Select one or more personnel"
        ),
    )

    date_mode = st.radio(
        "Date selection",
        options=[
            "Single date",
            "Date range",
        ],
        horizontal=True,
    )

    if date_mode == "Single date":
        selected_start_date = st.date_input(
            "Unavailable date",
            value=selected_month,
            min_value=selected_month,
            max_value=month_last_day,
            format="DD/MM/YYYY",
        )

        selected_end_date = (
            selected_start_date
        )

    else:
        selected_range = st.date_input(
            "Unavailable date range",
            value=(
                selected_month,
                selected_month,
            ),
            min_value=selected_month,
            max_value=month_last_day,
            format="DD/MM/YYYY",
        )

        if (
            isinstance(selected_range, tuple)
            and len(selected_range) == 2
        ):
            selected_start_date = (
                selected_range[0]
            )
            selected_end_date = (
                selected_range[1]
            )
        else:
            selected_start_date = None
            selected_end_date = None

    selected_code = st.selectbox(
        "Availability code",
        options=AVAILABILITY_CODES,
    )

    notes = st.text_area(
        "Notes",
        placeholder=(
            "Optional notes for this availability entry"
        ),
    )

    selected_records = [
        personnel_options[label]
        for label in selected_labels
    ]

    if (
        selected_start_date is not None
        and selected_end_date is not None
    ):
        selected_dates = dates_between(
            selected_start_date,
            selected_end_date,
        )
    else:
        selected_dates = []

    number_of_changes = (
        len(selected_records)
        * len(selected_dates)
    )

    st.caption(
        f"{len(selected_records)} personnel × "
        f"{len(selected_dates)} date(s) = "
        f"{number_of_changes} entry changes"
    )

    save_clicked = st.button(
        "Save availability",
        type="primary",
        use_container_width=True,
        disabled=(
            not selected_records
            or not selected_dates
        ),
    )

    if save_clicked:
        try:
            roster_month = (
                repository.get_or_create_roster_month(
                    selected_month
                )
            )

            progress = st.progress(0)

            completed = 0

            for record in selected_records:
                for unavailable_date in selected_dates:
                    repository.add_availability_entry(
                        roster_month_id=(
                            roster_month.id
                        ),
                        personnel_id=record.id,
                        unavailable_date=(
                            unavailable_date
                        ),
                        reason=selected_code,
                        source="manual",
                        notes=notes,
                    )

                    completed += 1

                    progress.progress(
                        completed
                        / number_of_changes
                    )

            st.success(
                f"Saved {number_of_changes} "
                "availability entry changes."
            )

            st.rerun()

        except Exception as exc:
            st.error(
                f"Unable to save availability: {exc}"
            )


with review_tab:
    st.subheader(
        f"Availability for "
        f"{selected_month:%B %Y}"
    )

    review_centre = st.selectbox(
        "Filter entries by centre",
        options=[
            "All",
            "PT",
            "RH",
        ],
        key="review_centre",
    )

    review_code = st.selectbox(
        "Filter entries by code",
        options=[
            "All",
            *AVAILABILITY_CODES,
        ],
    )

    filtered_entries = stored_entries

    if review_centre != "All":
        filtered_entries = [
            entry
            for entry in filtered_entries
            if entry.centre == review_centre
        ]

    if review_code != "All":
        filtered_entries = [
            entry
            for entry in filtered_entries
            if entry.reason == review_code
        ]

    search_text = st.text_input(
        "Search personnel",
        placeholder="Enter a name",
    ).strip().upper()

    if search_text:
        filtered_entries = [
            entry
            for entry in filtered_entries
            if search_text
            in entry.person_name.upper()
        ]

    if not filtered_entries:
        st.info(
            "No availability entries match the selected filters."
        )

    else:
        table_rows = [
            {
                "Date": entry.unavailable_date,
                "Day": entry.unavailable_date.strftime(
                    "%a"
                ),
                "Centre": entry.centre,
                "Rank": entry.rank,
                "Personnel": entry.person_name,
                "Code": entry.reason,
                "Notes": entry.notes or "",
                "Source": entry.source,
            }
            for entry in filtered_entries
        ]

        st.dataframe(
            table_rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn(
                    "Date",
                    format="DD/MM/YYYY",
                ),
            },
        )

        st.divider()
        st.subheader("Delete entries")

        deletion_options = {
            (
                f"{entry.unavailable_date:%d/%m/%Y}"
                f" — {entry.centre}"
                f" — {entry.rank} {entry.person_name}"
                f" — {entry.reason}"
            ): entry
            for entry in filtered_entries
        }

        selected_deletion_labels = st.multiselect(
            "Entries to delete",
            options=list(
                deletion_options.keys()
            ),
        )

        confirm_delete = st.checkbox(
            "I confirm that these entries should be deleted."
        )

        delete_clicked = st.button(
            "Delete selected entries",
            type="secondary",
            use_container_width=True,
            disabled=(
                not selected_deletion_labels
                or not confirm_delete
            ),
        )

        if delete_clicked:
            try:
                for label in selected_deletion_labels:
                    entry = deletion_options[
                        label
                    ]

                    repository.delete_availability_entry(
                        entry.id
                    )

                st.success(
                    f"Deleted "
                    f"{len(selected_deletion_labels)} "
                    "availability entries."
                )

                st.rerun()

            except Exception as exc:
                st.error(
                    f"Unable to delete availability: {exc}"
                )