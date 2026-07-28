from pathlib import Path

EXPORTER = Path("roster_engine/exporter.py")
SAVED = Path("pages/8_Saved_Rosters.py")

if not EXPORTER.exists() or not SAVED.exists():
    raise SystemExit("Run this from the PTMC-Rostering repository root.")

exporter = EXPORTER.read_text()
saved = SAVED.read_text()

old_import = "from roster_engine.models import Assignment, Person, Schedule\n"
new_import = """from roster_engine.models import (
    Assignment,
    AvailabilityEntry,
    Person,
    Schedule,
)
"""

if old_import in exporter:
    exporter = exporter.replace(old_import, new_import, 1)
elif "AvailabilityEntry" not in exporter:
    raise SystemExit("Could not find exporter models import. No files changed.")

old_signature = """    month: int,
    personnel: list[Person] | None = None,
    worksheet_name: str | None = None,
) -> Path:
"""
new_signature = """    month: int,
    personnel: list[Person] | None = None,
    availability_entries: list[AvailabilityEntry] | None = None,
    worksheet_name: str | None = None,
) -> Path:
"""

if old_signature not in exporter:
    raise SystemExit("Could not find export_schedule signature. No files changed.")

exporter = exporter.replace(old_signature, new_signature, 1)

marker = "        if missing_people:\n"

availability_block = """        # Plot availability into otherwise blank cells. Assignments are
        # deliberately written first, so manual/generated duties and covers
        # override availability display.
        availability_by_cell: dict[
            tuple[str, date],
            list[str],
        ] = {}

        for entry in availability_entries or []:
            if (
                entry.unavailable_date.year != year
                or entry.unavailable_date.month != month
            ):
                continue

            person_key = canonical_person_name(
                entry.person_name
            )
            code = str(
                entry.reason or ""
            ).strip()

            if not person_key or not code:
                continue

            key = (
                person_key,
                entry.unavailable_date,
            )
            codes = availability_by_cell.setdefault(
                key,
                [],
            )

            if code.upper() not in {
                existing.upper()
                for existing in codes
            }:
                codes.append(code)

        for (
            person_key,
            availability_date,
        ), codes in availability_by_cell.items():
            row_number = personnel_rows.get(
                person_key
            )
            column_number = date_columns.get(
                availability_date
            )

            if (
                row_number is None
                or column_number is None
            ):
                continue

            target_cell = worksheet.cell(
                row=row_number,
                column=column_number,
            )

            if target_cell.value not in (
                None,
                "",
            ):
                continue

            target_cell.value = " + ".join(
                codes
            )

"""

if marker not in exporter:
    raise SystemExit("Could not find exporter post-assignment marker. No files changed.")

exporter = exporter.replace(marker, availability_block + marker, 1)

old_call = """                        personnel=[
                            record.person
                            for record
                            in personnel_records
                        ],
                    )
"""
new_call = """                        personnel=[
                            record.person
                            for record
                            in personnel_records
                        ],
                        availability_entries=(
                            availability_entries
                        ),
                    )
"""

if old_call not in saved:
    raise SystemExit(
        "Could not find Saved Rosters export_schedule call. No files changed."
    )

saved = saved.replace(old_call, new_call, 1)

compile(exporter, str(EXPORTER), "exec")
compile(saved, str(SAVED), "exec")

for path, content in ((EXPORTER, exporter), (SAVED, saved)):
    backup = path.with_suffix(".py.step26_backup")
    if not backup.exists():
        backup.write_text(path.read_text())
    path.write_text(content)

print("Step 26 applied successfully.")
print("Availability codes will be shown in blank exported roster cells.")
