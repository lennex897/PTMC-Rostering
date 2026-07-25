from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from roster_engine.availability_repository import (
    AvailabilityRepository,
)
from roster_engine.cover_repository import (
    CoverRepository,
    CoverRequirement,
    CoverType,
    DailyCoverSlot,
)
from roster_engine.database import get_supabase
from roster_engine.duty_interest_repository import (
    DutyInterest,
    DutyInterestRepository,
)
from roster_engine.manual_planning_repository import (
    ManualAssignment,
    ManualPlanningRepository,
)
from roster_engine.models import (
    AvailabilityEntry,
    Person,
    RosterMonth,
)
from roster_engine.personnel_repository import (
    load_personnel_from_supabase,
)
from roster_engine.roster_rules import RosterRules
from roster_engine.roster_rules_repository import (
    RosterRulesRepository,
)


@dataclass(frozen=True)
class PlanningContext:
    roster_month: RosterMonth
    personnel: list[Person]
    availability_entries: list[AvailabilityEntry]
    cover_types: list[CoverType]
    cover_requirements: list[CoverRequirement]
    cover_slots: list[DailyCoverSlot]
    manual_assignments: list[ManualAssignment]
    duty_interests: list[DutyInterest]
    # Default preserves compatibility with tests/non-Supabase callers that
    # construct PlanningContext directly.
    roster_rules: RosterRules = field(
        default_factory=RosterRules
    )


def load_planning_context(
    *,
    year: int,
    month: int,
) -> PlanningContext:
    supabase = get_supabase()

    availability_repository = AvailabilityRepository(
        supabase
    )
    cover_repository = CoverRepository(
        supabase
    )
    manual_repository = ManualPlanningRepository(
        supabase
    )
    interest_repository = DutyInterestRepository(
        supabase
    )
    rules_repository = RosterRulesRepository(
        supabase
    )

    roster_month = (
        availability_repository.get_roster_month(
            date(year, month, 1)
        )
    )

    if roster_month is None:
        raise ValueError(
            f"Roster month {year:04d}-{month:02d} does not exist."
        )

    roster_rules = rules_repository.load_rules()

    personnel = load_personnel_from_supabase(
        include_inactive=False
    )

    availability_entries = (
        availability_repository.load_month_availability(
            year=year,
            month=month,
        )
    )

    cover_types = cover_repository.list_cover_types(
        include_inactive=True
    )

    cover_requirements = (
        cover_repository.list_month_requirements(
            roster_month.id
        )
    )

    cover_slots = cover_repository.expand_daily_slots(
        cover_requirements,
        rules=roster_rules,
    )

    manual_assignments = (
        manual_repository.list_month_assignments(
            roster_month.id
        )
    )

    duty_interests = (
        interest_repository.list_month_interests(
            roster_month.id
        )
    )

    return PlanningContext(
        roster_month=roster_month,
        personnel=personnel,
        availability_entries=availability_entries,
        cover_types=cover_types,
        cover_requirements=cover_requirements,
        cover_slots=cover_slots,
        manual_assignments=manual_assignments,
        duty_interests=duty_interests,
        roster_rules=roster_rules,
    )
