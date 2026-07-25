from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from roster_engine.cover_repository import DailyCoverSlot
from roster_engine.cover_scheduler import CoverAssignment, generate_cover_assignments
from roster_engine.generator import (
    GenerationReport,
    GenerationSettings,
    RosterGenerationResult,
    assignments_in_target_month,
)
from roster_engine.manual_planning_repository import ManualAssignment
from roster_engine.models import Assignment, DutyRequirement, RolePriority, Schedule
from roster_engine.planning_loader import PlanningContext
from roster_engine.requirements import generate_month_requirements
from roster_engine.scheduler import generate_schedule


@dataclass
class PlanningGenerationResult:
    roster_result: RosterGenerationResult
    locked_duty_assignments: list[Assignment] = field(default_factory=list)
    cover_assignments: list[CoverAssignment] = field(default_factory=list)
    unfilled_cover_slots: list[DailyCoverSlot] = field(default_factory=list)
    planning_warnings: list[str] = field(default_factory=list)

    @property
    def schedule(self) -> Schedule:
        return self.roster_result.schedule

    @property
    def locked_cover_assignments(self) -> list[CoverAssignment]:
        return [a for a in self.cover_assignments if a.is_locked]

    @property
    def generated_cover_assignments(self) -> list[CoverAssignment]:
        return [a for a in self.cover_assignments if not a.is_locked]

    @property
    def covers_complete(self) -> bool:
        return not self.unfilled_cover_slots


def _normalise(value: str) -> str:
    return " ".join(value.strip().upper().split())


def _duty_key(requirement: DutyRequirement) -> tuple[date, str]:
    return requirement.duty_date, _normalise(requirement.role)


def _manual_duty_key(assignment: ManualAssignment) -> tuple[date, str] | None:
    role = assignment.qualified_role
    if not role:
        return None
    return assignment.assignment_date, _normalise(role)


def _split_locked_manual_assignments(
    manual_assignments: list[ManualAssignment],
) -> tuple[
    list[ManualAssignment],
    list[ManualAssignment],
    list[ManualAssignment],
]:
    duties: list[ManualAssignment] = []
    reserves: list[ManualAssignment] = []
    covers: list[ManualAssignment] = []

    for assignment in manual_assignments:
        if not assignment.is_locked:
            continue

        if assignment.assignment_kind == "DUTY":
            duties.append(assignment)

        elif assignment.assignment_kind == "RESERVE":
            reserves.append(assignment)

        elif assignment.assignment_kind in {
            "COVER",
            "COVER_RESERVE",
        }:
            covers.append(assignment)

    return duties, reserves, covers

def _apply_locked_reserves(
    manual_reserves: list[ManualAssignment],
) -> list[Assignment]:
    """
    Convert manual reserves into zero-point same-day commitments.
    They do not consume a generated DutyRequirement.
    """
    assignments: list[Assignment] = []

    for manual in manual_reserves:
        centre = _normalise(
            manual.centre or ""
        )

        if centre not in {"PT", "RH"}:
            raise ValueError(
                "Manual reserve must have PT or RH centre: "
                f"{manual.personnel_name} / {manual.assignment_date}."
            )

        assignments.append(
            Assignment(
                duty_date=manual.assignment_date,
                role=f"{centre} RESERVE",
                centre=centre,
                person_name=manual.personnel_name,
                points=0.0,
                is_overnight=False,
            )
        )

    return assignments


def _apply_locked_duties(
    *,
    requirements: list[DutyRequirement],
    manual_duties: list[ManualAssignment],
) -> tuple[list[Assignment], list[DutyRequirement]]:
    remaining = list(requirements)
    locked_assignments: list[Assignment] = []

    for manual in manual_duties:
        key = _manual_duty_key(manual)
        if key is None:
            raise ValueError(f"Locked manual duty {manual.id} has no role.")

        match_index = next(
            (
                index
                for index, requirement in enumerate(remaining)
                if _duty_key(requirement) == key
            ),
            None,
        )

        if match_index is None:
            raise ValueError(
                "Locked manual duty does not match a required duty slot: "
                f"{manual.personnel_name} / {manual.assignment_date} / "
                f"{manual.qualified_role}."
            )

        requirement = remaining.pop(match_index)
        locked_assignments.append(
            Assignment(
                duty_date=requirement.duty_date,
                role=requirement.role,
                centre=requirement.centre,
                person_name=manual.personnel_name,
                points=requirement.points,
                is_overnight=requirement.is_overnight,
            )
        )

    return locked_assignments, remaining


def _consume_cover_slot(
    *,
    slots: list[DailyCoverSlot],
    manual: ManualAssignment,
) -> DailyCoverSlot:
    for index, slot in enumerate(slots):
        if slot.duty_date != manual.assignment_date:
            continue
        if manual.assignment_kind == "COVER_RESERVE":
            if not slot.is_reserve:
                continue
        else:
            if slot.is_reserve:
                continue
            if (
                manual.cover_requirement_id
                and slot.cover_requirement_id != manual.cover_requirement_id
            ):
                continue
        return slots.pop(index)

    raise ValueError(
        "Locked manual cover does not match an available cover slot: "
        f"{manual.personnel_name} / {manual.assignment_date} / "
        f"{manual.assignment_kind}."
    )


