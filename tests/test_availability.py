from datetime import date
from pathlib import Path

import openpyxl

from roster_engine.availability import load_availability


def test_load_availability(tmp_path: Path) -> None:
    workbook_path = tmp_path / "Anon_Leave_Off_Impt Dates Forecast.xlsx"

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Aug 26"

    worksheet["A1"] = "Name"
    worksheet["B1"] = date(2026, 8, 1)
    worksheet["C1"] = date(2026, 8, 2)

    worksheet["A2"] = "CPL TEST PERSON"
    worksheet["B2"] = "AL"
    worksheet["C2"] = ""

    worksheet["A3"] = "LCP SECOND PERSON"
    worksheet["B3"] = ""
    worksheet["C3"] = "MC"

    workbook.save(workbook_path)

    entries = load_availability(
        workbook_path,
        "Aug 26",
    )

    assert len(entries) == 2

    assert entries[0].person_name == "CPL TEST PERSON"
    assert entries[0].unavailable_date == date(2026, 8, 1)
    assert entries[0].reason == "AL"

    assert entries[1].person_name == "LCP SECOND PERSON"
    assert entries[1].unavailable_date == date(2026, 8, 2)
    assert entries[1].reason == "MC"


def test_missing_worksheet_raises_error(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "leave.xlsx"

    workbook = openpyxl.Workbook()
    workbook.save(workbook_path)

    try:
        load_availability(
            workbook_path,
            "Aug 26",
        )
    except ValueError as error:
        assert "Aug 26" in str(error)
    else:
        raise AssertionError(
            "Expected ValueError for missing worksheet."
        )