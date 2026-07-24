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
    eligible_roles: set[str] | None = None,
    leaving_date: date | None = None,
    is_active: bool = True,
) -> Person:
    if eligible_roles is None:
        eligible_roles = (
            {"PT DM", "PT CS1", "PT SB1"}
            if centre == "PT"
            else {"RH DM", "RH SB1"}
        )
    return Person(
        name=name,
        rank="CPL",
        centre=centre,
        department="TEST DEPARTMENT",
        ampt_status=ampt_status,
        eligible_roles=eligible_roles,
        leaving_date=leaving_date,
        is_active=is_active,
    )


def test_pt_person_gets_only_configured_pt_roles() -> None:
    person = make_person(eligible_roles={"PT DM", "PT SB1"})
    assert allowed_roles_for_person(person) == {"PT DM", "PT SB1"}


def test_rh_person_gets_only_configured_rh_roles() -> None:
    person = make_person(centre="RH", eligible_roles={"RH SB1", "RH SB2"})
    assert allowed_roles_for_person(person) == {"RH SB1", "RH SB2"}


def test_cross_centre_role_is_ignored_even_if_misconfigured() -> None:
    person = make_person(centre="RH", eligible_roles={"RH SB1", "PT DM"})
    assert allowed_roles_for_person(person) == {"RH SB1"}


def test_person_with_no_configured_roles_gets_no_roles() -> None:
    person = make_person(eligible_roles=set())
    assert allowed_roles_for_person(person) == set()


def test_invalid_ampt_gets_no_roles() -> None:
    person = make_person(ampt_status="FAIL")
    assert allowed_roles_for_person(person) == set()


def test_inactive_person_gets_no_roles() -> None:
    person = make_person(is_active=False)
    assert allowed_roles_for_person(person) == set()


def test_leave_blocks_assignment() -> None:
    duty_date = date(2026, 8, 4)
    person = make_person()
    availability = [AvailabilityEntry(person_name=person.name, unavailable_date=duty_date, reason="AL")]
    assert not is_eligible_for_role(person, "PT DM", duty_date, availability)


def test_person_is_eligible_when_available_and_role_configured() -> None:
    person = make_person(eligible_roles={"PT DM"})
    assert is_eligible_for_role(person, "PT DM", date(2026, 8, 4), [])


def test_unconfigured_role_is_blocked() -> None:
    person = make_person(eligible_roles={"PT SB1"})
    assert not is_eligible_for_role(person, "PT DM", date(2026, 8, 4), [])


def test_wrong_centre_role_is_blocked() -> None:
    person = make_person(centre="RH", eligible_roles={"RH SB1"})
    assert not is_eligible_for_role(person, "PT DM", date(2026, 8, 4), [])


def test_person_is_blocked_on_leaving_date() -> None:
    leaving_date = date(2026, 8, 19)
    person = make_person(leaving_date=leaving_date)
    assert not is_eligible_for_role(person, "PT DM", leaving_date, [])


def test_person_is_allowed_before_leaving_date() -> None:
    person = make_person(leaving_date=date(2026, 8, 19))
    assert is_eligible_for_role(person, "PT DM", date(2026, 8, 18), [])


def test_eligible_people_filters_by_configured_roles() -> None:
    duty_date = date(2026, 8, 4)
    eligible_person = make_person(name="CPL ELIGIBLE PERSON", eligible_roles={"PT DM"})
    junior_only = make_person(name="CPL JUNIOR PERSON", eligible_roles={"PT SB1"})
    rh_person = make_person(name="CPL RH PERSON", centre="RH", eligible_roles={"RH SB1"})
    results = eligible_people_for_role(
        personnel=[eligible_person, junior_only, rh_person],
        role="PT DM",
        duty_date=duty_date,
        availability_entries=[],
    )
    assert results == [eligible_person]
