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


@dataclass
class Schedule:
    assignments: list[Assignment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_assignment(self, assignment: Assignment) -> None:
        self.assignments.append(assignment)

    def assignments_for_person(
        self,
        person_name: str,
    ) -> list[Assignment]:
        return [
            assignment
            for assignment in self.assignments
            if assignment.person_name == person_name
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
            for assignment in self.assignments
            if assignment.person_name == person_name
        )