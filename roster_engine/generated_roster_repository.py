from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from supabase import Client

from roster_engine.planning_generation import PlanningGenerationResult


GENERATIONS_TABLE = "roster_generations"
ASSIGNMENTS_TABLE = "roster_generated_assignments"
PERSONNEL_TABLE = "roster_personnel"


@dataclass(frozen=True)
class StoredGeneration:
    id: str
    roster_month_id: str
    version: int
    status: str
    is_current: bool
    personnel_count: int
    duty_assignment_count: int
    cover_assignment_count: int
    unfilled_duty_count: int
    unfilled_cover_count: int


@dataclass(frozen=True)
class StoredGeneratedAssignment:
    id: str
    generation_id: str
    roster_month_id: str
    personnel_id: str | None
    person_name: str
    assignment_date: date
    assignment_kind: str
    centre: str | None
    role_name: str | None
    cover_requirement_id: str | None
    requesting_unit: str | None
    cover_category: str | None
    cover_type: str | None
    session: str | None
    points: float
    is_overnight: bool
    is_reserve: bool
    is_locked: bool


def normalise_name(value: str) -> str:
    return " ".join(value.strip().upper().split())


def build_assignment_rows(
    *,
    generation_id: str,
    roster_month_id: str,
    result: PlanningGenerationResult,
    personnel_ids_by_name: dict[str, str] | None = None,
) -> list[dict]:
    personnel_ids_by_name = {
        normalise_name(name): personnel_id
        for name, personnel_id in (personnel_ids_by_name or {}).items()
    }

    locked_duty_keys = {
        (
            item.duty_date,
            normalise_name(item.person_name),
            item.role,
        )
        for item in result.locked_duty_assignments
    }

    rows: list[dict] = []

    for assignment in result.schedule.assignments:
        key = normalise_name(assignment.person_name)

        rows.append({
            "generation_id": generation_id,
            "roster_month_id": roster_month_id,
            "personnel_id": personnel_ids_by_name.get(key),
            "person_name": assignment.person_name,
            "assignment_date": assignment.duty_date.isoformat(),
            "assignment_kind": "DUTY",
            "centre": assignment.centre,
            "role_name": assignment.role,
            "cover_requirement_id": None,
            "requesting_unit": None,
            "cover_category": None,
            "cover_type": None,
            "session": "FULL_DAY",
            "points": float(assignment.points),
            "is_overnight": bool(assignment.is_overnight),
            "is_reserve": False,
            "is_locked": (
                assignment.duty_date,
                key,
                assignment.role,
            ) in locked_duty_keys,
        })

    for assignment in result.cover_assignments:
        key = normalise_name(assignment.person_name)

        rows.append({
            "generation_id": generation_id,
            "roster_month_id": roster_month_id,
            "personnel_id": personnel_ids_by_name.get(key),
            "person_name": assignment.person_name,
            "assignment_date": assignment.duty_date.isoformat(),
            "assignment_kind": (
                "COVER_RESERVE"
                if assignment.is_reserve
                else "COVER"
            ),
            "centre": None,
            "role_name": None,
            "cover_requirement_id": assignment.cover_requirement_id,
            "requesting_unit": assignment.requesting_unit,
            "cover_category": assignment.cover_category,
            "cover_type": assignment.cover_type,
            "session": assignment.session,
            "points": float(assignment.points),
            "is_overnight": False,
            "is_reserve": bool(assignment.is_reserve),
            "is_locked": bool(assignment.is_locked),
        })

    return rows


class GeneratedRosterRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_generations(
        self,
        roster_month_id: str,
    ) -> list[StoredGeneration]:
        response = (
            self.supabase
            .table(GENERATIONS_TABLE)
            .select(
                "id,roster_month_id,version,status,is_current,"
                "personnel_count,duty_assignment_count,cover_assignment_count,"
                "unfilled_duty_count,unfilled_cover_count"
            )
            .eq("roster_month_id", roster_month_id)
            .order("version", desc=True)
            .execute()
        )

        return [
            self._row_to_generation(row)
            for row in (response.data or [])
        ]

    def get_current_generation(
        self,
        roster_month_id: str,
    ) -> StoredGeneration | None:
        response = (
            self.supabase
            .table(GENERATIONS_TABLE)
            .select(
                "id,roster_month_id,version,status,is_current,"
                "personnel_count,duty_assignment_count,cover_assignment_count,"
                "unfilled_duty_count,unfilled_cover_count"
            )
            .eq("roster_month_id", roster_month_id)
            .eq("is_current", True)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        return self._row_to_generation(rows[0])

    def list_assignments(
        self,
        generation_id: str,
    ) -> list[StoredGeneratedAssignment]:
        response = (
            self.supabase
            .table(ASSIGNMENTS_TABLE)
            .select(
                "id,generation_id,roster_month_id,personnel_id,person_name,"
                "assignment_date,assignment_kind,centre,role_name,"
                "cover_requirement_id,requesting_unit,cover_category,"
                "cover_type,session,points,is_overnight,is_reserve,is_locked"
            )
            .eq("generation_id", generation_id)
            .order("assignment_date")
            .order("assignment_kind")
            .order("person_name")
            .execute()
        )

        return [
            self._row_to_assignment(row)
            for row in (response.data or [])
        ]

    def update_assignment_person(
        self,
        *,
        assignment_id: str,
        personnel_id: str,
        person_name: str,
    ) -> StoredGeneratedAssignment:
        """
        Replace the person on an existing saved assignment.

        The assignment's date, role/cover, points and requirement identity are
        intentionally left unchanged. This makes post-generation editing a
        controlled personnel swap rather than an arbitrary rewrite.
        """
        payload = {
            "personnel_id": personnel_id,
            "person_name": person_name,
        }

        response = (
            self.supabase
            .table(ASSIGNMENTS_TABLE)
            .update(payload)
            .eq("id", assignment_id)
            .execute()
        )

        rows = response.data or []

        if not rows:
            raise ValueError(
                "Generated assignment was not found."
            )

        return self._row_to_assignment(
            rows[0]
        )

    def set_generation_status(
        self,
        *,
        generation_id: str,
        status: str,
    ) -> StoredGeneration:
        if status not in {
            "draft",
            "published",
            "superseded",
        }:
            raise ValueError(
                "Unsupported generation status."
            )

        response = (
            self.supabase
            .table(GENERATIONS_TABLE)
            .update(
                {
                    "status": status,
                }
            )
            .eq("id", generation_id)
            .execute()
        )

        rows = response.data or []

        if not rows:
            raise ValueError(
                "Generated roster was not found."
            )

        return self._row_to_generation(
            rows[0]
        )

    def next_version(
        self,
        roster_month_id: str,
    ) -> int:
        generations = self.list_generations(
            roster_month_id
        )

        return (
            1
            if not generations
            else max(
                item.version
                for item in generations
            ) + 1
        )

    def _load_personnel_ids(
        self,
    ) -> dict[str, str]:
        response = (
            self.supabase
            .table(PERSONNEL_TABLE)
            .select("id,name")
            .execute()
        )

        return {
            normalise_name(
                str(row["name"])
            ): str(row["id"])
            for row in (response.data or [])
            if row.get("id") and row.get("name")
        }

    def save_generation(
        self,
        *,
        roster_month_id: str,
        result: PlanningGenerationResult,
        personnel_count: int,
        status: str = "draft",
        notes: str | None = None,
    ) -> StoredGeneration:
        if status not in {
            "draft",
            "published",
        }:
            raise ValueError(
                "Generation status must be draft or published."
            )

        version = self.next_version(
            roster_month_id
        )

        unfilled_duties = (
            result
            .roster_result
            .scheduler_result
            .unfilled_requirements
        )

        unfilled_covers = (
            result.unfilled_cover_slots
        )

        target_year = (
            result.roster_result.report.year
        )
        target_month = (
            result.roster_result.report.month
        )

        duty_assignments = [
            item
            for item in result.schedule.assignments
            if (
                item.duty_date.year == target_year
                and item.duty_date.month == target_month
            )
        ]

        (
            self.supabase
            .table(GENERATIONS_TABLE)
            .update(
                {
                    "is_current": False,
                    "status": "superseded",
                }
            )
            .eq(
                "roster_month_id",
                roster_month_id,
            )
            .eq("is_current", True)
            .execute()
        )

        response = (
            self.supabase
            .table(GENERATIONS_TABLE)
            .insert(
                {
                    "roster_month_id": roster_month_id,
                    "version": version,
                    "status": status,
                    "is_current": True,
                    "personnel_count": int(personnel_count),
                    "duty_assignment_count": len(duty_assignments),
                    "cover_assignment_count": len(
                        result.cover_assignments
                    ),
                    "unfilled_duty_count": len(
                        unfilled_duties
                    ),
                    "unfilled_cover_count": len(
                        unfilled_covers
                    ),
                    "notes": (
                        notes.strip()
                        if notes and notes.strip()
                        else None
                    ),
                }
            )
            .execute()
        )

        rows = response.data or []

        if not rows or not rows[0].get("id"):
            raise RuntimeError(
                "Supabase did not return the new generation ID."
            )

        generation_id = str(
            rows[0]["id"]
        )

        assignment_rows = build_assignment_rows(
            generation_id=generation_id,
            roster_month_id=roster_month_id,
            result=result,
            personnel_ids_by_name=(
                self._load_personnel_ids()
            ),
        )

        if assignment_rows:
            (
                self.supabase
                .table(ASSIGNMENTS_TABLE)
                .insert(assignment_rows)
                .execute()
            )

        return self.get_generation(
            generation_id
        )

    def get_generation(
        self,
        generation_id: str,
    ) -> StoredGeneration:
        response = (
            self.supabase
            .table(GENERATIONS_TABLE)
            .select(
                "id,roster_month_id,version,status,is_current,"
                "personnel_count,duty_assignment_count,cover_assignment_count,"
                "unfilled_duty_count,unfilled_cover_count"
            )
            .eq("id", generation_id)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            raise ValueError(
                "Generated roster was not found."
            )

        return self._row_to_generation(
            rows[0]
        )

    @staticmethod
    def _row_to_generation(
        row: dict,
    ) -> StoredGeneration:
        return StoredGeneration(
            id=str(row["id"]),
            roster_month_id=str(
                row["roster_month_id"]
            ),
            version=int(row["version"]),
            status=str(row["status"]),
            is_current=bool(row["is_current"]),
            personnel_count=int(
                row.get("personnel_count", 0)
                or 0
            ),
            duty_assignment_count=int(
                row.get(
                    "duty_assignment_count",
                    0,
                )
                or 0
            ),
            cover_assignment_count=int(
                row.get(
                    "cover_assignment_count",
                    0,
                )
                or 0
            ),
            unfilled_duty_count=int(
                row.get(
                    "unfilled_duty_count",
                    0,
                )
                or 0
            ),
            unfilled_cover_count=int(
                row.get(
                    "unfilled_cover_count",
                    0,
                )
                or 0
            ),
        )

    @staticmethod
    def _row_to_assignment(
        row: dict,
    ) -> StoredGeneratedAssignment:
        return StoredGeneratedAssignment(
            id=str(row["id"]),
            generation_id=str(
                row["generation_id"]
            ),
            roster_month_id=str(
                row["roster_month_id"]
            ),
            personnel_id=(
                str(row["personnel_id"])
                if row.get("personnel_id")
                else None
            ),
            person_name=str(
                row.get("person_name")
                or ""
            ),
            assignment_date=date.fromisoformat(
                str(row["assignment_date"])
            ),
            assignment_kind=str(
                row.get("assignment_kind")
                or ""
            ),
            centre=(
                str(row["centre"])
                if row.get("centre") is not None
                else None
            ),
            role_name=(
                str(row["role_name"])
                if row.get("role_name") is not None
                else None
            ),
            cover_requirement_id=(
                str(
                    row[
                        "cover_requirement_id"
                    ]
                )
                if row.get(
                    "cover_requirement_id"
                )
                else None
            ),
            requesting_unit=(
                str(row["requesting_unit"])
                if row.get("requesting_unit") is not None
                else None
            ),
            cover_category=(
                str(row["cover_category"])
                if row.get("cover_category") is not None
                else None
            ),
            cover_type=(
                str(row["cover_type"])
                if row.get("cover_type") is not None
                else None
            ),
            session=(
                str(row["session"])
                if row.get("session") is not None
                else None
            ),
            points=float(
                row.get("points", 0)
                or 0
            ),
            is_overnight=bool(
                row.get("is_overnight", False)
            ),
            is_reserve=bool(
                row.get("is_reserve", False)
            ),
            is_locked=bool(
                row.get("is_locked", False)
            ),
        )
