from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from roster_engine.cover_repository import DailyCoverSlot
from roster_engine.eligibility import BLOCKING_REASONS
from roster_engine.models import AvailabilityEntry, Assignment, Person, Schedule


def _normalise(value: str) -> str:
    return " ".join(value.strip().upper().split())


def _sessions_conflict(first: str, second: str) -> bool:
    first = _normalise(first)
    second = _normalise(second)

    if "FULL_DAY" in {first, second}:
        return True

    return first == second


@dataclass(frozen=True)
class CoverAssignment:
    duty_date: date
    person_name: str
    requesting_unit: str
    cover_category: str
    cover_type: str
    session: str
    points: float
    cover_requirement_id: str | None
    is_reserve: bool = False
    is_locked: bool = False


@dataclass
class CoverSchedulerResult:
    assignments: list[CoverAssignment] = field(default_factory=list)
    unfilled_slots: list[DailyCoverSlot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not self.unfilled_slots


def _person_is_available(
    *,
    person: Person,
    duty_date: date,
    availability_entries: list[AvailabilityEntry],
) -> bool:
    if not person.is_active:
        return False

    if person.is_cover_fit is not True:
        return False

    if person.leaving_date is not None and duty_date >= person.leaving_date:
        return False

    person_name = _normalise(person.name)

    for entry in availability_entries:
        if (
            _normalise(entry.person_name) == person_name
            and entry.unavailable_date == duty_date
            and _normalise(entry.reason) in BLOCKING_REASONS
        ):
            return False

    return True


def _has_locked_duty_on_date(
    *,
    person: Person,
    duty_date: date,
    locked_duties: list[Assignment],
) -> bool:
    person_name = _normalise(person.name)

    return any(
        assignment.duty_date == duty_date
        and _normalise(assignment.person_name) == person_name
        for assignment in locked_duties
    )


def _has_cover_conflict(
    *,
    person: Person,
    slot: DailyCoverSlot,
    cover_assignments: list[CoverAssignment],
) -> bool:
    person_name = _normalise(person.name)

    for assignment in cover_assignments:
        if (
            assignment.duty_date == slot.duty_date
            and _normalise(assignment.person_name) == person_name
            and _sessions_conflict(assignment.session, slot.session)
        ):
            return True

    return False


def _current_workload_points(
    *,
    person: Person,
    historical_schedule: Schedule | None,
    locked_duties: list[Assignment],
    existing_cover_assignments: list[CoverAssignment],
) -> float:
    total = 0.0

    if historical_schedule is not None:
        total += historical_schedule.total_points_for_person(
            person.name
        )

    person_name = _normalise(person.name)

    total += sum(
        assignment.points
        for assignment in locked_duties
        if _normalise(assignment.person_name) == person_name
    )

    total += sum(
        assignment.points
        for assignment in existing_cover_assignments
        if _normalise(assignment.person_name) == person_name
    )

    return total


def _candidate_sort_key(
    *,
    person: Person,
    historical_schedule: Schedule | None,
    locked_duties: list[Assignment],
    existing_cover_assignments: list[CoverAssignment],
) -> tuple[float, str]:
    return (
        _current_workload_points(
            person=person,
            historical_schedule=historical_schedule,
            locked_duties=locked_duties,
            existing_cover_assignments=existing_cover_assignments,
        ),
        _normalise(person.name),
    )


def generate_cover_assignments(
    *,
    personnel: list[Person],
    cover_slots: list[DailyCoverSlot],
    availability_entries: list[AvailabilityEntry],
    locked_duties: list[Assignment] | None = None,
    locked_cover_assignments: list[CoverAssignment] | None = None,
    historical_schedule: Schedule | None = None,
) -> CoverSchedulerResult:
    """
    Fill remaining cover slots using active Cover Fit personnel from either centre.

    Hard constraints:
    - Cover Fit only.
    - Availability / leaving date respected.
    - A person with a locked duty cannot also be assigned a cover that date.
    - Simultaneous cover sessions require separate personnel.
      FULL_DAY conflicts with AM and PM; AM and PM can be performed by the
      same person because they do not overlap.

    Selection:
    - Prefer the currently lowest total workload points.
    - Locked/generated cover points participate in balancing.

    If a mandatory slot cannot be filled, it is returned in unfilled_slots
    rather than silently dropped.
    """
    locked_duties = list(locked_duties or [])
    assignments = list(locked_cover_assignments or [])

    result = CoverSchedulerResult(
        assignments=assignments,
    )

    sorted_slots = sorted(
        cover_slots,
        key=lambda slot: (
            slot.duty_date,
            0 if slot.is_reserve else 1,
            0 if slot.session == "FULL_DAY" else 1,
            slot.session,
            slot.requesting_unit,
            slot.cover_type,
        ),
    )

    for slot in sorted_slots:
        candidates = [
            person
            for person in personnel
            if _person_is_available(
                person=person,
                duty_date=slot.duty_date,
                availability_entries=availability_entries,
            )
            and not _has_locked_duty_on_date(
                person=person,
                duty_date=slot.duty_date,
                locked_duties=locked_duties,
            )
            and not _has_cover_conflict(
                person=person,
                slot=slot,
                cover_assignments=result.assignments,
            )
        ]

        candidates = sorted(
            candidates,
            key=lambda person: _candidate_sort_key(
                person=person,
                historical_schedule=historical_schedule,
                locked_duties=locked_duties,
                existing_cover_assignments=result.assignments,
            ),
        )

        if not candidates:
            result.unfilled_slots.append(slot)

            message = (
                "No eligible Cover Fit personnel for "
                f"{slot.cover_type} on {slot.duty_date.isoformat()} "
                f"({slot.session})."
            )

            if slot.mandatory:
                message = "MANDATORY: " + message

            result.warnings.append(message)
            continue

        selected = candidates[0]

        result.assignments.append(
            CoverAssignment(
                duty_date=slot.duty_date,
                person_name=selected.name,
                requesting_unit=slot.requesting_unit,
                cover_category=slot.cover_category,
                cover_type=slot.cover_type,
                session=slot.session,
                points=slot.points,
                cover_requirement_id=slot.cover_requirement_id,
                is_reserve=slot.is_reserve,
                is_locked=False,
            )
        )

    return result
