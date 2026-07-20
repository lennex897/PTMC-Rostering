from __future__ import annotations

from datetime import date

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


def role_selector(
    *,
    centre: str,
    selected_roles: set[str],
    key_prefix: str,
) -> set[str]:
    available_roles = get_roles_for_centre(
        centre
    )

    chosen_roles: set[str] = set()

    st.markdown("#### Eligible roles")

    columns = st.columns(3)

    for index, role in enumerate(
        available_roles
    ):
        column = columns[
            index % len(columns)
        ]

        checked = column.checkbox(
            role,
            value=role in selected_roles,
            key=f"{key_prefix}_{role}",
        )

        if checked:
            chosen_roles.add(role)

    return chosen_roles


def render_add_person_form() -> None:
    with st.expander(
        "Add new personnel",
        expanded=False,
    ):
        with st.form(
            "add_person_form",
            clear_on_submit=True,
        ):
            left, middle, right = st.columns(3)

            with left:
                name = st.text_input(
                    "Name",
                )

                rank = st.text_input(
                    "Rank",
                )

                centre = st.selectbox(
                    "Centre",
                    options=["PT", "RH"],
                )

            with middle:
                department = st.text_input(
                    "Department",
                )

                ampt_status = st.selectbox(
                    "AMPT status",
                    options=["PASS", "FAIL"],
                )

                is_bcf = st.checkbox(
                    "BCF",
                    value=False,
                )

            with right:
                has_leaving_date = st.checkbox(
                    "Set leaving date",
                    value=False,
                )

                leaving_date_value = st.date_input(
                    "Leaving date",
                    value=date.today(),
                    disabled=not has_leaving_date,
                )

                display_order = st.number_input(
                    "Display order",
                    min_value=0,
                    value=0,
                    step=1,
                )

            available_roles = (
                get_roles_for_centre(
                    centre
                )
            )

            selected_roles: set[str] = set()

            st.markdown(
                "#### Eligible roles"
            )

            role_columns = st.columns(3)

            for index, role in enumerate(
                available_roles
            ):
                role_column = role_columns[
                    index % len(
                        role_columns
                    )
                ]

                if role_column.checkbox(
                    role,
                    key=f"add_role_{role}",
                ):
                    selected_roles.add(role)

            submitted = st.form_submit_button(
                "Create personnel",
                type="primary",
            )

        if submitted:
            try:
                create_person(
                    name=name,
                    rank=rank,
                    centre=centre,
                    department=department,
                    ampt_status=ampt_status,
                    is_bcf=is_bcf,
                    leaving_date=(
                        leaving_date_value
                        if has_leaving_date
                        else None
                    ),
                    display_order=int(
                        display_order
                    ),
                    eligible_roles=(
                        selected_roles
                    ),
                )

            except PersonnelRepositoryError as exc:
                st.error(str(exc))

            else:
                st.success(
                    f"{name.strip()} was created."
                )
                rerun()


def render_active_personnel(
    records,
) -> None:
    st.subheader("Active personnel")

    active_records = [
        record
        for record in records
        if record.person.is_active
    ]

    if not active_records:
        st.info(
            "No active personnel records found."
        )
        return

    search_term = st.text_input(
        "Search active personnel",
        key="active_person_search",
    ).strip().lower()

    filtered_records = [
        record
        for record in active_records
        if (
            not search_term
            or search_term
            in record.person.name.lower()
            or search_term
            in record.person.rank.lower()
            or search_term
            in record.person.centre.lower()
            or search_term
            in record.person.department.lower()
        )
    ]

    if not filtered_records:
        st.warning(
            "No active personnel match the search."
        )
        return

    label_to_record = {
        (
            f"{record.person.name} "
            f"({record.person.centre})"
        ): record
        for record in filtered_records
    }

    selected_label = st.selectbox(
        "Select personnel to edit",
        options=list(
            label_to_record.keys()
        ),
        key="active_person_selector",
    )

    selected_record = (
        label_to_record[selected_label]
    )

    render_edit_form(
        selected_record
    )


