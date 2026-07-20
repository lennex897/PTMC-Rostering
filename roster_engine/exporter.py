from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import openpyxl

from roster_engine.models import Assignment
from roster_engine.personnel import normalise_text

import calendar
from datetime import date, datetime


EVENT_ROW = 2
DATE_ROW = 3
DAY_ROW = 4

PERSONNEL_START_ROW = 5
PERSONNEL_COLUMN = 2
SCHEDULE_START_COLUMN = 3


DUTY_CODES = {
    "DM",
    "CS1",
    "CS2",
    "CS/B",
    "SB1",
    "SB2",
    "AE",
}


@dataclass
class ExportReport:
    output_path: Path
    written_assignments: int = 0
    missing_people: list[str] = field(
        default_factory=list
    )
    missing_dates: list[date] = field(
        default_factory=list
    )
    skipped_assignments: list[Assignment] = field(
        default_factory=list
    )
    cleared_cells: int = 0

    @property
    def successful(self) -> bool:
        return (
            not self.missing_people
            and not self.missing_dates
            and not self.skipped_assignments
        )


def parse_roster_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return None


def assignment_code(role: str) -> str:
    """
    Convert a centre-prefixed role such as 'PT DM' or 'RH SB1'
    into the value written into the roster grid.
    """
    normalised_role = normalise_text(role)

    for centre_prefix in ("PT ", "RH "):
        if normalised_role.startswith(centre_prefix):
            return normalised_role[
                len(centre_prefix):
            ]

    return normalised_role


def configure_month_header(
    worksheet,
    target_year: int,
    target_month: int,
) -> dict[date, int]:
    """
    Configure the roster calendar so column C is the first day of
    the target month and subsequent columns contain consecutive days.

    Returns the date-to-column mapping without relying on Excel to
    calculate formulas.
    """
    days_in_month = calendar.monthrange(
        target_year,
        target_month,
    )[1]

    date_columns: dict[date, int] = {}

    for day_number in range(1, 32):
        column_number = (
            SCHEDULE_START_COLUMN
            + day_number
            - 1
        )

        date_cell = worksheet.cell(
            row=DATE_ROW,
            column=column_number,
        )

        if day_number <= days_in_month:
            roster_date = date(
                target_year,
                target_month,
                day_number,
            )

            date_columns[roster_date] = column_number

            if day_number == 1:
                # Store an actual Excel date in the first cell.
                date_cell.value = datetime(
                    target_year,
                    target_month,
                    1,
                )
            else:
                previous_cell = worksheet.cell(
                    row=DATE_ROW,
                    column=column_number - 1,
                )

                date_cell.value = (
                    f"={previous_cell.coordinate}+1"
                )
        else:
            # For February, April, June, September and November,
            # clear unused calendar columns.
            date_cell.value = None

    return date_columns


def find_date_columns(
    worksheet,
    target_year: int,
    target_month: int,
) -> dict[date, int]:
    """
    Return calendar columns for the requested month.

    The roster template always starts its calendar in column C, so
    formula evaluation is not required.
    """
    return configure_month_header(
        worksheet=worksheet,
        target_year=target_year,
        target_month=target_month,
    )


def find_person_rows(
    worksheet,
    valid_person_names: set[str] | None = None,
) -> dict[str, int]:
    """
    Locate personnel rows in column B.

    When valid_person_names is supplied, summary rows such as DM,
    CS1 and RESERVE are automatically ignored.
    """
    person_rows: dict[str, int] = {}

    normalised_valid_names = None

    if valid_person_names is not None:
        normalised_valid_names = {
            normalise_text(name)
            for name in valid_person_names
        }

    for row_number in range(
        PERSONNEL_START_ROW,
        worksheet.max_row + 1,
    ):
        name = normalise_text(
            worksheet.cell(
                row=row_number,
                column=PERSONNEL_COLUMN,
            ).value
        )

        if not name:
            continue

        if (
            normalised_valid_names is not None
            and name not in normalised_valid_names
        ):
            continue

        person_rows[name] = row_number

    return person_rows


def clear_generated_duties(
    worksheet,
    person_rows: dict[str, int],
    date_columns: dict[date, int],
) -> int:
    """
    Clear only recognised duty codes from the target roster grid.

    Leave, reserve, deployment and other non-duty values are
    preserved.
    """
    cleared_cells = 0

    for row_number in person_rows.values():
        for column_number in date_columns.values():
            cell = worksheet.cell(
                row=row_number,
                column=column_number,
            )

            existing_value = normalise_text(cell.value)

            if existing_value in DUTY_CODES:
                cell.value = None
                cleared_cells += 1

    return cleared_cells


def export_assignments_to_workbook(
    template_workbook_path: Path,
    output_workbook_path: Path,
    worksheet_name: str,
    assignments: list[Assignment],
    target_year: int,
    target_month: int,
    valid_person_names: set[str] | None = None,
    clear_existing_duties: bool = True,
) -> ExportReport:
    """
    Copy the source workbook and write generated assignments into
    the selected roster worksheet.

    The original workbook is never modified.
    """
    if not template_workbook_path.exists():
        raise FileNotFoundError(
            "Scheduling workbook not found: "
            f"{template_workbook_path}"
        )

    output_workbook_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        template_workbook_path,
        output_workbook_path,
    )

    workbook = openpyxl.load_workbook(
        output_workbook_path,
        data_only=False,
    )

    try:
        if worksheet_name not in workbook.sheetnames:
            raise ValueError(
                f"Worksheet '{worksheet_name}' was not found."
            )

        worksheet = workbook[worksheet_name]

        date_columns = find_date_columns(
            worksheet=worksheet,
            target_year=target_year,
            target_month=target_month,
        )

        if not date_columns:
            raise ValueError(
                "No matching date columns were found in "
                f"worksheet '{worksheet_name}' for "
                f"{target_year}-{target_month:02d}."
            )

        person_rows = find_person_rows(
            worksheet=worksheet,
            valid_person_names=valid_person_names,
        )

        report = ExportReport(
            output_path=output_workbook_path,
        )

        if clear_existing_duties:
            report.cleared_cells = (
                clear_generated_duties(
                    worksheet=worksheet,
                    person_rows=person_rows,
                    date_columns=date_columns,
                )
            )

        missing_people: set[str] = set()
        missing_dates: set[date] = set()

        for assignment in assignments:
            if (
                assignment.duty_date.year
                != target_year
                or assignment.duty_date.month
                != target_month
            ):
                report.skipped_assignments.append(
                    assignment
                )
                continue

            normalised_name = normalise_text(
                assignment.person_name
            )

            row_number = person_rows.get(
                normalised_name
            )

            column_number = date_columns.get(
                assignment.duty_date
            )

            if row_number is None:
                missing_people.add(
                    assignment.person_name
                )
                report.skipped_assignments.append(
                    assignment
                )
                continue

            if column_number is None:
                missing_dates.add(
                    assignment.duty_date
                )
                report.skipped_assignments.append(
                    assignment
                )
                continue

            duty_code = assignment_code(
                assignment.role
            )

            if duty_code not in DUTY_CODES:
                report.skipped_assignments.append(
                    assignment
                )
                continue

            worksheet.cell(
                row=row_number,
                column=column_number,
            ).value = duty_code

            report.written_assignments += 1

        report.missing_people = sorted(
            missing_people
        )
        report.missing_dates = sorted(
            missing_dates
        )
        workbook.calculation.fullCalcOnLoad = True
        workbook.calculation.forceFullCalc = True
        workbook.calculation.calcMode = "auto"
        workbook.save(output_workbook_path)

        return report

    finally:
        workbook.close()
