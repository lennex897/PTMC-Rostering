from __future__ import annotations

from calendar import monthrange
from datetime import date

import streamlit as st

from roster_engine.database import get_supabase


st.set_page_config(
    page_title="Manual Planning",
    page_icon="📌",
    layout="wide",
)

st.title("Manual Planning")
st.caption(
    "Lock selected duties and covers before roster generation. "
    "The future generator will preserve these assignments and fill the remainder."
)


DUTY_ROLES = [
    "DM",
    "CS1",
    "CS2",
    "CS/B",
    "SB1",
    "SB2",
    "AE",
]

CENTRES = ["PT", "RH"]

SESSION_LABELS = {
    "AM": "AM",
    "PM": "PM",
    "FULL_DAY": "Full day",
}


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
    for item in response.data or []:
        raw = item.get("month_start")
        if not raw:
            continue

        parsed = (
            raw if isinstance(raw, date)
            else date.fromisoformat(str(raw))
        )

        rows.append({
            "id": str(item["id"]),
            "month_start": parsed.replace(day=1),
            "status": item.get("status") or "draft",
        })

    return rows


@st.cache_data(ttl=20)
def load_personnel() -> list[dict]:
    response = (
        get_supabase()
        .table("roster_personnel")
        .select("name,centre,is_active,is_cover_fit")
        .eq("is_active", True)
        .order("name")
        .execute()
    )
    return list(response.data or [])


@st.cache_data(ttl=15)
def load_cover_requirements(roster_month_id: str) -> list[dict]:
    response = (
        get_supabase()
        .table("roster_cover_requirements")
        .select(
            "id,requesting_unit,cover_category,cover_type,session,"
            "start_date,end_date,personnel_required,mandatory,remarks"
        )
        .eq("roster_month_id", roster_month_id)
        .order("start_date")
        .execute()
    )
    return list(response.data or [])


@st.cache_data(ttl=15)
def load_manual_assignments(roster_month_id: str) -> list[dict]:
    response = (
        get_supabase()
        .table("roster_manual_assignments")
        .select(
            "id,personnel_name,assignment_date,assignment_kind,centre,"
            "role_name,cover_requirement_id,cover_label,session,"
            "is_locked,allow_override,remarks"
        )
        .eq("roster_month_id", roster_month_id)
        .order("assignment_date")
        .order("personnel_name")
        .execute()
    )
    return list(response.data or [])


@st.cache_data(ttl=15)
def load_availability(roster_month_id: str) -> list[dict]:
    response = (
        get_supabase()
        .table("roster_availability")
        .select("person_name,availability_date,code")
        .eq("roster_month_id", roster_month_id)
        .execute()
    )
    return list(response.data or [])


def clear_manual_cache() -> None:
    load_manual_assignments.clear()


def requirement_contains_date(requirement: dict, current_date: date) -> bool:
    start = date.fromisoformat(str(requirement["start_date"]))
    end = date.fromisoformat(str(requirement["end_date"]))
    return start <= current_date <= end


def get_availability_code(
    availability_rows: list[dict],
    person_name: str,
    current_date: date,
) -> str | None:
    for row in availability_rows:
        if (
            str(row.get("person_name")) == person_name
            and str(row.get("availability_date")) == current_date.isoformat()
        ):
            return str(row.get("code") or "").upper() or None
    return None


try:
    months = load_roster_months()
    personnel = load_personnel()
except Exception as exc:
    st.error(f"Unable to load planning data: {exc}")
    st.stop()

if not months:
    st.warning("Create a roster month first.")
    st.stop()

stored_month = st.session_state.get("selected_roster_month")
default_index = 0

if stored_month:
    for idx, item in enumerate(months):
        if item["month_start"].isoformat() == str(stored_month):
            default_index = idx
            break

selected_month_record = st.selectbox(
    "Roster month",
    options=months,
    index=default_index,
    format_func=lambda item: item["month_start"].strftime("%b %y"),
)

selected_month = selected_month_record["month_start"]
selected_month_end = month_end(selected_month)
roster_month_id = selected_month_record["id"]

st.session_state["selected_roster_month"] = selected_month.isoformat()

try:
    cover_requirements = load_cover_requirements(roster_month_id)
    manual_assignments = load_manual_assignments(roster_month_id)
    availability_rows = load_availability(roster_month_id)
except Exception as exc:
    st.error(
        "Unable to load manual-planning data. Make sure the SQL migration "
        f"has been applied.\n\n{exc}"
    )
    st.stop()

active_people = [
    row for row in personnel
    if bool(row.get("is_active", True))
]

person_by_name = {
    str(row["name"]): row
    for row in active_people
}

cover_fit_names = sorted(
    str(row["name"])
    for row in active_people
    if bool(row.get("is_cover_fit"))
)

all_person_names = sorted(person_by_name)

