from datetime import date

from roster_engine.dm_shadow_repository import SavedDMShadow
from roster_engine.saved_roster_export import (
    saved_roster_to_schedule,
)


def test_dm_shadow_is_added_to_export_schedule() -> None:
    schedule = saved_roster_to_schedule(
        assignments=[],
        dm_shadows=[
            SavedDMShadow(
                id="s1",
                roster_month_id="m1",
                personnel_name="CPL SHADOW",
                shadow_date=date(
                    2026,
                    8,
                    12,
                ),
                centre="PT",
                points=1.0,
                remarks=None,
            )
        ],
    )

    assert len(
        schedule.assignments
    ) == 1

    assignment = (
        schedule.assignments[0]
    )

    assert assignment.role == "DM SHADOW"
    assert assignment.person_name == "CPL SHADOW"
    assert assignment.duty_date == date(
        2026,
        8,
        12,
    )
    assert assignment.points == 1.0
    assert assignment.is_overnight is True
