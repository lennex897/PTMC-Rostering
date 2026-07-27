from __future__ import annotations

from roster_engine.dm_shadow_repository import SavedDMShadow
from roster_engine.generated_roster_repository import (
    StoredGeneratedAssignment,
)
from roster_engine.models import Assignment, Schedule


def saved_roster_to_schedule(
    *,
    assignments: list[StoredGeneratedAssignment],
    dm_shadows: list[SavedDMShadow],
) -> Schedule:
    """
    Flatten the editable saved roster plus manually plotted DM Shadows into
    the Schedule model consumed by the existing Excel exporter.

    DM Shadows are additional overnight assignments. They do not consume the
    PT DM requirement, but they are exported into the shadowing person's
    normal person/date cell as "DM SHADOW".
    """
    export_assignments: list[Assignment] = []

    for item in assignments:
        # FC SWAP is an audit/points record for a legitimate FC handover.
        # It is not a separate rostered commitment and must not be written
        # into the Excel person/date cell on top of the actual FC cover.
        if (
            item.assignment_kind != "DUTY"
            and (item.cover_type or "").strip().upper() == "FC SWAP"
        ):
            continue

        if item.assignment_kind == "DUTY":
            role = item.role_name or "DUTY"
        else:
            unit = (
                item.requesting_unit
                or ""
            ).strip()

            cover = (
                item.cover_type
                or item.assignment_kind
            )

            session = (
                item.session
                or "FULL_DAY"
            ).strip().upper()

            session_label = (
                session
                if session in {"AM", "PM"}
                else ""
            )

            role_parts = [
                value
                for value in (
                    unit,
                    session_label,
                    cover,
                )
                if value
            ]

            role = " ".join(
                role_parts
            )

        export_assignments.append(
            Assignment(
                duty_date=item.assignment_date,
                role=role,
                centre=item.centre or "PT",
                person_name=item.person_name,
                points=item.points,
                is_overnight=item.is_overnight,
            )
        )

    for shadow in dm_shadows:
        export_assignments.append(
            Assignment(
                duty_date=shadow.shadow_date,
                role="DM SHADOW",
                centre="PT",
                person_name=shadow.personnel_name,
                points=shadow.points,
                is_overnight=True,
            )
        )

    return Schedule(
        assignments=export_assignments
    )
