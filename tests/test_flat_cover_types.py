from datetime import date

from roster_engine.cover_repository import CoverRepository, CoverRequirement
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
        end_date=date(2026, 8, 2),
        personnel_required=1,
        mandatory=True,
    )


def test_fc_identity_comes_from_cover_type() -> None:
    assert is_active_fc_requirement(
        make_requirement("NON_FC", "FC")
    )


def test_legacy_fc_category_does_not_make_gp_an_fc() -> None:
    assert not is_active_fc_requirement(
        make_requirement("FC", "GP")
    )


def test_fc_reserves_use_cover_type() -> None:
    item = make_requirement("NON_FC", "FC")
    slots = CoverRepository(supabase=None).expand_daily_slots([item])
    assert any(slot.is_reserve for slot in slots)
