from datetime import date

from roster_engine.cover_repository import CoverRequirement
from roster_engine.fc_manual_continuity import (
    availability_conflict_dates,
    build_fc_segment_payloads,
    group_fc_segments,
    uncovered_fc_dates,
)
from roster_engine.manual_planning_repository import ManualAssignment
from roster_engine.models import AvailabilityEntry


def requirement() -> CoverRequirement:
    return CoverRequirement(
        id="fc-1",
        roster_month_id="m1",
        requesting_unit="A COY",
        cover_category="FC",
        cover_type="FC",
        cover_type_id=None,
        points=1.0,
        session="FULL_DAY",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 5),
        personnel_required=1,
        mandatory=True,
    )


def manual(assignment_id: str, person: str, duty_date: date) -> ManualAssignment:
    return ManualAssignment(
        id=assignment_id,
        roster_month_id="m1",
        personnel_name=person,
        assignment_date=duty_date,
        assignment_kind="COVER",
        centre=None,
        role_name=None,
        cover_requirement_id="fc-1",
        cover_label="A COY — FC",
        session="FULL_DAY",
        is_locked=True,
        allow_override=False,
        remarks=None,
    )


def test_whole_fc_builds_one_row_per_day() -> None:
    rows = build_fc_segment_payloads(
        roster_month_id="m1",
        requirement=requirement(),
        person_name="MEDIC A",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 5),
        allow_override=False,
    )

    assert len(rows) == 5
    assert rows[0]["assignment_date"] == "2026-08-01"
    assert rows[-1]["assignment_date"] == "2026-08-05"


def test_handover_segments_group_separately() -> None:
    assignments = [
        manual("a1", "MEDIC A", date(2026, 8, 1)),
        manual("a2", "MEDIC A", date(2026, 8, 2)),
        manual("b1", "MEDIC B", date(2026, 8, 3)),
        manual("b2", "MEDIC B", date(2026, 8, 4)),
    ]

    segments = group_fc_segments(
        requirement_id="fc-1",
        assignments=assignments,
    )

    assert len(segments) == 2
    assert segments[0].person_name == "MEDIC A"
    assert segments[0].start_date == date(2026, 8, 1)
    assert segments[0].end_date == date(2026, 8, 2)
    assert segments[1].person_name == "MEDIC B"


def test_uncovered_dates_detect_gap() -> None:
    assignments = [
        manual("a1", "MEDIC A", date(2026, 8, 1)),
        manual("a2", "MEDIC A", date(2026, 8, 2)),
        manual("b1", "MEDIC B", date(2026, 8, 4)),
        manual("b2", "MEDIC B", date(2026, 8, 5)),
    ]

    assert uncovered_fc_dates(
        requirement=requirement(),
        assignments=assignments,
    ) == [date(2026, 8, 3)]


def test_any_availability_code_is_reported() -> None:
    conflicts = availability_conflict_dates(
        person_name="MEDIC A",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 5),
        availability_entries=[
            AvailabilityEntry(
                person_name="MEDIC A",
                unavailable_date=date(2026, 8, 3),
                reason="SERVE+",
            )
        ],
    )

    assert conflicts == [date(2026, 8, 3)]
