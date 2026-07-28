from pathlib import Path


def test_exporter_accepts_availability_entries() -> None:
    text = Path("roster_engine/exporter.py").read_text()
    assert "availability_entries: list[AvailabilityEntry] | None = None" in text


def test_exporter_combines_multiple_availability_codes() -> None:
    text = Path("roster_engine/exporter.py").read_text()
    assert '" + ".join(' in text
    assert "availability_by_cell" in text


def test_assignments_are_written_before_availability() -> None:
    text = Path("roster_engine/exporter.py").read_text()
    assert text.index(
        "for assignment in schedule.assignments:"
    ) < text.index(
        "for entry in availability_entries or []:"
    )


def test_saved_rosters_passes_availability_to_exporter() -> None:
    text = Path("pages/8_Saved_Rosters.py").read_text()
    assert "availability_entries=(" in text
