from datetime import date

from roster_engine.cover_scheduler import CoverAssignment
from roster_engine.generated_roster_repository import build_assignment_rows
from roster_engine.generator import GenerationReport, RosterGenerationResult
from roster_engine.models import Assignment, Schedule
from roster_engine.planning_generation import PlanningGenerationResult
from roster_engine.scheduler import SchedulerResult


def build_result() -> PlanningGenerationResult:
    duty = Assignment(
        duty_date=date(2026, 8, 3),
        role="PT DM",
        centre="PT",
        person_name="CPL DUTY",
        points=1.0,
        is_overnight=True,
    )
    roster_result = RosterGenerationResult(
        scheduler_result=SchedulerResult(schedule=Schedule(assignments=[duty])),
        report=GenerationReport(
            year=2026,
            month=8,
            personnel_count=2,
            availability_entry_count=0,
            requirement_count=1,
            generated_assignment_count=1,
            unfilled_requirement_count=0,
            warnings=[],
        ),
        requirements=[],
    )
    cover = CoverAssignment(
        duty_date=date(2026, 8, 4),
        person_name="CPL COVER",
        requesting_unit="1 COY",
        cover_category="NON_FC",
        cover_type="BTP",
        session="FULL_DAY",
        points=1.5,
        cover_requirement_id="cover-1",
        is_reserve=False,
        is_locked=True,
    )
    return PlanningGenerationResult(
        roster_result=roster_result,
        locked_duty_assignments=[duty],
        cover_assignments=[cover],
        unfilled_cover_slots=[],
    )


def test_build_assignment_rows_flattens_duty_and_cover() -> None:
    rows = build_assignment_rows(
        generation_id="generation-1",
        roster_month_id="month-1",
        result=build_result(),
        personnel_ids_by_name={
            "CPL DUTY": "person-1",
            "CPL COVER": "person-2",
        },
    )
    assert len(rows) == 2
    duty = next(row for row in rows if row["assignment_kind"] == "DUTY")
    cover = next(row for row in rows if row["assignment_kind"] == "COVER")
    assert duty["personnel_id"] == "person-1"
    assert duty["is_locked"] is True
    assert cover["personnel_id"] == "person-2"
    assert cover["cover_type"] == "BTP"


def test_cover_reserve_is_stored_separately() -> None:
    result = build_result()
    result.cover_assignments.append(
        CoverAssignment(
            duty_date=date(2026, 8, 5),
            person_name="CPL RESERVE",
            requesting_unit="SHARED FC RESERVE",
            cover_category="FC",
            cover_type="FC RESERVE",
            session="FULL_DAY",
            points=0.0,
            cover_requirement_id=None,
            is_reserve=True,
            is_locked=False,
        )
    )
    rows = build_assignment_rows(
        generation_id="generation-1",
        roster_month_id="month-1",
        result=result,
    )
    reserve = next(
        row for row in rows
        if row["assignment_kind"] == "COVER_RESERVE"
    )
    assert reserve["is_reserve"] is True
    assert reserve["cover_type"] == "FC RESERVE"
