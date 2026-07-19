from datetime import date

from roster_engine.generator import (
    GenerationSettings,
    assignments_in_target_month,
    generate_roster,
    unfilled_requirements_by_date,
)
from roster_engine.models import (
    Assignment,
    AvailabilityEntry,
    Person,
    Schedule,
)
from roster_engine.requirements import (
    RequirementSettings,
)


def make_person(
    name: str,
    *,
    centre: str = "PT",
    department: str = "ALPHA",
) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre=centre,
        department=department,
        ampt_status="PASS",
    )


def minimal_requirement_settings(
) -> RequirementSettings:
    return RequirementSettings(
        include_pt_core_roles=True,
        include_pt_csb=False,
        include_pt_sb2=False,
        include_rh_sb1_deployment=False,
        include_rh_sb2_deployment=False,
    )


def test_generate_roster_returns_report() -> None:
    personnel = [
        make_person(
            f"CPL PERSON {number}",
            department=f"DEPT {number}",
        )
        for number in range(1, 20)
    ]

    result = generate_roster(
        personnel=personnel,
        availability_entries=[],
        settings=GenerationSettings(
            year=2026,
            month=8,
            requirement_settings=(
                minimal_requirement_settings()
            ),
        ),
    )

    assert result.report.year == 2026
    assert result.report.month == 8
    assert result.report.personnel_count == 19
    assert result.report.requirement_count > 0
    assert (
        result.report.generated_assignment_count
        == len(
            assignments_in_target_month(
                result.schedule,
                2026,
                8,
            )
        )
    )


def test_report_detects_unfilled_requirements() -> None:
    result = generate_roster(
        personnel=[],
        availability_entries=[],
        settings=GenerationSettings(
            year=2026,
            month=8,
            requirement_settings=(
                minimal_requirement_settings()
            ),
        ),
    )

    assert result.report.is_complete is False
    assert result.report.generated_assignment_count == 0
    assert result.report.unfilled_requirement_count > 0
    assert result.report.completion_rate == 0.0


def test_leave_entries_are_used() -> None:
    person = make_person(
        "CPL PERSON ONE",
    )

    leave_date = date(2026, 8, 1)

    result = generate_roster(
        personnel=[person],
        availability_entries=[
            AvailabilityEntry(
                person_name=person.name,
                unavailable_date=leave_date,
                reason="AL",
            )
        ],
        settings=GenerationSettings(
            year=2026,
            month=8,
            requirement_settings=(
                minimal_requirement_settings()
            ),
        ),
    )

    assignments_on_leave_date = [
        assignment
        for assignment in result.schedule.assignments
        if assignment.duty_date == leave_date
        and assignment.person_name == person.name
    ]

    assert assignments_on_leave_date == []


def test_historical_assignments_affect_generation() -> None:
    person_one = make_person(
        "CPL PERSON ONE",
    )

    person_two = make_person(
        "CPL PERSON TWO",
    )

    historical_schedule = Schedule(
        assignments=[
            Assignment(
                duty_date=date(2026, 7, 31),
                role="PT DM",
                centre="PT",
                person_name=person_one.name,
                points=1.5,
                is_overnight=True,
            )
        ]
    )

    result = generate_roster(
        personnel=[
            person_one,
            person_two,
        ],
        availability_entries=[],
        settings=GenerationSettings(
            year=2026,
            month=8,
            requirement_settings=(
                minimal_requirement_settings()
            ),
        ),
        historical_schedule=historical_schedule,
    )

    assignments_on_first_day = [
        assignment
        for assignment in result.schedule.assignments
        if assignment.duty_date
        == date(2026, 8, 1)
    ]

    assert assignments_on_first_day
    assert all(
        assignment.person_name
        != person_one.name
        for assignment in assignments_on_first_day
    )


def test_assignments_in_target_month_filters_history() -> None:
    schedule = Schedule(
        assignments=[
            Assignment(
                duty_date=date(2026, 7, 31),
                role="PT DM",
                centre="PT",
                person_name="CPL HISTORICAL",
                points=1.5,
                is_overnight=True,
            ),
            Assignment(
                duty_date=date(2026, 8, 1),
                role="PT DM",
                centre="PT",
                person_name="CPL GENERATED",
                points=2.0,
                is_overnight=True,
            ),
        ]
    )

    assignments = assignments_in_target_month(
        schedule=schedule,
        year=2026,
        month=8,
    )

    assert len(assignments) == 1
    assert (
        assignments[0].person_name
        == "CPL GENERATED"
    )


def test_unfilled_requirements_are_grouped_by_date() -> None:
    result = generate_roster(
        personnel=[],
        availability_entries=[],
        settings=GenerationSettings(
            year=2026,
            month=8,
            requirement_settings=(
                minimal_requirement_settings()
            ),
        ),
    )

    grouped = unfilled_requirements_by_date(
        result
    )

    assert grouped
    assert date(2026, 8, 1) in grouped
    assert all(
        requirement.duty_date == duty_date
        for duty_date, requirements in grouped.items()
        for requirement in requirements
    )