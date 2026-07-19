from pathlib import Path

from roster_engine.roster_grid import parse_roster_grid


APP_ROOT = Path(__file__).resolve().parent

workbook_path = (
    APP_ROOT
    / "reference"
    / "Scheduling Roster 2026.xlsx"
)

grid = parse_roster_grid(
    workbook_path=workbook_path,
    worksheet_name="Jul-2026 Roster",
)

print(f"Worksheet: {grid.worksheet_name}")
print(f"Calendar days: {len(grid.days)}")
print(f"Personnel rows: {len(grid.personnel_rows)}")

print("\nFirst date:")
print(grid.days[0])

print("\nLast date:")
print(grid.days[-1])

print("\nEvents:")
for day in grid.days:
    if day.event:
        print(
            f"{day.roster_date}: {day.event}"
        )