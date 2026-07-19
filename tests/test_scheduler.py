from datetime import date

from roster_engine.models import (
    AvailabilityEntry,
    DutyRequirement,
    Person,
    RolePriority,
)
from roster_engine.scheduler import generate_schedule


def make_person(
    *,
    name: str,
    centre: str = "PT",
    department: str = "ALPHA",
    is_bcf: bool = False,
    ampt_status: str = "PASS",
) -> Person:
    return Person(
        name=name,
        rank=name.split()[0],
        centre=centre,
        department=department,
        ampt_status=ampt_status,
        is_bcf=is_bcf,
    )


def make_requirement(
    *,
    duty_date: date,
    role: str,
    centre: str = "PT",
    is_overnight: bool = True,
    points: float = 1.0,
) -> DutyRequirement:
    return DutyRequirement(
        duty_date=duty_date,
        role=role,
        centre=centre,
        is_overnight=is_overnight,
        points=points,
    )


def test_scheduler_assigns_eligible_person() -> None:
    person = make_person(
        name="CPL TEST PERSON",
    )

    requirement = make_requirement(
        duty_date=date(2026, 8, 3),
        role="PT DM",
    )

    result = generate_schedule(
        personnel=[person],
        requirements=[requirement],
        availability_entries=[],
    )

    assert result.is_complete is True
    assert len(result.schedule.assignments) == 1
    assert (
        result.schedule.assignments[0].person_name
        == person.name
    )


def test_scheduler_does_not_assign_person_on_leave() -> None:
    person = make_person(
        name="CPL TEST PERSON",
    )

    duty_date = date(2026, 8, 3)

    result = generate_schedule(
        personnel=[person],
        requirements=[
            make_requirement(
                duty_date=duty_date,
                role="PT DM",
            )
        ],
        availability_entries=[
            AvailabilityEntry(
                person_name=person.name,
                unavailable_date=duty_date,
                reason="AL",
            )
        ],
    )

    assert result.is_complete is False
    assert len(result.schedule.assignments) == 0
    assert len(result.unfilled_requirements) == 1


def test_scheduler_does_not_assign_same_person_twice_same_day() -> None:
    person = make_person(
        name="CPL ONLY PERSON",
    )

    duty_date = date(2026, 8, 3)

    requirements = [
        make_requirement(
            duty_date=duty_date,
            role="PT DM",
        ),
        make_requirement(
            duty_date=duty_date,
            role="PT CS1",
        ),
    ]

    result = generate_schedule(
        personnel=[person],
        requirements=requirements,
        availability_entries=[],
    )

    assert len(result.schedule.assignments) == 1
    assert len(result.unfilled_requirements) == 1


def test_scheduler_respects_bcf_role_restrictions() -> None:
    bcf_person = make_person(
        name="CPL BCF PERSON",
        is_bcf=True,
    )

    result = generate_schedule(
        personnel=[bcf_person],
        requirements=[
            make_requirement(
                duty_date=date(2026, 8, 3),
                role="PT DM",
            )
        ],
        availability_entries=[],
    )

    assert result.is_complete is False
    assert result.schedule.assignments == []


def test_scheduler_can_assign_bcf_to_sb1() -> None:
    bcf_person = make_person(
        name="CPL BCF PERSON",
        is_bcf=True,
    )

    result = generate_schedule(
        personnel=[bcf_person],
        requirements=[
            make_requirement(
                duty_date=date(2026, 8, 3),
                role="PT SB1",
            )
        ],
        availability_entries=[],
    )

    assert result.is_complete is True
    assert (
        result.schedule.assignments[0].person_name
        == bcf_person.name
    )


def test_scheduler_uses_role_priority() -> None:
    preferred = make_person(
        name="CPL PREFERRED PERSON",
        department="ALPHA",
    )

    regular = make_person(
        name="CPL REGULAR PERSON",
        department="BRAVO",
    )

    priority = RolePriority(
        person_name=preferred.name,
        role="PT DM",
        adjustment=25.0,
        reason="Higher DM priority",
    )

    result = generate_schedule(
        personnel=[
            regular,
            preferred,
        ],
        requirements=[
            make_requirement(
                duty_date=date(2026, 8, 3),
                role="PT DM",
            )
        ],
        availability_entries=[],
        role_priorities=(priority,),
    )

    assert (
        result.schedule.assignments[0].person_name
        == preferred.name
    )


def test_scheduler_respects_overnight_day_break() -> None:
    person_one = make_person(
        name="CPL PERSON ONE",
    )

    person_two = make_person(
        name="CPL PERSON TWO",
    )

    requirements = [
        make_requirement(
            duty_date=date(2026, 8, 3),
            role="PT DM",
        ),
        make_requirement(
            duty_date=date(2026, 8, 4),
            role="PT DM",
        ),
    ]

    result = generate_schedule(
        personnel=[
            person_one,
            person_two,
        ],
        requirements=requirements,
        availability_entries=[],
    )

    assignments = result.schedule.assignments

    assert len(assignments) == 2
    assert (
        assignments[0].person_name
        != assignments[1].person_name
    )


def test_scheduler_tracks_assignment_score() -> None:
    person = make_person(
        name="CPL TEST PERSON",
    )

    duty_date = date(2026, 8, 3)

    result = generate_schedule(
        personnel=[person],
        requirements=[
            make_requirement(
                duty_date=duty_date,
                role="PT DM",
            )
        ],
        availability_entries=[],
    )

    score = result.assignment_scores[
        (duty_date, "PT DM")
    ]

    assert score.person == person
    assert score.components