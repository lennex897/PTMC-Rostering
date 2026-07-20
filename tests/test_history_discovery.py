from roster_engine.history import (
    parse_roster_worksheet_name,
)


def test_parse_hyphenated_roster_sheet() -> None:
    result = parse_roster_worksheet_name(
        "May-2026-Roster"
    )

    assert result is not None
    assert result.year == 2026
    assert result.month == 5


def test_parse_space_before_roster() -> None:
    result = parse_roster_worksheet_name(
        "Jul-2026 Roster"
    )

    assert result is not None
    assert result.year == 2026
    assert result.month == 7


def test_ignore_non_roster_sheet() -> None:
    result = parse_roster_worksheet_name(
        "Personnel"
    )

    assert result is None
