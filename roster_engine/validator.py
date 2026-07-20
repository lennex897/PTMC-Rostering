from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from roster_engine.eligibility import is_eligible_for_role
from roster_engine.models import (
    Assignment,
    AvailabilityEntry,
    DutyRequirement,
    Person,
    Schedule,
)


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: ValidationSeverity
    message: str
    duty_date: date | None = None
    person_name: str | None = None
    role: str | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == ValidationSeverity.ERROR
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == ValidationSeverity.WARNING
        ]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def add_error(
        self,
        *,
        code: str,
        message: str,
        duty_date: date | None = None,
        person_name: str | None = None,
        role: str | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                severity=ValidationSeverity.ERROR,
                message=message,
                duty_date=duty_date,
                person_name=person_name,
                role=role,
            )
        )

    def add_warning(
        self,
        *,
        code: str,
        message: str,
        duty_date: date | None = None,
        person_name: str | None = None,
        role: str | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                severity=ValidationSeverity.WARNING,
                message=message,
                duty_date=duty_date,
                person_name=person_name,
                role=role,
            )
        )


def normalise_text(value: str) -> str:
    return " ".join(value.strip().upper().split())


def requirement_key(
    requirement: DutyRequirement,
) -> tuple[date, str, str]:
    return (
        requirement.duty_date,
        normalise_text(requirement.role),
        normalise_text(requirement.centre),
    )


def assignment_key(
    assignment: Assignment,
) -> tuple[date, str, str]:
    return (
        assignment.duty_date,
        normalise_text(assignment.role),
        normalise_text(assignment.centre),
    )


def week_start(duty_date: date) -> date:
    return duty_date - timedelta(days=duty_date.weekday())


