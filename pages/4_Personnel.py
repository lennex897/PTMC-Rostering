from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
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

SERVICE_TYPE_OPTIONS = ["Not set", "CBT", "SVC"]
COVER_FITNESS_OPTIONS = ["Not set", "Cover fit", "Not cover fit"]

st.set_page_config(
    page_title="Personnel Management",
    page_icon="👥",
    layout="wide",
)
st.title("Personnel Management")
st.caption(
    "Create, edit, deactivate, and reactivate roster personnel."
)


def rerun() -> None:
    st.rerun()


def service_type_to_database(
    value: str,
) -> str | None:
    if value in {"CBT", "SVC"}:
        return value
    return None


def service_type_from_database(
    value: str | None,
) -> str:
    normalised = str(value or "").strip().upper()
    if normalised in {"CBT", "SVC"}:
        return normalised
    return "Not set"


def cover_fitness_to_database(
    value: str,
) -> bool | None:
    if value == "Cover fit":
        return True
    if value == "Not cover fit":
        return False
    return None


def cover_fitness_from_database(
    value: bool | None,
) -> str:
    if value is True:
        return "Cover fit"
    if value is False:
        return "Not cover fit"
    return "Not set"


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
            "Nothing is saved until Create personnel is clicked."
        )

        left, middle, right = st.columns(3)

        with left:
            st.markdown("#### Basic information")
            name = st.text_input("Name", key="add_name")
            rank = st.text_input("Rank", key="add_rank")
            centre = st.selectbox(
                "Centre",
                ["PT", "RH"],
                key="add_centre",
            )
            department = st.text_input(
                "Department",
                key="add_department",
            )

        with middle:
            st.markdown("#### Operational status")
            ampt_status = st.selectbox(
                "AMPT status",
                ["PASS", "FAIL"],
                key="add_ampt_status",
            )
            service_type_label = st.selectbox(
                "Service type",
                SERVICE_TYPE_OPTIONS,
                key="add_service_type",
            )
            cover_fitness_label = st.selectbox(
                "Cover fitness",
                COVER_FITNESS_OPTIONS,
                key="add_cover_fitness",
            )

        with right:
            st.markdown("#### Planning")
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

        if st.button(
            "Create personnel",
            type="primary",
            key="create_personnel",
        ):
            try:
                create_person(
                    name=name,
                    rank=rank,
                    centre=centre,
                    department=department,
                    ampt_status=ampt_status,
                    service_type=service_type_to_database(
                        service_type_label
                    ),
                    is_cover_fit=cover_fitness_to_database(
                        cover_fitness_label
                    ),
                    leaving_date=(
                        leaving_date_value
                        if has_leaving_date
                        else None
                    ),
                    display_order=int(display_order),
                    eligible_roles=selected_roles,
                )
            except PersonnelRepositoryError as exc:
                st.error(str(exc))
            else:
                st.success(f"{name.strip()} was created.")
                rerun()


def personnel_table_row(
    record: Any,
) -> dict[str, object]:
    person = record.person

    return {
        "Order": record.display_order,
        "Rank": person.rank,
        "Name": person.name,
        "Centre": person.centre,
        "Department": person.department,
        "AMPT": person.ampt_status,
        "Service": service_type_from_database(
            person.service_type
        ),
        "Cover fitness": cover_fitness_from_database(
            person.is_cover_fit
        ),
        "Leaving date": person.leaving_date,
        "Eligible roles": ", ".join(
            sorted(person.eligible_roles)
        ),
        "_record_id": record.id,
    }


