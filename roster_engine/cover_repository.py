from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from supabase import Client

from roster_engine.roster_rules import RosterRules


COVER_TYPES_TABLE = "roster_cover_types"
COVER_REQUIREMENTS_TABLE = "roster_cover_requirements"


def classify_cover_category(
    cover_type: str | None,
) -> str:
    """
    Derive the internal scheduler category from the user-facing Cover Type.

    $FC is the actual FC cover type used by the Cover Planner, but internally
    it belongs to the FC category so that FC continuity, reserves, swaps, and
    manual FC handling are applied.

    GP and GX retain their own categories. All other cover types are treated
    as NON_FC.
    """
    value = " ".join(
        str(cover_type or "")
        .strip()
        .upper()
        .split()
    )

    if value in {
        "FC",
        "$FC",
    }:
        return "FC"

    if value == "GP":
        return "GP"

    if value == "GX":
        return "GX"

    return "NON_FC"


@dataclass(frozen=True)
class CoverType:
    id: str
    category: str
    cover_type: str
    points: float
    default_session: str | None
    is_active: bool
    display_order: int
    notes: str | None = None


@dataclass(frozen=True)
class CoverRequirement:
    id: str
    roster_month_id: str
    requesting_unit: str
    cover_category: str
    cover_type: str
    cover_type_id: str | None
    points: float
    session: str
    start_date: date
    end_date: date
    personnel_required: int
    mandatory: bool
    remarks: str | None = None

    def dates(self) -> list[date]:
        return [
            self.start_date + timedelta(days=offset)
            for offset in range(
                (self.end_date - self.start_date).days + 1
            )
        ]

    def includes_date(self, value: date) -> bool:
        return self.start_date <= value <= self.end_date


@dataclass(frozen=True)
class DailyCoverSlot:
    duty_date: date
    requesting_unit: str
    cover_category: str
    cover_type: str
    session: str
    points: float
    mandatory: bool
    cover_requirement_id: str | None
    is_reserve: bool = False


class CoverRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_cover_types(
        self,
        *,
        include_inactive: bool = False,
    ) -> list[CoverType]:
        query = (
            self.supabase
            .table(COVER_TYPES_TABLE)
            .select(
                "id,category,cover_type,points,default_session,"
                "is_active,display_order,notes"
            )
            .order("display_order")
            .order("category")
            .order("cover_type")
        )

        if not include_inactive:
            query = query.eq("is_active", True)

        response = query.execute()

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading cover types."
            )

        return [
            self._row_to_cover_type(row)
            for row in (response.data or [])
        ]

    def list_month_requirements(
        self,
        roster_month_id: str,
    ) -> list[CoverRequirement]:
        response = (
            self.supabase
            .table(COVER_REQUIREMENTS_TABLE)
            .select(
                "id,roster_month_id,requesting_unit,cover_category,"
                "cover_type,cover_type_id,points_snapshot,session,"
                "start_date,end_date,personnel_required,mandatory,remarks"
            )
            .eq("roster_month_id", roster_month_id)
            .order("start_date")
            .order("requesting_unit")
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading cover requirements."
            )

        type_lookup = {
            item.id: item
            for item in self.list_cover_types(include_inactive=True)
        }

        return [
            self._row_to_requirement(
                row=row,
                type_lookup=type_lookup,
            )
            for row in (response.data or [])
        ]

    def expand_daily_slots(
        self,
        requirements: list[CoverRequirement],
        *,
        rules: RosterRules | None = None,
    ) -> list[DailyCoverSlot]:
        """
        Expand cover requirements into daily staffing slots.

        FC reserve count is now rule-driven. Whenever at least one FC is
        active on a date, exactly rules.fc_reserve_count shared FC reserve
        slots are created, regardless of the number of overlapping FCs.
        """
        if rules is None:
            rules = RosterRules()

        slots: list[DailyCoverSlot] = []
        active_fc_dates: set[date] = set()

        for requirement in requirements:
            for current_date in requirement.dates():
                for _ in range(requirement.personnel_required):
                    slots.append(
                        DailyCoverSlot(
                            duty_date=current_date,
                            requesting_unit=requirement.requesting_unit,
                            cover_category=requirement.cover_category,
                            cover_type=requirement.cover_type,
                            session=requirement.session,
                            points=requirement.points,
                            mandatory=requirement.mandatory,
                            cover_requirement_id=requirement.id,
                            is_reserve=False,
                        )
                    )

                if requirement.cover_category == "FC":
                    active_fc_dates.add(
                        current_date
                    )

        reserve_count = max(
            0,
            int(rules.fc_reserve_count),
        )

        for current_date in sorted(
            active_fc_dates
        ):
            for _ in range(reserve_count):
                slots.append(
                    DailyCoverSlot(
                        duty_date=current_date,
                        requesting_unit="SHARED FC RESERVE",
                        cover_category="FC",
                        cover_type="FC RESERVE",
                        session="FULL_DAY",
                        points=0.0,
                        mandatory=True,
                        cover_requirement_id=None,
                        is_reserve=True,
                    )
                )

        return sorted(
            slots,
            key=lambda slot: (
                slot.duty_date,
                slot.is_reserve,
                slot.requesting_unit,
                slot.cover_type,
            ),
        )

    @staticmethod
    def _row_to_cover_type(row: dict) -> CoverType:
        return CoverType(
            id=str(row["id"]),
            category=classify_cover_category(
                str(row.get("cover_type") or "")
            ),
            cover_type=str(row.get("cover_type") or "").upper(),
            points=float(row.get("points") or 0.0),
            default_session=(
                str(row["default_session"])
                if row.get("default_session") is not None
                else None
            ),
            is_active=bool(row.get("is_active", True)),
            display_order=int(row.get("display_order", 0) or 0),
            notes=(
                str(row["notes"]).strip()
                if row.get("notes")
                else None
            ),
        )

    @staticmethod
    def _row_to_requirement(
        *,
        row: dict,
        type_lookup: dict[str, CoverType],
    ) -> CoverRequirement:
        cover_type_id = (
            str(row["cover_type_id"])
            if row.get("cover_type_id") is not None
            else None
        )

        if row.get("points_snapshot") is not None:
            points = float(row["points_snapshot"])
        elif cover_type_id and cover_type_id in type_lookup:
            points = type_lookup[cover_type_id].points
        else:
            points = 0.0

        return CoverRequirement(
            id=str(row["id"]),
            roster_month_id=str(row["roster_month_id"]),
            requesting_unit=str(row.get("requesting_unit") or "").strip(),
            cover_category=classify_cover_category(
                str(row.get("cover_type") or "")
            ),
            cover_type=str(row.get("cover_type") or "").upper(),
            cover_type_id=cover_type_id,
            points=points,
            session=str(row.get("session") or "FULL_DAY").upper(),
            start_date=date.fromisoformat(str(row["start_date"])),
            end_date=date.fromisoformat(str(row["end_date"])),
            personnel_required=int(row.get("personnel_required", 1) or 1),
            mandatory=bool(row.get("mandatory", True)),
            remarks=(
                str(row["remarks"]).strip()
                if row.get("remarks")
                else None
            ),
        )
