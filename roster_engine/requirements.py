from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date

from roster_engine.models import DutyRequirement


# Monday = 0, Sunday = 6
MONDAY = 0
TUESDAY = 1
WEDNESDAY = 2
THURSDAY = 3
FRIDAY = 4
SATURDAY = 5
SUNDAY = 6


PT_CORE_OVERNIGHT_ROLES = (
    "PT DM",
    "PT CS1",
    "PT CS2",
    "PT SB1",
    "PT AE",
)

RH_DAYTIME_ROLES = (
    "RH DM",
    "RH CS1",
    "RH AE",
)

PT_CSB_DAYS = {
    MONDAY,
    THURSDAY,
    SUNDAY,
}

PT_SB2_DAYS = {
    MONDAY,
    TUESDAY,
    WEDNESDAY,
    THURSDAY,
    FRIDAY,
}

RH_SB1_DEPLOYMENT_DAYS = {
    MONDAY,
    TUESDAY,
    WEDNESDAY,
    THURSDAY,
    FRIDAY,
    SATURDAY,
    SUNDAY,
}

RH_SB2_DEPLOYMENT_DAYS = {
    MONDAY,
    THURSDAY,
    SUNDAY,
}


@dataclass(frozen=True)
class RequirementSettings:
    include_pt_core_roles: bool = True
    include_pt_csb: bool = True
    include_pt_sb2: bool = True
    include_rh_sb1_deployment: bool = True
    include_rh_sb2_deployment: bool = True
    include_rh_daytime_roles: bool = True

    # Dates listed here will not receive RH daytime duties.
    public_holidays: frozenset[date] = field(
        default_factory=frozenset
    )


def overnight_points_for_date(
    duty_date: date,
) -> float:
    """
    Overnight point values:

    Monday–Thursday: 1 point
    Friday: 1.5 points
    Saturday–Sunday: 2 points

    Public holidays currently retain the normal value for
    their respective weekday, as stated in the rulebook.
    """

    weekday = duty_date.weekday()

    if weekday == FRIDAY:
        return 1.5

    if weekday in {SATURDAY, SUNDAY}:
        return 2.0

    return 1.0


def day_duty_points() -> float:
    return 0.5


def is_rh_working_day(
    duty_date: date,
    public_holidays: frozenset[date],
) -> bool:
    """
    RH operates daytime duties on Mondays to Fridays,
    excluding public holidays.
    """

    return (
        duty_date.weekday() < SATURDAY
        and duty_date not in public_holidays
    )


def requirements_for_date(
    duty_date: date,
    settings: RequirementSettings | None = None,
) -> list[DutyRequirement]:
    if settings is None:
        settings = RequirementSettings()

    requirements: list[DutyRequirement] = []
    weekday = duty_date.weekday()

    overnight_points = overnight_points_for_date(
        duty_date
    )

    if settings.include_pt_core_roles:
        for role in PT_CORE_OVERNIGHT_ROLES:
            requirements.append(
                DutyRequirement(
                    duty_date=duty_date,
                    role=role,
                    centre="PT",
                    is_overnight=True,
                    points=overnight_points,
                )
            )

    if (
        settings.include_pt_csb
        and weekday in PT_CSB_DAYS
    ):
        requirements.append(
            DutyRequirement(
                duty_date=duty_date,
                role="PT CS/B",
                centre="PT",
                is_overnight=True,
                points=overnight_points,
            )
        )

    if (
        settings.include_pt_sb2
        and weekday in PT_SB2_DAYS
    ):
        requirements.append(
            DutyRequirement(
                duty_date=duty_date,
                role="PT SB2",
                centre="PT",
                is_overnight=True,
                points=overnight_points,
            )
        )

    if (
        settings.include_rh_sb1_deployment
        and weekday in RH_SB1_DEPLOYMENT_DAYS
    ):
        requirements.append(
            DutyRequirement(
                duty_date=duty_date,
                role="RH SB1",
                centre="RH",
                is_overnight=True,
                points=overnight_points,
            )
        )

    if (
        settings.include_rh_sb2_deployment
        and weekday in RH_SB2_DEPLOYMENT_DAYS
    ):
        requirements.append(
            DutyRequirement(
                duty_date=duty_date,
                role="RH SB2",
                centre="RH",
                is_overnight=True,
                points=overnight_points,
            )
        )

    if (
        settings.include_rh_daytime_roles
        and is_rh_working_day(
            duty_date,
            settings.public_holidays,
        )
    ):
        for role in RH_DAYTIME_ROLES:
            requirements.append(
                DutyRequirement(
                    duty_date=duty_date,
                    role=role,
                    centre="RH",
                    is_overnight=False,
                    points=day_duty_points(),
                )
            )

    return requirements


def generate_month_requirements(
    year: int,
    month: int,
    settings: RequirementSettings | None = None,
) -> list[DutyRequirement]:
    if not 1 <= month <= 12:
        raise ValueError(
            f"Month must be between 1 and 12, got {month}."
        )

    if settings is None:
        settings = RequirementSettings()

    days_in_month = monthrange(
        year,
        month,
    )[1]

    requirements: list[DutyRequirement] = []

    for day_number in range(
        1,
        days_in_month + 1,
    ):
        duty_date = date(
            year,
            month,
            day_number,
        )

        requirements.extend(
            requirements_for_date(
                duty_date=duty_date,
                settings=settings,
            )
        )

    return requirements