from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from roster_engine.cover_repository import DailyCoverSlot
from roster_engine.eligibility import BLOCKING_REASONS
from roster_engine.models import AvailabilityEntry, Assignment, Person, Schedule
from roster_engine.roster_rules import RosterRules



def _normalise(value: str) -> str:
    return " ".join(value.strip().upper().split())


def _sessions_conflict(first: str, second: str) -> bool:
    first = _normalise(first)
    second = _normalise(second)

    if "FULL_DAY" in {first, second}:
        return True

    return first == second


def cover_owner_centre(
    requesting_unit: str,
) -> str | None:
    import re

    unit = _normalise(
        requesting_unit
    )

    if re.match(
        r"^[A-W]\s+COY\b",
        unit,
    ):
        return "PT"

    if re.match(
        r"^[1-7](?:ST|ND|RD|TH)?\s+COY\b",
        unit,
    ):
        return "RH"

    return None


def _is_short_cover(
    slot: DailyCoverSlot,
) -> bool:
    return _normalise(
        slot.session
    ) in {
        "AM",
        "PM",
    }


def _service_type(
    person: Person,
) -> str:
    return _normalise(
        person.service_type
        or ""
    )


def _preferred_cover_candidates(
    *,
    candidates: list[Person],
    slot: DailyCoverSlot,
) -> list[Person]:
    cbt = [
        person
        for person in candidates
        if _service_type(
            person
        ) == "CBT"
    ]

    if cbt:
        return cbt

    legacy = [
        person
        for person in candidates
        if _service_type(
            person
        ) not in {
            "CBT",
            "SVC",
        }
    ]

    if legacy:
        return legacy

    if _is_short_cover(
        slot
    ):
        return [
            person
            for person in candidates
            if _service_type(
                person
            ) == "SVC"
        ]

    return []


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
        # FC SWAP is only a points record; it must not create another conflict.
        if _normalise(assignment.cover_type) == "FC SWAP":
            continue

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
    slot: DailyCoverSlot,
    historical_schedule: Schedule | None,
    locked_duties: list[Assignment],
    existing_cover_assignments: list[CoverAssignment],
) -> tuple[int, float, str]:
    owner = cover_owner_centre(
        slot.requesting_unit
    )

    centre_priority = (
        0
        if (
            owner is not None
            and _normalise(
                person.centre
            ) == owner
        )
        else 1
    )

    return (
        centre_priority,
        _current_workload_points(
            person=person,
            historical_schedule=historical_schedule,
            locked_duties=locked_duties,
            existing_cover_assignments=existing_cover_assignments,
        ),
        _normalise(
            person.name
        ),
    )


def _eligible_candidates(
    *,
    personnel: list[Person],
    slot: DailyCoverSlot,
    availability_entries: list[AvailabilityEntry],
    locked_duties: list[Assignment],
    cover_assignments: list[CoverAssignment],
    manual_only_personnel: set[str] | None = None,
) -> list[Person]:
    manual_only_personnel = manual_only_personnel or set()

    return [
        person
        for person in personnel
        if _normalise(person.name) not in manual_only_personnel
        and _person_is_available(
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
            cover_assignments=cover_assignments,
        )
    ]


def _add_unfilled(
    *,
    result: CoverSchedulerResult,
    slot: DailyCoverSlot,
) -> None:
    result.unfilled_slots.append(slot)

    message = (
        "No eligible Cover Fit personnel for "
        f"{slot.cover_type} on {slot.duty_date.isoformat()} "
        f"({slot.session})."
    )

    if slot.mandatory:
        message = "MANDATORY: " + message

    result.warnings.append(message)


def _assign_normal_slot(
    *,
    result: CoverSchedulerResult,
    slot: DailyCoverSlot,
    personnel: list[Person],
    availability_entries: list[AvailabilityEntry],
    locked_duties: list[Assignment],
    historical_schedule: Schedule | None,
    manual_only_personnel: set[str],
) -> None:
    candidates = _eligible_candidates(
        personnel=personnel,
        slot=slot,
        availability_entries=availability_entries,
        locked_duties=locked_duties,
        cover_assignments=result.assignments,
        manual_only_personnel=manual_only_personnel,
    )

    candidates = _preferred_cover_candidates(
        candidates=candidates,
        slot=slot,
    )

    candidates = sorted(
        candidates,
        key=lambda person: _candidate_sort_key(
            person=person,
            slot=slot,
            historical_schedule=historical_schedule,
            locked_duties=locked_duties,
            existing_cover_assignments=result.assignments,
        ),
    )

    if not candidates:
        _add_unfilled(
            result=result,
            slot=slot,
        )
        return

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


