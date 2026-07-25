from datetime import date

from roster_engine.cover_repository import CoverRepository, CoverRequirement
from roster_engine.requirements import requirements_for_date
from roster_engine.roster_rules import RosterRules


def test_requirements_use_rule_driven_csb_days() -> None:
    rules = RosterRules(
        pt_csb_days=("TUE",),
    )

    monday_roles = {
        item.role
        for item in requirements_for_date(
            date(2026, 8, 3),
            rules=rules,
        )
    }

    tuesday_roles = {
        item.role
        for item in requirements_for_date(
            date(2026, 8, 4),
            rules=rules,
        )
    }

    assert "PT CS/B" not in monday_roles
    assert "PT CS/B" in tuesday_roles


def test_requirements_use_rule_driven_points() -> None:
    rules = RosterRules(
        overnight_weekday_points=9.0,
        day_duty_points=4.0,
    )

    requirements = requirements_for_date(
        date(2026, 8, 3),
        rules=rules,
    )

    pt_dm = next(
        item
        for item in requirements
        if item.role == "PT DM"
    )

    rh_dm = next(
        item
        for item in requirements
        if item.role == "RH DM"
    )

    assert pt_dm.points == 9.0
    assert rh_dm.points == 4.0


def test_fc_reserve_count_comes_from_rules() -> None:
    requirement = CoverRequirement(
        id="fc-1",
        roster_month_id="month-1",
        requesting_unit="1 COY",
        cover_category="FC",
        cover_type="FC",
        cover_type_id=None,
        points=1.0,
        session="FULL_DAY",
        start_date=date(2026, 8, 3),
        end_date=date(2026, 8, 4),
        personnel_required=3,
        mandatory=True,
    )

    slots = CoverRepository(None).expand_daily_slots(
        [requirement],
        rules=RosterRules(
            fc_reserve_count=2
        ),
    )

    for day in (3, 4):
        assert sum(
            1
            for slot in slots
            if (
                slot.is_reserve
                and slot.duty_date
                == date(2026, 8, day)
            )
        ) == 2
