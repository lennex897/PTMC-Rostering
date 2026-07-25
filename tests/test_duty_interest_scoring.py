from datetime import date

from roster_engine.duty_interest_repository import DutyInterest
from roster_engine.models import DutyRequirement, Person
from roster_engine.scheduler import generate_schedule


def person(
    name: str,
    *,
    centre: str = "PT",
    roles: set[str] | None = None,
) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre=centre,
        department=name,
        ampt_status="PASS",
        eligible_roles=roles or {"PT DM"},
    )


def test_interested_candidate_wins_when_other_factors_are_equal() -> None:
    interested = person("CPL INTERESTED")
    regular = person("CPL REGULAR")
    duty_date = date(2026, 8, 4)

    result = generate_schedule(
        personnel=[regular, interested],
        requirements=[
            DutyRequirement(
                duty_date=duty_date,
                role="PT DM",
                centre="PT",
                is_overnight=True,
                points=1.0,
            )
        ],
        availability_entries=[],
        duty_interests=[
            DutyInterest(
                id="i1",
                roster_month_id="m1",
                personnel_id="p1",
                person_name=interested.name,
                centre="PT",
                interest_date=duty_date,
                preferred_role=None,
            )
        ],
    )

    assert (
        result.schedule.assignments[0].person_name
        == interested.name
    )

    score = result.assignment_scores[
        (duty_date, "PT DM")
    ]

    assert any(
        component.description
        == "PTMC overnight duty interest"
        for component in score.components
    )


def test_specific_role_interest_only_boosts_matching_role() -> None:
    interested = person(
        "CPL INTERESTED",
        roles={"PT DM", "PT CS1"},
    )
    regular = person(
        "CPL REGULAR",
        roles={"PT DM", "PT CS1"},
    )
    duty_date = date(2026, 8, 4)

    result = generate_schedule(
        personnel=[regular, interested],
        requirements=[
            DutyRequirement(
                duty_date=duty_date,
                role="PT DM",
                centre="PT",
                is_overnight=True,
                points=1.0,
            )
        ],
        availability_entries=[],
        duty_interests=[
            DutyInterest(
                id="i1",
                roster_month_id="m1",
                personnel_id="p1",
                person_name=interested.name,
                centre="PT",
                interest_date=duty_date,
                preferred_role="PT CS1",
            )
        ],
    )

    assert len(result.schedule.assignments) == 1

    score = result.assignment_scores[
        (duty_date, "PT DM")
    ]

    assert all(
        component.description
        != "PTMC overnight duty interest"
        for component in score.components
    )


def test_interest_does_not_apply_to_day_duty() -> None:
    interested = person(
        "CPL RH INTERESTED",
        centre="RH",
        roles={"RH DM"},
    )
    regular = person(
        "CPL RH REGULAR",
        centre="RH",
        roles={"RH DM"},
    )
    duty_date = date(2026, 8, 4)

    result = generate_schedule(
        personnel=[regular, interested],
        requirements=[
            DutyRequirement(
                duty_date=duty_date,
                role="RH DM",
                centre="RH",
                is_overnight=False,
                points=0.5,
            )
        ],
        availability_entries=[],
        duty_interests=[
            DutyInterest(
                id="i1",
                roster_month_id="m1",
                personnel_id="p1",
                person_name=interested.name,
                centre="RH",
                interest_date=duty_date,
                preferred_role=None,
            )
        ],
    )

    assert len(result.schedule.assignments) == 1

    score = result.assignment_scores[
        (duty_date, "RH DM")
    ]

    assert all(
        component.description
        != "PTMC overnight duty interest"
        for component in score.components
    )


def test_rh_sb1_interest_affects_only_rh_sb1_requirement() -> None:
    interested = person(
        "CPL RH INTERESTED",
        centre="RH",
        roles={"RH SB1"},
    )
    regular = person(
        "CPL RH REGULAR",
        centre="RH",
        roles={"RH SB1"},
    )
    duty_date = date(2026, 8, 4)

    result = generate_schedule(
        personnel=[regular, interested],
        requirements=[
            DutyRequirement(
                duty_date=duty_date,
                role="RH SB1",
                centre="PT",
                is_overnight=True,
                points=1.0,
            )
        ],
        availability_entries=[],
        duty_interests=[
            DutyInterest(
                id="i1",
                roster_month_id="m1",
                personnel_id="p1",
                person_name=interested.name,
                centre="RH",
                interest_date=duty_date,
                preferred_role="RH SB1",
            )
        ],
    )

    assert (
        result.schedule.assignments[0].person_name
        == interested.name
    )


def test_interest_does_not_override_leave() -> None:
    from roster_engine.models import AvailabilityEntry

    interested = person("CPL INTERESTED")
    regular = person("CPL REGULAR")
    duty_date = date(2026, 8, 4)

    result = generate_schedule(
        personnel=[regular, interested],
        requirements=[
            DutyRequirement(
                duty_date=duty_date,
                role="PT DM",
                centre="PT",
                is_overnight=True,
                points=1.0,
            )
        ],
        availability_entries=[
            AvailabilityEntry(
                person_name=interested.name,
                unavailable_date=duty_date,
                reason="AL",
            )
        ],
        duty_interests=[
            DutyInterest(
                id="i1",
                roster_month_id="m1",
                personnel_id="p1",
                person_name=interested.name,
                centre="PT",
                interest_date=duty_date,
                preferred_role=None,
            )
        ],
    )

    assert (
        result.schedule.assignments[0].person_name
        == regular.name
    )