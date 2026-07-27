from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from roster_engine.cover_repository import CoverRequirement
from roster_engine.manual_planning_repository import ManualAssignment
from roster_engine.models import AvailabilityEntry


@dataclass(frozen=True)
class FCManualSegment:
    person_name: str
    start_date: date
    end_date: date
    assignment_ids: tuple[str, ...]
    allow_override: bool
    remarks: str | None

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1


def normalise(value: str | None) -> str:
    return " ".join((value or "").strip().upper().split())


def is_active_fc_requirement(requirement: CoverRequirement) -> bool:
    return (
        normalise(requirement.cover_category) == "FC"
        and normalise(requirement.cover_type) == "FC"
    )


def inclusive_dates(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        raise ValueError("FC segment end date cannot be before start date.")

    return [
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    ]


def availability_conflict_dates(
    *,
    person_name: str,
    start_date: date,
    end_date: date,
    availability_entries: Iterable[AvailabilityEntry],
) -> list[date]:
    person_key = normalise(person_name)
    wanted_dates = set(inclusive_dates(start_date, end_date))

    return sorted({
        entry.unavailable_date
        for entry in availability_entries
        if (
            normalise(entry.person_name) == person_key
            and entry.unavailable_date in wanted_dates
        )
    })


def build_fc_segment_payloads(
    *,
    roster_month_id: str,
    requirement: CoverRequirement,
    person_name: str,
    start_date: date,
    end_date: date,
    allow_override: bool,
    remarks: str | None = None,
) -> list[dict]:
    if not is_active_fc_requirement(requirement):
        raise ValueError("Selected requirement is not an active FC requirement.")

    if end_date < start_date:
        raise ValueError("FC segment end date cannot be before start date.")

    if (
        start_date < requirement.start_date
        or end_date > requirement.end_date
    ):
        raise ValueError(
            "FC segment must remain within the FC requirement dates."
        )

    clean_remarks = remarks.strip() if remarks and remarks.strip() else None

    return [
        {
            "roster_month_id": roster_month_id,
            "personnel_name": person_name,
            "assignment_date": current_date.isoformat(),
            "assignment_kind": "COVER",
            "centre": None,
            "role_name": None,
            "cover_requirement_id": requirement.id,
            "cover_label": (
                f"{requirement.requesting_unit} — "
                f"{requirement.cover_type}"
            ),
            "session": requirement.session,
            "is_locked": True,
            "allow_override": bool(allow_override),
            "remarks": clean_remarks,
        }
        for current_date in inclusive_dates(start_date, end_date)
    ]


def group_fc_segments(
    *,
    requirement_id: str,
    assignments: Iterable[ManualAssignment],
) -> list[FCManualSegment]:
    relevant = sorted(
        [
            assignment
            for assignment in assignments
            if (
                assignment.assignment_kind == "COVER"
                and assignment.cover_requirement_id == requirement_id
                and assignment.is_locked
            )
        ],
        key=lambda assignment: (
            assignment.assignment_date,
            normalise(assignment.personnel_name),
        ),
    )

    groups: list[list[ManualAssignment]] = []

    for assignment in relevant:
        if not groups:
            groups.append([assignment])
            continue

        previous = groups[-1][-1]

        if (
            normalise(previous.personnel_name)
            == normalise(assignment.personnel_name)
            and assignment.assignment_date
            == previous.assignment_date + timedelta(days=1)
            and previous.allow_override == assignment.allow_override
            and (previous.remarks or None) == (assignment.remarks or None)
        ):
            groups[-1].append(assignment)
        else:
            groups.append([assignment])

    return [
        FCManualSegment(
            person_name=group[0].personnel_name,
            start_date=group[0].assignment_date,
            end_date=group[-1].assignment_date,
            assignment_ids=tuple(item.id for item in group),
            allow_override=group[0].allow_override,
            remarks=group[0].remarks or None,
        )
        for group in groups
    ]


def occupied_fc_dates(
    *,
    requirement_id: str,
    assignments: Iterable[ManualAssignment],
) -> set[date]:
    return {
        assignment.assignment_date
        for assignment in assignments
        if (
            assignment.assignment_kind == "COVER"
            and assignment.cover_requirement_id == requirement_id
            and assignment.is_locked
        )
    }


def segment_overlap_dates(
    *,
    requirement: CoverRequirement,
    start_date: date,
    end_date: date,
    assignments: Iterable[ManualAssignment],
) -> list[date]:
    occupied = occupied_fc_dates(
        requirement_id=requirement.id,
        assignments=assignments,
    )

    return [
        current_date
        for current_date in inclusive_dates(start_date, end_date)
        if current_date in occupied
    ]


def uncovered_fc_dates(
    *,
    requirement: CoverRequirement,
    assignments: Iterable[ManualAssignment],
) -> list[date]:
    occupied = occupied_fc_dates(
        requirement_id=requirement.id,
        assignments=assignments,
    )

    return [
        current_date
        for current_date in requirement.dates()
        if current_date not in occupied
    ]
