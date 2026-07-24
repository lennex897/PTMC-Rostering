from datetime import date

import pytest

from roster_engine.requirements import (
    RequirementSettings,
    day_duty_points,
    generate_month_requirements,
    overnight_points_for_date,
    requirements_for_date,
)


def role_names(
    duty_date: date,
) -> set[str]:
    return {
        requirement.role
        for requirement in requirements_for_date(
            duty_date
        )
    }


def test_monday_requirements() -> None:
    # Monday includes PT overnight/deployment roles plus RH weekday day roles.
    roles = role_names(
        date(2026, 8, 3)
    )

    assert roles == {
        "PT DM",
        "PT CS1",
        "PT CS2",
        "PT CS/B",
        "PT SB1",
        "PT SB2",
        "PT AE",
        "RH SB1",
        "RH SB2",
        "RH DM",
        "RH CS1",
        "RH AE",
    }


def test_tuesday_requirements() -> None:
    roles = role_names(
        date(2026, 8, 4)
    )

    assert roles == {
        "PT DM",
        "PT CS1",
        "PT CS2",
        "PT SB1",
        "PT SB2",
        "PT AE",
        "RH SB1",
        "RH DM",
        "RH CS1",
        "RH AE",
    }


def test_saturday_requirements() -> None:
    roles = role_names(
        date(2026, 8, 1)
    )

    assert roles == {
        "PT DM",
        "PT CS1",
        "PT CS2",
        "PT SB1",
        "PT AE",
        "RH SB1",
    }

    assert "PT SB2" not in roles
    assert "PT CS/B" not in roles
    assert "RH SB2" not in roles
    assert "RH DM" not in roles
    assert "RH CS1" not in roles
    assert "RH AE" not in roles


def test_sunday_requirements() -> None:
    roles = role_names(
        date(2026, 8, 2)
    )

    assert roles == {
        "PT DM",
        "PT CS1",
        "PT CS2",
        "PT CS/B",
        "PT SB1",
        "PT AE",
        "RH SB1",
        "RH SB2",
    }

    assert "PT SB2" not in roles
    assert "RH DM" not in roles
    assert "RH CS1" not in roles
    assert "RH AE" not in roles


def test_weekday_overnight_points() -> None:
    assert (
        overnight_points_for_date(
            date(2026, 8, 3)
        )
        == 1.0
    )


def test_friday_overnight_points() -> None:
    assert (
        overnight_points_for_date(
            date(2026, 8, 7)
        )
        == 1.5
    )


def test_weekend_overnight_points() -> None:
    assert (
        overnight_points_for_date(
            date(2026, 8, 1)
        )
        == 2.0
    )

    assert (
        overnight_points_for_date(
            date(2026, 8, 2)
        )
        == 2.0
    )


def test_day_duty_points() -> None:
    assert day_duty_points() == 0.5


def test_generated_requirements_include_overnight_and_day_duties() -> None:
    requirements = generate_month_requirements(
        year=2026,
        month=8,
    )

    assert requirements
    assert any(
        requirement.is_overnight
        for requirement in requirements
    )
    assert any(
        not requirement.is_overnight
        for requirement in requirements
    )


def test_rh_day_roles_are_weekdays_only() -> None:
    monday = requirements_for_date(
        date(2026, 8, 3)
    )
    saturday = requirements_for_date(
        date(2026, 8, 1)
    )

    monday_roles = {
        requirement.role
        for requirement in monday
    }
    saturday_roles = {
        requirement.role
        for requirement in saturday
    }

    assert {
        "RH DM",
        "RH CS1",
        "RH AE",
    }.issubset(monday_roles)

    assert {
        "RH DM",
        "RH CS1",
        "RH AE",
    }.isdisjoint(saturday_roles)


def test_month_generator_covers_every_date() -> None:
    requirements = generate_month_requirements(
        year=2026,
        month=8,
    )

    generated_dates = {
        requirement.duty_date
        for requirement in requirements
    }

    assert len(generated_dates) == 31
    assert date(2026, 8, 1) in generated_dates
    assert date(2026, 8, 31) in generated_dates


def test_settings_can_disable_a_role_group() -> None:
    requirements = requirements_for_date(
        duty_date=date(2026, 8, 3),
        settings=RequirementSettings(
            include_pt_csb=False,
            include_rh_sb2_deployment=False,
        ),
    )

    roles = {
        requirement.role
        for requirement in requirements
    }

    assert "PT CS/B" not in roles
    assert "RH SB2" not in roles
    assert "PT DM" in roles


def test_invalid_month_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="Month must be between",
    ):
        generate_month_requirements(
            year=2026,
            month=13,
        )
