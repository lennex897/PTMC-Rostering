from datetime import date

from roster_engine.dm_shadow_repository import (
    DMShadowRepository,
)


def test_dm_shadow_row_parser() -> None:
    shadow = DMShadowRepository._row_to_shadow(
        {
            "id": "s1",
            "roster_month_id": "m1",
            "personnel_name": "CPL SHADOW",
            "assignment_date": "2026-08-12",
            "centre": "PT",
            "points": 1.0,
            "remarks": "Training",
        }
    )

    assert shadow.shadow_date == date(
        2026,
        8,
        12,
    )
    assert shadow.personnel_name == "CPL SHADOW"
    assert shadow.points == 1.0
