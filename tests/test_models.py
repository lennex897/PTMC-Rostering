from datetime import date

from roster_engine.models import (
    Assignment,
    Person,
    Schedule,
)


def test_person_ampt_pass_is_valid() -> None:
    person = Person(
        name="TEST PERSON",
        rank="CPL",
        centre="PT",
        department="DEPARTMENT A",
        ampt_status="PASS",
    )

    assert person.is_ampt_valid is True


def test_person_ampt_fail_is_invalid() -> None:
    person = Person(
        name="TEST PERSON",
        rank="CPL",
        centre="PT",
        department="DEPARTMENT A",
        ampt_status="FAIL",
    )

    assert person.is_ampt_valid is False


def test_schedule_calculates_person_points() -> None:
    schedule = Schedule()

    schedule.add_assignment(
        Assignment(
            duty_date=date(2026, 8, 3),
            role="PT DM",
            centre="PT",
            person_name="TEST PERSON",
            points=1.0,
            is_overnight=True,
        )
    )

    schedule.add_assignment(
        Assignment(
            duty_date=date(2026, 8, 7),
            role="PT CS1",
            centre="PT",
            person_name="TEST PERSON",
            points=1.5,
            is_overnight=True,
        )
    )

    assert schedule.total_points_for_person(
        "TEST PERSON"
    ) == 2.5