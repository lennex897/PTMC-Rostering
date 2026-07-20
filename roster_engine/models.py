from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Person:
    name: str
    rank: str
    centre: str
    department: str
    ampt_status: str
    is_bcf: bool = False
    leaving_date: date | None = None
    eligible_roles: set[str] = field(default_factory=set)
    is_active: bool = True

    @property
    def is_ampt_valid(self) -> bool:
        return self.ampt_status.strip().upper() == "PASS"


@dataclass(frozen=True)
class AvailabilityEntry:
    person_name: str
    unavailable_date: date
    reason: str


@dataclass(frozen=True)
class DutyRequirement:
    duty_date: date
    role: str
    centre: str
    is_overnight: bool
    points: float


@dataclass(frozen=True)
class Assignment:
    duty_date: date
    role: str
    centre: str
    person_name: str
    points: float
    is_overnight: bool


@dataclass(frozen=True)
class RolePriority:
    """
    A configurable score adjustment for one person and one role.

    Positive adjustment:
        Higher priority for the role.

    Negative adjustment:
        Lower priority for the role.

    effective_from and effective_until are optional and inclusive.
    """

    person_name: str
    role: str
    adjustment: float
    reason: str = ""
    is_active: bool = True
    effective_from: date | None = None
    effective_until: date | None = None

    def applies_on(self, duty_date: date) -> bool:
        if not self.is_active:
            return False

        if (
            self.effective_from is not None
            and duty_date < self.effective_from
        ):
            return False

        if (
            self.effective_until is not None
            and duty_date > self.effective_until
        ):
            return False

        return True


@dataclass
class Schedule:
    assignments: list[Assignment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_assignment(
        self,
        assignment: Assignment,
    ) -> None:
        self.assignments.append(assignment)

    def assignments_for_person(
        self,
        person_name: str,
    ) -> list[Assignment]:
        normalised_name = person_name.strip().upper()

        return [
            assignment
            for assignment in self.assignments
            if assignment.person_name.strip().upper()
            == normalised_name
        ]

    def assignments_for_date(
        self,
        duty_date: date,
    ) -> list[Assignment]:
        return [
            assignment
            for assignment in self.assignments
            if assignment.duty_date == duty_date
        ]

    def total_points_for_person(
        self,
        person_name: str,
    ) -> float:
        return sum(
            assignment.points
            for assignment in self.assignments_for_person(
                person_name
            )
        )