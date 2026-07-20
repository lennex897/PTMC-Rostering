from pathlib import Path

from roster_engine.availability import load_availability
from roster_engine.exporter import (
    export_assignments_to_workbook,
)
from roster_engine.generator import (
    GenerationSettings,
    assignments_in_target_month,
    generate_roster,
)
from roster_engine.history import (
    find_historical_roster_sheets,
    load_historical_schedules,
)
from roster_engine.personnel import (
    load_personnel,
    normalise_text,
)


SCHEDULING_WORKBOOK = Path(
    "reference/Scheduling Roster 2026.xlsx"
)

LEAVE_WORKBOOK = Path(
    "reference/Leave_Off_Impt Dates Forecast.xlsx"
)

HISTORY_LOOKBACK_MONTHS = 3
TARGET_WORKSHEET = "Aug-2026 Roster"
LEAVE_WORKSHEET = "Aug 26"

TARGET_YEAR = 2026
TARGET_MONTH = 8

OUTPUT_WORKBOOK = Path(
    "output/August-2026-Generated-Roster.xlsx"
)


def main() -> None:
    print("Loading personnel...")

    personnel = load_personnel(
        SCHEDULING_WORKBOOK
    )

    print(f"Loaded {len(personnel)} personnel.")

    print("Loading August availability...")

    availability_entries = load_availability(
        workbook_path=LEAVE_WORKBOOK,
        worksheet_name=LEAVE_WORKSHEET,
    )

    personnel_names = {
        normalise_text(person.name)
        for person in personnel
    }

    availability_names = {
        normalise_text(entry.person_name)
        for entry in availability_entries
    }

    matched_leave_names = (
        personnel_names & availability_names
    )

    unmatched_leave_names = (
        availability_names - personnel_names
    )

    print(
        "Availability entries: "
        f"{len(availability_entries)}"
    )
    print(
        "Matched leave names: "
        f"{len(matched_leave_names)}"
    )
    print(
        "Unmatched leave names: "
        f"{len(unmatched_leave_names)}"
    )

    if unmatched_leave_names:
        print()
        print(
            "WARNING: Leave entries with unmatched names "
            "will not affect generation:"
        )

        for name in sorted(unmatched_leave_names):
            print(f"  - {name}")

        print()

    print("Discovering historical roster sheets...")

    historical_worksheets = (
        find_historical_roster_sheets(
            workbook_path=SCHEDULING_WORKBOOK,
            target_year=TARGET_YEAR,
            target_month=TARGET_MONTH,
            maximum_months=HISTORY_LOOKBACK_MONTHS,
        )
    )

    if not historical_worksheets:
        print(
            "WARNING: No historical roster sheets "
            "were found."
        )
    else:
        print("Historical worksheets:")

        for worksheet_name in historical_worksheets:
            print(f"  - {worksheet_name}")

    print("Loading historical assignments...")

    historical_schedule = load_historical_schedules(
        workbook_path=SCHEDULING_WORKBOOK,
        worksheet_names=historical_worksheets,
        personnel=personnel,
    )

    print(
        "Historical assignments: "
        f"{len(historical_schedule.assignments)}"
    )

    print("Generating August roster...")

    result = generate_roster(
        personnel=personnel,
        availability_entries=availability_entries,
        settings=GenerationSettings(
            year=TARGET_YEAR,
            month=TARGET_MONTH,
        ),
        historical_schedule=historical_schedule,
    )

    august_assignments = (
        assignments_in_target_month(
            schedule=result.schedule,
            year=TARGET_YEAR,
            month=TARGET_MONTH,
        )
    )

    print(
        "Generated assignments: "
        f"{len(august_assignments)}"
    )
    print(
        "Unfilled requirements: "
        f"{len(result.unfilled_requirements)}"
    )

    if result.unfilled_requirements:
        print()
        print(
            "WARNING: The generated roster is incomplete."
        )

        for requirement in (
            result.unfilled_requirements
        ):
            print(
                f"  - {requirement.duty_date}: "
                f"{requirement.role}"
            )

        print()

    print("Writing assignments into workbook...")

    export_report = (
        export_assignments_to_workbook(
            template_workbook_path=(
                SCHEDULING_WORKBOOK
            ),
            output_workbook_path=OUTPUT_WORKBOOK,
            worksheet_name=TARGET_WORKSHEET,
            assignments=august_assignments,
            target_year=TARGET_YEAR,
            target_month=TARGET_MONTH,
            valid_person_names={
                person.name
                for person in personnel
            },
        )
    )

    print()
    print("=" * 72)
    print("EXPORT COMPLETE")
    print("=" * 72)
    print(
        f"Output:              "
        f"{export_report.output_path}"
    )
    print(
        f"Assignments written: "
        f"{export_report.written_assignments}"
    )
    print(
        f"Old duties cleared:  "
        f"{export_report.cleared_cells}"
    )
    print(
        f"Missing people:      "
        f"{len(export_report.missing_people)}"
    )
    print(
        f"Missing dates:       "
        f"{len(export_report.missing_dates)}"
    )
    print(
        f"Skipped assignments: "
        f"{len(export_report.skipped_assignments)}"
    )

    if export_report.missing_people:
        print()
        print("Missing personnel rows:")

        for person_name in (
            export_report.missing_people
        ):
            print(f"  - {person_name}")

    if export_report.missing_dates:
        print()
        print("Missing date columns:")

        for missing_date in (
            export_report.missing_dates
        ):
            print(f"  - {missing_date}")

    print()
    print(
        "IMPORTANT: The current anonymised leave names "
        "do not match the personnel names."
    )
    print(
        "This workbook tests the export pipeline, but "
        "must not yet be treated as a leave-safe roster."
    )


if __name__ == "__main__":
    main()
