from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from roster_engine.personnel_repository import (
    PersonnelRepositoryError,
    create_person,
    deactivate_person,
    get_roles_for_centre,
    load_personnel_records,
    reactivate_person,
    update_person,
)

st.set_page_config(page_title="Personnel Management", page_icon="👥", layout="wide")
st.title("Personnel Management")
st.caption("Create, edit, deactivate, and reactivate roster personnel.")


def rerun() -> None:
    st.rerun()


def role_selector(
    *,
    centre: str,
    selected_roles: set[str],
    key_prefix: str,
) -> set[str]:
    available_roles = get_roles_for_centre(centre)
    chosen_roles: set[str] = set()

    st.markdown("#### Eligible roles")
    columns = st.columns(3)

    for index, role in enumerate(available_roles):
        checked = columns[index % len(columns)].checkbox(
            role,
            value=role in selected_roles,
            key=f"{key_prefix}_{role}",
        )
        if checked:
            chosen_roles.add(role)

    return chosen_roles


def render_summary(records: list[Any]) -> None:
    active = [r for r in records if r.person.is_active]
    inactive = [r for r in records if not r.person.is_active]
    pt = [r for r in active if r.person.centre == "PT"]
    rh = [r for r in active if r.person.centre == "RH"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active personnel", len(active))
    c2.metric("PT personnel", len(pt))
    c3.metric("RH personnel", len(rh))
    c4.metric("Inactive personnel", len(inactive))


def render_add_person_form() -> None:
    with st.expander("Add new personnel", expanded=False):
        st.caption(
            "Centre and leaving-date controls update immediately. "
            "Nothing is saved until Create personnel is clicked."
        )

        left, middle, right = st.columns(3)

        with left:
            name = st.text_input("Name", key="add_name")
            rank = st.text_input("Rank", key="add_rank")
            centre = st.selectbox("Centre", ["PT", "RH"], key="add_centre")

        with middle:
            department = st.text_input("Department", key="add_department")
            ampt_status = st.selectbox(
                "AMPT status",
                ["PASS", "FAIL"],
                key="add_ampt_status",
            )
            is_bcf = st.checkbox("BCF", key="add_is_bcf")

        with right:
            has_leaving_date = st.checkbox(
                "Set leaving date",
                key="add_has_leaving_date",
            )
            leaving_date_value = st.date_input(
                "Leaving date",
                value=date.today(),
                disabled=not has_leaving_date,
                key="add_leaving_date",
            )
            display_order = st.number_input(
                "Display order",
                min_value=0,
                value=0,
                step=1,
                key="add_display_order",
            )

        selected_roles = role_selector(
            centre=centre,
            selected_roles=set(),
            key_prefix=f"add_role_{centre}",
        )

        if st.button("Create personnel", type="primary", key="create_personnel"):
            try:
                create_person(
                    name=name,
                    rank=rank,
                    centre=centre,
                    department=department,
                    ampt_status=ampt_status,
                    is_bcf=is_bcf,
                    leaving_date=leaving_date_value if has_leaving_date else None,
                    display_order=int(display_order),
                    eligible_roles=selected_roles,
                )
            except PersonnelRepositoryError as exc:
                st.error(str(exc))
            else:
                st.success(f"{name.strip()} was created.")
                rerun()


def record_label(record: Any) -> str:
    person = record.person
    rank = person.rank.strip() if person.rank else "No rank"
    return f"{person.name} · {rank} · {person.centre}"


def render_personnel_browser(records: list[Any]) -> None:
    active_records = [r for r in records if r.person.is_active]

    if not active_records:
        st.info("No active personnel records found.")
        return

    st.subheader("Active personnel")

    browser_col, editor_col = st.columns([1, 2.4], gap="large")

    with browser_col:
        search_term = st.text_input(
            "Search",
            placeholder="Name, rank, centre, department...",
            key="active_person_search",
        ).strip().lower()

        centre_filter = st.segmented_control(
            "Centre",
            options=["All", "PT", "RH"],
            default="All",
            key="personnel_centre_filter",
        )

        filtered_records = [
            record
            for record in active_records
            if (
                (centre_filter == "All" or record.person.centre == centre_filter)
                and (
                    not search_term
                    or search_term in record.person.name.lower()
                    or search_term in record.person.rank.lower()
                    or search_term in record.person.centre.lower()
                    or search_term in record.person.department.lower()
                )
            )
        ]

        st.caption(f"{len(filtered_records)} personnel shown")

        if not filtered_records:
            st.warning("No active personnel match the current filters.")
            return

        valid_ids = {str(record.id) for record in filtered_records}
        selected_id = st.session_state.get("selected_personnel_id")

        if selected_id not in valid_ids:
            selected_id = str(filtered_records[0].id)
            st.session_state["selected_personnel_id"] = selected_id

        with st.container(height=560, border=True):
            for record in filtered_records:
                person = record.person
                is_selected = str(record.id) == selected_id

                label = (
                    f"● {person.name}\n"
                    f"{person.rank or 'No rank'} · {person.centre}"
                    if is_selected
                    else (
                        f"{person.name}\n"
                        f"{person.rank or 'No rank'} · {person.centre}"
                    )
                )

                if st.button(
                    label,
                    key=f"select_person_{record.id}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    st.session_state["selected_personnel_id"] = str(record.id)
                    rerun()

    selected_record = next(
        (
            record
            for record in filtered_records
            if str(record.id) == st.session_state["selected_personnel_id"]
        ),
        filtered_records[0],
    )

    with editor_col:
        render_edit_form(selected_record)


def render_edit_form(record: Any) -> None:
    person = record.person

    st.subheader(f"Edit: {person.name}")
    st.caption(
        "Centre and leaving-date controls update immediately. "
        "Changes are saved only after Save changes is clicked."
    )

    left, middle, right = st.columns(3)

    with left:
        name = st.text_input(
            "Name",
            value=person.name,
            key=f"edit_name_{record.id}",
        )
        rank = st.text_input(
            "Rank",
            value=person.rank,
            key=f"edit_rank_{record.id}",
        )
        centre = st.selectbox(
            "Centre",
            ["PT", "RH"],
            index=0 if person.centre == "PT" else 1,
            key=f"edit_centre_{record.id}",
        )

    with middle:
        department = st.text_input(
            "Department",
            value=person.department,
            key=f"edit_department_{record.id}",
        )
        ampt_status = st.selectbox(
            "AMPT status",
            ["PASS", "FAIL"],
            index=0 if person.ampt_status == "PASS" else 1,
            key=f"edit_ampt_{record.id}",
        )
        is_bcf = st.checkbox(
            "BCF",
            value=person.is_bcf,
            key=f"edit_bcf_{record.id}",
        )

    with right:
        has_leaving_date = st.checkbox(
            "Set leaving date",
            value=person.leaving_date is not None,
            key=f"edit_has_leaving_date_{record.id}",
        )
        leaving_date_value = st.date_input(
            "Leaving date",
            value=person.leaving_date or date.today(),
            disabled=not has_leaving_date,
            key=f"edit_leaving_date_{record.id}",
        )
        display_order = st.number_input(
            "Display order",
            min_value=0,
            value=record.display_order,
            step=1,
            key=f"edit_display_order_{record.id}",
        )

    selected_roles = role_selector(
        centre=centre,
        selected_roles=set(person.eligible_roles),
        key_prefix=f"edit_role_{record.id}_{centre}",
    )

    action_left, action_right = st.columns([1, 1])

    with action_left:
        if st.button(
            "Save changes",
            type="primary",
            key=f"save_person_{record.id}",
            use_container_width=True,
        ):
            try:
                update_person(
                    personnel_id=record.id,
                    name=name,
                    rank=rank,
                    centre=centre,
                    department=department,
                    ampt_status=ampt_status,
                    is_bcf=is_bcf,
                    leaving_date=leaving_date_value if has_leaving_date else None,
                    display_order=int(display_order),
                    eligible_roles=selected_roles,
                )
            except PersonnelRepositoryError as exc:
                st.error(str(exc))
            else:
                st.success(f"{name.strip()} was updated.")
                rerun()

    with action_right:
        confirm_deactivate = st.checkbox(
            "Confirm deactivation",
            key=f"confirm_deactivate_{record.id}",
        )

        if st.button(
            "Deactivate personnel",
            disabled=not confirm_deactivate,
            key=f"deactivate_{record.id}",
            use_container_width=True,
        ):
            try:
                deactivate_person(record.id)
            except PersonnelRepositoryError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("selected_personnel_id", None)
                st.success(f"{person.name} was deactivated.")
                rerun()


def render_inactive_personnel(records: list[Any]) -> None:
    st.markdown("---")
    st.subheader("Inactive personnel")

    inactive_records = [r for r in records if not r.person.is_active]
    if not inactive_records:
        st.info("No inactive personnel records.")
        return

    with st.expander(f"View inactive personnel ({len(inactive_records)})"):
        for record in inactive_records:
            person = record.person
            left, right = st.columns([4, 1])

            with left:
                st.write(
                    f"**{person.name}** — "
                    f"{person.rank or 'No rank'} — "
                    f"{person.centre}"
                )

            with right:
                if st.button("Reactivate", key=f"reactivate_{record.id}"):
                    try:
                        reactivate_person(record.id)
                    except PersonnelRepositoryError as exc:
                        st.error(str(exc))
                    else:
                        st.success(f"{person.name} was reactivated.")
                        rerun()


try:
    personnel_records = load_personnel_records(include_inactive=True)
except PersonnelRepositoryError as exc:
    st.error(str(exc))
    st.stop()

render_summary(personnel_records)
render_add_person_form()
render_personnel_browser(personnel_records)
render_inactive_personnel(personnel_records)