from datetime import date

from roster_engine.models import (
    Assignment,
    AvailabilityEntry,
    DutyRequirement,
    Person,
    Schedule,
)
from roster_engine.validator import validate_schedule


def make_person(
    name: str = "CPL TEST PERSON",
) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre="PT",
        department="ALPHA",
        ampt_status="PASS",
    )


def make_requirement(
    duty_date: date,
    role: str = "PT DM",
) -> DutyRequirement:
    return DutyRequirement(
        duty_date=duty_date,
        role=role,
        centre="PT",
        is_overnight=True,
        points=1.0,
    )


def make_assignment(
    duty_date: date,
    person_name: str = "CPL TEST PERSON",
    role: str = "PT DM",
) -> Assignment:
    return Assignment(
        duty_date=duty_date,
        role=role,
        centre="PT",
        person_name=person_name,
        points=1.0,
        is_overnight=True,
    )


def test_valid_schedule_passes() -> None:
    duty_date = date(2026, 8, 3)
    person = make_person()

    report = validate_schedule(
        schedule=Schedule(
            assignments=[
                make_assignment(duty_date),
            ]
        ),
        personnel=[person],
        availability_entries=[],
        requirements=[
            make_requirement(duty_date),
        ],
        year=2026,
        month=8,
    )

    assert report.is_valid
    assert report.error_count == 0


def test_missing_requirement_fails() -> None:
    duty_date = date(2026, 8, 3)

    report = validate_schedule(
        schedule=Schedule(),
        personnel=[make_person()],
        availability_entries=[],
        requirements=[
            make_requirement(duty_date),
        ],
        year=2026,
        month=8,
    )

    assert not report.is_valid
    assert any(
        issue.code == "MISSING_REQUIREMENT"
        for issue in report.errors
    )


def test_person_on_leave_fails() -> None:
    duty_date = date(2026, 8, 3)
    person = make_person()

    report = validate_schedule(
        schedule=Schedule(
            assignments=[
                make_assignment(duty_date),
            ]
        ),
        personnel=[person],
        availability_entries=[
            AvailabilityEntry(
                person_name=person.name,
                unavailable_date=duty_date,
                reason="AL",
            )
        ],
        requirements=[
            make_requirement(duty_date),
        ],
        year=2026,
        month=8,
    )

    assert not report.is_valid
    assert any(
        issue.code == "INELIGIBLE_ASSIGNMENT"
        for issue in report.errors
    )


def test_same_person_twice_same_day_fails() -> None:
    duty_date = date(2026, 8, 3)
    person = make_person()

    report = validate_schedule(
        schedule=Schedule(
            assignments=[
                make_assignment(
                    duty_date,
                    role="PT DM",
                ),
                make_assignment(
                    duty_date,
                    role="PT CS1",
                ),
            ]
        ),
        personnel=[person],
        availability_entries=[],
        requirements=[
            make_requirement(
                duty_date,
                role="PT DM",
            ),
            make_requirement(
                duty_date,
                role="PT CS1",
            ),
        ],
        year=2026,
        month=8,
    )

    assert not report.is_valid
    assert any(
        issue.code
        == "MULTIPLE_ASSIGNMENTS_SAME_DAY"
        for issue in report.errors
    )


def test_consecutive_overnights_fail() -> None:
    person = make_person()
    first_date = date(2026, 8, 3)
    second_date = date(2026, 8, 4)

    report = validate_schedule(
        schedule=Schedule(
            assignments=[
                make_assignment(first_date),
                make_assignment(second_date),
            ]
        ),
        personnel=[person],
        availability_entries=[],
        requirements=[
            make_requirement(first_date),
            make_requirement(second_date),
        ],
        year=2026,
        month=8,
    )

    assert not report.is_valid
    assert any(
        issue.code
        == "INSUFFICIENT_OVERNIGHT_BREAK"
        for issue in report.errors
    )