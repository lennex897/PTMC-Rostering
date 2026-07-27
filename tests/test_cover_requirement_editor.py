from pathlib import Path


def test_cover_planner_has_requirement_editor() -> None:
    text = Path(
        "pages/6_Cover_Planner.py"
    ).read_text()

    assert '"Edit requirement"' in text
    assert '"Save requirement changes"' in text
    assert '"roster_cover_requirements"' in text


def test_editor_uses_flat_cover_type_compatibility() -> None:
    text = Path(
        "pages/6_Cover_Planner.py"
    ).read_text()

    assert "legacy_category_for_type(" in text
    assert '"points_snapshot": (' in text


def test_editor_warns_about_linked_manual_assignments() -> None:
    text = Path(
        "pages/6_Cover_Planner.py"
    ).read_text()

    assert '"roster_manual_assignments"' in text
    assert "linked manual assignment row(s)" in text
