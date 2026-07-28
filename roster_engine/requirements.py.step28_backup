from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date

from roster_engine.models import DutyRequirement
from roster_engine.roster_rules import RosterRules


# Monday = 0, Sunday = 6
MONDAY = 0
TUESDAY = 1
WEDNESDAY = 2
THURSDAY = 3
FRIDAY = 4
SATURDAY = 5
SUNDAY = 6


DAY_NAME_TO_INDEX = {
    "MON": MONDAY,
    "TUE": TUESDAY,
    "WED": WEDNESDAY,
    "THU": THURSDAY,
    "FRI": FRIDAY,
    "SAT": SATURDAY,
    "SUN": SUNDAY,
}


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

# Legacy/default constants remain for compatibility. Live planning generation
# now derives these sets from RosterRules.
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

    public_holidays: frozenset[date] = field(
        default_factory=frozenset
    )


def _weekday_indexes(
    day_names: tuple[str, ...],
) -> set[int]:
    indexes: set[int] = set()

    for raw_name in day_names:
        name = str(raw_name).strip().upper()

        if name not in DAY_NAME_TO_INDEX:
            raise ValueError(
                f"Unknown roster weekday value: {raw_name!r}"
            )

        indexes.add(
            DAY_NAME_TO_INDEX[name]
        )

    return indexes


def overnight_points_for_date(
    duty_date: date,
    rules: RosterRules | None = None,
) -> float:
    if rules is None:
        rules = RosterRules()

    weekday = duty_date.weekday()

    if weekday == FRIDAY:
        return rules.overnight_friday_points

    if weekday in {SATURDAY, SUNDAY}:
        return rules.overnight_weekend_points

    return rules.overnight_weekday_points


def day_duty_points(
    rules: RosterRules | None = None,
) -> float:
    if rules is None:
        rules = RosterRules()

    return rules.day_duty_points


def is_rh_working_day(
    duty_date: date,
    public_holidays: frozenset[date],
) -> bool:
    return (
        duty_date.weekday() < SATURDAY
        and duty_date not in public_holidays
    )


def requirements_for_date(
    duty_date: date,
    settings: RequirementSettings | None = None,
    rules: RosterRules | None = None,
) -> list[DutyRequirement]:
    if settings is None:
        settings = RequirementSettings()

    if rules is None:
        rules = RosterRules()

    requirements: list[DutyRequirement] = []
    weekday = duty_date.weekday()

    pt_csb_days = _weekday_indexes(
        rules.pt_csb_days
    )
    pt_sb2_days = _weekday_indexes(
        rules.pt_sb2_days
    )
    rh_sb1_days = _weekday_indexes(
        rules.rh_sb1_deployment_days
    )
    rh_sb2_days = _weekday_indexes(
        rules.rh_sb2_deployment_days
    )

    overnight_points = overnight_points_for_date(
        duty_date,
        rules=rules,
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
        and weekday in pt_csb_days
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
        and weekday in pt_sb2_days
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
        and weekday in rh_sb1_days
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
        and weekday in rh_sb2_days
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
                    points=day_duty_points(
                        rules=rules
                    ),
                )
            )

    return requirements


def generate_month_requirements(
    year: int,
    month: int,
    settings: RequirementSettings | None = None,
    rules: RosterRules | None = None,
) -> list[DutyRequirement]:
    if not 1 <= month <= 12:
        raise ValueError(
            f"Month must be between 1 and 12, got {month}."
        )

    if settings is None:
        settings = RequirementSettings()

    if rules is None:
        rules = RosterRules()

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
                rules=rules,
            )
        )

    return requirements