metric_1, metric_2, metric_3 = st.columns(3)
metric_1.metric("Locked assignments", len(manual_assignments))
metric_2.metric(
    "Locked duties",
    sum(
        1 for row in manual_assignments
        if row["assignment_kind"] == "DUTY"
    ),
)
metric_3.metric(
    "Locked covers",
    sum(
        1 for row in manual_assignments
        if row["assignment_kind"] in ("COVER", "COVER_RESERVE")
    ),
)

st.divider()

duty_tab, cover_tab, review_tab = st.tabs(
    ["Manual duties", "Manual covers", "Review locked assignments"]
)

with duty_tab:
    st.subheader("Lock a duty assignment")

    with st.form("manual_duty_form"):
        c1, c2, c3, c4 = st.columns([1.1, 1.5, 1, 1])

        with c1:
            duty_date = st.date_input(
                "Date",
                value=selected_month,
                min_value=selected_month,
                max_value=selected_month_end,
                format="DD/MM/YYYY",
                key="manual_duty_date",
            )

        with c2:
            duty_person = st.selectbox(
                "Personnel",
                options=all_person_names,
                key="manual_duty_person",
            )

        with c3:
            duty_centre = st.selectbox(
                "Centre",
                options=CENTRES,
                key="manual_duty_centre",
            )

        with c4:
            duty_role = st.selectbox(
                "Role",
                options=DUTY_ROLES,
                key="manual_duty_role",
            )

        allow_override = st.checkbox(
            "Allow manual override if this conflicts with availability",
            value=False,
            key="manual_duty_override",
        )

        duty_remarks = st.text_input(
            "Remarks",
            key="manual_duty_remarks",
        )

        availability_code = get_availability_code(
            availability_rows,
            duty_person,
            duty_date,
        )

        if availability_code:
            st.warning(
                f"{duty_person} has availability code "
                f"{availability_code} on {duty_date:%d %b %Y}."
            )

        submit_duty = st.form_submit_button(
            "Lock duty",
            type="primary",
            use_container_width=True,
        )

    if submit_duty:
        payload = {
            "roster_month_id": roster_month_id,
            "personnel_name": duty_person,
            "assignment_date": duty_date.isoformat(),
            "assignment_kind": "DUTY",
            "centre": duty_centre,
            "role_name": duty_role,
            "cover_requirement_id": None,
            "cover_label": None,
            "session": "FULL_DAY",
            "is_locked": True,
            "allow_override": allow_override,
            "remarks": duty_remarks.strip() or None,
        }

        try:
            (
                get_supabase()
                .table("roster_manual_assignments")
                .insert(payload)
                .execute()
            )
        except Exception as exc:
            st.error(f"Unable to save manual duty: {exc}")
        else:
            clear_manual_cache()
            st.success("Duty locked.")
            st.rerun()


with cover_tab:
    st.subheader("Lock a cover assignment")

    if not cover_requirements:
        st.info(
            "No cover requirements exist for this month. "
            "Add them in Cover Planner first."
        )
    elif not cover_fit_names:
        st.warning("No active Cover Fit personnel are available.")
    else:
        cover_date = st.date_input(
            "Cover date",
            value=selected_month,
            min_value=selected_month,
            max_value=selected_month_end,
            format="DD/MM/YYYY",
            key="manual_cover_date",
        )

        available_requirements = [
            req
            for req in cover_requirements
            if requirement_contains_date(req, cover_date)
        ]

        if not available_requirements:
            st.info("No cover requirements exist on this date.")
        else:
            requirement_by_id = {
                str(req["id"]): req
                for req in available_requirements
            }

            selected_requirement_id = st.selectbox(
                "Cover requirement",
                options=list(requirement_by_id),
                format_func=lambda req_id: (
                    f"{requirement_by_id[req_id]['requesting_unit']} — "
                    f"{requirement_by_id[req_id]['cover_type']} "
                    f"({SESSION_LABELS.get(str(requirement_by_id[req_id]['session']), requirement_by_id[req_id]['session'])})"
                ),
            )

            selected_requirement = requirement_by_id[
                selected_requirement_id
            ]

            assignment_mode = st.radio(
                "Assignment",
                options=["Active cover", "FC reserve"],
                horizontal=True,
            )

            if (
                assignment_mode == "FC reserve"
                and selected_requirement["cover_category"] != "FC"
            ):
                st.warning(
                    "Reserve assignments are currently intended for FC."
                )

            cover_person = st.selectbox(
                "Cover Fit personnel",
                options=cover_fit_names,
                key="manual_cover_person",
            )

            availability_code = get_availability_code(
                availability_rows,
                cover_person,
                cover_date,
            )

            existing_same_day = [
                row for row in manual_assignments
                if (
                    row["personnel_name"] == cover_person
                    and str(row["assignment_date"]) == cover_date.isoformat()
                )
            ]

            if availability_code:
                st.warning(
                    f"{cover_person} has availability code "
                    f"{availability_code} on {cover_date:%d %b %Y}."
                )

            if existing_same_day:
                st.warning(
                    f"{cover_person} already has "
                    f"{len(existing_same_day)} locked assignment(s) "
                    "on this date."
                )

            allow_cover_override = st.checkbox(
                "Allow manual override if validation finds a conflict",
                value=False,
                key="manual_cover_override",
            )

            cover_remarks = st.text_input(
                "Remarks",
                key="manual_cover_remarks",
            )

            if st.button(
                "Lock cover assignment",
                type="primary",
                use_container_width=True,
            ):
                kind = (
                    "COVER"
                    if assignment_mode == "Active cover"
                    else "COVER_RESERVE"
                )

                label = (
                    f"{selected_requirement['requesting_unit']} — "
                    f"{selected_requirement['cover_type']}"
                )

                if kind == "COVER_RESERVE":
                    label = "FC RESERVE"

                payload = {
                    "roster_month_id": roster_month_id,
                    "personnel_name": cover_person,
                    "assignment_date": cover_date.isoformat(),
                    "assignment_kind": kind,
                    "centre": None,
                    "role_name": None,
                    "cover_requirement_id": selected_requirement_id,
                    "cover_label": label,
                    "session": selected_requirement["session"],
                    "is_locked": True,
                    "allow_override": allow_cover_override,
                    "remarks": cover_remarks.strip() or None,
                }

                try:
                    (
                        get_supabase()
                        .table("roster_manual_assignments")
                        .insert(payload)
                        .execute()
                    )
                except Exception as exc:
                    st.error(
                        f"Unable to save manual cover assignment: {exc}"
                    )
                else:
                    clear_manual_cache()
                    st.success("Cover assignment locked.")
                    st.rerun()


