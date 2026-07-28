from datetime import date

from roster_engine.cover_repository import (
    CoverRepository,
    CoverRequirement,
    classify_cover_category,
)
from roster_engine.fc_manual_continuity import is_active_fc_requirement


def make_requirement(category: str, cover_type: str) -> CoverRequirement:
    return CoverRequirement(
        id="r1",
        roster_month_id="m1",
        requesting_unit="A COY",
        cover_category=category,
        cover_type=cover_type,
        cover_type_id=None,
        points=1.0,
        session="FULL_DAY",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
        personnel_required=1,
        mandatory=True,
    )


def test_category_is_derived_from_cover_type() -> None:
    assert classify_cover_category("FC") == "FC"
    assert classify_cover_category("GP") == "GP"
    assert classify_cover_category("GX") == "GX"
    assert classify_cover_category("$S IPPT") == "NON_FC"


def test_manual_fc_continuity_uses_category() -> None:
    assert is_active_fc_requirement(
        make_requirement("FC", "FC")
    )
    assert not is_active_fc_requirement(
        make_requirement("NON_FC", "FC")
    )


def test_fc_reserve_generation_uses_category() -> None:
    slots = CoverRepository(
        supabase=None
    ).expand_daily_slots(
        [make_requirement("FC", "FC")]
    )

    assert any(slot.is_reserve for slot in slots)


def test_non_fc_category_does_not_generate_fc_reserve() -> None:
    slots = CoverRepository(
        supabase=None
    ).expand_daily_slots(
        [make_requirement("NON_FC", "FC")]
    )

    assert not any(slot.is_reserve for slot in slots)
