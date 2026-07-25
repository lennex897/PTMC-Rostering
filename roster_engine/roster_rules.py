from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RosterRule:
    key: str
    group: str
    value_type: str
    value: int | float | bool | str | tuple[str, ...]
    description: str | None = None
    is_active: bool = True
    display_order: int = 0


@dataclass(frozen=True)
class RosterRules:
    """
    Typed snapshot of active machine-readable roster rules.

    Step 11 only establishes the configuration model. Existing scheduling
    behavior remains unchanged until later integration steps.
    """

    maximum_weekly_overnights: int = 3
    overnight_min_break_days: int = 1

    overnight_weekday_points: float = 1.0
    overnight_friday_points: float = 1.5
    overnight_weekend_points: float = 2.0
    day_duty_points: float = 0.5
    public_holiday_uses_day_weight: bool = True

    pt_csb_days: tuple[str, ...] = ("MON", "THU", "SUN")
    pt_sb2_days: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI")
    rh_sb1_deployment_days: tuple[str, ...] = (
        "MON",
        "TUE",
        "WED",
        "THU",
        "FRI",
        "SAT",
        "SUN",
    )
    rh_sb2_deployment_days: tuple[str, ...] = ("MON", "THU", "SUN")

    daily_pt_reserve_count: int = 1
    daily_rh_reserve_count: int = 1

    fc_reserve_count: int = 2
    fc_continuity_required: bool = True
    fc_swap_points: float = 0.5

    leaving_reduction_days: int = 90
    manual_only_personnel: tuple[str, ...] = (
        "TAN JUN HONG JUDAH",
        "LAM KAI JUE",
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__dataclass_fields__
        }
