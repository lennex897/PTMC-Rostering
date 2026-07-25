from datetime import date
from types import SimpleNamespace

from roster_engine.planning_generation import (
    _apply_locked_reserves,
    _split_locked_manual_assignments,
)


def reserve_assignment():
    return SimpleNamespace(
        id="reserve-1",
        roster_month_id="month-1",
        personnel_name="CPL RESERVE",
        assignment_date=date(2026, 8, 3),
        assignment_kind="RESERVE",
        centre="PT",
        role_name="RESERVE",
        qualified_role="PT RESERVE",
        cover_requirement_id=None,
        cover_label=None,
        session="FULL_DAY",
        is_locked=True,
        allow_override=False,
        remarks=None,
    )


def test_manual_reserve_is_split_from_generated_duties() -> None:
    duties, reserves, covers = _split_locked_manual_assignments(
        [reserve_assignment()]
    )

    assert duties == []
    assert len(reserves) == 1
    assert covers == []


def test_manual_reserve_becomes_zero_point_commitment() -> None:
    assignments = _apply_locked_reserves(
        [reserve_assignment()]
    )

    assert len(assignments) == 1
    assignment = assignments[0]

    assert assignment.role == "PT RESERVE"
    assert assignment.points == 0.0
    assert assignment.is_overnight is False
