from __future__ import annotations

from calendar import monthrange
from datetime import date

import streamlit as st

from roster_engine.cover_repository import CoverRepository
from roster_engine.database import get_supabase


SESSION_OPTIONS = ["AM", "PM", "FULL_DAY"]
SESSION_LABELS = {
    "AM": "AM",
    "PM": "PM",
    "FULL_DAY": "Full day",
}

st.set_page_config(
    page_title="Cover Planner",
    page_icon="🩺",
    layout="wide",
)

st.title("Cover Planner")
st.caption(
    "Plan monthly cover requirements and manage the cover catalogue "
    "used by the roster generator."
)

def legacy_category_for_type(
    cover_type: str,
) -> str:
    value = " ".join(
        cover_type.strip().upper().split()
    )

    if value in {
        "FC",
        "GP",
        "GX",
    }:
        return value

    return "NON_FC"

def month_start(value: date) -> date:
    return value.replace(day=1)


def month_end(value: date) -> date:
    return date(
        value.year,
        value.month,
        monthrange(value.year, value.month)[1],
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

    rows = []
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
                "month_start": month_start(parsed),
                "status": str(row.get("status") or "draft"),
            }
        )

    return rows


@st.cache_data(ttl=20)
def load_cover_types(
    *,
    include_inactive: bool = False,
):
    repository = CoverRepository(get_supabase())
    return repository.list_cover_types(
        include_inactive=include_inactive
    )


@st.cache_data(ttl=15)
def load_cover_requirements(
    roster_month_id: str,
):
    repository = CoverRepository(get_supabase())
    return repository.list_month_requirements(
        roster_month_id
    )


def clear_cover_type_cache() -> None:
    load_cover_types.clear()


def clear_cover_requirement_cache() -> None:
    load_cover_requirements.clear()




try:
    roster_months = load_roster_months()
    all_cover_types = [
        {
            "id": item.id,
            "category": item.category,
            "cover_type": item.cover_type,
            "points": item.points,
            "default_session": item.default_session,
            "is_active": item.is_active,
            "display_order": item.display_order,
            "notes": item.notes,
        }
        for item in load_cover_types(
            include_inactive=True
        )
    ]
except Exception as exc:
    st.error(
        "Unable to load Cover Planner data. Run the latest SQL "
        f"migration first.\n\n{exc}"
    )
    st.stop()

if not roster_months:
    st.warning(
        "Create a roster month before adding cover requirements."
    )
    st.stop()

stored_month = st.session_state.get(
    "selected_roster_month"
)
default_index = 0

if stored_month:
    for index, item in enumerate(roster_months):
        if (
            item["month_start"].isoformat()
            == str(stored_month)
        ):
            default_index = index
            break

selected_month_record = st.selectbox(
    "Roster month",
    options=roster_months,
    index=default_index,
    format_func=lambda item: (
        item["month_start"].strftime("%b %y")
    ),
)

selected_month = selected_month_record[
    "month_start"
]
selected_month_end = month_end(
    selected_month
)
roster_month_id = selected_month_record["id"]

st.session_state[
    "selected_roster_month"
] = selected_month.isoformat()

try:
    stored_requirements = load_cover_requirements(
        roster_month_id
    )
    requirements = [
        {
            "id": item.id,
            "roster_month_id": item.roster_month_id,
            "requesting_unit": item.requesting_unit,
            "cover_category": item.cover_category,
            "cover_type": item.cover_type,
            "cover_type_id": item.cover_type_id,
            "points": item.points,
            "session": item.session,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "personnel_required": item.personnel_required,
            "mandatory": item.mandatory,
            "remarks": item.remarks,
        }
        for item in stored_requirements
    ]
except Exception as exc:
    st.error(
        "Unable to load cover requirements. "
        f"Run the latest migration first.\n\n{exc}"
    )
    st.stop()

cover_type_lookup = {
    str(row["id"]): row
    for row in all_cover_types
}

