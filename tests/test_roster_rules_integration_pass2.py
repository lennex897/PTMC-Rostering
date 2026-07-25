from datetime import date

from roster_engine.models import (
    Assignment,
    DutyRequirement,
    Person,
    Schedule,
)
from roster_engine.roster_rules import RosterRules
from roster_engine.scheduler import generate_schedule
from roster_engine.scoring import ScoringContext, score_candidate
from roster_engine.validator import validate_schedule


def person(name: str) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre="PT",
        department="ALPHA",
        ampt_status="PASS",
        eligible_roles={"PT DM"},
    )


def requirement(day: int) -> DutyRequirement:
    return DutyRequirement(
        duty_date=date(2026, 8, day),
        role="PT DM",
        centre="PT",
        is_overnight=True,
        points=1.0,
    )


def test_manual_only_person_is_excluded_from_automatic_duty() -> None:
    manual_only = person("CPL MANUAL ONLY")
    regular = person("CPL REGULAR")

    result = generate_schedule(
        personnel=[manual_only, regular],
        requirements=[requirement(3)],
        availability_entries=[],
        manual_only_personnel=(
            manual_only.name,
        ),
    )

    assert (
        result.schedule.assignments[0].person_name
        == regular.name
    )


def test_leaving_reduction_window_is_rule_driven() -> None:
    leaving = Person(
        name="CPL LEAVING",
        rank="CPL",
        centre="PT",
        department="ALPHA",
        ampt_status="PASS",
        eligible_roles={"PT DM"},
        leaving_date=date(2026, 10, 1),
    )

    context_short = ScoringContext(
        duty_date=date(2026, 8, 1),
        role="PT DM",
        schedule=Schedule(),
        is_overnight=True,
        leaving_reduction_days=30,
    )

    context_long = ScoringContext(
        duty_date=date(2026, 8, 1),
        role="PT DM",
        schedule=Schedule(),
        is_overnight=True,
        leaving_reduction_days=90,
    )

    short_score = score_candidate(
        leaving,
        context_short,
    )

    long_score = score_candidate(
        leaving,
        context_long,
    )

    assert long_score.total < short_score.total


def test_custom_overnight_break_rule_blocks_two_day_gap_when_set_to_two() -> None:
    medic = person("CPL MEDIC")

    schedule = Schedule(
        assignments=[
            Assignment(
                duty_date=date(2026, 8, 3),
                role="PT DM",
                centre="PT",
                person_name=medic.name,
                points=1.0,
                is_overnight=True,
            )
        ]
    )

    context = ScoringContext(
        duty_date=date(2026, 8, 5),
        role="PT DM",
        schedule=schedule,
        is_overnight=True,
        overnight_min_break_days=2,
    )

    score = score_candidate(
        medic,
        context,
    )

    assert not score.is_selectable


def test_validator_uses_custom_overnight_break_rule() -> None:
    medic = person("CPL MEDIC")

    schedule = Schedule(
        assignments=[
            Assignment(
                duty_date=date(2026, 8, 3),
                role="PT DM",
                centre="PT",
                person_name=medic.name,
                points=1.0,
                is_overnight=True,
            ),
            Assignment(
                duty_date=date(2026, 8, 5),
                role="PT DM",
                centre="PT",
                person_name=medic.name,
                points=1.0,
                is_overnight=True,
            ),
        ]
    )

    report = validate_schedule(
        schedule=schedule,
        personnel=[medic],
        availability_entries=[],
        requirements=[
            requirement(3),
            requirement(5),
        ],
        year=2026,
        month=8,
        overnight_min_break_days=2,
    )

    assert any(
        issue.code
        == "INSUFFICIENT_OVERNIGHT_BREAK"
        for issue in report.errors
    )
