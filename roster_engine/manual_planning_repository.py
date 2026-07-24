from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from supabase import Client


MANUAL_ASSIGNMENTS_TABLE = "roster_manual_assignments"


@dataclass(frozen=True)
class ManualAssignment:
    id: str
    roster_month_id: str
    personnel_name: str
    assignment_date: date
    assignment_kind: str
    centre: str | None
    role_name: str | None
    cover_requirement_id: str | None
    cover_label: str | None
    session: str | None
    is_locked: bool
    allow_override: bool
    remarks: str | None = None

    @property
    def qualified_role(self) -> str | None:
        if self.assignment_kind != "DUTY":
            return None

        if not self.role_name:
            return None

        role = self.role_name.strip().upper()

        if role.startswith("PT ") or role.startswith("RH "):
            return role

        if not self.centre:
            return role

        return f"{self.centre.strip().upper()} {role}"


class ManualPlanningRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_month_assignments(
        self,
        roster_month_id: str,
    ) -> list[ManualAssignment]:
        response = (
            self.supabase
            .table(MANUAL_ASSIGNMENTS_TABLE)
            .select(
                "id,roster_month_id,personnel_name,assignment_date,"
                "assignment_kind,centre,role_name,cover_requirement_id,"
                "cover_label,session,is_locked,allow_override,remarks"
            )
            .eq("roster_month_id", roster_month_id)
            .order("assignment_date")
            .order("personnel_name")
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading manual assignments."
            )

        return [
            self._row_to_assignment(row)
            for row in (response.data or [])
        ]

    @staticmethod
    def _row_to_assignment(
        row: dict,
    ) -> ManualAssignment:
        return ManualAssignment(
            id=str(row["id"]),
            roster_month_id=str(row["roster_month_id"]),
            personnel_name=str(row.get("personnel_name") or "").strip(),
            assignment_date=date.fromisoformat(
                str(row["assignment_date"])
            ),
            assignment_kind=str(
                row.get("assignment_kind") or ""
            ).upper(),
            centre=(
                str(row["centre"]).upper()
                if row.get("centre") is not None
                else None
            ),
            role_name=(
                str(row["role_name"]).upper()
                if row.get("role_name") is not None
                else None
            ),
            cover_requirement_id=(
                str(row["cover_requirement_id"])
                if row.get("cover_requirement_id") is not None
                else None
            ),
            cover_label=(
                str(row["cover_label"]).strip()
                if row.get("cover_label")
                else None
            ),
            session=(
                str(row["session"]).upper()
                if row.get("session") is not None
                else None
            ),
            is_locked=bool(row.get("is_locked", True)),
            allow_override=bool(row.get("allow_override", False)),
            remarks=(
                str(row["remarks"]).strip()
                if row.get("remarks")
                else None
            ),
        )
