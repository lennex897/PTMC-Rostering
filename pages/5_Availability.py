from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

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

entry_tab, review_tab = st.tabs(
    [
        "Plot availability",
        "Review entries",
    ]
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