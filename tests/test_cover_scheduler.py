from datetime import date

from roster_engine.cover_repository import DailyCoverSlot
from roster_engine.cover_scheduler import generate_cover_assignments
from roster_engine.models import AvailabilityEntry, Assignment, Person


def cover_person(name: str, *, centre: str = "PT") -> Person:
    return Person(
        name=name,
        rank="CPL",
        centre=centre,
        department=name,
        ampt_status="PASS",
        eligible_roles=set(),
        is_cover_fit=True,
    )


def slot(
    *,
    session: str = "FULL_DAY",
    cover_type: str = "IPPT",
    is_reserve: bool = False,
) -> DailyCoverSlot:
    return DailyCoverSlot(
        duty_date=date(2026, 8, 3),
        requesting_unit="1 COY",
        cover_category="FC" if is_reserve else "NON_FC",
        cover_type="FC RESERVE" if is_reserve else cover_type,
        session=session,
        points=0.0 if is_reserve else 0.5,
        mandatory=True,
        cover_requirement_id=None if is_reserve else "req-1",
        is_reserve=is_reserve,
    )


def test_cover_scheduler_accepts_cover_fit_person_from_rh() -> None:
    rh = cover_person("CPL RH", centre="RH")

    result = generate_cover_assignments(
        personnel=[rh],
        cover_slots=[slot()],
        availability_entries=[],
    )

    assert result.is_complete
    assert result.assignments[0].person_name == rh.name


def test_simultaneous_cover_slots_use_separate_people() -> None:
    one = cover_person("CPL ONE")
    two = cover_person("CPL TWO")

    result = generate_cover_assignments(
        personnel=[one, two],
        cover_slots=[
            slot(session="AM", cover_type="IPPT"),
            slot(session="AM", cover_type="SOC"),
        ],
        availability_entries=[],
    )

    assert result.is_complete
    assert len(result.assignments) == 2
    assert len({
        assignment.person_name
        for assignment in result.assignments
    }) == 2


def test_am_and_pm_can_use_same_person() -> None:
    one = cover_person("CPL ONE")

    result = generate_cover_assignments(
        personnel=[one],
        cover_slots=[
            slot(session="AM", cover_type="IPPT"),
            slot(session="PM", cover_type="SOC"),
        ],
        availability_entries=[],
    )

    assert result.is_complete
    assert len(result.assignments) == 2
    assert all(
        assignment.person_name == one.name
        for assignment in result.assignments
    )


def test_unavailable_cover_fit_person_is_not_assigned() -> None:
    one = cover_person("CPL ONE")

    result = generate_cover_assignments(
        personnel=[one],
        cover_slots=[slot()],
        availability_entries=[
            AvailabilityEntry(
                person_name=one.name,
                unavailable_date=date(2026, 8, 3),
                reason="AL",
            )
        ],
    )

    assert not result.is_complete
    assert result.assignments == []
    assert len(result.unfilled_slots) == 1


def test_locked_duty_blocks_cover_assignment() -> None:
    locked = cover_person("CPL LOCKED")

    result = generate_cover_assignments(
        personnel=[locked],
        cover_slots=[slot()],
        availability_entries=[],
        locked_duties=[
            Assignment(
                duty_date=date(2026, 8, 3),
                role="PT DM",
                centre="PT",
                person_name=locked.name,
                points=1.0,
                is_overnight=True,
            )
        ],
    )

    assert not result.is_complete
    assert result.assignments == []