active_cover_types = [
    row
    for row in all_cover_types
    if bool(row.get("is_active", True))
]

cover_repository = CoverRepository(get_supabase())
expanded_cover_slots = cover_repository.expand_daily_slots(
    stored_requirements
)

expanded_slots = sum(
    1
    for slot in expanded_cover_slots
    if not slot.is_reserve
)

derived_fc_reserves = sum(
    1
    for slot in expanded_cover_slots
    if slot.is_reserve
)

m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "Requirements",
    len(requirements),
)

m2.metric(
    "Active cover slots",
    expanded_slots,
)

m3.metric(
    "Derived FC reserves",
    derived_fc_reserves,
)

m4.metric(
    "Total generated slots",
    expanded_slots + derived_fc_reserves,
)

st.divider()

(
    add_tab,
    planner_tab,
    daily_tab,
    types_tab,
) = st.tabs(
    [
        "Add requirement",
        "Planner table",
        "Daily requirement preview",
        "Cover Types",
    ]
)


with add_tab:
    st.subheader(
        "New cover requirement"
    )
    st.caption(
        "Selections update immediately. Nothing is saved until "
        "Add cover requirement is clicked."
    )

    if not active_cover_types:
        st.warning(
            "No active cover types are configured. "
            "Add or reactivate one in Cover Types."
        )
    else:
        c1, c2 = st.columns(2)

        with c1:
            requesting_unit = st.text_input(
                "Requesting unit",
                placeholder="e.g. 1 COY",
                key="cover_requesting_unit",
            )

        type_by_id = {
            str(row["id"]): row
            for row in active_cover_types
        }

        with c2:
            selected_type_id = st.selectbox(
                "Cover type",
                options=list(type_by_id),
                format_func=lambda item_id: str(
                    type_by_id[item_id]["cover_type"]
                ),
                key="cover_type",
            )

        selected_type = type_by_id[
            selected_type_id
        ]

        cover_type = str(
            selected_type["cover_type"]
        )

        points = float(
            selected_type.get("points")
            or 0.0
        )

        d1, d2, d3, d4 = (
            st.columns(4)
        )

        with d1:
            start_date = st.date_input(
                "Start date",
                value=selected_month,
                min_value=selected_month,
                max_value=selected_month_end,
                format="DD/MM/YYYY",
                key="cover_start_date",
            )

        with d2:
            end_date = st.date_input(
                "End date",
                value=start_date,
                min_value=selected_month,
                max_value=selected_month_end,
                format="DD/MM/YYYY",
                key="cover_end_date",
            )

        default_session = (
            selected_type.get(
                "default_session"
            )
        )

        session_index = (
            SESSION_OPTIONS.index(
                default_session
            )
            if default_session
            in SESSION_OPTIONS
            else 2
        )

        with d3:
            session = st.selectbox(
                "Session",
                options=SESSION_OPTIONS,
                index=session_index,
                format_func=lambda value: (
                    SESSION_LABELS[value]
                ),
                key=(
                    "cover_session_"
                    f"{selected_type_id}"
                ),
            )

        with d4:
            personnel_required = (
                st.number_input(
                    "Personnel required",
                    min_value=1,
                    max_value=20,
                    value=1,
                    step=1,
                    key=(
                        "cover_personnel_required"
                    ),
                )
            )

        mandatory = st.checkbox(
            "Mandatory requirement",
            value=True,
            key="cover_mandatory",
        )

        remarks = st.text_area(
            "Remarks",
            placeholder=(
                "Optional operational details"
            ),
            key="cover_remarks",
        )

        day_count = (
            (end_date - start_date).days
            + 1
            if end_date >= start_date
            else 0
        )

        active_slots = (
            day_count
            * int(personnel_required)
        )

        if cover_type == "FC":
            # Mirrors CoverRepository.expand_daily_slots():
            # ceil(active FC / 2) reserves per day.
            daily_reserves = (
                int(personnel_required) + 1
            ) // 2

            reserve_slots = (
                day_count
                * daily_reserves
            )

            st.info(
                f"{cover_type}: "
                f"{points:g} point(s) per assigned cover. "
                f"This creates {active_slots} active FC slot(s) "
                f"and {reserve_slots} derived FC reserve slot(s) "
                f"across {day_count} day(s)."
            )
        else:
            st.info(
                f"{cover_type}: "
                f"{points:g} point(s) per assigned cover. "
                f"This creates {active_slots} active slot(s) "
                f"across {day_count} day(s)."
            )

        if end_date < start_date:
            st.error(
                "End date cannot be before start date."
            )

        if st.button(
            "Add cover requirement",
            type="primary",
            use_container_width=True,
            key=(
                "add_cover_requirement_button"
            ),
            disabled=(
                end_date < start_date
            ),
        ):
            if not requesting_unit.strip():
                st.error(
                    "Requesting unit is required."
                )
            else:
                payload = {
                    "roster_month_id": (
                        roster_month_id
                    ),
                    "requesting_unit": (
                        requesting_unit
                        .strip()
                        .upper()
                    ),
                    # Legacy compatibility only; cover_type is now
                    # the application source of truth.
                   "cover_category": (
                        legacy_category_for_type(
                            cover_type
                        )
                    ),
                    "cover_type": (
                        cover_type
                    ),
                    "cover_type_id": (
                        selected_type_id
                    ),
                    "points_snapshot": (
                        points
                    ),
                    "session": session,
                    "start_date": (
                        start_date
                        .isoformat()
                    ),
                    "end_date": (
                        end_date
                        .isoformat()
                    ),
                    "personnel_required": (
                        int(
                            personnel_required
                        )
                    ),
                    "mandatory": (
                        bool(mandatory)
                    ),
                    "remarks": (
                        remarks.strip()
                        or None
                    ),
                }

                try:
                    (
                        get_supabase()
                        .table(
                            "roster_cover_requirements"
                        )
                        .insert(payload)
                        .execute()
                    )
                except Exception as exc:
                    st.error(
                        "Unable to add "
                        f"requirement: {exc}"
                    )
                else:
                    clear_cover_requirement_cache()
                    st.success(
                        "Cover requirement added."
                    )
                    st.rerun()


