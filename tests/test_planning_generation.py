from datetime import date

from roster_engine.cover_repository import (
    DailyCoverSlot,
)
from roster_engine.generator import (
    GenerationSettings,
)
from roster_engine.manual_planning_repository import (
    ManualAssignment,
)
from roster_engine.models import (
    Person,
    RosterMonth,
)
from roster_engine.planning_generation import (
    generate_roster_from_planning,
)
from roster_engine.planning_loader import (
    PlanningContext,
)
from roster_engine.requirements import (
    RequirementSettings,
)


def person(
    name: str,
    roles: set[str],
    *,
    cover_fit: bool = True,
) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre="PT",
        department=name,
        ampt_status="PASS",
        eligible_roles=roles,
        is_cover_fit=cover_fit,
    )


def settings() -> GenerationSettings:
    return GenerationSettings(
        year=2026,
        month=8,
        requirement_settings=(
            RequirementSettings(
                include_pt_core_roles=True,
                include_pt_csb=False,
                include_pt_sb2=False,
                include_rh_sb1_deployment=False,
                include_rh_sb2_deployment=False,
            )
        ),
    )


def context(
    *,
    personnel: list[Person],
    manual_assignments: list[
        ManualAssignment
    ],
    cover_slots: list[
        DailyCoverSlot
    ] | None = None,
) -> PlanningContext:
    return PlanningContext(
        roster_month=RosterMonth(
            id="month-1",
            month_start=date(
                2026,
                8,
                1,
            ),
            status="draft",
        ),
        personnel=personnel,
        availability_entries=[],
        cover_types=[],
        cover_requirements=[],
        cover_slots=(
            cover_slots or []
        ),
        manual_assignments=(
            manual_assignments
        ),
        duty_interests=[],
    )


def test_locked_duty_is_preserved_and_consumes_requirement() -> None:
    locked_person = person(
        "CPL LOCKED",
        {
            "PT DM",
            "PT CS1",
            "PT CS2",
            "PT SB1",
            "PT AE",
        },
    )

    others = [
        person(
            f"CPL OTHER {n}",
            {
                "PT DM",
                "PT CS1",
                "PT CS2",
                "PT SB1",
                "PT AE",
            },
        )
        for n in range(1, 8)
    ]

    manual = ManualAssignment(
        id="m1",
        roster_month_id="month-1",
        personnel_name=locked_person.name,
        assignment_date=date(
            2026,
            8,
            1,
        ),
        assignment_kind="DUTY",
        centre="PT",
        role_name="DM",
        cover_requirement_id=None,
        cover_label=None,
        session="FULL_DAY",
        is_locked=True,
        allow_override=False,
    )

    result = generate_roster_from_planning(
        planning=context(
            personnel=[
                locked_person,
                *others,
            ],
            manual_assignments=[
                manual
            ],
        ),
        settings=settings(),
    )

    matches = [
        assignment
        for assignment
        in result.schedule.assignments
        if (
            assignment.duty_date
            == date(2026, 8, 1)
            and assignment.role
            == "PT DM"
        )
    ]

    assert len(matches) == 1
    assert (
        matches[0].person_name
        == locked_person.name
    )


def test_locked_cover_consumes_slot_and_blocks_duty() -> None:
    covered = person(
        "CPL COVERED",
        {
            "PT DM",
            "PT CS1",
            "PT CS2",
            "PT SB1",
            "PT AE",
        },
    )

    others = [
        person(
            f"CPL OTHER {n}",
            {
                "PT DM",
                "PT CS1",
                "PT CS2",
                "PT SB1",
                "PT AE",
            },
        )
        for n in range(1, 8)
    ]

    manual = ManualAssignment(
        id="m-cover",
        roster_month_id="month-1",
        personnel_name=covered.name,
        assignment_date=date(
            2026,
            8,
            1,
        ),
        assignment_kind="COVER",
        centre=None,
        role_name=None,
        cover_requirement_id="cover-1",
        cover_label="1 COY — BTP",
        session="FULL_DAY",
        is_locked=True,
        allow_override=False,
    )

    slot = DailyCoverSlot(
        duty_date=date(
            2026,
            8,
            1,
        ),
        requesting_unit="1 COY",
        cover_category="NON_FC",
        cover_type="BTP",
        session="FULL_DAY",
        points=1.5,
        mandatory=True,
        cover_requirement_id="cover-1",
        is_reserve=False,
    )

    result = generate_roster_from_planning(
        planning=context(
            personnel=[
                covered,
                *others,
            ],
            manual_assignments=[
                manual
            ],
            cover_slots=[slot],
        ),
        settings=settings(),
    )

    assert (
        len(
            result.locked_cover_assignments
        )
        == 1
    )
    assert (
        result.unfilled_cover_slots
        == []
    )

    assert all(
        not (
            assignment.duty_date
            == date(2026, 8, 1)
            and assignment.person_name
            == covered.name
        )
        for assignment
        in result.schedule.assignments
    )
