from datetime import date

from roster_engine.generated_roster_repository import (
    GeneratedRosterRepository,
    StoredGeneratedAssignment,
)


def test_row_to_assignment_parses_generated_assignment() -> None:
    row = {
        "id": "a1",
        "generation_id": "g1",
        "roster_month_id": "m1",
        "personnel_id": "p1",
        "person_name": "CPL TEST",
        "assignment_date": "2026-08-03",
        "assignment_kind": "DUTY",
        "centre": "PT",
        "role_name": "PT DM",
        "cover_requirement_id": None,
        "requesting_unit": None,
        "cover_category": None,
        "cover_type": None,
        "session": "FULL_DAY",
        "points": 1.0,
        "is_overnight": True,
        "is_reserve": False,
        "is_locked": True,
    }

    assignment = GeneratedRosterRepository._row_to_assignment(row)

    assert isinstance(
        assignment,
        StoredGeneratedAssignment,
    )
    assert assignment.assignment_date == date(2026, 8, 3)
    assert assignment.role_name == "PT DM"
    assert assignment.is_locked is True