def _apply_locked_covers(
    *,
    cover_slots: list[DailyCoverSlot],
    manual_covers: list[ManualAssignment],
) -> tuple[list[CoverAssignment], list[DailyCoverSlot]]:
    remaining_slots = list(cover_slots)
    assignments: list[CoverAssignment] = []

    for manual in manual_covers:
        slot = _consume_cover_slot(
            slots=remaining_slots,
            manual=manual,
        )
        assignments.append(
            CoverAssignment(
                duty_date=manual.assignment_date,
                person_name=manual.personnel_name,
                requesting_unit=slot.requesting_unit,
                cover_category=slot.cover_category,
                cover_type=slot.cover_type,
                session=slot.session,
                points=slot.points,
                cover_requirement_id=slot.cover_requirement_id,
                is_reserve=slot.is_reserve,
                is_locked=True,
            )
        )

    return assignments, remaining_slots


def _cover_blocked_people(
    cover_assignments: list[CoverAssignment],
) -> dict[date, set[str]]:
    blocked: dict[date, set[str]] = defaultdict(set)
    for assignment in cover_assignments:
        if assignment.cover_type == "FC SWAP":
            continue
        blocked[assignment.duty_date].add(assignment.person_name)
    return dict(blocked)


def _cover_points(
    cover_assignments: list[CoverAssignment],
) -> dict[str, float]:
    points: dict[str, float] = defaultdict(float)
    for assignment in cover_assignments:
        points[_normalise(assignment.person_name)] += assignment.points
    return dict(points)


def generate_roster_from_planning(
    *,
    planning: PlanningContext,
    settings: GenerationSettings,
    historical_schedule: Schedule | None = None,
    role_priorities: tuple[RolePriority, ...] | None = None,
) -> PlanningGenerationResult:
    rules = planning.roster_rules

    requirements = generate_month_requirements(
        year=settings.year,
        month=settings.month,
        settings=settings.requirement_settings,
        rules=rules,
    )

    manual_duties, manual_reserves, manual_covers = (
        _split_locked_manual_assignments(
            planning.manual_assignments
        )
    )

    locked_duties, remaining_requirements = _apply_locked_duties(
        requirements=requirements,
        manual_duties=manual_duties,
    )

    locked_reserves = _apply_locked_reserves(
        manual_reserves
    )

    locked_covers, remaining_cover_slots = _apply_locked_covers(
        cover_slots=planning.cover_slots,
        manual_covers=manual_covers,
    )

    cover_result = generate_cover_assignments(
        personnel=planning.personnel,
        cover_slots=remaining_cover_slots,
        availability_entries=planning.availability_entries,
        locked_duties=[
            *locked_duties,
            *locked_reserves,
        ],
        locked_cover_assignments=locked_covers,
        historical_schedule=historical_schedule,
        rules=rules,
    )

    all_cover_assignments = cover_result.assignments
    blocked_people_by_date = _cover_blocked_people(all_cover_assignments)
    cover_points_by_person = _cover_points(all_cover_assignments)

    scheduler_result = generate_schedule(
        personnel=planning.personnel,
        requirements=remaining_requirements,
        availability_entries=planning.availability_entries,
        historical_schedule=historical_schedule,
        role_priorities=role_priorities,
        maximum_weekly_overnights=rules.maximum_weekly_overnights,
        overnight_min_break_days=rules.overnight_min_break_days,
        leaving_reduction_days=rules.leaving_reduction_days,
        manual_only_personnel=rules.manual_only_personnel,
        initial_assignments=[
            *locked_duties,
            *locked_reserves,
        ],
        blocked_people_by_date=blocked_people_by_date,
        point_offsets_by_person=cover_points_by_person,
        duty_interests=planning.duty_interests,
    )

    generated_assignments = assignments_in_target_month(
        schedule=scheduler_result.schedule,
        year=settings.year,
        month=settings.month,
    )

    warnings = [
        *cover_result.warnings,
        *scheduler_result.schedule.warnings,
    ]

    report = GenerationReport(
        year=settings.year,
        month=settings.month,
        personnel_count=len(planning.personnel),
        availability_entry_count=len(planning.availability_entries),
        requirement_count=len(requirements),
        generated_assignment_count=len(generated_assignments),
        unfilled_requirement_count=len(scheduler_result.unfilled_requirements),
        warnings=warnings,
    )

    roster_result = RosterGenerationResult(
        scheduler_result=scheduler_result,
        report=report,
        requirements=requirements,
    )

    return PlanningGenerationResult(
        roster_result=roster_result,
        locked_duty_assignments=[
            *locked_duties,
            *locked_reserves,
        ],
        cover_assignments=all_cover_assignments,
        unfilled_cover_slots=cover_result.unfilled_slots,
        planning_warnings=cover_result.warnings,
    )
