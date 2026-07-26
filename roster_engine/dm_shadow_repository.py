from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from supabase import Client


MANUAL_ASSIGNMENTS_TABLE = "roster_manual_assignments"


@dataclass(frozen=True)
class SavedDMShadow:
    id: str
    roster_month_id: str
    personnel_name: str
    shadow_date: date
    centre: str
    points: float
    remarks: str | None = None


class DMShadowRepository:
    """
    Thin repository over roster_manual_assignments.

    DM Shadows are stored as assignment_kind='DM_SHADOW'. They remain manual
    interventions and do not consume the real PT DM requirement.
    """

    def __init__(
        self,
        supabase: Client,
    ):
        self.supabase = supabase

    def list_month_shadows(
        self,
        roster_month_id: str,
    ) -> list[SavedDMShadow]:
        response = (
            self.supabase
            .table(MANUAL_ASSIGNMENTS_TABLE)
            .select(
                "id,roster_month_id,personnel_name,"
                "assignment_date,centre,points,remarks"
            )
            .eq(
                "roster_month_id",
                roster_month_id,
            )
            .eq(
                "assignment_kind",
                "DM_SHADOW",
            )
            .order("assignment_date")
            .order("personnel_name")
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading DM Shadows."
            )

        return [
            self._row_to_shadow(row)
            for row in (
                response.data or []
            )
        ]

    def add_dm_shadow(
        self,
        *,
        roster_month_id: str,
        personnel_name: str,
        shadow_date: date,
        points: float,
        remarks: str | None = None,
    ) -> SavedDMShadow:
        payload = {
            "roster_month_id": roster_month_id,
            "personnel_name": personnel_name,
            "assignment_date": shadow_date.isoformat(),
            "assignment_kind": "DM_SHADOW",
            "centre": "PT",
            "role_name": "DM SHADOW",
            "cover_requirement_id": None,
            "cover_label": None,
            "session": "FULL_DAY",
            "is_locked": True,
            "allow_override": False,
            "points": float(points),
            "remarks": (
                remarks.strip()
                if remarks
                and remarks.strip()
                else None
            ),
        }

        response = (
            self.supabase
            .table(MANUAL_ASSIGNMENTS_TABLE)
            .insert(payload)
            .execute()
        )

        rows = response.data or []

        if not rows:
            raise RuntimeError(
                "Supabase did not return the new DM Shadow."
            )

        return self._row_to_shadow(
            rows[0]
        )

    def delete_dm_shadow(
        self,
        shadow_id: str,
    ) -> None:
        (
            self.supabase
            .table(MANUAL_ASSIGNMENTS_TABLE)
            .delete()
            .eq(
                "id",
                shadow_id,
            )
            .eq(
                "assignment_kind",
                "DM_SHADOW",
            )
            .execute()
        )

    @staticmethod
    def _row_to_shadow(
        row: dict,
    ) -> SavedDMShadow:
        return SavedDMShadow(
            id=str(
                row["id"]
            ),
            roster_month_id=str(
                row["roster_month_id"]
            ),
            personnel_name=str(
                row.get(
                    "personnel_name"
                )
                or ""
            ),
            shadow_date=date.fromisoformat(
                str(
                    row["assignment_date"]
                )
            ),
            centre=str(
                row.get(
                    "centre"
                )
                or "PT"
            ),
            points=float(
                row.get(
                    "points",
                    0,
                )
                or 0
            ),
            remarks=(
                str(
                    row["remarks"]
                ).strip()
                if row.get(
                    "remarks"
                )
                else None
            ),
        )