def render_active_personnel(
    records: list[Any],
) -> None:
    st.markdown("---")
    st.subheader("Personnel list")
    st.caption(
        "Use the filters or sort the table, then select a row "
        "to open that person's edit form."
    )

    active_records = [
        record
        for record in records
        if record.person.is_active
    ]

    if not active_records:
        st.info("No active personnel records found.")
        return

    filter_left, filter_middle, filter_right = st.columns(
        [2, 1, 1]
    )

    with filter_left:
        search_term = st.text_input(
            "Search",
            placeholder=(
                "Name, rank, department, service type, "
                "cover fitness, or role"
            ),
            key="active_person_search",
        ).strip().lower()

    with filter_middle:
        centre_filter = st.selectbox(
            "Centre",
            ["All", "PT", "RH"],
            key="active_person_centre_filter",
        )

    with filter_right:
        service_filter = st.selectbox(
            "Service type",
            ["All", *SERVICE_TYPE_OPTIONS],
            key="active_person_service_filter",
        )

    filtered_records: list[Any] = []

    for record in active_records:
        person = record.person
        service_label = service_type_from_database(
            person.service_type
        )
        cover_label = cover_fitness_from_database(
            person.is_cover_fit
        )
        searchable_text = " ".join(
            [
                person.name,
                person.rank,
                person.centre,
                person.department,
                person.ampt_status,
                service_label,
                cover_label,
                " ".join(
                    sorted(person.eligible_roles)
                ),
            ]
        ).lower()

        if (
            search_term
            and search_term not in searchable_text
        ):
            continue

        if (
            centre_filter != "All"
            and person.centre != centre_filter
        ):
            continue

        if (
            service_filter != "All"
            and service_label != service_filter
        ):
            continue

        filtered_records.append(record)

    if not filtered_records:
        st.warning(
            "No active personnel match the current filters."
        )
        return

    table_data = pd.DataFrame(
        [
            personnel_table_row(record)
            for record in filtered_records
        ]
    )

    selected_record: Any | None = None

    try:
        selection_event = st.dataframe(
            table_data,
            width="stretch",
            height=520,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="active_person_table",
            column_config={
                "Order": st.column_config.NumberColumn(
                    "Order",
                    format="%d",
                    width="small",
                ),
                "Rank": st.column_config.TextColumn(
                    "Rank",
                    width="small",
                ),
                "Name": st.column_config.TextColumn(
                    "Name",
                    width="medium",
                ),
                "Centre": st.column_config.TextColumn(
                    "Centre",
                    width="small",
                ),
                "Department": st.column_config.TextColumn(
                    "Department",
                    width="medium",
                ),
                "AMPT": st.column_config.TextColumn(
                    "AMPT",
                    width="small",
                ),
                "Service": st.column_config.TextColumn(
                    "Service",
                    width="small",
                ),
                "Cover fitness": st.column_config.TextColumn(
                    "Cover fitness",
                    width="medium",
                ),
                "Leaving date": st.column_config.DateColumn(
                    "Leaving date",
                    format="DD MMM YYYY",
                    width="medium",
                ),
                "Eligible roles": st.column_config.TextColumn(
                    "Eligible roles",
                    width="large",
                ),
                "_record_id": None,
            },
        )

        selected_rows = selection_event.selection.rows

        if selected_rows:
            selected_index = selected_rows[0]
            selected_record_id = str(
                table_data.iloc[
                    selected_index
                ]["_record_id"]
            )
            selected_record = next(
                (
                    record
                    for record in filtered_records
                    if record.id == selected_record_id
                ),
                None,
            )

    except TypeError:
        # Compatibility fallback for older Streamlit releases
        # that do not support dataframe row selection.
        st.dataframe(
            table_data.drop(
                columns=["_record_id"]
            ),
            width="stretch",
            height=520,
            hide_index=True,
        )

        label_to_record = {
            (
                f"{record.person.name} "
                f"({record.person.centre})"
            ): record
            for record in filtered_records
        }

        selected_label = st.selectbox(
            "Select personnel to edit",
            ["— Select —", *label_to_record],
            key="active_person_selector_fallback",
        )

        if selected_label != "— Select —":
            selected_record = label_to_record[
                selected_label
            ]

    if selected_record is None:
        st.info(
            "Select a row in the table to edit that person."
        )
        return

    render_edit_form(selected_record)