def _fc_locked_people_for_day(
    *,
    assignments: list[CoverAssignment],
    requirement_id: str,
    duty_date: date,
) -> list[CoverAssignment]:
    return [
        assignment
        for assignment in assignments
        if (
            assignment.is_locked
            and not assignment.is_reserve
            and _normalise(assignment.cover_type) == "FC"
            and assignment.cover_requirement_id == requirement_id
            and assignment.duty_date == duty_date
        )
    ]


def _append_fc_swap_points(
    *,
    result: CoverSchedulerResult,
    duty_date: date,
    requesting_unit: str,
    requirement_id: str,
    previous_people: set[str],
    current_people: set[str],
    display_names: dict[str, str],
    swap_points: float,
) -> None:
    """
    A change in the active FC medic pool is treated as a swap.

    On the day of the swap, every outgoing and incoming medic gets 0.5 point.
    The extra CoverAssignment rows are workload/record entries only.
    """
    outgoing = previous_people - current_people
    incoming = current_people - previous_people

    if not outgoing or not incoming:
        return

    for person_key in sorted(outgoing | incoming):
        result.assignments.append(
            CoverAssignment(
                duty_date=duty_date,
                person_name=display_names[person_key],
                requesting_unit=requesting_unit,
                cover_category="FC",
                cover_type="FC SWAP",
                session="FULL_DAY",
                points=swap_points,
                cover_requirement_id=requirement_id,
                is_reserve=False,
                is_locked=False,
            )
        )

    result.warnings.append(
        "FC medic swap on "
        f"{duty_date.isoformat()} for {requesting_unit}: "
        f"{', '.join(display_names[key] for key in sorted(outgoing))} "
        "→ "
        f"{', '.join(display_names[key] for key in sorted(incoming))}."
    )


def _assign_fc_requirement(
    *,
    result: CoverSchedulerResult,
    requirement_id: str,
    slots: list[DailyCoverSlot],
    personnel: list[Person],
    availability_entries: list[AvailabilityEntry],
    locked_duties: list[Assignment],
    historical_schedule: Schedule | None,
    rules: RosterRules,
    manual_only_personnel: set[str],
) -> None:
    """
    Assign one multi-day FC requirement with continuity.

    The previous day's active FC medic(s) are always preferred if still feasible.
    A locked manual FC assignment on a date overrides continuity and becomes the
    continuity pool for the following day(s).
    """
    slots_by_date: dict[date, list[DailyCoverSlot]] = defaultdict(list)

    for slot in slots:
        slots_by_date[slot.duty_date].append(slot)

    previous_people: set[str] = set()

    display_names = {
        _normalise(person.name): person.name
        for person in personnel
    }

    locked_dates = {
        assignment.duty_date
        for assignment in result.assignments
        if (
            assignment.is_locked
            and not assignment.is_reserve
            and _normalise(assignment.cover_type) == "FC"
            and assignment.cover_requirement_id == requirement_id
        )
    }

    timeline_dates = set(slots_by_date) | locked_dates

    for duty_date in sorted(timeline_dates):
        day_slots = slots_by_date.get(duty_date, [])

        locked_today = _fc_locked_people_for_day(
            assignments=result.assignments,
            requirement_id=requirement_id,
            duty_date=duty_date,
        )

        current_people: set[str] = {
            _normalise(item.person_name)
            for item in locked_today
        }

        slots_to_fill = list(day_slots)

        # Locked manual assignments have already consumed their DailyCoverSlot in
        # planning_generation.py, so only the remaining slots are present here.
        for slot in slots_to_fill:
            candidates = _eligible_candidates(
                personnel=personnel,
                slot=slot,
                availability_entries=availability_entries,
                locked_duties=locked_duties,
                cover_assignments=result.assignments,
                manual_only_personnel=manual_only_personnel,
            )

            # Do not place the same person twice into parallel FC lanes.
            candidates = [
                person
                for person in candidates
                if _normalise(person.name) not in current_people
            ]

            continuity_candidates = [
                person
                for person in candidates
                if _normalise(person.name) in previous_people
            ]

            pool = (
                continuity_candidates
                if continuity_candidates
                else candidates
            )

            pool = _preferred_cover_candidates(
                candidates=pool,
                slot=slot,
            )

            pool = sorted(
                pool,
                key=lambda person: _candidate_sort_key(
                    person=person,
                    slot=slot,
                    historical_schedule=historical_schedule,
                    locked_duties=locked_duties,
                    existing_cover_assignments=result.assignments,
                ),
            )

            if not pool:
                _add_unfilled(
                    result=result,
                    slot=slot,
                )
                continue

            selected = pool[0]
            selected_key = _normalise(selected.name)

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
                    is_reserve=False,
                    is_locked=False,
                )
            )

            current_people.add(selected_key)
            display_names.setdefault(
                selected_key,
                selected.name,
            )

        if previous_people and current_people != previous_people:
            requesting_unit = (
                day_slots[0].requesting_unit
                if day_slots
                else (
                    locked_today[0].requesting_unit
                    if locked_today
                    else "FC"
                )
            )

            _append_fc_swap_points(
                result=result,
                duty_date=duty_date,
                requesting_unit=requesting_unit,
                requirement_id=requirement_id,
                previous_people=previous_people,
                current_people=current_people,
                display_names=display_names,
                swap_points=rules.fc_swap_points,
            )

        if current_people:
            previous_people = current_people


