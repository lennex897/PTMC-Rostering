from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from roster_engine.duty_interest_repository import DutyInterest
from roster_engine.eligibility import eligible_people_for_role
from roster_engine.models import (
    Assignment,
    AvailabilityEntry,
    DutyRequirement,
    Person,
    RolePriority,
    Schedule,
)
from roster_engine.scoring import (
    CandidateScore,
    DEFAULT_ROLE_PRIORITIES,
    ScoringContext,
    normalise_text,
    rank_candidates,
)


@dataclass
class SchedulerResult:
    schedule: Schedule
    unfilled_requirements: list[
        DutyRequirement
    ] = field(default_factory=list)
    assignment_scores: dict[
        tuple[date, str],
        CandidateScore,
    ] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return not self.unfilled_requirements


def requirement_sort_key(
    requirement: DutyRequirement,
) -> tuple[date, int, str]:
    role_priority = {
        "PT DM": 0,
        "RH DM": 0,
        "PT CS1": 1,
        "PT CS2": 1,
        "PT CS/B": 1,
        "RH CS1": 1,
        "PT AE": 2,
        "RH AE": 2,
        "PT SB1": 3,
        "PT SB2": 3,
        "RH SB1": 3,
        "RH SB2": 3,
    }

    return (
        requirement.duty_date,
        role_priority.get(
            requirement.role,
            100,
        ),
        requirement.role,
    )


def people_already_assigned_on_date(
    schedule: Schedule,
    duty_date: date,
) -> set[str]:
    return {
        normalise_text(
            assignment.person_name
        )
        for assignment
        in schedule.assignments_for_date(
            duty_date
        )
    }


def selected_departments_for_date(
    schedule: Schedule,
    duty_date: date,
    personnel_by_name: dict[str, Person],
    centre: str,
) -> frozenset[str]:
    departments: set[str] = set()

    for assignment in schedule.assignments_for_date(
        duty_date
    ):
        if assignment.centre != centre:
            continue

        person = personnel_by_name.get(
            normalise_text(
                assignment.person_name
            )
        )

        if person is None:
            continue

        if person.department:
            departments.add(
                person.department
            )

    return frozenset(departments)


def generate_schedule(
    *,
    personnel: list[Person],
    requirements: list[DutyRequirement],
    availability_entries: list[AvailabilityEntry],
    historical_schedule: Schedule | None = None,
    role_priorities: tuple[
        RolePriority,
        ...
    ] | None = None,
    maximum_weekly_overnights: int = 3,
    overnight_min_break_days: int = 1,
    leaving_reduction_days: int = 90,
    manual_only_personnel: tuple[str, ...] | list[str] | set[str] = (),
    initial_assignments: list[Assignment] | None = None,
    blocked_people_by_date: dict[
        date,
        set[str],
    ] | None = None,
    point_offsets_by_person: dict[
        str,
        float,
    ] | None = None,
    duty_interests: tuple[
        DutyInterest,
        ...
    ] | list[DutyInterest] | None = None,
) -> SchedulerResult:
    if role_priorities is None:
        role_priorities = (
            DEFAULT_ROLE_PRIORITIES
        )

    manual_only_names = {
        normalise_text(name)
        for name in manual_only_personnel
    }

    blocked_people_by_date = {
        duty_date: {
            normalise_text(name)
            for name in names
        }
        for duty_date, names
        in (
            blocked_people_by_date
            or {}
        ).items()
    }

    point_offsets_by_person = {
        normalise_text(name): float(points)
        for name, points
        in (
            point_offsets_by_person
            or {}
        ).items()
    }

    duty_interests = tuple(
        duty_interests or ()
    )

    schedule = Schedule()

    if historical_schedule is not None:
        schedule.assignments.extend(
            historical_schedule.assignments
        )

    if initial_assignments:
        schedule.assignments.extend(
            initial_assignments
        )

    result = SchedulerResult(
        schedule=schedule,
    )

    personnel_by_name = {
        normalise_text(
            person.name
        ): person
        for person in personnel
    }

    sorted_requirements = sorted(
        requirements,
        key=requirement_sort_key,
    )

    assignments_created_by_date: dict[
        date,
        list[Assignment],
    ] = defaultdict(list)

    for requirement in sorted_requirements:
        eligible_people = (
            eligible_people_for_role(
                personnel=personnel,
                role=requirement.role,
                duty_date=requirement.duty_date,
                availability_entries=(
                    availability_entries
                ),
            )
        )

        assigned_names = (
            people_already_assigned_on_date(
                schedule=schedule,
                duty_date=requirement.duty_date,
            )
        )

        externally_blocked = (
            blocked_people_by_date.get(
                requirement.duty_date,
                set(),
            )
        )

        eligible_people = [
            person
            for person in eligible_people
            if (
                normalise_text(person.name)
                not in assigned_names
                and normalise_text(person.name)
                not in externally_blocked
                and normalise_text(person.name)
                not in manual_only_names
            )
        ]

        selected_departments = (
            selected_departments_for_date(
                schedule=schedule,
                duty_date=requirement.duty_date,
                personnel_by_name=(
                    personnel_by_name
                ),
                centre=requirement.centre,
            )
        )

        context = ScoringContext(
            duty_date=requirement.duty_date,
            role=requirement.role,
            schedule=schedule,
            selected_departments=(
                selected_departments
            ),
            maximum_weekly_overnights=(
                maximum_weekly_overnights
            ),
            overnight_min_break_days=(
                overnight_min_break_days
            ),
            leaving_reduction_days=(
                leaving_reduction_days
            ),
            is_overnight=(
                requirement.is_overnight
            ),
            role_priorities=(
                role_priorities
            ),
            point_offsets_by_person=(
                point_offsets_by_person
            ),
            duty_interests=(
                duty_interests
            ),
        )

        ranked_candidates = rank_candidates(
            personnel=eligible_people,
            context=context,
        )

        selectable_candidates = [
            candidate
            for candidate in ranked_candidates
            if candidate.is_selectable
        ]

        if not selectable_candidates:
            result.unfilled_requirements.append(
                requirement
            )
            schedule.warnings.append(
                "No eligible selectable person for "
                f"{requirement.role} on "
                f"{requirement.duty_date.isoformat()}."
            )
            continue

        selected_score = (
            selectable_candidates[0]
        )
        selected_person = (
            selected_score.person
        )

        assignment = Assignment(
            duty_date=requirement.duty_date,
            role=requirement.role,
            centre=requirement.centre,
            person_name=(
                selected_person.name
            ),
            points=requirement.points,
            is_overnight=(
                requirement.is_overnight
            ),
        )

        schedule.add_assignment(
            assignment
        )

        assignments_created_by_date[
            requirement.duty_date
        ].append(assignment)

        result.assignment_scores[
            (
                requirement.duty_date,
                requirement.role,
            )
        ] = selected_score

    return result
