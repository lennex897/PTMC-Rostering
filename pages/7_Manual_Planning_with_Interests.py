from __future__ import annotations

from calendar import monthrange
from datetime import date

import streamlit as st

from roster_engine.availability_repository import AvailabilityRepository
from roster_engine.cover_repository import CoverRepository
from roster_engine.database import get_supabase
from roster_engine.duty_interest_repository import DutyInterestRepository
from roster_engine.manual_planning_repository import ManualPlanningRepository
from roster_engine.personnel_repository import load_personnel_records


st.set_page_config(page_title="Manual Planning", page_icon="📌", layout="wide")
st.title("Manual Planning")
st.caption(
    "Lock selected duties and covers, or record duty interest before roster generation."
)

DUTY_ROLES = ["DM", "CS1", "CS2", "CS/B", "SB1", "SB2", "AE"]
CENTRES = ["PT", "RH"]
SESSION_LABELS = {"AM": "AM", "PM": "PM", "FULL_DAY": "Full day"}


def month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


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
        parsed = raw if isinstance(raw, date) else date.fromisoformat(str(raw))
        rows.append({
            "id": str(item["id"]),
            "month_start": parsed.replace(day=1),
            "status": item.get("status") or "draft",
        })
    return rows


@st.cache_data(ttl=20)
def load_personnel():
    return load_personnel_records(include_inactive=False)


@st.cache_data(ttl=15)
def load_cover_requirements(roster_month_id: str):
    return CoverRepository(get_supabase()).list_month_requirements(roster_month_id)


@st.cache_data(ttl=15)
def load_manual_assignments(roster_month_id: str):
    return ManualPlanningRepository(get_supabase()).list_month_assignments(roster_month_id)


@st.cache_data(ttl=15)
def load_duty_interests(roster_month_id: str):
    return DutyInterestRepository(get_supabase()).list_month_interests(roster_month_id)


@st.cache_data(ttl=15)
def load_availability(*, year: int, month: int):
    return AvailabilityRepository(get_supabase()).load_month_availability(
        year=year, month=month
    )


def clear_manual_cache() -> None:
    load_manual_assignments.clear()


def clear_interest_cache() -> None:
    load_duty_interests.clear()


PTMC_OVERNIGHT_ROLES = {
    "PT DM",
    "PT CS1",
    "PT CS2",
    "PT CS/B",
    "PT SB1",
    "PT AE",
    "RH SB1",
    "RH SB2",
}


def eligible_overnight_roles(person_record) -> list[str]:
    roles = {
        str(raw_role).strip().upper()
        for raw_role in person_record.person.eligible_roles
        if str(raw_role).strip()
    }

    roles &= PTMC_OVERNIGHT_ROLES

    preferred_order = {
        "DM": 0,
        "CS1": 1,
        "CS2": 2,
        "CS/B": 3,
        "SB1": 4,
        "SB2": 5,
        "AE": 6,
    }

    def sort_key(role: str) -> tuple[int, str]:
        short_role = role.split(" ", 1)[1] if " " in role else role
        return (preferred_order.get(short_role, 99), role)

    return sorted(roles, key=sort_key)


def get_availability_code(availability_rows, person_name: str, current_date: date) -> str | None:
    for entry in availability_rows:
        if entry.person_name == person_name and entry.unavailable_date == current_date:
            return entry.reason.strip().upper() or None
    return None


def is_before_leaving_date(person_record, current_date: date) -> bool:
    """
    leaving_date is treated as the first date the person is no longer usable.
    A person may therefore only be manually planned on dates strictly before it.
    """
    leaving_date = person_record.person.leaving_date
    return leaving_date is None or current_date < leaving_date


def personnel_available_on(
    person_by_name: dict,
    current_date: date,
    *,
    cover_fit_only: bool = False,
) -> list[str]:
    names = []

    for name, record in person_by_name.items():
        if not is_before_leaving_date(record, current_date):
            continue

        if cover_fit_only and record.person.is_cover_fit is not True:
            continue

        names.append(name)

    return sorted(names)


