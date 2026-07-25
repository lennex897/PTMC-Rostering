from datetime import date

from roster_engine.duty_interest_repository import DutyInterest
from roster_engine.generator import GenerationSettings
from roster_engine.models import Person, RosterMonth
from roster_engine.planning_generation import generate_roster_from_planning
from roster_engine.planning_loader import PlanningContext
from roster_engine.requirements import RequirementSettings


def make_person(name: str) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre="PT",
        department=name,
        ampt_status="PASS",
        eligible_roles={
            "PT DM",
            "PT CS1",
            "PT CS2",
            "PT SB1",
            "PT AE",
        },
        is_cover_fit=False,
    )


def test_planning_context_interests_reach_duty_scheduler() -> None:
    interested = make_person("CPL INTERESTED")
    others = [
        make_person(f"CPL PERSON {number}")
        for number in range(1, 8)
    ]

    duty_date = date(2026, 8, 1)

    planning = PlanningContext(
        roster_month=RosterMonth(
            id="m1",
            month_start=date(2026, 8, 1),
            status="draft",
        ),
        personnel=[*others, interested],
        availability_entries=[],
        cover_types=[],
        cover_requirements=[],
        cover_slots=[],
        manual_assignments=[],
        duty_interests=[
            DutyInterest(
                id="i1",
                roster_month_id="m1",
                personnel_id="p-interested",
                person_name=interested.name,
                centre="PT",
                interest_date=duty_date,
                preferred_role="PT DM",
            )
        ],
    )

    result = generate_roster_from_planning(
        planning=planning,
        settings=GenerationSettings(
            year=2026,
            month=8,
            requirement_settings=RequirementSettings(
                include_pt_core_roles=True,
                include_pt_csb=False,
                include_pt_sb2=False,
                include_rh_sb1_deployment=False,
                include_rh_sb2_deployment=False,
            ),
        ),
    )

    dm_assignment = next(
        assignment
        for assignment in result.schedule.assignments
        if (
            assignment.duty_date == duty_date
            and assignment.role == "PT DM"
        )
    )

    assert dm_assignment.person_name == interested.name
