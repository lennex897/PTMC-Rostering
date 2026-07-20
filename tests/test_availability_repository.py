from datetime import date
from pathlib import Path

from roster_engine.availability import load_availability
from roster_engine.availability_repository import AvailabilityRepository
from roster_engine.database import get_supabase


def main() -> None:
    workbook_path = Path(
        "/workspaces/PTMC-Rostering/reference/Leave_Off_Impt Dates Forecast.xlsx"
    )

    worksheet_name = "Aug 26"

    repo = AvailabilityRepository(get_supabase())

    entries = load_availability(
        workbook_path=workbook_path,
        worksheet_name=worksheet_name,
    )

    print(f"Parsed {len(entries)} availability entries.")

    month = repo.replace_month_availability(
        month_start=date(2026, 8, 1),
        entries=entries,
        source="workbook",
    )

    print(
        f"Imported availability for "
        f"{month.month_start:%B %Y}."
    )


if __name__ == "__main__":
    main()