def generate_cover_assignments(
    *,
    personnel: list[Person],
    cover_slots: list[DailyCoverSlot],
    availability_entries: list[AvailabilityEntry],
    locked_duties: list[Assignment] | None = None,
    locked_cover_assignments: list[CoverAssignment] | None = None,
    historical_schedule: Schedule | None = None,
    rules: RosterRules | None = None,
) -> CoverSchedulerResult:
    """
    Fill remaining covers.

    FC active covers are handled as continuous multi-day deployments:
    the same medic is retained across consecutive days whenever feasible.

    Manual locked FC assignments override continuity. If continuity changes,
    both outgoing and incoming medics receive a 0.5 FC swap point entry.

    FC reserves remain daily assignments.
    """
    locked_duties = list(locked_duties or [])

    if rules is None:
        rules = RosterRules()

    manual_only_personnel = {
        _normalise(name)
        for name in rules.manual_only_personnel
    }

    result = CoverSchedulerResult(
        assignments=list(
            locked_cover_assignments or []
        ),
    )

    fc_active_slots: list[DailyCoverSlot] = []
    other_slots: list[DailyCoverSlot] = []

    for slot in cover_slots:
        if (
            rules.fc_continuity_required
            and _normalise(slot.cover_type) == "FC"
            and not slot.is_reserve
            and _normalise(slot.cover_type) == "FC"
            and slot.cover_requirement_id is not None
        ):
            fc_active_slots.append(slot)
        else:
            other_slots.append(slot)

    fc_groups: dict[str, list[DailyCoverSlot]] = defaultdict(list)

    for slot in fc_active_slots:
        fc_groups[str(slot.cover_requirement_id)].append(slot)

    for requirement_id in sorted(fc_groups):
        _assign_fc_requirement(
            result=result,
            requirement_id=requirement_id,
            slots=fc_groups[requirement_id],
            personnel=personnel,
            availability_entries=availability_entries,
            locked_duties=locked_duties,
            historical_schedule=historical_schedule,
            rules=rules,
            manual_only_personnel=manual_only_personnel,
        )

    # Reserves/full-day covers before short covers; otherwise preserve prior logic.
    other_slots = sorted(
        other_slots,
        key=lambda slot: (
            slot.duty_date,
            0 if slot.is_reserve else 1,
            0 if slot.session == "FULL_DAY" else 1,
            slot.session,
            slot.requesting_unit,
            slot.cover_type,
        ),
    )

    for slot in other_slots:
        _assign_normal_slot(
            result=result,
            slot=slot,
            personnel=personnel,
            availability_entries=availability_entries,
            locked_duties=locked_duties,
            historical_schedule=historical_schedule,
            manual_only_personnel=manual_only_personnel,
        )

    return result