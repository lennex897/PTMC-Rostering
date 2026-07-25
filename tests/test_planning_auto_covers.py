from datetime import date

from roster_engine.cover_repository import DailyCoverSlot
from roster_engine.generator import GenerationSettings
from roster_engine.models import Person, RosterMonth
from roster_engine.planning_generation import generate_roster_from_planning
from roster_engine.planning_loader import PlanningContext
from roster_engine.requirements import RequirementSettings


def make_person(name: str, *, cover_fit: bool) -> Person:
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
        is_cover_fit=cover_fit,
    )


def test_planning_generation_autofills_cover_before_duties() -> None:
    cover_fit = make_person("CPL COVER FIT", cover_fit=True)

    others = [
        make_person(f"CPL OTHER {n}", cover_fit=False)
        for n in range(1, 8)
    ]

    planning = PlanningContext(
        roster_month=RosterMonth(
            id="month-1",
            month_start=date(2026, 8, 1),
            status="draft",
        ),
        personnel=[cover_fit, *others],
        availability_entries=[],
        cover_types=[],
        cover_requirements=[],
        cover_slots=[
            DailyCoverSlot(
                duty_date=date(2026, 8, 1),
                requesting_unit="1 COY",
                cover_category="NON_FC",
                cover_type="BTP",
                session="FULL_DAY",
                points=1.5,
                mandatory=True,
                cover_requirement_id="req-1",
                is_reserve=False,
            )
        ],
        manual_assignments=[],
        duty_interests=[],
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

    assert result.covers_complete
    assert len(result.generated_cover_assignments) == 1
    assert (
        result.generated_cover_assignments[0].person_name
        == cover_fit.name
    )

    assert all(
        not (
            assignment.duty_date == date(2026, 8, 1)
            and assignment.person_name == cover_fit.name
        )
        for assignment in result.schedule.assignments
    )