months = load_roster_months()
personnel = load_personnel()

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

cover_requirements = load_cover_requirements(roster_month_id)
manual_assignments = load_manual_assignments(roster_month_id)
duty_interests = load_duty_interests(roster_month_id)
availability_rows = load_availability(
    year=selected_month.year,
    month=selected_month.month,
)

active_people = [
    record
    for record in personnel
    if (
        record.person.is_active
        and (
            record.person.leaving_date is None
            or record.person.leaving_date > selected_month
        )
    )
]

person_by_name = {
    record.person.name: record
    for record in active_people
}

all_person_names = sorted(person_by_name)
cover_fit_names = sorted(
    record.person.name
    for record in active_people
    if record.person.is_cover_fit is True
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Locked assignments", len(manual_assignments))
m2.metric("Locked duties", sum(1 for r in manual_assignments if r.assignment_kind == "DUTY"))
m3.metric(
    "Locked covers",
    sum(1 for r in manual_assignments if r.assignment_kind in ("COVER", "COVER_RESERVE")),
)
m4.metric("PTMC Overnight Interests", len(duty_interests))

st.divider()

duty_tab, cover_tab, interest_tab, review_tab = st.tabs(
    ["Manual duties", "Manual covers", "PTMC Overnight Interest", "Review planning inputs"]
)

with duty_tab:
    st.subheader("Lock a duty assignment")

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

    duty_person_options = personnel_available_on(
        person_by_name,
        duty_date,
    )

    with c2:
        duty_person = st.selectbox(
            "Personnel",
            duty_person_options,
            key=f"manual_duty_person_{duty_date.isoformat()}",
            disabled=not duty_person_options,
        )

    with c3:
        duty_centre = st.selectbox(
            "Centre",
            CENTRES,
            key="manual_duty_centre",
        )

    with c4:
        duty_role = st.selectbox(
            "Role",
            DUTY_ROLES,
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

    availability_code = (
        get_availability_code(
            availability_rows,
            duty_person,
            duty_date,
        )
        if duty_person
        else None
    )

    existing_same_day = (
        [
            row
            for row in manual_assignments
            if (
                row.personnel_name == duty_person
                and row.assignment_date == duty_date
            )
        ]
        if duty_person
        else []
    )

    if not duty_person_options:
        st.warning(
            "No active personnel remain eligible for manual duty "
            "on this date after applying leaving dates."
        )

    if availability_code:
        st.warning(
            f"{duty_person} has availability code {availability_code} "
            f"on {duty_date:%d %b %Y}."
        )

    if existing_same_day:
        st.warning(
            f"{duty_person} already has "
            f"{len(existing_same_day)} locked assignment(s) "
            "on this date."
        )

    if st.button(
        "Lock duty",
        type="primary",
        use_container_width=True,
        key="lock_manual_duty_button",
        disabled=not duty_person_options,
    ):
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
    st.caption("Selections and conflict warnings update immediately.")

    if not cover_requirements:
        st.info("No cover requirements exist for this month.")
    elif not cover_fit_names:
        st.warning("No active Cover Fit personnel are available.")
    else:
        cover_date = st.date_input(
            "Cover date", value=selected_month, min_value=selected_month,
            max_value=selected_month_end, format="DD/MM/YYYY",
            key="manual_cover_date",
        )

        available_requirements = [
            req for req in cover_requirements
            if req.includes_date(cover_date)
        ]

        cover_fit_options = personnel_available_on(
            person_by_name,
            cover_date,
            cover_fit_only=True,
        )

        if not available_requirements:
            st.info("No cover requirements exist on this date.")
        elif not cover_fit_options:
            st.warning(
                "No active Cover Fit personnel remain eligible on this date "
                "after applying leaving dates."
            )
        else:
            requirement_by_id = {req.id: req for req in available_requirements}

            selected_requirement_id = st.selectbox(
                "Cover requirement",
                options=list(requirement_by_id),
                format_func=lambda req_id: (
                    f"{requirement_by_id[req_id].requesting_unit} — "
                    f"{requirement_by_id[req_id].cover_type} "
                    f"({SESSION_LABELS.get(requirement_by_id[req_id].session, requirement_by_id[req_id].session)})"
                ),
            )
            selected_requirement = requirement_by_id[selected_requirement_id]

            assignment_mode = st.radio(
                "Assignment", ["Active cover", "FC reserve"], horizontal=True
            )
            cover_person = st.selectbox(
                "Cover Fit personnel",
                cover_fit_options,
                key=f"manual_cover_person_{cover_date.isoformat()}",
            )

            availability_code = get_availability_code(
                availability_rows, cover_person, cover_date
            )
            if availability_code:
                st.warning(
                    f"{cover_person} has availability code {availability_code} "
                    f"on {cover_date:%d %b %Y}."
                )

            allow_cover_override = st.checkbox(
                "Allow manual override if validation finds a conflict",
                value=False,
                key="manual_cover_override",
            )
            cover_remarks = st.text_input("Remarks", key="manual_cover_remarks")

            if st.button("Lock cover assignment", type="primary", use_container_width=True):
                kind = "COVER" if assignment_mode == "Active cover" else "COVER_RESERVE"
                label = (
                    f"{selected_requirement.requesting_unit} — "
                    f"{selected_requirement.cover_type}"
                    if kind == "COVER" else "FC RESERVE"
                )
                payload = {
                    "roster_month_id": roster_month_id,
                    "personnel_name": cover_person,
                    "assignment_date": cover_date.isoformat(),
                    "assignment_kind": kind,
                    "centre": None,
                    "role_name": None,
                    "cover_requirement_id": selected_requirement_id,
                    "cover_label": label,
                    "session": selected_requirement.session,
                    "is_locked": True,
                    "allow_override": allow_cover_override,
                    "remarks": cover_remarks.strip() or None,
                }
                get_supabase().table("roster_manual_assignments").insert(payload).execute()
                clear_manual_cache()
                st.success("Cover assignment locked.")
                st.rerun()

with interest_tab:
    st.subheader("Record PTMC overnight interest")
    st.caption(
        "PTMC overnight interest is a soft preference, not a guaranteed assignment. "
        "The generator should only honour it for eligible overnight roles when the final team remains feasible."
    )

    c1, c2, c3 = st.columns([1.1, 1.6, 1.3])

    with c1:
        interest_date = st.date_input(
            "Date",
            value=selected_month,
            min_value=selected_month,
            max_value=selected_month_end,
            format="DD/MM/YYYY",
            key="duty_interest_date",
        )

    interest_person_options = personnel_available_on(
        person_by_name,
        interest_date,
    )

    with c2:
        interest_person = st.selectbox(
            "Personnel",
            interest_person_options,
            key=f"duty_interest_person_{interest_date.isoformat()}",
            disabled=not interest_person_options,
        )

    selected_person_record = (
        person_by_name[interest_person]
        if interest_person
        else None
    )

    actual_eligible_roles = (
        eligible_overnight_roles(
            selected_person_record
        )
        if selected_person_record
        else []
    )

    with c3:
        preferred_role_label = st.selectbox(
            "Preferred overnight role",
            [
                "Any eligible overnight role",
                *actual_eligible_roles,
            ],
            key=f"duty_interest_role_{interest_person}",
            help=(
                "Only this person's configured PTMC overnight roles are shown. "
                "PT CS/B is included because it is an overnight role on "
                "Monday, Thursday, and Sunday. PT SB2 and RH daytime roles "
                "are excluded."
            ),
        )

    if not interest_person_options:
        st.warning(
            "No active personnel remain eligible for PTMC overnight interest "
            "on this date after applying leaving dates."
        )
    elif actual_eligible_roles:
        st.caption(
            "Eligible overnight roles: "
            + ", ".join(actual_eligible_roles)
        )
    else:
        st.warning(
            f"{interest_person} currently has no PTMC overnight roles "
            "configured, so an overnight interest cannot be recorded."
        )

    interest_remarks = st.text_input(
        "Remarks",
        placeholder="Optional reason or note",
        key="duty_interest_remarks",
    )

    availability_code = (
        get_availability_code(
            availability_rows,
            interest_person,
            interest_date,
        )
        if interest_person
        else None
    )

    if availability_code:
        st.warning(
            f"{interest_person} has availability code {availability_code} "
            f"on {interest_date:%d %b %Y}. The generator should ignore "
            "this interest if that code blocks duty."
        )

    submit_interest = st.button(
        "Add PTMC overnight interest",
        type="primary",
        use_container_width=True,
        key="add_duty_interest_button",
        disabled=(
            not interest_person_options
            or not actual_eligible_roles
        ),
    )

    if submit_interest:
        preferred_role = (
            None
            if preferred_role_label == "Any eligible overnight role"
            else preferred_role_label
        )

        payload = {
            "roster_month_id": roster_month_id,
            "personnel_id": str(
                person_by_name[interest_person].id
            ),
            "interest_date": interest_date.isoformat(),
            "preferred_role": preferred_role,
            "remarks": interest_remarks.strip() or None,
        }

        try:
            (
                get_supabase()
                .table("roster_duty_interests")
                .insert(payload)
                .execute()
            )
        except Exception as exc:
            st.error(
                "Unable to save PTMC overnight interest. "
                "The same interest may already exist.\n\n"
                f"{exc}"
            )
        else:
            clear_interest_cache()
            st.success("PTMC overnight interest recorded.")
            st.rerun()

    st.divider()
    st.subheader("PTMC Overnight Interest for selected month")

    if not duty_interests:
        st.info("No PTMC overnight interests have been recorded.")
    else:
        rows = []

        for item in duty_interests:
            rows.append({
                "ID": item.id,
                "Date": item.interest_date,
                "Personnel": item.person_name or "Unknown",
                "Centre": item.centre,
                "Preference": item.preferred_role or "Any eligible overnight role",
                "Remarks": item.remarks or "",
            })

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": None,
                "Date": st.column_config.DateColumn(
                    "Date",
                    format="DD MMM",
                ),
            },
        )

        interest_lookup = {item.id: item for item in duty_interests}

        delete_interest_id = st.selectbox(
            "Select overnight interest to delete",
            options=list(interest_lookup),
            format_func=lambda item_id: (
                f"{interest_lookup[item_id].interest_date:%d %b} — "
                f"{interest_lookup[item_id].person_name or 'Unknown'} — "
                f"{interest_lookup[item_id].preferred_role or 'Any eligible overnight role'}"
            ),
            key="delete_interest_selector",
        )

        confirm_interest_delete = st.checkbox(
            "Confirm overnight interest deletion",
            key="confirm_interest_delete",
        )

        if st.button(
            "Delete selected duty interest",
            disabled=not confirm_interest_delete,
            key="delete_interest_button",
        ):
            (
                get_supabase()
                .table("roster_duty_interests")
                .delete()
                .eq("id", delete_interest_id)
                .execute()
            )

            clear_interest_cache()
            st.success("PTMC overnight interest deleted.")
            st.rerun()


