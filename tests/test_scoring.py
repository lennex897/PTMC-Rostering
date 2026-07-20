from datetime import date

from roster_engine.models import (
    Assignment,
    Person,
    Schedule,
)
from roster_engine.scoring import (
    ScoringContext,
    rank_candidates,
    score_candidate,
)


def make_person(
    *,
    name: str = "CPL TEST PERSON",
    department: str = "ALPHA",
    leaving_date: date | None = None,
) -> Person:
    return Person(
        name=name,
        rank=name.split()[0],
        centre="PT",
        department=department,
        ampt_status="PASS",
        leaving_date=leaving_date,
    )


def add_overnight(
    schedule: Schedule,
    *,
    person_name: str,
    duty_date: date,
    points: float = 1.0,
) -> None:
    schedule.add_assignment(
        Assignment(
            duty_date=duty_date,
            role="PT DM",
            centre="PT",
            person_name=person_name,
            points=points,
            is_overnight=True,
        )
    )


def test_lower_points_produce_higher_score() -> None:
    low_points = make_person(
        name="CPL LOW POINTS",
    )
    high_points = make_person(
        name="CPL HIGH POINTS",
    )

    schedule = Schedule()

    add_overnight(
        schedule,
        person_name=high_points.name,
        duty_date=date(2026, 8, 1),
        points=2.0,
    )

    context = ScoringContext(
        duty_date=date(2026, 8, 5),
        role="PT DM",
        schedule=schedule,
    )

    low_result = score_candidate(
        low_points,
        context,
    )
    high_result = score_candidate(
        high_points,
        context,
    )

    assert low_result.total > high_result.total


def test_previous_day_overnight_blocks_candidate() -> None:
    person = make_person()
    schedule = Schedule()

    add_overnight(
        schedule,
        person_name=person.name,
        duty_date=date(2026, 8, 4),
    )

    result = score_candidate(
        person,
        ScoringContext(
            duty_date=date(2026, 8, 5),
            role="PT DM",
            schedule=schedule,
        ),
    )

    assert result.is_selectable is False
    assert any(
        "day break" in reason.lower()
        for reason in result.blocked_reasons
    )


def test_two_day_gap_is_allowed() -> None:
    person = make_person()
    schedule = Schedule()

    add_overnight(
        schedule,
        person_name=person.name,
        duty_date=date(2026, 8, 3),
    )

    result = score_candidate(
        person,
        ScoringContext(
            duty_date=date(2026, 8, 5),
            role="PT DM",
            schedule=schedule,
        ),
    )

    assert result.is_selectable is True


def test_weekly_limit_blocks_candidate() -> None:
    person = make_person()
    schedule = Schedule()

    for duty_day in [3, 5, 7]:
        add_overnight(
            schedule,
            person_name=person.name,
            duty_date=date(2026, 8, duty_day),
        )

    result = score_candidate(
        person,
        ScoringContext(
            duty_date=date(2026, 8, 9),
            role="PT DM",
            schedule=schedule,
            maximum_weekly_overnights=3,
        ),
    )

    assert result.is_selectable is False
    assert any(
        "maximum weekly" in reason.lower()
        for reason in result.blocked_reasons
    )


def test_same_department_receives_penalty() -> None:
    person = make_person(
        department="ALPHA",
    )

    schedule = Schedule()

    repeated = score_candidate(
        person,
        ScoringContext(
            duty_date=date(2026, 8, 5),
            role="PT DM",
            schedule=schedule,
            selected_departments=frozenset(
                {"ALPHA"}
            ),
        ),
    )

    new_department = score_candidate(
        person,
        ScoringContext(
            duty_date=date(2026, 8, 5),
            role="PT DM",
            schedule=schedule,
            selected_departments=frozenset(
                {"BRAVO"}
            ),
        ),
    )

    assert repeated.total < new_department.total


def test_leaving_person_receives_penalty() -> None:
    regular = make_person(
        name="CPL REGULAR",
    )
    leaving = make_person(
        name="CPL LEAVING",
        leaving_date=date(2026, 8, 31),
    )

    context = ScoringContext(
        duty_date=date(2026, 8, 5),
        role="PT DM",
        schedule=Schedule(),
    )

    assert (
        score_candidate(leaving, context).total
        < score_candidate(regular, context).total
    )


def test_samuel_tan_receives_ae_penalty() -> None:
    samuel = make_person(
        name="3SG SAMUEL TAN ENG WEE",
    )
    regular = make_person(
        name="3SG REGULAR PERSON",
    )

    context = ScoringContext(
        duty_date=date(2026, 8, 5),
        role="PT AE",
        schedule=Schedule(),
    )

    assert (
        score_candidate(samuel, context).total
        < score_candidate(regular, context).total
    )


def test_stephen_tay_receives_cs_penalty() -> None:
    stephen = make_person(
        name="LCP STEPHEN TAY",
    )
    regular = make_person(
        name="LCP REGULAR PERSON",
    )

    context = ScoringContext(
        duty_date=date(2026, 8, 5),
        role="PT CS1",
        schedule=Schedule(),
    )

    assert (
        score_candidate(stephen, context).total
        < score_candidate(regular, context).total
    )


def test_rank_candidates_places_best_first() -> None:
    low_points = make_person(
        name="CPL LOW POINTS",
    )
    high_points = make_person(
        name="CPL HIGH POINTS",
    )

    schedule = Schedule()

    add_overnight(
        schedule,
        person_name=high_points.name,
        duty_date=date(2026, 8, 1),
        points=2.0,
    )

    results = rank_candidates(
        personnel=[
            high_points,
            low_points,
        ],
        context=ScoringContext(
            duty_date=date(2026, 8, 5),
            role="PT DM",
            schedule=schedule,
        ),
    )

    assert results[0].person == low_points