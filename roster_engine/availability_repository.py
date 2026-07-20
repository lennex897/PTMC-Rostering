from __future__ import annotations

from datetime import date, datetime

from supabase import Client

from roster_engine.models import (
    AvailabilityEntry,
    RosterMonth,
    StoredAvailabilityEntry,
)

from roster_engine.personnel import normalise_text


def _normalise_month_start(value: date) -> date:
    return value.replace(day=1)


class AvailabilityRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def get_roster_month(
        self,
        month_start: date,
    ) -> RosterMonth | None:
        normalised_month = _normalise_month_start(month_start)

        response = (
            self.supabase
            .table("roster_months")
            .select(
                "id, month_start, status, "
                "source_filename, imported_at"
            )
            .eq(
                "month_start",
                normalised_month.isoformat(),
            )
            .limit(1)
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading roster month."
            )

        rows = response.data or []

        if not rows:
            return None

        return self._row_to_roster_month(rows[0])

    @staticmethod
    def _row_to_roster_month(
        row: dict[str, object],
    ) -> RosterMonth:
        imported_at_value = row.get("imported_at")

        return RosterMonth(
            id=str(row["id"]),
            month_start=date.fromisoformat(
                str(row["month_start"])
            ),
            status=str(row["status"]),
            source_filename=(
                str(row["source_filename"])
                if row.get("source_filename") is not None
                else None
            ),
            imported_at=(
                datetime.fromisoformat(
                    str(imported_at_value).replace("Z", "+00:00")
                )
                if imported_at_value is not None
                else None
            ),
        )

    def get_or_create_roster_month(
        self,
        month_start: date,
    ) -> RosterMonth:
        existing = self.get_roster_month(month_start)

        if existing is not None:
            return existing

        normalised_month = _normalise_month_start(month_start)

        response = (
            self.supabase
            .table("roster_months")
            .insert(
                {
                    "month_start": normalised_month.isoformat(),
                    "status": "draft",
                }
            )
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while creating roster month."
            )

        rows = response.data or []

        if not rows:
            raise RuntimeError(
                "Roster month was not created."
            )

        return self._row_to_roster_month(rows[0])
    
    def list_roster_months(self) -> list[RosterMonth]:
        response = (
            self.supabase
            .table("roster_months")
            .select(
                "id, month_start, status, "
                "source_filename, imported_at"
            )
            .order("month_start", desc=True)
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while listing roster months."
            )

        rows = response.data or []

        return [
            self._row_to_roster_month(row)
            for row in rows
        ]
    
    def delete_month_availability(
        self,
        roster_month_id: str,
    ) -> int:
        response = (
            self.supabase
            .table("roster_availability")
            .delete()
            .eq("roster_month_id", roster_month_id)
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while deleting "
                "monthly availability."
            )

        deleted_rows = response.data or []

        return len(deleted_rows)
    
    def bulk_insert_availability(
        self,
        rows: list[dict[str, object]],
    ) -> int:
        if not rows:
            return 0

        response = (
            self.supabase
            .table("roster_availability")
            .insert(rows)
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while inserting "
                "availability."
            )

        inserted_rows = response.data or []

        return len(inserted_rows)
    
    def load_personnel_id_map(self) -> dict[str, str]:
        response = (
            self.supabase
            .table("roster_personnel")
            .select("id, name, rank")
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading personnel."
            )

        rows = response.data or []

        personnel_lookup: dict[str, str] = {}

        for row in rows:
            personnel_id = row.get("id")
            name = row.get("name")
            rank = row.get("rank")

            if personnel_id is None or name is None:
                continue

            normalised_name = normalise_text(name)
            personnel_id_text = str(personnel_id)

            # Match a workbook containing names without ranks.
            personnel_lookup[normalised_name] = personnel_id_text

            # Also match a workbook containing values such as
            # "LCP GERALD TAN" or "PTE IGNATIUS QUEK".
            if rank is not None and normalise_text(rank):
                ranked_name = normalise_text(
                    f"{rank} {name}"
                )

                personnel_lookup[ranked_name] = personnel_id_text

        return personnel_lookup
    
    def replace_month_availability(
        self,
        month_start: date,
        entries: list[AvailabilityEntry],
        source: str = "workbook",
    ) -> RosterMonth:
        month = self.get_or_create_roster_month(
            month_start
        )

        personnel_lookup = self.load_personnel_id_map()

        unknown_people: set[str] = set()
        rows: list[dict[str, object]] = []

        for entry in entries:
            personnel_id = personnel_lookup.get(
                normalise_text(entry.person_name)
            )

            if personnel_id is None:
                unknown_people.add(entry.person_name)
                continue

            rows.append(
                {
                    "roster_month_id": month.id,
                    "personnel_id": personnel_id,
                    "availability_date": (
                        entry.unavailable_date.isoformat()
                    ),
                    "code": entry.reason,
                    "source": source,
                    "notes": None,
                }
            )

        if unknown_people:
            raise ValueError(
                "Unknown personnel:\n"
                + "\n".join(sorted(unknown_people))
            )

        self.delete_month_availability(month.id)
        self.bulk_insert_availability(rows)

        return month