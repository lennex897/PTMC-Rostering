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

RANK_PREFIXES = {
    "REC",
    "PTE",
    "LCP",
    "CPL",
    "CFC",
    "3SG",
    "2SG",
    "1SG",
    "SSG",
    "MSG",
    "3WO",
    "2WO",
    "1WO",
    "MWO",
    "SWO",
    "ME1",
    "ME2",
    "ME3",
    "ME4",
    "ME5",
    "ME6",
    "ME7",
    "ME8",
}


def _personnel_name_candidates(value: object) -> list[str]:
    normalised = normalise_text(value)

    if not normalised:
        return []

    candidates = [normalised]
    parts = normalised.split()

    if len(parts) >= 2 and parts[0] in RANK_PREFIXES:
        candidates.append(" ".join(parts[1:]))

    return candidates

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

    def add_availability_entry(
        self,
        *,
        roster_month_id: str,
        personnel_id: str,
        unavailable_date: date,
        reason: str,
        source: str = "manual",
        notes: str | None = None,
    ) -> str:
        """
        Add or update one personnel availability entry.

        The database should enforce one entry per person per date.
        """
        normalised_reason = normalise_text(reason).upper()

        if not normalised_reason:
            raise ValueError(
                "Availability reason cannot be empty."
            )

        payload = {
            "roster_month_id": roster_month_id,
            "personnel_id": personnel_id,
            "availability_date": (
                unavailable_date.isoformat()
            ),
            "code": normalised_reason,
            "source": source,
            "notes": (
                notes.strip()
                if notes and notes.strip()
                else None
            ),
        }

        response = (
            self.supabase
            .table("roster_availability")
            .upsert(
                payload,
                on_conflict=(
                    "roster_month_id,"
                    "personnel_id,"
                    "availability_date"
                ),
            )
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while saving "
                "availability."
            )

        rows = response.data or []

        if not rows or not rows[0].get("id"):
            raise RuntimeError(
                "Supabase did not return the saved "
                "availability entry."
            )

        return str(rows[0]["id"])


    def delete_availability_entry(
        self,
        availability_id: str,
    ) -> None:
        """
        Delete one availability entry by UUID.
        """
        response = (
            self.supabase
            .table("roster_availability")
            .delete()
            .eq("id", availability_id)
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while deleting "
                "availability."
            )

        if not response.data:
            raise ValueError(
                "Availability entry was not found."
            )

    def load_month_availability(
        self,
        *,
        year: int,
        month: int,
    ) -> list[AvailabilityEntry]:
        """
        Load a month's availability from Supabase and convert it into
        AvailabilityEntry objects used by the scheduler.
        """
        month_start = date(year, month, 1)
        roster_month = self.get_roster_month(month_start)

        if roster_month is None:
            return []

        response = (
            self.supabase
            .table("roster_availability")
            .select(
                "availability_date, code, "
                "roster_personnel(name)"
            )
            .eq("roster_month_id", roster_month.id)
            .order("availability_date")
            .execute()
        )

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading "
                "monthly availability."
            )

        entries: list[AvailabilityEntry] = []

        for row in response.data or []:
            personnel_data = (
                row.get("roster_personnel") or {}
            )

            person_name = personnel_data.get("name")
            availability_date = row.get(
                "availability_date"
            )
            code = row.get("code")

            if (
                person_name is None
                or availability_date is None
                or code is None
            ):
                continue

            entries.append(
                AvailabilityEntry(
                    person_name=str(person_name),
                    unavailable_date=date.fromisoformat(
                        str(availability_date)
                    ),
                    reason=str(code),
                )
            )

        return entries

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
            personnel_id = None

            for candidate in _personnel_name_candidates(
                entry.person_name
            ):
                personnel_id = personnel_lookup.get(candidate)

                if personnel_id is not None:
                    break

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

def list_month_availability(
    self,
    *,
    year: int,
    month: int,
) -> list[StoredAvailabilityEntry]:
    """
    Load stored availability records for one month.

    Unlike load_month_availability(), this preserves database IDs
    and metadata for use by the Availability Management page.
    """
    month_start = date(year, month, 1)
    roster_month = self.get_roster_month(month_start)

    if roster_month is None:
        return []

    try:
        response = (
            self.supabase
            .table("roster_availability")
            .select(
                """
                id,
                roster_month_id,
                personnel_id,
                availability_date,
                code,
                source,
                notes,
                roster_personnel(
                    name,
                    rank,
                    centre
                )
                """
            )
            .eq(
                "roster_month_id",
                roster_month.id,
            )
            .order(
                "availability_date"
            )
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(
            "Unable to load stored availability from Supabase."
        ) from exc

    entries: list[StoredAvailabilityEntry] = []

    for row in response.data or []:
        personnel_data = (
            row.get("roster_personnel") or {}
        )

        # Defensive handling in case Supabase returns a list.
        if isinstance(personnel_data, list):
            personnel_data = (
                personnel_data[0]
                if personnel_data
                else {}
            )

        entries.append(
            StoredAvailabilityEntry(
                id=str(row["id"]),
                roster_month_id=str(
                    row["roster_month_id"]
                ),
                personnel_id=str(
                    row["personnel_id"]
                ),
                person_name=str(
                    personnel_data.get("name") or ""
                ).strip(),
                rank=str(
                    personnel_data.get("rank") or ""
                ).strip(),
                centre=str(
                    personnel_data.get("centre") or ""
                ).strip().upper(),
                unavailable_date=date.fromisoformat(
                    str(row["availability_date"])
                ),
                reason=str(
                    row.get("code") or ""
                ).strip().upper(),
                source=str(
                    row.get("source") or "manual"
                ).strip(),
                notes=(
                    str(row["notes"]).strip()
                    if row.get("notes")
                    else None
                ),
            )
        )

    return entries