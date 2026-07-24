from datetime import date

from roster_engine.manual_planning_repository import (
    ManualAssignment,
)


def test_manual_duty_builds_qualified_role() -> None:
    assignment = ManualAssignment(
        id="a1",
        roster_month_id="m1",
        personnel_name="CPL TEST",
        assignment_date=date(2026, 8, 3),
        assignment_kind="DUTY",
        centre="PT",
        role_name="DM",
        cover_requirement_id=None,
        cover_label=None,
        session="FULL_DAY",
        is_locked=True,
        allow_override=False,
    )

    assert assignment.qualified_role == "PT DM"


def test_already_qualified_role_is_preserved() -> None:
    assignment = ManualAssignment(
        id="a1",
        roster_month_id="m1",
        personnel_name="CPL TEST",
        assignment_date=date(2026, 8, 3),
        assignment_kind="DUTY",
        centre="PT",
        role_name="PT DM",
        cover_requirement_id=None,
        cover_label=None,
        session="FULL_DAY",
        is_locked=True,
        allow_override=False,
    )

    assert assignment.qualified_role == "PT DM"


def test_cover_has_no_qualified_role() -> None:
    assignment = ManualAssignment(
        id="a1",
        roster_month_id="m1",
        personnel_name="CPL TEST",
        assignment_date=date(2026, 8, 3),
        assignment_kind="COVER",
        centre=None,
        role_name=None,
        cover_requirement_id="cover-1",
        cover_label="1 COY — IPPT",
        session="AM",
        is_locked=True,
        allow_override=False,
    )

    assert assignment.qualified_role is None