with planner_tab:
    st.subheader(
        "Cover requirements — "
        f"{selected_month:%B %Y}"
    )

    if not requirements:
        st.info(
            "No cover requirements have been added."
        )
    else:
        rows = []

        for item in requirements:
            quantity = int(
                item[
                    "personnel_required"
                ]
            )

            days = (
                item["end_date"] - item["start_date"]
            ).days + 1

            rows.append(
                {
                    "ID": item["id"],
                    "Unit": (
                        item[
                            "requesting_unit"
                        ]
                    ),
                    "Cover type": (
                        item["cover_type"]
                    ),
                    "Session": (
                        SESSION_LABELS.get(
                            str(
                                item["session"]
                            ),
                            str(
                                item["session"]
                            ),
                        )
                    ),
                    "Start": item["start_date"],
                    "End": item["end_date"],
                    "Qty/day": quantity,
                    "Points": float(item["points"]),
                    "Active slots": (
                        days * quantity
                    ),
                    "Mandatory": bool(
                        item["mandatory"]
                    ),
                    "Remarks": (
                        item.get("remarks")
                        or ""
                    ),
                }
            )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            height=min(
                700,
                90 + len(rows) * 35,
            ),
            column_config={
                "ID": None,
                "Start": (
                    st.column_config.DateColumn(
                        "Start",
                        format="DD MMM",
                    )
                ),
                "End": (
                    st.column_config.DateColumn(
                        "End",
                        format="DD MMM",
                    )
                ),
                "Points": (
                    st.column_config.NumberColumn(
                        "Points",
                        format="%.2f",
                    )
                ),
                "Mandatory": (
                    st.column_config.CheckboxColumn(
                        "Mandatory"
                    )
                ),
            },
        )

        st.divider()
        st.subheader(
            "Delete requirement"
        )

        requirement_by_id = {
            str(item["id"]): item
            for item in requirements
        }

        delete_id = st.selectbox(
            "Select requirement",
            options=list(
                requirement_by_id
            ),
            format_func=lambda item_id: (
                f"{requirement_by_id[item_id]['requesting_unit']} — "
                f"{requirement_by_id[item_id]['cover_type']} — "
                f"{requirement_by_id[item_id]['start_date']:%d %b} to "
                f"{requirement_by_id[item_id]['end_date']:%d %b}"
            ),
        )

        confirm_delete = st.checkbox(
            "Confirm deletion",
            key=(
                "confirm_cover_requirement_delete"
            ),
        )

        if st.button(
            "Delete selected requirement",
            disabled=not confirm_delete,
        ):
            try:
                (
                    get_supabase()
                    .table(
                        "roster_cover_requirements"
                    )
                    .delete()
                    .eq(
                        "id",
                        delete_id,
                    )
                    .execute()
                )
            except Exception as exc:
                st.error(
                    "Unable to delete "
                    f"requirement: {exc}"
                )
            else:
                clear_cover_requirement_cache()
                st.success(
                    "Cover requirement deleted."
                )
                st.rerun()


