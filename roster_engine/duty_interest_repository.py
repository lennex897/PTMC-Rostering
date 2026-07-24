from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from supabase import Client


DUTY_INTERESTS_TABLE = "roster_duty_interests"


@dataclass(frozen=True)
class DutyInterest:
    id: str
    roster_month_id: str
    personnel_id: str
    person_name: str
    centre: str
    interest_date: date
    preferred_role: str | None
    remarks: str | None = None

    def applies_to_role(
        self,
        role: str,
    ) -> bool:
        if self.preferred_role is None:
            return True

        return (
            self.preferred_role.strip().upper()
            == role.strip().upper()
        )


class DutyInterestRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_month_interests(
        self,
        roster_month_id: str,
    ) -> list[DutyInterest]:
        response = (
            self.supabase
            .table(DUTY_INTERESTS_TABLE)
            .select(
                "id,roster_month_id,personnel_id,interest_date,"
                "preferred_role,remarks,"
                "personnel:roster_personnel(name,centre)"
            )
            .eq("roster_month_id", roster_month_id)
            .order("interest_date")
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading duty interests."
            )

        return [
            self._row_to_interest(row)
            for row in (response.data or [])
        ]

    @staticmethod
    def _row_to_interest(
        row: dict,
    ) -> DutyInterest:
        personnel = row.get("personnel") or {}

        if isinstance(personnel, list):
            personnel = personnel[0] if personnel else {}

        preferred_role = (
            str(row["preferred_role"]).upper()
            if row.get("preferred_role") is not None
            else None
        )

        return DutyInterest(
            id=str(row["id"]),
            roster_month_id=str(row["roster_month_id"]),
            personnel_id=str(row["personnel_id"]),
            person_name=str(personnel.get("name") or "").strip(),
            centre=str(personnel.get("centre") or "").strip().upper(),
            interest_date=date.fromisoformat(
                str(row["interest_date"])
            ),
            preferred_role=preferred_role,
            remarks=(
                str(row["remarks"]).strip()
                if row.get("remarks")
                else None
            ),
        )
