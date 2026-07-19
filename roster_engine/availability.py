from datetime import date, datetime
from pathlib import Path

import openpyxl

from roster_engine.models import AvailabilityEntry
from roster_engine.personnel import normalise_text


BLOCKING_CODES = {
    "AL",
    "OL",
    "MA",
    "MC",
    "HL",
    "WISDOM",
    "SURGERY",
    "OUTPRO",
    "ORD",
}


def parse_date_header(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return None


def load_availability(
    workbook_path: Path,
    worksheet_name: str,
) -> list[AvailabilityEntry]:
    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Leave workbook not found: {workbook_path}"
        )

    workbook = openpyxl.load_workbook(
        workbook_path,
        read_only=True,
        data_only=True,
    )

    try:
        if worksheet_name not in workbook.sheetnames:
            raise ValueError(
                f"Worksheet '{worksheet_name}' was not found."
            )

        worksheet = workbook[worksheet_name]

        date_columns: dict[int, date] = {}

        for column_number in range(
            1,
            worksheet.max_column + 1,
        ):
            for row_number in range(
                1,
                min(10, worksheet.max_row) + 1,
            ):
                parsed_date = parse_date_header(
                    worksheet.cell(
                        row=row_number,
                        column=column_number,
                    ).value
                )

                if parsed_date is not None:
                    date_columns[column_number] = parsed_date
                    break

        if not date_columns:
            raise ValueError(
                "No date columns were found in the selected "
                "leave worksheet."
            )

        entries: list[AvailabilityEntry] = []

        for row_number in range(
            1,
            worksheet.max_row + 1,
        ):
            person_name = normalise_text(
                worksheet.cell(
                    row=row_number,
                    column=1,
                ).value
            )

            if not person_name:
                continue

            for column_number, unavailable_date in (
                date_columns.items()
            ):
                raw_reason = worksheet.cell(
                    row=row_number,
                    column=column_number,
                ).value

                reason = normalise_text(raw_reason)

                if not reason:
                    continue

                matched_code = next(
                    (
                        code
                        for code in BLOCKING_CODES
                        if code in reason
                    ),
                    None,
                )

                if matched_code is None:
                    continue

                entries.append(
                    AvailabilityEntry(
                        person_name=person_name,
                        unavailable_date=unavailable_date,
                        reason=matched_code,
                    )
                )

        return entries

    finally:
        workbook.close()