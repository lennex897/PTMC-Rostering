from datetime import date

from roster_engine.eligibility import (
    allowed_roles_for_person,
    eligible_people_for_role,
    is_eligible_for_role,
)
from roster_engine.models import AvailabilityEntry, Person


def make_person(
    *,
    name: str = "CPL TEST PERSON",
    centre: str = "PT",
    ampt_status: str = "PASS",
    is_bcf: bool = False,
    leaving_date: date | None = None,
) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre=centre,
        department="TEST DEPARTMENT",
        ampt_status=ampt_status,
        is_bcf=is_bcf,
        leaving_date=leaving_date,
    )


def test_regular_pt_person_gets_pt_roles() -> None:
    person = make_person()

    roles = allowed_roles_for_person(person)

    assert "PT DM" in roles
    assert "PT CS1" in roles
    assert "PT SB1" in roles
    assert "RH DM" not in roles


def test_rh_person_gets_only_rh_roles() -> None:
    person = make_person(centre="RH")

    roles = allowed_roles_for_person(person)

    assert "RH DM" in roles
    assert "RH SB1" in roles
    assert "PT DM" not in roles


def test_bcf_person_only_gets_allowed_roles() -> None:
    person = make_person(is_bcf=True)

    assert allowed_roles_for_person(person) == {
        "PT AE",
        "PT SB1",
        "PT SB2",
    }


def test_invalid_ampt_gets_no_roles() -> None:
    person = make_person(ampt_status="FAIL")

    assert allowed_roles_for_person(person) == set()


def test_leave_blocks_assignment() -> None:
    duty_date = date(2026, 8, 4)
    person = make_person()

    availability = [
        AvailabilityEntry(
            person_name=person.name,
            unavailable_date=duty_date,
            reason="AL",
        )
    ]

    assert (
        is_eligible_for_role(
            person=person,
            role="PT DM",
            duty_date=duty_date,
            availability_entries=availability,
        )
        is False
    )


def test_person_is_eligible_when_available() -> None:
    person = make_person()

    assert (
        is_eligible_for_role(
            person=person,
            role="PT DM",
            duty_date=date(2026, 8, 4),
            availability_entries=[],
        )
        is True
    )


def test_wrong_centre_role_is_blocked() -> None:
    person = make_person(centre="RH")

    assert (
        is_eligible_for_role(
            person=person,
            role="PT DM",
            duty_date=date(2026, 8, 4),
            availability_entries=[],
        )
        is False
    )


def test_person_is_blocked_on_leaving_date() -> None:
    leaving_date = date(2026, 8, 19)

    person = make_person(
        leaving_date=leaving_date,
    )

    assert (
        is_eligible_for_role(
            person=person,
            role="PT DM",
            duty_date=leaving_date,
            availability_entries=[],
        )
        is False
    )


def test_person_is_allowed_before_leaving_date() -> None:
    person = make_person(
        leaving_date=date(2026, 8, 19),
    )

    assert (
        is_eligible_for_role(
            person=person,
            role="PT DM",
            duty_date=date(2026, 8, 18),
            availability_entries=[],
        )
        is True
    )


def test_eligible_people_filters_personnel() -> None:
    duty_date = date(2026, 8, 4)

    eligible_person = make_person(
        name="CPL ELIGIBLE PERSON",
    )

    bcf_person = make_person(
        name="CPL BCF PERSON",
        is_bcf=True,
    )

    rh_person = make_person(
        name="CPL RH PERSON",
        centre="RH",
    )

    results = eligible_people_for_role(
        personnel=[
            eligible_person,
            bcf_person,
            rh_person,
        ],
        role="PT DM",
        duty_date=duty_date,
        availability_entries=[],
    )

    assert results == [eligible_person]