with daily_tab:
    st.subheader(
        "Daily expanded requirement preview"
    )

    st.caption(
        "FC reserve slots are derived automatically as "
        "ceil(active FC / 2)."
    )

    preview_date = st.date_input(
        "Preview date",
        value=selected_month,
        min_value=selected_month,
        max_value=selected_month_end,
        format="DD/MM/YYYY",
        key="cover_daily_preview_date",
    )

    preview_slots = [
        slot
        for slot in expanded_cover_slots
        if slot.duty_date == preview_date
    ]

    grouped_daily_slots: dict[tuple, dict] = {}

    for slot in preview_slots:
        key = (
            slot.requesting_unit,
            slot.cover_type,
            slot.session,
            slot.points,
            slot.mandatory,
            slot.is_reserve,
        )

        if key not in grouped_daily_slots:
            grouped_daily_slots[key] = {
                "Date": preview_date,
                "Unit": slot.requesting_unit,
                "Cover type": slot.cover_type,
                "Session": SESSION_LABELS.get(
                    slot.session,
                    slot.session,
                ),
                "Slots": 0,
                "Points each": slot.points,
                "Mandatory": slot.mandatory,
                "Derived": slot.is_reserve,
            }

        grouped_daily_slots[key]["Slots"] += 1

    daily_rows = list(grouped_daily_slots.values())

    active_slots = sum(
        int(row["Slots"])
        for row in daily_rows
        if not row["Derived"]
    )

    reserve_slots = sum(
        int(row["Slots"])
        for row in daily_rows
        if row["Derived"]
    )

    p1, p2, p3 = st.columns(3)

    p1.metric(
        "Active cover slots",
        active_slots,
    )

    p2.metric(
        "FC reserve slots",
        reserve_slots,
    )

    p3.metric(
        "Total personnel needed",
        active_slots + reserve_slots,
    )

    if not daily_rows:
        st.info(
            "No cover requirements fall on this date."
        )
    else:
        st.dataframe(
            daily_rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": (
                    st.column_config.DateColumn(
                        "Date",
                        format=(
                            "DD MMM YYYY"
                        ),
                    )
                ),
                "Points each": (
                    st.column_config.NumberColumn(
                        "Points",
                        format="%.2f",
                    )
                ),
                "Mandatory": (
                    st.column_config.CheckboxColumn(
                        "Mandatory"
                    )
                ),
                "Derived": (
                    st.column_config.CheckboxColumn(
                        "Derived"
                    )
                ),
            },
        )


