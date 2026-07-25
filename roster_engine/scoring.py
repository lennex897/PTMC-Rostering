from dataclasses import dataclass, field
from datetime import date, timedelta

from roster_engine.duty_interest_repository import DutyInterest
from roster_engine.models import (
    Person,
    RolePriority,
    Schedule,
)


DEFAULT_DUTY_INTEREST_BONUS = 15.0


DEFAULT_ROLE_PRIORITIES: tuple[RolePriority, ...] = (
    RolePriority(
        person_name="3SG SAMUEL TAN ENG WEE",
        role="PT AE",
        adjustment=-15.0,
        reason="Lower priority for AE",
    ),
    RolePriority(
        person_name="LCP STEPHEN TAY",
        role="PT CS1",
        adjustment=-15.0,
        reason="Lower priority for CS",
    ),
    RolePriority(
        person_name="LCP STEPHEN TAY",
        role="PT CS2",
        adjustment=-15.0,
        reason="Lower priority for CS",
    ),
    RolePriority(
        person_name="LCP STEPHEN TAY",
        role="PT CS/B",
        adjustment=-15.0,
        reason="Lower priority for CS",
    ),
    RolePriority(
        person_name="LCP STEPHEN TAY",
        role="RH CS1",
        adjustment=-15.0,
        reason="Lower priority for CS",
    ),
)


@dataclass(frozen=True)
class ScoreComponent:
    description: str
    value: float


@dataclass
class CandidateScore:
    person: Person
    total: float = 0.0
    components: list[ScoreComponent] = field(
        default_factory=list
    )
    blocked_reasons: list[str] = field(
        default_factory=list
    )

    @property
    def is_selectable(self) -> bool:
        return not self.blocked_reasons

    def add(
        self,
        description: str,
        value: float,
    ) -> None:
        self.components.append(
            ScoreComponent(
                description=description,
                value=value,
            )
        )
        self.total += value

    def block(
        self,
        reason: str,
    ) -> None:
        if reason not in self.blocked_reasons:
            self.blocked_reasons.append(reason)


@dataclass(frozen=True)
class ScoringContext:
    duty_date: date
    role: str
    schedule: Schedule
    selected_departments: frozenset[str] = frozenset()
    maximum_weekly_overnights: int = 3
    is_overnight: bool | None = None
    role_priorities: tuple[RolePriority, ...] = (
        DEFAULT_ROLE_PRIORITIES
    )
    point_offsets_by_person: dict[str, float] = field(
        default_factory=dict
    )
    duty_interests: tuple[DutyInterest, ...] = ()
    duty_interest_bonus: float = DEFAULT_DUTY_INTEREST_BONUS


def normalise_text(
    value: str,
) -> str:
    return " ".join(
        value.strip().upper().split()
    )


def is_overnight_role(
    role: str,
) -> bool:
    return normalise_text(role).startswith("PT ")


def assignments_in_week(
    person: Person,
    duty_date: date,
    schedule: Schedule,
):
    week_start = duty_date - timedelta(
        days=duty_date.weekday()
    )
    week_end = week_start + timedelta(days=6)

    return [
        assignment
        for assignment
        in schedule.assignments_for_person(
            person.name
        )
        if (
            week_start
            <= assignment.duty_date
            <= week_end
        )
    ]


def overnight_assignments(
    person: Person,
    schedule: Schedule,
):
    return [
        assignment
        for assignment
        in schedule.assignments_for_person(
            person.name
        )
        if assignment.is_overnight
    ]


def last_overnight_before(
    person: Person,
    duty_date: date,
    schedule: Schedule,
):
    previous_assignments = [
        assignment
        for assignment
        in overnight_assignments(
            person,
            schedule,
        )
        if assignment.duty_date < duty_date
    ]

    if not previous_assignments:
        return None

    return max(
        previous_assignments,
        key=lambda assignment: (
            assignment.duty_date
        ),
    )


def apply_role_priorities(
    result: CandidateScore,
    context: ScoringContext,
) -> None:
    person_name = normalise_text(
        result.person.name
    )
    role = normalise_text(
        context.role
    )

    for priority in context.role_priorities:
        if not priority.applies_on(
            context.duty_date
        ):
            continue

        if (
            normalise_text(priority.person_name)
            != person_name
        ):
            continue

        if (
            normalise_text(priority.role)
            != role
        ):
            continue

        result.add(
            description=(
                priority.reason
                or "Role priority adjustment"
            ),
            value=priority.adjustment,
        )


