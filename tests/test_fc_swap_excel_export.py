from datetime import date
from types import SimpleNamespace

from roster_engine.saved_roster_export import (
    saved_roster_to_schedule,
)


def test_fc_swap_is_not_written_as_separate_excel_assignment() -> None:
    fc_cover = SimpleNamespace(
        assignment_kind="COVER",
        role_name=None,
        requesting_unit="A COY",
        cover_type="FC",
        assignment_date=date(2026, 8, 4),
        centre="PT",
        person_name="CPL MEDIC",
        points=1.0,
        is_overnight=False,
    )

    fc_swap = SimpleNamespace(
        assignment_kind="COVER",
        role_name=None,
        requesting_unit="A COY",
        cover_type="FC SWAP",
        assignment_date=date(2026, 8, 4),
        centre="PT",
        person_name="CPL MEDIC",
        points=0.5,
        is_overnight=False,
    )

    schedule = saved_roster_to_schedule(
        assignments=[
            fc_cover,
            fc_swap,
        ],
        dm_shadows=[],
    )

    assert len(schedule.assignments) == 1
    assert schedule.assignments[0].role == "A COY — FC"