with types_tab:
    st.subheader(
        "Cover Type Management"
    )

    st.caption(
        "Add, edit, deactivate, or reactivate cover types. "
        "Deactivation is preferred to deletion so historical "
        "requirements remain intact."
    )

    active_count = sum(
        1
        for row in all_cover_types
        if bool(
            row.get(
                "is_active",
                True,
            )
        )
    )

    t1, t2 = st.columns(2)

    t1.metric(
        "Active cover types",
        active_count,
    )

    t2.metric(
        "Inactive cover types",
        (
            len(all_cover_types)
            - active_count
        ),
    )

    if all_cover_types:
        display_rows = []

        for row in all_cover_types:
            display_rows.append(
                {
                    "ID": row["id"],
                    "Order": int(
                        row.get(
                            "display_order"
                        )
                        or 0
                    ),
                    "Cover type": (
                        row["cover_type"]
                    ),
                    "Points": float(
                        row.get("points")
                        or 0.0
                    ),
                    "Default session": (
                        SESSION_LABELS.get(
                            str(
                                row.get(
                                    "default_session"
                                )
                            ),
                            "Not set",
                        )
                        if row.get(
                            "default_session"
                        )
                        else "Not set"
                    ),
                    "Active": bool(
                        row.get(
                            "is_active",
                            True,
                        )
                    ),
                    "Notes": (
                        row.get("notes")
                        or ""
                    ),
                }
            )

        st.dataframe(
            display_rows,
            use_container_width=True,
            hide_index=True,
            height=min(
                650,
                90
                + len(
                    display_rows
                )
                * 35,
            ),
            column_config={
                "ID": None,
                "Points": (
                    st.column_config.NumberColumn(
                        "Points",
                        format="%.2f",
                    )
                ),
                "Active": (
                    st.column_config.CheckboxColumn(
                        "Active"
                    )
                ),
            },
        )
    else:
        st.info(
            "No cover types have been configured."
        )

    st.divider()
    st.markdown(
        "#### Add cover type"
    )

    a1, a2, a3 = (
        st.columns(3)
    )

    with a1:
        new_name = st.text_input(
            "Cover type",
            key="new_cover_type_name",
        )

    with a2:
        new_points = st.number_input(
            "Points",
            min_value=0.0,
            value=0.5,
            step=0.5,
            key="new_cover_type_points",
        )

    with a3:
        new_session_label = (
            st.selectbox(
                "Default session",
                options=[
                    "Not set",
                    "AM",
                    "PM",
                    "Full day",
                ],
                key=(
                    "new_cover_type_session"
                ),
            )
        )

    new_order = st.number_input(
        "Display order",
        min_value=0,
        value=0,
        step=1,
        key="new_cover_type_order",
    )

    new_notes = st.text_input(
        "Notes",
        key="new_cover_type_notes",
    )

    if st.button(
        "Add cover type",
        type="primary",
        key="add_cover_type_button",
    ):
        if not new_name.strip():
            st.error(
                "Cover type name is required."
            )
        else:
            session_map = {
                "Not set": None,
                "AM": "AM",
                "PM": "PM",
                "Full day": "FULL_DAY",
            }

            normalised_type = (
                new_name
                .strip()
                .upper()
            )

            payload = {
                # Compatibility with the legacy Supabase category constraint.
                "category": legacy_category_for_type(
                    normalised_type
                ),
                "cover_type": normalised_type,
                "points": float(
                    new_points
                ),
                "default_session": (
                    session_map[
                        new_session_label
                    ]
                ),
                "is_active": True,
                "display_order": int(
                    new_order
                ),
                "notes": (
                    new_notes.strip()
                    or None
                ),
            }

            try:
                (
                    get_supabase()
                    .table(
                        "roster_cover_types"
                    )
                    .insert(payload)
                    .execute()
                )
            except Exception as exc:
                st.error(
                    "Unable to add cover type. "
                    "The same cover type may already exist.\n\n"
                    f"{exc}"
                )
            else:
                clear_cover_type_cache()
                st.success(
                    "Cover type added."
                )
                st.rerun()

    if all_cover_types:
        st.divider()
        st.markdown(
            "#### Edit cover type"
        )

        type_lookup = {
            str(row["id"]): row
            for row in all_cover_types
        }

        selected_edit_id = (
            st.selectbox(
                "Select cover type",
                options=list(
                    type_lookup
                ),
                format_func=lambda item_id: (
                    f"{type_lookup[item_id]['cover_type']}"
                ),
                key=(
                    "edit_cover_type_selector"
                ),
            )
        )

        selected_edit = (
            type_lookup[
                selected_edit_id
            ]
        )

        e1, e2, e3 = (
            st.columns(3)
        )

        with e1:
            edit_name = st.text_input(
                "Cover type",
                value=str(
                    selected_edit[
                        "cover_type"
                    ]
                ),
                key=(
                    "edit_name_"
                    f"{selected_edit_id}"
                ),
            )

        with e2:
            edit_points = (
                st.number_input(
                    "Points",
                    min_value=0.0,
                    value=float(
                        selected_edit.get(
                            "points"
                        )
                        or 0.0
                    ),
                    step=0.5,
                    key=(
                        "edit_points_"
                        f"{selected_edit_id}"
                    ),
                )
            )

        reverse_session = {
            None: "Not set",
            "AM": "AM",
            "PM": "PM",
            "FULL_DAY": (
                "Full day"
            ),
        }

        current_session_label = (
            reverse_session.get(
                selected_edit.get(
                    "default_session"
                ),
                "Not set",
            )
        )

        session_labels = [
            "Not set",
            "AM",
            "PM",
            "Full day",
        ]

        with e3:
            edit_session_label = (
                st.selectbox(
                    "Default session",
                    options=session_labels,
                    index=(
                        session_labels.index(
                            current_session_label
                        )
                    ),
                    key=(
                        "edit_session_"
                        f"{selected_edit_id}"
                    ),
                )
            )

        edit_order = st.number_input(
            "Display order",
            min_value=0,
            value=int(
                selected_edit.get(
                    "display_order"
                )
                or 0
            ),
            step=1,
            key=(
                "edit_order_"
                f"{selected_edit_id}"
            ),
        )

        edit_active = st.checkbox(
            "Active",
            value=bool(
                selected_edit.get(
                    "is_active",
                    True,
                )
            ),
            key=(
                "edit_active_"
                f"{selected_edit_id}"
            ),
        )

        edit_notes = st.text_input(
            "Notes",
            value=str(
                selected_edit.get(
                    "notes"
                )
                or ""
            ),
            key=(
                "edit_notes_"
                f"{selected_edit_id}"
            ),
        )

        if st.button(
            "Save cover type changes",
            type="primary",
            key=(
                "save_cover_type_"
                f"{selected_edit_id}"
            ),
        ):
            if not edit_name.strip():
                st.error(
                    "Cover type name is required."
                )
            else:
                session_map = {
                    "Not set": None,
                    "AM": "AM",
                    "PM": "PM",
                    "Full day": (
                        "FULL_DAY"
                    ),
                }

                normalised_type = (
                    edit_name
                    .strip()
                    .upper()
                )

                payload = {
                    "category": legacy_category_for_type(
                        normalised_type
                    ),
                    "cover_type": normalised_type,
                    "points": float(
                        edit_points
                    ),
                    "default_session": (
                        session_map[
                            edit_session_label
                        ]
                    ),
                    "display_order": int(
                        edit_order
                    ),
                    "is_active": bool(
                        edit_active
                    ),
                    "notes": (
                        edit_notes.strip()
                        or None
                    ),
                }

                try:
                    (
                        get_supabase()
                        .table(
                            "roster_cover_types"
                        )
                        .update(payload)
                        .eq(
                            "id",
                            selected_edit_id,
                        )
                        .execute()
                    )
                except Exception as exc:
                    st.error(
                        "Unable to update "
                        f"cover type.\n\n{exc}"
                    )
                else:
                    clear_cover_type_cache()
                    st.success(
                        "Cover type updated."
                    )
                    st.rerun()