with review_tab:
    st.subheader("Locked assignments")

    if not manual_assignments:
        st.info("No manual assignments have been added.")
    else:
        cover_lookup = {
            str(row["id"]): row
            for row in cover_requirements
        }

        display_rows = []

        for row in manual_assignments:
            assignment_kind = str(row["assignment_kind"])
            details = ""

            if assignment_kind == "DUTY":
                details = (
                    f"{row.get('centre') or ''} "
                    f"{row.get('role_name') or ''}"
                ).strip()
            else:
                requirement = cover_lookup.get(
                    str(row.get("cover_requirement_id"))
                )
                if requirement:
                    details = (
                        f"{requirement['requesting_unit']} — "
                        f"{requirement['cover_type']} "
                        f"({SESSION_LABELS.get(str(requirement['session']), requirement['session'])})"
                    )
                else:
                    details = str(row.get("cover_label") or assignment_kind)

            availability_code = get_availability_code(
                availability_rows,
                str(row["personnel_name"]),
                date.fromisoformat(str(row["assignment_date"])),
            )

            display_rows.append({
                "ID": row["id"],
                "Date": date.fromisoformat(str(row["assignment_date"])),
                "Personnel": row["personnel_name"],
                "Kind": assignment_kind.replace("_", " ").title(),
                "Details": details,
                "Availability": availability_code or "",
                "Locked": bool(row["is_locked"]),
                "Override": bool(row["allow_override"]),
                "Remarks": row.get("remarks") or "",
            })

        st.dataframe(
            display_rows,
            use_container_width=True,
            hide_index=True,
            height=min(700, 90 + len(display_rows) * 35),
            column_config={
                "ID": None,
                "Date": st.column_config.DateColumn(
                    "Date",
                    format="DD MMM",
                ),
                "Locked": st.column_config.CheckboxColumn("Locked"),
                "Override": st.column_config.CheckboxColumn("Override"),
            },
        )

        st.divider()
        st.subheader("Delete locked assignment")

        assignment_lookup = {
            str(row["id"]): row
            for row in manual_assignments
        }

        delete_id = st.selectbox(
            "Select assignment",
            options=list(assignment_lookup),
            format_func=lambda assignment_id: (
                f"{assignment_lookup[assignment_id]['assignment_date']} — "
                f"{assignment_lookup[assignment_id]['personnel_name']} — "
                f"{assignment_lookup[assignment_id]['assignment_kind']}"
            ),
        )

        confirm_delete = st.checkbox(
            "Confirm deletion",
            key="confirm_manual_assignment_delete",
        )

        if st.button(
            "Delete selected assignment",
            disabled=not confirm_delete,
        ):
            try:
                (
                    get_supabase()
                    .table("roster_manual_assignments")
                    .delete()
                    .eq("id", delete_id)
                    .execute()
                )
            except Exception as exc:
                st.error(f"Unable to delete assignment: {exc}")
            else:
                clear_manual_cache()
                st.success("Manual assignment deleted.")
                st.rerun()