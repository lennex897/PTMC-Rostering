from datetime import date

from roster_engine.requirements import (
    RequirementSettings,
    requirements_for_date,
)
from roster_engine.roster_rules import RosterRules


def roles_for(duty_date: date) -> set[str]:
    return {
        requirement.role
        for requirement in requirements_for_date(
            duty_date=duty_date,
            settings=RequirementSettings(),
            rules=RosterRules(),
        )
    }


def test_monday_uses_csb_pattern() -> None:
    roles = roles_for(date(2026, 8, 3))
    assert "PT CS/B" in roles
    assert "PT CS2" not in roles
    assert "PT SB1" not in roles
    assert "PT DM" in roles
    assert "PT CS1" in roles
    assert "PT AE" in roles


def test_thursday_uses_csb_pattern() -> None:
    roles = roles_for(date(2026, 8, 6))
    assert "PT CS/B" in roles
    assert "PT CS2" not in roles
    assert "PT SB1" not in roles


def test_sunday_uses_csb_pattern() -> None:
    roles = roles_for(date(2026, 8, 2))
    assert "PT CS/B" in roles
    assert "PT CS2" not in roles
    assert "PT SB1" not in roles


def test_tuesday_uses_cs2_sb1_pattern() -> None:
    roles = roles_for(date(2026, 8, 4))
    assert "PT CS/B" not in roles
    assert "PT CS2" in roles
    assert "PT SB1" in roles


def test_friday_uses_cs2_sb1_pattern() -> None:
    roles = roles_for(date(2026, 8, 7))
    assert "PT CS/B" not in roles
    assert "PT CS2" in roles
    assert "PT SB1" in roles


def test_saturday_uses_cs2_sb1_pattern() -> None:
    roles = roles_for(date(2026, 8, 1))
    assert "PT CS/B" not in roles
    assert "PT CS2" in roles
    assert "PT SB1" in roles


def test_mon_thu_sun_full_overnight_pattern() -> None:
    monday = roles_for(date(2026, 8, 3))

    expected = {
        "PT DM",
        "PT CS1",
        "PT CS/B",
        "PT AE",
        "RH SB1",
        "RH SB2",
    }

    assert expected.issubset(monday)
    assert "PT CS2" not in monday
    assert "PT SB1" not in monday
