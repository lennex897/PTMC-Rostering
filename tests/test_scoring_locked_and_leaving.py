from datetime import date

from roster_engine.models import Assignment, Person, Schedule
from roster_engine.scoring import ScoringContext, score_candidate


def person(name: str, leaving_date: date | None = None) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre="PT",
        department="ALPHA",
        ampt_status="PASS",
        eligible_roles={"PT DM"},
        leaving_date=leaving_date,
    )


def overnight(name: str, duty_date: date) -> Assignment:
    return Assignment(
        duty_date=duty_date,
        role="PT DM",
        centre="PT",
        person_name=name,
        points=1.0,
        is_overnight=True,
    )


def test_future_locked_overnight_blocks_previous_day() -> None:
    medic = person("CPL MEDIC")
    schedule = Schedule(
        assignments=[
            overnight(medic.name, date(2026, 8, 10)),
        ]
    )

    score = score_candidate(
        medic,
        ScoringContext(
            duty_date=date(2026, 8, 9),
            role="PT DM",
            schedule=schedule,
            is_overnight=True,
            overnight_min_break_days=1,
        ),
    )

    assert not score.is_selectable


def test_locked_overnight_blocks_following_day() -> None:
    medic = person("CPL MEDIC")
    schedule = Schedule(
        assignments=[
            overnight(medic.name, date(2026, 8, 10)),
        ]
    )

    score = score_candidate(
        medic,
        ScoringContext(
            duty_date=date(2026, 8, 11),
            role="PT DM",
            schedule=schedule,
            is_overnight=True,
            overnight_min_break_days=1,
        ),
    )

    assert not score.is_selectable


def test_two_day_break_respects_future_locked_overnight() -> None:
    medic = person("CPL MEDIC")
    schedule = Schedule(
        assignments=[
            overnight(medic.name, date(2026, 8, 10)),
        ]
    )

    score = score_candidate(
        medic,
        ScoringContext(
            duty_date=date(2026, 8, 8),
            role="PT DM",
            schedule=schedule,
            is_overnight=True,
            overnight_min_break_days=2,
        ),
    )

    assert not score.is_selectable


def test_leaving_person_has_lower_priority() -> None:
    normal = person("CPL NORMAL")
    leaving = person(
        "CPL LEAVING",
        leaving_date=date(2026, 8, 31),
    )

    context = ScoringContext(
        duty_date=date(2026, 8, 24),
        role="PT DM",
        schedule=Schedule(),
        is_overnight=True,
        leaving_reduction_days=90,
    )

    assert (
        score_candidate(leaving, context).total
        < score_candidate(normal, context).total
    )