def apply_duty_interest(
    result: CandidateScore,
    context: ScoringContext,
    *,
    is_overnight: bool,
) -> None:
    """
    Apply PTMC overnight interest as a soft preference only.

    Interest never makes a candidate eligible and never bypasses hard
    constraints. Eligibility filtering occurs before scoring in scheduler.py.

    An interest with preferred_role=None means "any eligible overnight role".
    """
    if not is_overnight:
        return

    person_name = normalise_text(
        result.person.name
    )
    role = normalise_text(
        context.role
    )

    matching_interests = [
        interest
        for interest in context.duty_interests
        if (
            normalise_text(
                interest.person_name
            )
            == person_name
            and interest.interest_date
            == context.duty_date
            and interest.applies_to_role(
                role
            )
        )
    ]

    if not matching_interests:
        return

    # Multiple duplicate interests should not stack bonuses.
    result.add(
        description=(
            "PTMC overnight duty interest"
        ),
        value=context.duty_interest_bonus,
    )


def score_candidate(
    person: Person,
    context: ScoringContext,
) -> CandidateScore:
    result = CandidateScore(
        person=person
    )

    role = normalise_text(
        context.role
    )
    department = normalise_text(
        person.department
    )
    person_key = normalise_text(
        person.name
    )

    scheduled_points = (
        context.schedule.total_points_for_person(
            person.name
        )
    )
    external_points = float(
        context.point_offsets_by_person.get(
            person_key,
            0.0,
        )
    )
    current_points = (
        scheduled_points
        + external_points
    )

    result.add(
        description=(
            f"Current total workload points: "
            f"{current_points:g}"
        ),
        value=-10.0 * current_points,
    )

    selected_departments = {
        normalise_text(value)
        for value
        in context.selected_departments
    }

    if (
        department
        and department != "UNSPECIFIED"
        and department
        in selected_departments
    ):
        result.add(
            description=(
                "Department already represented "
                "in this team"
            ),
            value=-8.0,
        )
    else:
        result.add(
            description=(
                "Department not yet represented "
                "in this team"
            ),
            value=5.0,
        )

    overnight_duty = (
        context.is_overnight
        if context.is_overnight
        is not None
        else is_overnight_role(role)
    )

    if overnight_duty:
        previous_overnight = (
            last_overnight_before(
                person=person,
                duty_date=context.duty_date,
                schedule=context.schedule,
            )
        )

        if previous_overnight is None:
            result.add(
                description=(
                    "No previous overnight duty "
                    "in current schedule"
                ),
                value=10.0,
            )
        else:
            days_since_previous = (
                context.duty_date
                - previous_overnight.duty_date
            ).days

            if days_since_previous <= 1:
                result.block(
                    "No day break since previous "
                    "overnight duty"
                )
            else:
                spacing_bonus = min(
                    float(days_since_previous),
                    10.0,
                )
                result.add(
                    description=(
                        f"{days_since_previous} days "
                        "since previous overnight duty"
                    ),
                    value=spacing_bonus,
                )

        weekly_overnights = sum(
            1
            for assignment
            in assignments_in_week(
                person=person,
                duty_date=context.duty_date,
                schedule=context.schedule,
            )
            if assignment.is_overnight
        )

        if (
            weekly_overnights
            >= context.maximum_weekly_overnights
        ):
            result.block(
                "Maximum weekly overnight duties "
                "already reached"
            )
        else:
            result.add(
                description=(
                    f"{weekly_overnights} overnight "
                    "duties assigned this week"
                ),
                value=-5.0 * weekly_overnights,
            )

    if person.leaving_date is not None:
        days_until_leaving = (
            person.leaving_date
            - context.duty_date
        ).days

        if 0 < days_until_leaving <= 90:
            departure_penalty = (
                91 - days_until_leaving
            ) / 5

            result.add(
                description=(
                    f"Leaving unit in "
                    f"{days_until_leaving} days"
                ),
                value=-departure_penalty,
            )

    apply_duty_interest(
        result=result,
        context=context,
        is_overnight=overnight_duty,
    )

    apply_role_priorities(
        result=result,
        context=context,
    )

    return result


def rank_candidates(
    personnel: list[Person],
    context: ScoringContext,
) -> list[CandidateScore]:
    results = [
        score_candidate(
            person=person,
            context=context,
        )
        for person in personnel
    ]

    return sorted(
        results,
        key=lambda result: (
            not result.is_selectable,
            -result.total,
            normalise_text(
                result.person.name
            ),
        ),
    )
