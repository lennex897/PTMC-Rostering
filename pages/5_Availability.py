from __future__ import annotations

from calendar import month_name, monthrange
from datetime import date, timedelta
from collections import Counter, defaultdict

import streamlit as st

from roster_engine.availability_repository import (
    AvailabilityRepository,
)
from roster_engine.database import get_supabase
from roster_engine.models import StoredAvailabilityEntry
from roster_engine.personnel_repository import (
    PersonnelRecord,
    load_personnel_records,
)


DEFAULT_AVAILABILITY_CODES = [
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

def matrix_date_column_name(
    unavailable_date: date,
) -> str:
    """
    Produce compact matrix column labels such as:

    01 Sat
    02 Sun
    03 Mon
    """
    return unavailable_date.strftime("%d %a")


def build_availability_matrix(
    *,
    personnel_records: list[PersonnelRecord],
    stored_entries: list[StoredAvailabilityEntry],
    month_dates: list[date],
) -> list[dict[str, object]]:
    """
    Build one editable row per person.

    Multiple database records for the same person and date should not
    normally exist because of the database unique constraint. If they do,
    the final record encountered is displayed.
    """
    availability_lookup = {
        (
            entry.personnel_id,
            entry.unavailable_date,
        ): entry.reason
        for entry in stored_entries
    }

    matrix_rows: list[dict[str, object]] = []

    for record in personnel_records:
        person = record.person

        row: dict[str, object] = {
            "personnel_id": record.id,
            "Centre": person.centre,
            "Rank": person.rank or "",
            "Personnel": person.name,
        }

        for current_date in month_dates:
            row[
                matrix_date_column_name(current_date)
            ] = availability_lookup.get(
                (
                    record.id,
                    current_date,
                ),
                "",
            )

        matrix_rows.append(row)

    return matrix_rows


def matrix_values_by_person_and_date(
    *,
    matrix_rows: list[dict[str, object]],
    month_dates: list[date],
) -> dict[tuple[str, date], str]:
    """
    Convert matrix rows back into a person/date lookup.
    """
    values: dict[tuple[str, date], str] = {}

    rows = (
        matrix_rows.to_dict(orient="records")
        if hasattr(matrix_rows, "to_dict")
        else matrix_rows
    )

    for row in rows:
        personnel_id = str(
            row["personnel_id"]
        )

        for current_date in month_dates:
            column_name = matrix_date_column_name(
                current_date
            )

            raw_value = row.get(
                column_name,
                "",
            )

            value = (
                str(raw_value).strip().upper()
                if raw_value is not None
                else ""
            )

            values[
                (
                    personnel_id,
                    current_date,
                )
            ] = value

    return values


def render_manpower_calendar(
    *,
    selected_month: date,
    month_last_day: date,
    daily_entries: dict[date, list[StoredAvailabilityEntry]],
    total_personnel: int,
    centre: str = "Combined",
) -> None:
    """Render a compact month calendar shaded by unavailable headcount."""
    if total_personnel <= 0:
        st.info("No active personnel are available for this month.")
        return

    first_weekday = selected_month.weekday()
    month_dates = dates_between(selected_month, month_last_day)

    cells: list[str] = ["<td class='empty'></td>"] * first_weekday

    for current_date in month_dates:
        unavailable_count = len(
            {
                entry.personnel_id
                for entry in daily_entries.get(current_date, [])
                if centre == "Combined" or entry.centre == centre
            }
        )
        unavailable_ratio = unavailable_count / total_personnel

        if unavailable_ratio > 0.20:
            level = "high"
        elif unavailable_ratio > 0.10:
            level = "medium"
        else:
            level = "low"

        cells.append(
            "<td class='day {level}' title='{date}: {count} unavailable ({centre})'>"
            "<span class='day-number'>{day}</span>"
            "<span class='day-count'>{count}</span>"
            "</td>".format(
                level=level,
                date=current_date.strftime("%d %B %Y"),
                count=unavailable_count,
                day=current_date.day,
                centre=centre,
            )
        )

    while len(cells) % 7:
        cells.append("<td class='empty'></td>")

    rows = [
        "<tr>" + "".join(cells[index:index + 7]) + "</tr>"
        for index in range(0, len(cells), 7)
    ]

    calendar_html = f"""
    <style>
        .manpower-calendar {{
            width: 100%;
            max-width: 760px;
            border-collapse: separate;
            border-spacing: 5px;
            table-layout: fixed;
        }}
        .manpower-calendar th {{
            text-align: center;
            font-size: 0.78rem;
            font-weight: 600;
            opacity: 0.7;
            padding-bottom: 2px;
        }}
        .manpower-calendar td {{
            height: 58px;
            border-radius: 8px;
            padding: 6px 7px;
            vertical-align: top;
        }}
        .manpower-calendar .empty {{
            background: transparent;
        }}
        .manpower-calendar .day {{
            border: 1px solid rgba(128, 128, 128, 0.22);
        }}
        .manpower-calendar .low {{
            background: rgba(46, 160, 67, 0.18);
        }}
        .manpower-calendar .medium {{
            background: rgba(210, 153, 34, 0.24);
        }}
        .manpower-calendar .high {{
            background: rgba(248, 81, 73, 0.24);
        }}
        .manpower-calendar .day-number {{
            display: block;
            font-size: 0.82rem;
            font-weight: 700;
            line-height: 1;
        }}
        .manpower-calendar .day-count {{
            display: block;
            text-align: center;
            font-size: 1.08rem;
            font-weight: 700;
            margin-top: 8px;
        }}
        .manpower-legend {{
            display: flex;
            gap: 14px;
            flex-wrap: wrap;
            margin-top: 6px;
            font-size: 0.82rem;
            opacity: 0.84;
        }}
        .manpower-legend span::before {{
            content: "";
            display: inline-block;
            width: 11px;
            height: 11px;
            border-radius: 3px;
            margin-right: 5px;
            vertical-align: -1px;
        }}
        .legend-low::before {{ background: rgba(46, 160, 67, 0.55); }}
        .legend-medium::before {{ background: rgba(210, 153, 34, 0.65); }}
        .legend-high::before {{ background: rgba(248, 81, 73, 0.65); }}
    </style>
    <table class="manpower-calendar">
        <thead>
            <tr>
                <th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th>
                <th>Fri</th><th>Sat</th><th>Sun</th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    <div class="manpower-legend">
        <span class="legend-low">0–10% unavailable</span>
        <span class="legend-medium">&gt;10–20% unavailable</span>
        <span class="legend-high">&gt;20% unavailable</span>
    </div>
    """

    st.markdown(calendar_html, unsafe_allow_html=True)


@st.cache_data(ttl=30)
def load_cached_availability_codes() -> list[str]:
    """Load active availability codes from Supabase."""
    try:
        response = (
            get_supabase()
            .table("roster_availability_codes")
            .select("code")
            .eq("active", True)
            .order("display_order")
            .order("code")
            .execute()
        )

        codes = [
            str(row["code"]).strip().upper()
            for row in (response.data or [])
            if str(row.get("code", "")).strip()
        ]

        return codes or DEFAULT_AVAILABILITY_CODES.copy()

    except Exception:
        # Keep the page usable before the optional code table is created.
        return DEFAULT_AVAILABILITY_CODES.copy()


def add_availability_code(
    *,
    code: str,
    description: str | None = None,
) -> None:
    normalised_code = code.strip().upper()

    if not normalised_code:
        raise ValueError("Availability code cannot be blank.")

    if len(normalised_code) > 20:
        raise ValueError(
            "Availability code must contain no more than 20 characters."
        )

    payload = {
        "code": normalised_code,
        "description": (description or "").strip() or None,
        "active": True,
    }

    (
        get_supabase()
        .table("roster_availability_codes")
        .upsert(payload, on_conflict="code")
        .execute()
    )

    load_cached_availability_codes.clear()


def deactivate_availability_code(code: str) -> None:
    normalised_code = code.strip().upper()

    if not normalised_code:
        return

    (
        get_supabase()
        .table("roster_availability_codes")
        .update({"active": False})
        .eq("code", normalised_code)
        .execute()
    )

    load_cached_availability_codes.clear()


@st.cache_data(ttl=30)
def load_cached_personnel() -> list[PersonnelRecord]:
    return load_personnel_records()


def clear_page_cache() -> None:
    load_cached_personnel.clear()


@st.cache_data(ttl=30)
def load_roster_months() -> list[date]:
    """
    Load every roster month currently available in Supabase.
    """
    try:
        response = (
            get_supabase()
            .table("roster_months")
            .select("month_start")
            .order("month_start", desc=True)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(
            "Unable to load roster months from Supabase."
        ) from exc

    roster_months: list[date] = []

    for row in response.data or []:
        raw_value = row.get("month_start")

        if isinstance(raw_value, date):
            parsed_value = raw_value
        elif isinstance(raw_value, str):
            try:
                parsed_value = date.fromisoformat(
                    raw_value
                )
            except ValueError:
                continue
        else:
            continue

        roster_months.append(
            month_start(parsed_value)
        )

    return sorted(
        set(roster_months),
        reverse=True,
    )


def roster_month_label(
    value: date,
) -> str:
    return value.strftime("%b %y")


repository = AvailabilityRepository(
    get_supabase()
)

today = date.today()
current_month = today.replace(day=1)

try:
    available_roster_months = load_roster_months()
except Exception as exc:
    st.error(str(exc))
    st.stop()

month_column, create_column = st.columns(
    [4, 1]
)

selected_month: date | None = None

with month_column:
    if available_roster_months:
        stored_month_value = st.session_state.get(
            "selected_roster_month"
        )

        selected_index = 0

        if stored_month_value:
            try:
                stored_month = date.fromisoformat(
                    str(stored_month_value)
                )
            except ValueError:
                stored_month = None

            if stored_month in available_roster_months:
                selected_index = (
                    available_roster_months.index(
                        stored_month
                    )
                )
        elif current_month in available_roster_months:
            selected_index = (
                available_roster_months.index(
                    current_month
                )
            )

        selected_month = st.selectbox(
            "Roster month",
            options=available_roster_months,
            index=selected_index,
            format_func=roster_month_label,
            key="roster_month_selector",
        )

        st.session_state[
            "selected_roster_month"
        ] = selected_month.isoformat()
    else:
        st.info(
            "No roster months exist yet. "
            "Create the first month to begin."
        )

with create_column:
    st.write("")
    st.write("")

    if st.button(
        "＋ Create month",
        use_container_width=True,
    ):
        st.session_state[
            "show_create_roster_month"
        ] = True

if st.session_state.get(
    "show_create_roster_month",
    not available_roster_months,
):
    with st.expander(
        "Create roster month",
        expanded=True,
    ):
        with st.form(
            "create_roster_month_form"
        ):
            form_month, form_year = st.columns(2)

            with form_month:
                new_month_number = st.selectbox(
                    "Month",
                    options=list(range(1, 13)),
                    index=current_month.month - 1,
                    format_func=lambda number: (
                        month_name[number]
                    ),
                )

            with form_year:
                new_year = st.number_input(
                    "Year",
                    min_value=2020,
                    max_value=2100,
                    value=current_month.year,
                    step=1,
                )

            create_submitted = st.form_submit_button(
                "Create roster month",
                type="primary",
                use_container_width=True,
            )

        if create_submitted:
            requested_month = date(
                int(new_year),
                int(new_month_number),
                1,
            )

            try:
                repository.get_or_create_roster_month(
                    requested_month
                )
            except Exception as exc:
                st.error(
                    "Unable to create roster month: "
                    f"{exc}"
                )
            else:
                load_roster_months.clear()
                st.session_state[
                    "selected_roster_month"
                ] = requested_month.isoformat()
                st.session_state[
                    "show_create_roster_month"
                ] = False
                st.success(
                    f"{requested_month:%B %Y} is ready."
                )
                st.rerun()

if selected_month is None:
    st.stop()

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

availability_codes = load_cached_availability_codes()

# Preserve codes already stored in the selected month, including inactive ones.
stored_code_values: list[str] = []


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

stored_code_values = sorted(
    {
        entry.reason.strip().upper()
        for entry in stored_entries
        if entry.reason.strip()
    }
)

availability_codes = list(
    dict.fromkeys(
        [
            *availability_codes,
            *stored_code_values,
        ]
    )
)

matrix_availability_codes = [
    "",
    *availability_codes,
]


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

dashboard_tab, matrix_tab, entry_tab, review_tab = st.tabs(
    [
        "Dashboard",
        "Monthly matrix",
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

    st.subheader("Monthly manpower heatmap")

    heatmap_centre = st.segmented_control(
        "Heatmap centre",
        options=["Combined", "PT", "RH"],
        default="Combined",
        key="dashboard_heatmap_centre",
    )

    if heatmap_centre == "PT":
        heatmap_total_personnel = len(pt_personnel)
    elif heatmap_centre == "RH":
        heatmap_total_personnel = len(rh_personnel)
    else:
        heatmap_total_personnel = total_active_personnel

    st.caption(
        f"Showing {heatmap_centre} availability. Each date shows the number "
        "of personnel marked unavailable. Darker warning colours indicate "
        "a larger share of that centre's manpower."
    )

    render_manpower_calendar(
        selected_month=selected_month,
        month_last_day=month_last_day,
        daily_entries=daily_entries,
        total_personnel=heatmap_total_personnel,
        centre=heatmap_centre,
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

with matrix_tab:
    st.subheader(
        f"Monthly availability matrix — "
        f"{selected_month:%B %Y}"
    )

    st.caption(
        "Select an availability code in any date cell. "
        "Leave the cell blank when the person is available."
    )

    with st.expander("Manage availability codes", expanded=False):
        st.caption(
            "Add a reusable code to the matrix and manual-entry dropdowns. "
            "Codes are saved in uppercase."
        )

        code_column, description_column = st.columns([1, 2])

        with code_column:
            new_code = st.text_input(
                "New code",
                max_chars=20,
                placeholder="e.g. COURSE",
                key="new_availability_code",
            )

        with description_column:
            new_code_description = st.text_input(
                "Description",
                placeholder="Optional description",
                key="new_availability_code_description",
            )

        add_code_clicked = st.button(
            "Add or reactivate code",
            disabled=not new_code.strip(),
            key="add_availability_code",
        )

        if add_code_clicked:
            try:
                add_availability_code(
                    code=new_code,
                    description=new_code_description,
                )
                st.success(
                    f"Availability code {new_code.strip().upper()} is active."
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to save availability code: {exc}")

        if availability_codes:
            code_to_deactivate = st.selectbox(
                "Deactivate a code",
                options=["", *availability_codes],
                key="deactivate_availability_code_selection",
            )

            deactivate_clicked = st.button(
                "Deactivate selected code",
                disabled=not code_to_deactivate,
                key="deactivate_availability_code",
            )

            if deactivate_clicked:
                try:
                    deactivate_availability_code(code_to_deactivate)
                    st.success(
                        f"Availability code {code_to_deactivate} was deactivated. "
                        "Existing records are unchanged."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(
                        f"Unable to deactivate availability code: {exc}"
                    )

    matrix_filter_column, matrix_info_column = (
        st.columns([1, 2])
    )

    with matrix_filter_column:
        matrix_centre_filter = st.selectbox(
            "Centre",
            options=[
                "All",
                "PT",
                "RH",
            ],
            key="matrix_centre_filter",
        )

    with matrix_info_column:
        st.info(
            "Changes are not written to Supabase until "
            "you select **Save matrix changes**."
        )

    filtered_matrix_personnel = [
        record
        for record in personnel_records
        if (
            matrix_centre_filter == "All"
            or record.person.centre
            == matrix_centre_filter
        )
    ]

    month_dates = dates_between(
        selected_month,
        month_last_day,
    )

    matrix_rows = build_availability_matrix(
        personnel_records=filtered_matrix_personnel,
        stored_entries=stored_entries,
        month_dates=month_dates,
    )

    matrix_column_config: dict[
        str,
        object,
    ] = {
        "personnel_id": None,
        "Centre": st.column_config.TextColumn(
            "Centre",
            disabled=True,
            width="small",
            pinned=True,
        ),
        "Rank": st.column_config.TextColumn(
            "Rank",
            disabled=True,
            width="small",
            pinned=True,
        ),
        "Personnel": st.column_config.TextColumn(
            "Personnel",
            disabled=True,
            width="medium",
            pinned=True,
        ),
    }

    for current_date in month_dates:
        column_name = matrix_date_column_name(
            current_date
        )

        matrix_column_config[
            column_name
        ] = st.column_config.SelectboxColumn(
            column_name,
            options=matrix_availability_codes,
            required=False,
            width="small",
        )

    edited_matrix = st.data_editor(
        matrix_rows,
        column_config=matrix_column_config,
        disabled=[
            "Centre",
            "Rank",
            "Personnel",
        ],
        hide_index=True,
        use_container_width=True,
        height=min(
            900,
            90
            + len(matrix_rows) * 35,
        ),
        key=(
            "availability_matrix_"
            f"{selected_month:%Y_%m}_"
            f"{matrix_centre_filter}"
        ),
    )

    matrix_entry_lookup = {
        (
            entry.personnel_id,
            entry.unavailable_date,
        ): entry
        for entry in stored_entries
        if (
            matrix_centre_filter == "All"
            or entry.centre
            == matrix_centre_filter
        )
    }

    original_matrix_values = {
        key: entry.reason
        for key, entry
        in matrix_entry_lookup.items()
    }

    edited_matrix_values = (
        matrix_values_by_person_and_date(
            matrix_rows=edited_matrix,
            month_dates=month_dates,
        )
    )

    changed_cells: list[
        tuple[str, date, str, str]
    ] = []

    for key, edited_value in (
        edited_matrix_values.items()
    ):
        original_value = (
            original_matrix_values.get(
                key,
                "",
            )
        )

        if edited_value != original_value:
            personnel_id, unavailable_date = key

            changed_cells.append(
                (
                    personnel_id,
                    unavailable_date,
                    original_value,
                    edited_value,
                )
            )

    st.caption(
        f"{len(changed_cells)} unsaved "
        f"change"
        f"{'' if len(changed_cells) == 1 else 's'}."
    )

    if changed_cells:
        changed_personnel_lookup = {
            record.id: record
            for record in filtered_matrix_personnel
        }

        with st.expander(
            "Review unsaved changes",
            expanded=False,
        ):
            change_preview_rows = []

            for (
                personnel_id,
                unavailable_date,
                old_value,
                new_value,
            ) in changed_cells:
                record = (
                    changed_personnel_lookup[
                        personnel_id
                    ]
                )

                change_preview_rows.append(
                    {
                        "Personnel": (
                            record.person.name
                        ),
                        "Centre": (
                            record.person.centre
                        ),
                        "Date": unavailable_date,
                        "Previous": (
                            old_value or "Available"
                        ),
                        "New": (
                            new_value or "Available"
                        ),
                    }
                )

            st.dataframe(
                change_preview_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Date": (
                        st.column_config.DateColumn(
                            "Date",
                            format="DD/MM/YYYY",
                        )
                    ),
                },
            )

    save_matrix_changes = st.button(
        "Save matrix changes",
        type="primary",
        disabled=not changed_cells,
        key="save_availability_matrix",
    )

    if save_matrix_changes:
        save_errors: list[str] = []
        saved_changes = 0

        progress_bar = st.progress(
            0,
            text="Saving matrix changes...",
        )

        total_changes = len(changed_cells)
        roster_month = repository.get_or_create_roster_month(
            selected_month
        )

        for change_number, (
            personnel_id,
            unavailable_date,
            old_value,
            new_value,
        ) in enumerate(
            changed_cells,
            start=1,
        ):
            try:
                existing_entry = (
                    matrix_entry_lookup.get(
                        (
                            personnel_id,
                            unavailable_date,
                        )
                    )
                )

                if new_value:
                    repository.add_availability_entry(
                        roster_month_id=roster_month.id,
                        personnel_id=personnel_id,
                        unavailable_date=(
                            unavailable_date
                        ),
                        reason=new_value,
                        source="manual",
                        notes=None,
                    )

                elif existing_entry is not None:
                    repository.delete_availability_entry(
                        existing_entry.id
                    )

                saved_changes += 1

            except Exception as exc:
                record = next(
                    (
                        item
                        for item
                        in filtered_matrix_personnel
                        if item.id
                        == personnel_id
                    ),
                    None,
                )

                person_name = (
                    record.person.name
                    if record is not None
                    else personnel_id
                )

                save_errors.append(
                    f"{person_name}, "
                    f"{unavailable_date:%d/%m/%Y}: "
                    f"{exc}"
                )

            progress_bar.progress(
                change_number
                / total_changes,
                text=(
                    f"Saving change "
                    f"{change_number} of "
                    f"{total_changes}..."
                ),
            )

        progress_bar.empty()

        if save_errors:
            st.error(
                f"Saved {saved_changes} change(s), "
                f"but {len(save_errors)} failed."
            )

            with st.expander(
                "View save errors",
                expanded=True,
            ):
                for error_message in save_errors:
                    st.write(
                        f"- {error_message}"
                    )

        else:
            st.success(
                f"Saved {saved_changes} "
                f"matrix change(s)."
            )

            st.rerun()

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
        options=availability_codes,
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
            *availability_codes,
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