def render_edit_form(
    record,
) -> None:
    person = record.person

    st.markdown("---")
    st.subheader(
        f"Edit: {person.name}"
    )

    with st.form(
        f"edit_person_{record.id}"
    ):
        left, middle, right = st.columns(3)

        with left:
            name = st.text_input(
                "Name",
                value=person.name,
            )

            rank = st.text_input(
                "Rank",
                value=person.rank,
            )

            centre = st.selectbox(
                "Centre",
                options=["PT", "RH"],
                index=(
                    0
                    if person.centre == "PT"
                    else 1
                ),
            )

        with middle:
            department = st.text_input(
                "Department",
                value=person.department,
            )

            ampt_status = st.selectbox(
                "AMPT status",
                options=["PASS", "FAIL"],
                index=(
                    0
                    if person.ampt_status
                    == "PASS"
                    else 1
                ),
            )

            is_bcf = st.checkbox(
                "BCF",
                value=person.is_bcf,
            )

        with right:
            has_leaving_date = st.checkbox(
                "Set leaving date",
                value=(
                    person.leaving_date
                    is not None
                ),
            )

            leaving_date_value = st.date_input(
                "Leaving date",
                value=(
                    person.leaving_date
                    or date.today()
                ),
                disabled=not has_leaving_date,
            )

            display_order = st.number_input(
                "Display order",
                min_value=0,
                value=record.display_order,
                step=1,
            )

        selected_roles = role_selector(
            centre=centre,
            selected_roles=(
                person.eligible_roles
            ),
            key_prefix=(
                f"edit_{record.id}"
            ),
        )

        save_clicked = (
            st.form_submit_button(
                "Save changes",
                type="primary",
            )
        )

    if save_clicked:
        try:
            update_person(
                personnel_id=record.id,
                name=name,
                rank=rank,
                centre=centre,
                department=department,
                ampt_status=ampt_status,
                is_bcf=is_bcf,
                leaving_date=(
                    leaving_date_value
                    if has_leaving_date
                    else None
                ),
                display_order=int(
                    display_order
                ),
                eligible_roles=(
                    selected_roles
                ),
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
        "I understand this will remove the person from future roster generation.",
        key=(
            f"confirm_deactivate_"
            f"{record.id}"
        ),
    )

    if st.button(
        "Deactivate personnel",
        disabled=not confirm_deactivate,
        key=(
            f"deactivate_{record.id}"
        ),
    ):
        try:
            deactivate_person(
                record.id
            )

        except PersonnelRepositoryError as exc:
            st.error(str(exc))

        else:
            st.success(
                f"{person.name} was deactivated."
            )
            rerun()


def render_inactive_personnel(
    records,
) -> None:
    st.markdown("---")
    st.subheader("Inactive personnel")

    inactive_records = [
        record
        for record in records
        if not record.person.is_active
    ]

    if not inactive_records:
        st.info(
            "No inactive personnel records."
        )
        return

    for record in inactive_records:
        person = record.person

        left, right = st.columns(
            [4, 1]
        )

        with left:
            st.write(
                f"**{person.name}** — "
                f"{person.rank or 'No rank'} — "
                f"{person.centre}"
            )

        with right:
            if st.button(
                "Reactivate",
                key=(
                    f"reactivate_{record.id}"
                ),
            ):
                try:
                    reactivate_person(
                        record.id
                    )

                except PersonnelRepositoryError as exc:
                    st.error(str(exc))

                else:
                    st.success(
                        f"{person.name} was reactivated."
                    )
                    rerun()


render_add_person_form()

try:
    personnel_records = (
        load_personnel_records(
            include_inactive=True
        )
    )

except PersonnelRepositoryError as exc:
    st.error(str(exc))
    st.stop()

render_active_personnel(
    personnel_records
)

render_inactive_personnel(
    personnel_records
)