def validate_schedule(
    *,
    schedule: Schedule,
    personnel: list[Person],
    availability_entries: list[AvailabilityEntry],
    requirements: list[DutyRequirement],
    year: int,
    month: int,
    maximum_weekly_overnights: int = 3,
) -> ValidationReport:
    report = ValidationReport()

    target_assignments = [
        assignment
        for assignment in schedule.assignments
        if (
            assignment.duty_date.year == year
            and assignment.duty_date.month == month
        )
    ]

    target_requirements = [
        requirement
        for requirement in requirements
        if (
            requirement.duty_date.year == year
            and requirement.duty_date.month == month
        )
    ]

    personnel_by_name = {
        normalise_text(person.name): person
        for person in personnel
    }

    requirements_by_key: dict[
        tuple[date, str, str],
        list[DutyRequirement],
    ] = defaultdict(list)

    assignments_by_key: dict[
        tuple[date, str, str],
        list[Assignment],
    ] = defaultdict(list)

    for requirement in target_requirements:
        requirements_by_key[
            requirement_key(requirement)
        ].append(requirement)

    for assignment in target_assignments:
        assignments_by_key[
            assignment_key(assignment)
        ].append(assignment)

    # Every required slot must have exactly one assignment.
    for key, matching_requirements in requirements_by_key.items():
        matching_assignments = assignments_by_key.get(key, [])

        required_count = len(matching_requirements)
        assigned_count = len(matching_assignments)

        duty_date, role, centre = key

        if assigned_count < required_count:
            report.add_error(
                code="MISSING_REQUIREMENT",
                message=(
                    f"{required_count - assigned_count} assignment(s) "
                    f"missing for {role} at {centre}."
                ),
                duty_date=duty_date,
                role=role,
            )

        elif assigned_count > required_count:
            report.add_error(
                code="DUPLICATE_REQUIREMENT",
                message=(
                    f"{assigned_count} assignments were generated for "
                    f"{required_count} required slot(s) for {role}."
                ),
                duty_date=duty_date,
                role=role,
            )

    # No assignment should exist without a corresponding requirement.
    for key, matching_assignments in assignments_by_key.items():
        if key in requirements_by_key:
            continue

        duty_date, role, centre = key

        report.add_error(
            code="UNEXPECTED_ASSIGNMENT",
            message=(
                f"{len(matching_assignments)} unexpected assignment(s) "
                f"found for {role} at {centre}."
            ),
            duty_date=duty_date,
            role=role,
        )

    # Nobody may be assigned more than once on the same date.
    daily_person_counts = Counter(
        (
            assignment.duty_date,
            normalise_text(assignment.person_name),
        )
        for assignment in target_assignments
    )

    for (
        duty_date,
        person_name,
    ), assignment_count in daily_person_counts.items():
        if assignment_count <= 1:
            continue

        report.add_error(
            code="MULTIPLE_ASSIGNMENTS_SAME_DAY",
            message=(
                f"{person_name} has {assignment_count} assignments "
                "on the same date."
            ),
            duty_date=duty_date,
            person_name=person_name,
        )

    assignments_by_person: dict[
        str,
        list[Assignment],
    ] = defaultdict(list)

    weekly_overnight_counts: Counter[
        tuple[str, date]
    ] = Counter()

    for assignment in target_assignments:
        person_name = normalise_text(
            assignment.person_name
        )

        person = personnel_by_name.get(person_name)

        if person is None:
            report.add_error(
                code="UNKNOWN_PERSON",
                message=(
                    f"Assigned person {assignment.person_name!r} "
                    "was not found in the personnel list."
                ),
                duty_date=assignment.duty_date,
                person_name=assignment.person_name,
                role=assignment.role,
            )
            continue

        if not is_eligible_for_role(
            person=person,
            role=assignment.role,
            duty_date=assignment.duty_date,
            availability_entries=availability_entries,
        ):
            report.add_error(
                code="INELIGIBLE_ASSIGNMENT",
                message=(
                    f"{assignment.person_name} is not eligible for "
                    f"{assignment.role} on this date."
                ),
                duty_date=assignment.duty_date,
                person_name=assignment.person_name,
                role=assignment.role,
            )

        matching_requirements = requirements_by_key.get(
            assignment_key(assignment),
            [],
        )

        if matching_requirements:
            requirement = matching_requirements[0]

            if assignment.points != requirement.points:
                report.add_error(
                    code="POINTS_MISMATCH",
                    message=(
                        f"Assignment points {assignment.points:g} do not "
                        f"match required points {requirement.points:g}."
                    ),
                    duty_date=assignment.duty_date,
                    person_name=assignment.person_name,
                    role=assignment.role,
                )

            if (
                assignment.is_overnight
                != requirement.is_overnight
            ):
                report.add_error(
                    code="OVERNIGHT_FLAG_MISMATCH",
                    message=(
                        "Assignment overnight flag does not match "
                        "the requirement."
                    ),
                    duty_date=assignment.duty_date,
                    person_name=assignment.person_name,
                    role=assignment.role,
                )

        assignments_by_person[person_name].append(
            assignment
        )

        if assignment.is_overnight:
            weekly_overnight_counts[
                (
                    person_name,
                    week_start(assignment.duty_date),
                )
            ] += 1

    # Overnight duties require at least one clear day between them.
    for person_name, assignments in assignments_by_person.items():
        overnight_assignments = sorted(
            (
                assignment
                for assignment in assignments
                if assignment.is_overnight
            ),
            key=lambda assignment: assignment.duty_date,
        )

        for previous, current in zip(
            overnight_assignments,
            overnight_assignments[1:],
        ):
            days_between = (
                current.duty_date
                - previous.duty_date
            ).days

            if days_between <= 1:
                report.add_error(
                    code="INSUFFICIENT_OVERNIGHT_BREAK",
                    message=(
                        f"{person_name} has overnight duties on "
                        f"{previous.duty_date.isoformat()} and "
                        f"{current.duty_date.isoformat()} without "
                        "a full day break."
                    ),
                    duty_date=current.duty_date,
                    person_name=person_name,
                    role=current.role,
                )

    # Enforce the configured weekly overnight limit.
    for (
        person_name,
        start_of_week,
    ), overnight_count in weekly_overnight_counts.items():
        if overnight_count <= maximum_weekly_overnights:
            continue

        report.add_error(
            code="WEEKLY_OVERNIGHT_LIMIT",
            message=(
                f"{person_name} has {overnight_count} overnight "
                f"duties in the week beginning "
                f"{start_of_week.isoformat()}; maximum is "
                f"{maximum_weekly_overnights}."
            ),
            duty_date=start_of_week,
            person_name=person_name,
        )

    return report