with review_tab:
    st.subheader("Locked assignments")

    if not manual_assignments:
        st.info("No manual assignments have been added.")
    else:
        rows = []
        for row in manual_assignments:
            details = (
                row.qualified_role or ""
                if row.assignment_kind == "DUTY"
                else row.cover_label or row.assignment_kind
            )

            rows.append({
                "ID": row.id,
                "Date": row.assignment_date,
                "Personnel": row.personnel_name,
                "Kind": row.assignment_kind.replace("_", " ").title(),
                "Details": details,
                "Locked": row.is_locked,
                "Override": row.allow_override,
                "Remarks": row.remarks or "",
            })

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": None,
                "Date": st.column_config.DateColumn("Date", format="DD MMM"),
            },
        )

        st.divider()
        st.markdown("#### Edit or delete locked assignment")

        assignment_lookup = {
            row.id: row
            for row in manual_assignments
        }

        selected_assignment_id = st.selectbox(
            "Locked assignment",
            options=list(assignment_lookup),
            format_func=lambda assignment_id: (
                f"{assignment_lookup[assignment_id].assignment_date:%d %b} — "
                f"{assignment_lookup[assignment_id].personnel_name} — "
                f"{assignment_lookup[assignment_id].assignment_kind.replace('_', ' ').title()} — "
                f"{assignment_lookup[assignment_id].qualified_role or assignment_lookup[assignment_id].cover_label or ''}"
            ),
            key="edit_locked_assignment_selector",
        )

        selected_assignment = assignment_lookup[
            selected_assignment_id
        ]

        edit_date = st.date_input(
            "Assignment date",
            value=selected_assignment.assignment_date,
            min_value=selected_month,
            max_value=selected_month_end,
            format="DD/MM/YYYY",
            key=f"edit_assignment_date_{selected_assignment_id}",
        )

        edit_person_options = personnel_available_on(
            person_by_name,
            edit_date,
            cover_fit_only=(
                selected_assignment.assignment_kind
                in {"COVER", "COVER_RESERVE"}
            ),
        )

        selected_assignment_person_record = person_by_name.get(
            selected_assignment.personnel_name
        )

        if (
            selected_assignment.personnel_name
            not in edit_person_options
            and selected_assignment_person_record is not None
            and is_before_leaving_date(
                selected_assignment_person_record,
                edit_date,
            )
        ):
            edit_person_options = sorted(
                {
                    *edit_person_options,
                    selected_assignment.personnel_name,
                }
            )

        if not edit_person_options:
            st.warning(
                "No eligible personnel are available for this assignment date."
            )

        edit_person = st.selectbox(
            "Personnel",
            options=edit_person_options,
            index=(
                edit_person_options.index(
                    selected_assignment.personnel_name
                )
                if selected_assignment.personnel_name
                in edit_person_options
                else 0
            ) if edit_person_options else 0,
            key=f"edit_assignment_person_{selected_assignment_id}_{edit_date.isoformat()}",
            disabled=not edit_person_options,
        )

        edit_override = st.checkbox(
            "Allow override",
            value=selected_assignment.allow_override,
            key=f"edit_assignment_override_{selected_assignment_id}",
        )

        edit_remarks = st.text_input(
            "Remarks",
            value=selected_assignment.remarks or "",
            key=f"edit_assignment_remarks_{selected_assignment_id}",
        )

        edit_payload = {
            "personnel_name": edit_person if edit_person_options else selected_assignment.personnel_name,
            "assignment_date": edit_date.isoformat(),
            "allow_override": bool(edit_override),
            "remarks": edit_remarks.strip() or None,
        }

        if selected_assignment.assignment_kind == "DUTY":
            duty_edit_cols = st.columns(2)

            with duty_edit_cols[0]:
                edit_centre = st.selectbox(
                    "Centre",
                    CENTRES,
                    index=CENTRES.index(
                        selected_assignment.centre
                        if selected_assignment.centre in CENTRES
                        else "PT"
                    ),
                    key=f"edit_assignment_centre_{selected_assignment_id}",
                )

            with duty_edit_cols[1]:
                edit_role = st.selectbox(
                    "Role",
                    DUTY_ROLES,
                    index=DUTY_ROLES.index(
                        selected_assignment.role_name
                        if selected_assignment.role_name in DUTY_ROLES
                        else DUTY_ROLES[0]
                    ),
                    key=f"edit_assignment_role_{selected_assignment_id}",
                )

            edit_payload.update({
                "centre": edit_centre,
                "role_name": edit_role,
                "session": "FULL_DAY",
                "cover_requirement_id": None,
                "cover_label": None,
            })

        else:
            matching_requirements = [
                req
                for req in cover_requirements
                if req.includes_date(edit_date)
            ]

            if matching_requirements:
                edit_requirement_lookup = {
                    req.id: req
                    for req in matching_requirements
                }

                current_requirement_id = (
                    selected_assignment.cover_requirement_id
                    if selected_assignment.cover_requirement_id
                    in edit_requirement_lookup
                    else next(iter(edit_requirement_lookup))
                )

                edit_requirement_id = st.selectbox(
                    "Cover requirement",
                    options=list(edit_requirement_lookup),
                    index=list(edit_requirement_lookup).index(
                        current_requirement_id
                    ),
                    format_func=lambda req_id: (
                        f"{edit_requirement_lookup[req_id].requesting_unit} — "
                        f"{edit_requirement_lookup[req_id].cover_type} "
                        f"({SESSION_LABELS.get(edit_requirement_lookup[req_id].session, edit_requirement_lookup[req_id].session)})"
                    ),
                    key=f"edit_assignment_cover_req_{selected_assignment_id}_{edit_date.isoformat()}",
                )

                edit_requirement = edit_requirement_lookup[
                    edit_requirement_id
                ]

                edit_kind_label = st.radio(
                    "Assignment",
                    ["Active cover", "FC reserve"],
                    index=(
                        1
                        if selected_assignment.assignment_kind == "COVER_RESERVE"
                        else 0
                    ),
                    horizontal=True,
                    key=f"edit_assignment_cover_kind_{selected_assignment_id}",
                )

                edit_kind = (
                    "COVER_RESERVE"
                    if edit_kind_label == "FC reserve"
                    else "COVER"
                )

                edit_label = (
                    "FC RESERVE"
                    if edit_kind == "COVER_RESERVE"
                    else (
                        f"{edit_requirement.requesting_unit} — "
                        f"{edit_requirement.cover_type}"
                    )
                )

                edit_payload.update({
                    "assignment_kind": edit_kind,
                    "centre": None,
                    "role_name": None,
                    "cover_requirement_id": edit_requirement_id,
                    "cover_label": edit_label,
                    "session": edit_requirement.session,
                })
            else:
                st.warning(
                    "No cover requirement exists on the edited date. "
                    "Save is disabled until a valid requirement is available."
                )

        action_cols = st.columns(2)

        with action_cols[0]:
            save_disabled = (
                not edit_person_options
                or (
                    selected_assignment.assignment_kind
                    in {"COVER", "COVER_RESERVE"}
                    and not matching_requirements
                )
            )

            if st.button(
                "Save changes",
                type="primary",
                use_container_width=True,
                key=f"save_locked_assignment_{selected_assignment_id}",
                disabled=save_disabled,
            ):
                try:
                    (
                        get_supabase()
                        .table("roster_manual_assignments")
                        .update(edit_payload)
                        .eq("id", selected_assignment_id)
                        .execute()
                    )
                except Exception as exc:
                    st.error(
                        f"Unable to update locked assignment: {exc}"
                    )
                else:
                    clear_manual_cache()
                    st.success("Locked assignment updated.")
                    st.rerun()

        with action_cols[1]:
            if st.button(
                "Delete assignment",
                use_container_width=True,
                key=f"delete_locked_assignment_{selected_assignment_id}",
            ):
                try:
                    (
                        get_supabase()
                        .table("roster_manual_assignments")
                        .delete()
                        .eq("id", selected_assignment_id)
                        .execute()
                    )
                except Exception as exc:
                    st.error(
                        f"Unable to delete locked assignment: {exc}"
                    )
                else:
                    clear_manual_cache()
                    st.success("Locked assignment deleted.")
                    st.rerun()

    st.divider()
    st.subheader("PTMC Overnight Interests")

    if not duty_interests:
        st.info("No PTMC overnight interests have been recorded.")
    else:
        rows = []
        for item in duty_interests:
            rows.append({
                "Date": item.interest_date,
                "Personnel": item.person_name or "Unknown",
                "Centre": item.centre,
                "Preference": item.preferred_role or "Any eligible overnight role",
                "Remarks": item.remarks or "",
            })
        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="DD MMM"),
            },
        )
