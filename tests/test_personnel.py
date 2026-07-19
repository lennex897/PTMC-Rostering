from pathlib import Path

from roster_engine.personnel import load_personnel


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REFERENCE_WORKBOOK = (
    PROJECT_ROOT
    / "reference"
    / "Scheduling Roster 2026.xlsx"
)


def test_personnel_workbook_loads() -> None:
    personnel = load_personnel(REFERENCE_WORKBOOK)

    assert len(personnel) > 0


def test_personnel_have_valid_centres() -> None:
    personnel = load_personnel(REFERENCE_WORKBOOK)

    assert all(
        person.centre in {"PT", "RH"}
        for person in personnel
    )


def test_placeholder_rows_are_not_people() -> None:
    personnel = load_personnel(REFERENCE_WORKBOOK)

    names = {
        person.name
        for person in personnel
    }

    assert "DM" not in names
    assert "CS1" not in names
    assert "CS2" not in names
    assert "SB1" not in names
    assert "SB2" not in names
    assert "AE" not in names


def test_bcf_detection() -> None:
    personnel = load_personnel(REFERENCE_WORKBOOK)

    bcf_personnel = [
        person
        for person in personnel
        if "(BCF)" in person.name
    ]

    assert all(
        person.is_bcf
        for person in bcf_personnel
    )