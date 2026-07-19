from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from roster_engine.eligibility import (
    eligible_people_for_role,
)
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
    rank_candidates,
)


@dataclass
class SchedulerResult:
    schedule: Schedule
    unfilled_requirements: list[DutyRequirement] = field(
        default_factory=list
    )
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
    """
    Schedule harder or more specialised roles first.

    Lower number means earlier scheduling.
    """

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
        assignment.person_name.strip().upper()
        for assignment in schedule.assignments_for_date(
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
            assignment.person_name.strip().upper()
        )

        if person is None:
            continue

        if person.department:
            departments.add(person.department)

    return frozenset(departments)


def generate_schedule(
    *,
    personnel: list[Person],
    requirements: list[DutyRequirement],
    availability_entries: list[AvailabilityEntry],
    historical_schedule: Schedule | None = None,
    role_priorities: tuple[RolePriority, ...] | None = None,
    maximum_weekly_overnights: int = 3,
) -> SchedulerResult:
    """
    Generate a basic roster using eligibility and candidate scoring.

    The function processes each duty requirement, obtains eligible
    personnel, ranks them, and selects the highest-ranked available
    candidate.
    """
    if role_priorities is None:
        role_priorities = DEFAULT_ROLE_PRIORITIES
        
    schedule = Schedule()

    if historical_schedule is not None:
        schedule.assignments.extend(
            historical_schedule.assignments
        )

    result = SchedulerResult(
        schedule=schedule,
    )

    personnel_by_name = {
        person.name.strip().upper(): person
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
        eligible_people = eligible_people_for_role(
            personnel=personnel,
            role=requirement.role,
            duty_date=requirement.duty_date,
            availability_entries=availability_entries,
        )

        assigned_names = (
            people_already_assigned_on_date(
                schedule=schedule,
                duty_date=requirement.duty_date,
            )
        )

        eligible_people = [
            person
            for person in eligible_people
            if person.name.strip().upper()
            not in assigned_names
        ]

        selected_departments = (
            selected_departments_for_date(
                schedule=schedule,
                duty_date=requirement.duty_date,
                personnel_by_name=personnel_by_name,
                centre=requirement.centre,
            )
        )

        context = ScoringContext(
            duty_date=requirement.duty_date,
            role=requirement.role,
            schedule=schedule,
            selected_departments=selected_departments,
            maximum_weekly_overnights=(
                maximum_weekly_overnights
            ),
            is_overnight=requirement.is_overnight,
            role_priorities=role_priorities,
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

        selected_score = selectable_candidates[0]
        selected_person = selected_score.person

        assignment = Assignment(
            duty_date=requirement.duty_date,
            role=requirement.role,
            centre=requirement.centre,
            person_name=selected_person.name,
            points=requirement.points,
            is_overnight=requirement.is_overnight,
        )

        schedule.add_assignment(assignment)

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