def render_edit_form(
    record: Any,
) -> None:
    person = record.person

    st.markdown("---")
    st.subheader(f"Edit: {person.name}")
    st.caption(
        "Changes are saved only after Save changes is clicked."
    )

    left, middle, right = st.columns(3)

    with left:
        st.markdown("#### Basic information")
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
        department = st.text_input(
            "Department",
            value=person.department,
            key=f"edit_department_{record.id}",
        )

    with middle:
        st.markdown("#### Operational status")
        ampt_status = st.selectbox(
            "AMPT status",
            ["PASS", "FAIL"],
            index=(
                0
                if person.ampt_status == "PASS"
                else 1
            ),
            key=f"edit_ampt_{record.id}",
        )

        current_service_type = (
            service_type_from_database(
                person.service_type
            )
        )
        service_type_label = st.selectbox(
            "Service type",
            SERVICE_TYPE_OPTIONS,
            index=SERVICE_TYPE_OPTIONS.index(
                current_service_type
            ),
            key=f"edit_service_type_{record.id}",
        )

        current_cover_fitness = (
            cover_fitness_from_database(
                person.is_cover_fit
            )
        )
        cover_fitness_label = st.selectbox(
            "Cover fitness",
            COVER_FITNESS_OPTIONS,
            index=COVER_FITNESS_OPTIONS.index(
                current_cover_fitness
            ),
            key=f"edit_cover_fitness_{record.id}",
        )

    with right:
        st.markdown("#### Planning")
        has_leaving_date = st.checkbox(
            "Set leaving date",
            value=person.leaving_date is not None,
            key=f"edit_has_leaving_date_{record.id}",
        )
        leaving_date_value = st.date_input(
            "Leaving date",
            value=(
                person.leaving_date
                or date.today()
            ),
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
        selected_roles=set(
            person.eligible_roles
        ),
        key_prefix=(
            f"edit_role_{record.id}_{centre}"
        ),
    )

    if st.button(
        "Save changes",
        type="primary",
        key=f"save_person_{record.id}",
    ):
        try:
            update_person(
                personnel_id=record.id,
                name=name,
                rank=rank,
                centre=centre,
                department=department,
                ampt_status=ampt_status,
                service_type=service_type_to_database(
                    service_type_label
                ),
                is_cover_fit=cover_fitness_to_database(
                    cover_fitness_label
                ),
                leaving_date=(
                    leaving_date_value
                    if has_leaving_date
                    else None
                ),
                display_order=int(display_order),
                eligible_roles=selected_roles,
            )
        except PersonnelRepositoryError as exc:
            st.error(str(exc))
        else:
            st.success(
                f"{name.strip()} was updated."
            )
            rerun()

    st.markdown("#### Status")
    confirm_deactivate = st.checkbox(
        "I understand this will remove the person "
        "from future roster generation.",
        key=f"confirm_deactivate_{record.id}",
    )

    if st.button(
        "Deactivate personnel",
        disabled=not confirm_deactivate,
        key=f"deactivate_{record.id}",
    ):
        try:
            deactivate_person(record.id)
        except PersonnelRepositoryError as exc:
            st.error(str(exc))
        else:
            st.success(
                f"{person.name} was deactivated."
            )
            rerun()


def render_inactive_personnel(
    records: list[Any],
) -> None:
    st.markdown("---")
    st.subheader("Inactive personnel")

    inactive_records = [
        r for r in records
        if not r.person.is_active
    ]

    if not inactive_records:
        st.info("No inactive personnel records.")
        return

    for record in inactive_records:
        person = record.person
        left, right = st.columns([4, 1])

        with left:
            service_type = (
                person.service_type
                or "Not set"
            )
            cover_fitness = (
                cover_fitness_from_database(
                    person.is_cover_fit
                )
            )
            st.write(
                f"**{person.name}** — "
                f"{person.rank or 'No rank'} — "
                f"{person.centre} — "
                f"{service_type} — "
                f"{cover_fitness}"
            )

        with right:
            if st.button(
                "Reactivate",
                key=f"reactivate_{record.id}",
            ):
                try:
                    reactivate_person(record.id)
                except PersonnelRepositoryError as exc:
                    st.error(str(exc))
                else:
                    st.success(
                        f"{person.name} was reactivated."
                    )
                    rerun()


try:
    personnel_records = load_personnel_records(
        include_inactive=True
    )
except PersonnelRepositoryError as exc:
    st.error(str(exc))
    st.stop()

render_summary(personnel_records)
render_add_person_form()
render_active_personnel(personnel_records)
render_inactive_personnel(personnel_records)