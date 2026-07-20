from __future__ import annotations

from copy import copy
from datetime import date
from pathlib import Path

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from roster_engine.models import Assignment, Schedule
from roster_engine.personnel import normalise_text
from roster_engine.roster_grid import (
    DATE_ROW,
    PERSONNEL_COLUMN,
    PERSONNEL_START_ROW,
    SCHEDULE_START_COLUMN,
    normalise_date,
)


def roster_worksheet_name(year: int, month: int) -> str:
    """
    Return the expected roster worksheet name.

    Example:
        August 2026 -> Aug-2026 Roster
    """
    return date(year, month, 1).strftime("%b-%Y Roster")


def assignment_cell_value(assignment: Assignment) -> str:
    """
    Convert an internal role name into the value written into the roster.

    Examples:
        PT DM  -> DM
        RH SB1 -> SB1
        PT CS/B -> CS/B
    """
    role = assignment.role.strip()

    for prefix in ("PT ", "RH "):
        if role.upper().startswith(prefix):
            return role[len(prefix):].strip()

    return role


def find_date_columns(
    worksheet: Worksheet,
    *,
    year: int,
    month: int,
) -> dict[date, int]:
    """
    Map each calendar date in the target month to its worksheet column.
    """
    date_columns: dict[date, int] = {}

    for column_number in range(
        SCHEDULE_START_COLUMN,
        worksheet.max_column + 1,
    ):
        cell_date = normalise_date(
            worksheet.cell(
                row=DATE_ROW,
                column=column_number,
            ).value
        )

        if cell_date is None:
            continue

        if (
            cell_date.year == year
            and cell_date.month == month
        ):
            date_columns[cell_date] = column_number

    return date_columns


def find_personnel_rows(
    worksheet: Worksheet,
) -> dict[str, int]:
    """
    Map normalised personnel names to worksheet row numbers.
    """
    personnel_rows: dict[str, int] = {}

    for row_number in range(
        PERSONNEL_START_ROW,
        worksheet.max_row + 1,
    ):
        raw_name = worksheet.cell(
            row=row_number,
            column=PERSONNEL_COLUMN,
        ).value

        normalised_name = normalise_text(raw_name)

        if not normalised_name:
            continue

        personnel_rows[normalised_name] = row_number

    return personnel_rows


def copy_cell_style(
    source_cell,
    target_cell,
) -> None:
    """
    Copy formatting from one roster cell to another.

    This is useful when a blank template cell has lost formatting.
    """
    if source_cell.has_style:
        target_cell._style = copy(source_cell._style)

    if source_cell.number_format:
        target_cell.number_format = source_cell.number_format

    if source_cell.alignment:
        target_cell.alignment = copy(source_cell.alignment)

    if source_cell.protection:
        target_cell.protection = copy(source_cell.protection)


def export_schedule(
    *,
    template_path: Path,
    output_path: Path,
    schedule: Schedule,
    year: int,
    month: int,
    worksheet_name: str | None = None,
) -> Path:
    """
    Write generated assignments into a copy of the roster workbook.

    The original workbook is not modified.
    """
    if not template_path.exists():
        raise FileNotFoundError(
            f"Roster template was not found: {template_path}"
        )

    selected_worksheet = (
        worksheet_name
        or roster_worksheet_name(year, month)
    )

    workbook = openpyxl.load_workbook(template_path)

    try:
        if selected_worksheet not in workbook.sheetnames:
            raise ValueError(
                f"Worksheet '{selected_worksheet}' was not found. "
                f"Available worksheets: {workbook.sheetnames}"
            )

        worksheet = workbook[selected_worksheet]

        date_columns = find_date_columns(
            worksheet,
            year=year,
            month=month,
        )

        if not date_columns:
            raise ValueError(
                f"No dates for {year}-{month:02d} were found "
                f"in worksheet '{selected_worksheet}'."
            )

        personnel_rows = find_personnel_rows(worksheet)

        if not personnel_rows:
            raise ValueError(
                f"No personnel rows were found in "
                f"worksheet '{selected_worksheet}'."
            )

        missing_people: set[str] = set()
        missing_dates: set[date] = set()
        written_assignments = 0

        for assignment in schedule.assignments:
            if (
                assignment.duty_date.year != year
                or assignment.duty_date.month != month
            ):
                continue

            normalised_name = normalise_text(
                assignment.person_name
            )

            row_number = personnel_rows.get(normalised_name)
            column_number = date_columns.get(
                assignment.duty_date
            )

            if row_number is None:
                missing_people.add(assignment.person_name)
                continue

            if column_number is None:
                missing_dates.add(assignment.duty_date)
                continue

            target_cell = worksheet.cell(
                row=row_number,
                column=column_number,
            )

            if target_cell.value not in (None, ""):
                raise ValueError(
                    "Cannot overwrite an existing roster entry: "
                    f"{assignment.person_name}, "
                    f"{assignment.duty_date.isoformat()}, "
                    f"existing value={target_cell.value!r}"
                )

            target_cell.value = assignment_cell_value(
                assignment
            )

            written_assignments += 1

        if missing_people:
            missing_names = ", ".join(
                sorted(missing_people)
            )
            raise ValueError(
                "Some assigned personnel could not be found "
                f"in the roster worksheet: {missing_names}"
            )

        if missing_dates:
            missing_date_text = ", ".join(
                roster_date.isoformat()
                for roster_date in sorted(missing_dates)
            )
            raise ValueError(
                "Some assignment dates could not be found "
                f"in the roster worksheet: {missing_date_text}"
            )

        if written_assignments == 0:
            raise ValueError(
                "No assignments were written to the roster."
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        workbook.save(output_path)

    finally:
        workbook.close()

    return output_path