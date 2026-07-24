from datetime import date

from roster_engine.cover_repository import (
    CoverRepository,
    CoverRequirement,
)


def test_cover_requirement_expands_across_dates_and_quantity() -> None:
    repository = CoverRepository(None)

    requirement = CoverRequirement(
        id="req-1",
        roster_month_id="month-1",
        requesting_unit="1 COY",
        cover_category="NON_FC",
        cover_type="IPPT",
        cover_type_id="type-1",
        points=0.5,
        session="AM",
        start_date=date(2026, 8, 3),
        end_date=date(2026, 8, 4),
        personnel_required=2,
        mandatory=True,
    )

    slots = repository.expand_daily_slots([requirement])

    assert len(slots) == 4
    assert all(slot.is_reserve is False for slot in slots)
    assert {slot.duty_date for slot in slots} == {
        date(2026, 8, 3),
        date(2026, 8, 4),
    }


def test_fc_reserve_rule_is_ceil_active_fc_over_two() -> None:
    repository = CoverRepository(None)

    requirements = [
        CoverRequirement(
            id=f"req-{number}",
            roster_month_id="month-1",
            requesting_unit=f"{number} COY",
            cover_category="FC",
            cover_type="FC",
            cover_type_id="fc-type",
            points=1.0,
            session="FULL_DAY",
            start_date=date(2026, 8, 5),
            end_date=date(2026, 8, 5),
            personnel_required=1,
            mandatory=True,
        )
        for number in range(1, 4)
    ]

    slots = repository.expand_daily_slots(requirements)

    active_slots = [
        slot for slot in slots if not slot.is_reserve
    ]
    reserve_slots = [
        slot for slot in slots if slot.is_reserve
    ]

    assert len(active_slots) == 3
    assert len(reserve_slots) == 2


def test_two_fc_require_only_one_reserve() -> None:
    repository = CoverRepository(None)

    requirement = CoverRequirement(
        id="req-1",
        roster_month_id="month-1",
        requesting_unit="1 COY",
        cover_category="FC",
        cover_type="FC",
        cover_type_id="fc-type",
        points=1.0,
        session="FULL_DAY",
        start_date=date(2026, 8, 5),
        end_date=date(2026, 8, 5),
        personnel_required=2,
        mandatory=True,
    )

    slots = repository.expand_daily_slots([requirement])

    assert sum(slot.is_reserve for slot in slots) == 1
