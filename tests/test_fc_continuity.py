from datetime import date

from roster_engine.cover_repository import DailyCoverSlot
from roster_engine.cover_scheduler import generate_cover_assignments
from roster_engine.models import AvailabilityEntry, Person


def cover_person(name: str) -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre="PT",
        department=name,
        ampt_status="PASS",
        eligible_roles=set(),
        is_cover_fit=True,
    )


def fc_slot(day: int) -> DailyCoverSlot:
    return DailyCoverSlot(
        duty_date=date(2026, 8, day),
        requesting_unit="1 COY",
        cover_category="FC",
        cover_type="FC",
        session="FULL_DAY",
        points=1.0,
        mandatory=True,
        cover_requirement_id="fc-1",
        is_reserve=False,
    )


def test_multiday_fc_keeps_same_medic() -> None:
    alpha = cover_person("CPL ALPHA")
    bravo = cover_person("CPL BRAVO")

    result = generate_cover_assignments(
        personnel=[alpha, bravo],
        cover_slots=[
            fc_slot(3),
            fc_slot(4),
            fc_slot(5),
        ],
        availability_entries=[],
    )

    fc_assignments = [
        item
        for item in result.assignments
        if item.cover_type == "FC"
    ]

    assert len(fc_assignments) == 3
    assert {
        item.person_name
        for item in fc_assignments
    } == {"CPL ALPHA"}


def test_fc_forced_swap_when_original_medic_becomes_unavailable() -> None:
    alpha = cover_person("CPL ALPHA")
    bravo = cover_person("CPL BRAVO")

    result = generate_cover_assignments(
        personnel=[alpha, bravo],
        cover_slots=[
            fc_slot(3),
            fc_slot(4),
            fc_slot(5),
        ],
        availability_entries=[
            AvailabilityEntry(
                person_name=alpha.name,
                unavailable_date=date(2026, 8, 5),
                reason="AL",
            )
        ],
    )

    active = [
        item
        for item in result.assignments
        if item.cover_type == "FC"
    ]

    assert [
        item.person_name
        for item in active
    ] == [
        "CPL ALPHA",
        "CPL ALPHA",
        "CPL BRAVO",
    ]

    swap_rows = [
        item
        for item in result.assignments
        if item.cover_type == "FC SWAP"
    ]

    assert len(swap_rows) == 2
    assert {
        item.person_name
        for item in swap_rows
    } == {
        "CPL ALPHA",
        "CPL BRAVO",
    }
    assert all(
        item.points == 0.5
        for item in swap_rows
    )
    assert all(
        item.duty_date == date(2026, 8, 5)
        for item in swap_rows
    )


def test_manual_locked_fc_changes_continuity_from_that_day() -> None:
    from roster_engine.cover_scheduler import CoverAssignment

    alpha = cover_person("CPL ALPHA")
    bravo = cover_person("CPL BRAVO")

    locked = CoverAssignment(
        duty_date=date(2026, 8, 4),
        person_name=bravo.name,
        requesting_unit="1 COY",
        cover_category="FC",
        cover_type="FC",
        session="FULL_DAY",
        points=1.0,
        cover_requirement_id="fc-1",
        is_reserve=False,
        is_locked=True,
    )

    # Day 4's slot has already been consumed by manual planning.
    result = generate_cover_assignments(
        personnel=[alpha, bravo],
        cover_slots=[
            fc_slot(3),
            fc_slot(5),
        ],
        availability_entries=[],
        locked_cover_assignments=[locked],
    )

    active = sorted(
        [
            item
            for item in result.assignments
            if item.cover_type == "FC"
        ],
        key=lambda item: item.duty_date,
    )

    assert [
        (item.duty_date.day, item.person_name)
        for item in active
    ] == [
        (3, "CPL ALPHA"),
        (4, "CPL BRAVO"),
        (5, "CPL BRAVO"),
    ]
