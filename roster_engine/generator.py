from dataclasses import dataclass, field
from datetime import date

from roster_engine.models import (
    Assignment,
    AvailabilityEntry,
    DutyRequirement,
    Person,
    RolePriority,
    Schedule,
)
from roster_engine.requirements import (
    RequirementSettings,
    generate_month_requirements,
)
from roster_engine.scheduler import (
    SchedulerResult,
    generate_schedule,
)


@dataclass(frozen=True)
class GenerationSettings:
    year: int
    month: int
    maximum_weekly_overnights: int = 3
    requirement_settings: RequirementSettings = field(
        default_factory=RequirementSettings
    )


@dataclass
class GenerationReport:
    year: int
    month: int
    personnel_count: int
    availability_entry_count: int
    requirement_count: int
    generated_assignment_count: int
    unfilled_requirement_count: int
    warnings: list[str] = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        if self.requirement_count == 0:
            return 1.0

        return (
            self.generated_assignment_count
            / self.requirement_count
        )

    @property
    def is_complete(self) -> bool:
        return self.unfilled_requirement_count == 0


@dataclass
class RosterGenerationResult:
    scheduler_result: SchedulerResult
    report: GenerationReport
    requirements: list[DutyRequirement]

    @property
    def schedule(self) -> Schedule:
        return self.scheduler_result.schedule

    @property
    def unfilled_requirements(
        self,
    ) -> list[DutyRequirement]:
        return self.scheduler_result.unfilled_requirements


def assignments_in_target_month(
    schedule: Schedule,
    year: int,
    month: int,
) -> list[Assignment]:
    return [
        assignment
        for assignment in schedule.assignments
        if assignment.duty_date.year == year
        and assignment.duty_date.month == month
    ]


def generate_roster(
    *,
    personnel: list[Person],
    availability_entries: list[AvailabilityEntry],
    settings: GenerationSettings,
    historical_schedule: Schedule | None = None,
    role_priorities: tuple[RolePriority, ...] | None = None,
) -> RosterGenerationResult:
    """
    Coordinate monthly roster generation.

    This function:
    1. Generates the required duty slots.
    2. Sends them to the scheduler.
    3. Builds a generation report.
    """

    requirements = generate_month_requirements(
        year=settings.year,
        month=settings.month,
        settings=settings.requirement_settings,
    )

    scheduler_result = generate_schedule(
        personnel=personnel,
        requirements=requirements,
        availability_entries=availability_entries,
        historical_schedule=historical_schedule,
        role_priorities=role_priorities,
        maximum_weekly_overnights=(
            settings.maximum_weekly_overnights
        ),
    )

    generated_assignments = assignments_in_target_month(
        schedule=scheduler_result.schedule,
        year=settings.year,
        month=settings.month,
    )

    report = GenerationReport(
        year=settings.year,
        month=settings.month,
        personnel_count=len(personnel),
        availability_entry_count=len(
            availability_entries
        ),
        requirement_count=len(requirements),
        generated_assignment_count=len(
            generated_assignments
        ),
        unfilled_requirement_count=len(
            scheduler_result.unfilled_requirements
        ),
        warnings=list(
            scheduler_result.schedule.warnings
        ),
    )

    return RosterGenerationResult(
        scheduler_result=scheduler_result,
        report=report,
        requirements=requirements,
    )


def unfilled_requirements_by_date(
    result: RosterGenerationResult,
) -> dict[date, list[DutyRequirement]]:
    grouped: dict[
        date,
        list[DutyRequirement],
    ] = {}

    for requirement in result.unfilled_requirements:
        grouped.setdefault(
            requirement.duty_date,
            [],
        ).append(requirement)

    return grouped