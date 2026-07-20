from datetime import date
from pathlib import Path

import openpyxl

from roster_engine.history import (
    historical_role_name,
    load_historical_schedule,
    normalise_historical_role,
)
from roster_engine.models import Person


def make_person(
    name: str,
    centre: str = "PT",
) -> Person:
    return Person(
        name=name,
        rank=name.split()[0],
        centre=centre,
        department="TEST",
        ampt_status="PASS",
    )


def create_history_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "May-2026-Roster"

    worksheet["B2"] = "Event Log"

    worksheet["D3"] = date(2026, 5, 1)
    worksheet["E3"] = date(2026, 5, 2)
    worksheet["F3"] = date(2026, 5, 3)

    worksheet["D4"] = "Fri"
    worksheet["E4"] = "Sat"
    worksheet["F4"] = "Sun"

    # Valid PT person.
    worksheet["B5"] = "CPL TEST PERSON"
    worksheet["D5"] = "DM"
    worksheet["E5"] = "AL"
    worksheet["F5"] = "SB1"

    # Summary row that must not become a person.
    worksheet["B6"] = "DM"
    worksheet["D6"] = "CPL TEST PERSON"
    worksheet["E6"] = 1
    worksheet["F6"] = "#N/A"

    # Valid RH person.
    worksheet["B8"] = "LCP RH PERSON"
    worksheet["D8"] = "SB2"
    worksheet["E8"] = "RESERVE"
    worksheet["F8"] = "AE"

    workbook.save(path)


def test_normalise_historical_role() -> None:
    assert normalise_historical_role(" dm ") == "DM"
    assert normalise_historical_role("CS/B") == "CS/B"
    assert normalise_historical_role("AL") is None
    assert normalise_historical_role("#N/A") is None
    assert normalise_historical_role(1) is None


def test_historical_role_name() -> None:
    assert historical_role_name("PT", "DM") == "PT DM"
    assert historical_role_name("RH", "SB1") == "RH SB1"


def test_load_historical_schedule(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "history.xlsx"
    create_history_workbook(workbook_path)

    personnel = [
        make_person("CPL TEST PERSON", centre="PT"),
        make_person("LCP RH PERSON", centre="RH"),
    ]

    schedule = load_historical_schedule(
        workbook_path=workbook_path,
        worksheet_name="May-2026-Roster",
        personnel=personnel,
    )

    assert len(schedule.assignments) == 4

    assignments = {
        (
            assignment.person_name,
            assignment.duty_date,
            assignment.role,
        ): assignment
        for assignment in schedule.assignments
    }

    pt_dm = assignments[
        (
            "CPL TEST PERSON",
            date(2026, 5, 1),
            "PT DM",
        )
    ]
    assert pt_dm.points == 1.5
    assert pt_dm.is_overnight is True
    assert pt_dm.centre == "PT"

    pt_sb1 = assignments[
        (
            "CPL TEST PERSON",
            date(2026, 5, 3),
            "PT SB1",
        )
    ]
    assert pt_sb1.points == 2.0

    rh_sb2 = assignments[
        (
            "LCP RH PERSON",
            date(2026, 5, 1),
            "RH SB2",
        )
    ]
    assert rh_sb2.points == 1.5
    assert rh_sb2.centre == "RH"

    rh_ae = assignments[
        (
            "LCP RH PERSON",
            date(2026, 5, 3),
            "RH AE",
        )
    ]
    assert rh_ae.points == 2.0


def test_summary_rows_are_ignored(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "history.xlsx"
    create_history_workbook(workbook_path)

    personnel = [
        make_person("CPL TEST PERSON"),
        make_person("LCP RH PERSON", centre="RH"),
    ]

    schedule = load_historical_schedule(
        workbook_path=workbook_path,
        worksheet_name="May-2026-Roster",
        personnel=personnel,
    )

    assert all(
        assignment.person_name != "DM"
        for assignment in schedule.assignments
    )


def test_non_duty_values_are_ignored(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "history.xlsx"
    create_history_workbook(workbook_path)

    personnel = [
        make_person("CPL TEST PERSON"),
        make_person("LCP RH PERSON", centre="RH"),
    ]

    schedule = load_historical_schedule(
        workbook_path=workbook_path,
        worksheet_name="May-2026-Roster",
        personnel=personnel,
    )

    imported_roles = {
        assignment.role
        for assignment in schedule.assignments
    }

    assert imported_roles == {
        "PT DM",
        "PT SB1",
        "RH SB2",
        "RH AE",
    }
