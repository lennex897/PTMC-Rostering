from datetime import date

from roster_engine.models import (
    DutyRequirement,
    Person,
)
from roster_engine.scheduler import (
    generate_schedule,
)


def make_person(
    name: str,
) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre="PT",
        department=name,
        ampt_status="PASS",
        eligible_roles={"PT DM"},
    )


def test_cover_commitment_blocks_same_day_duty() -> None:
    covered = make_person(
        "CPL COVERED"
    )
    free = make_person(
        "CPL FREE"
    )

    result = generate_schedule(
        personnel=[covered, free],
        requirements=[
            DutyRequirement(
                duty_date=date(2026, 8, 3),
                role="PT DM",
                centre="PT",
                is_overnight=True,
                points=1.0,
            )
        ],
        availability_entries=[],
        blocked_people_by_date={
            date(2026, 8, 3): {
                covered.name
            }
        },
    )

    assert (
        result.schedule.assignments[0]
        .person_name
        == free.name
    )


def test_cover_points_affect_duty_balancing() -> None:
    loaded = make_person(
        "CPL LOADED"
    )
    free = make_person(
        "CPL FREE"
    )

    result = generate_schedule(
        personnel=[loaded, free],
        requirements=[
            DutyRequirement(
                duty_date=date(2026, 8, 3),
                role="PT DM",
                centre="PT",
                is_overnight=True,
                points=1.0,
            )
        ],
        availability_entries=[],
        point_offsets_by_person={
            loaded.name: 3.0,
        },
    )

    assert (
        result.schedule.assignments[0]
        .person_name
        == free.name
    )
