from dataclasses import dataclass, field
from datetime import date

from roster_engine.eligibility import is_eligible_for_role
from roster_engine.models import AvailabilityEntry, DutyRequirement, Person, Schedule
from roster_engine.scoring import normalise_text


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


@dataclass
class ValidationReport:
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def error_count(self) -> int:
        return len(self.errors)


def validate_schedule(
    *,
    schedule: Schedule,
    personnel: list[Person],
    availability_entries: list[AvailabilityEntry],
    requirements: list[DutyRequirement],
    year: int,
    month: int,
    maximum_weekly_overnights: int = 3,
    overnight_min_break_days: int = 1,
    manual_only_personnel: tuple[str, ...] | list[str] | set[str] = (),
) -> ValidationReport:
    report = ValidationReport()

    personnel_by_name = {
        normalise_text(person.name): person
        for person in personnel
    }

    manual_only_names = {
        normalise_text(name)
        for name in manual_only_personnel
    }

    target_assignments = [
        assignment
        for assignment in schedule.assignments
        if (
            assignment.duty_date.year == year
            and assignment.duty_date.month == month
        )
    ]

    requirement_keys = {
        (req.duty_date, req.role)
        for req in requirements
    }

    assignment_keys = {
        (item.duty_date, item.role)
        for item in target_assignments
    }

    for duty_date, role in sorted(
        requirement_keys - assignment_keys
    ):
        report.errors.append(
            ValidationIssue(
                code="MISSING_REQUIREMENT",
                message=(
                    f"Missing {role} on "
                    f"{duty_date.isoformat()}."
                ),
            )
        )

    seen_person_dates: set[
        tuple[str, date]
    ] = set()

    overnight_dates_by_person: dict[
        str,
        list[date],
    ] = {}

    for assignment in target_assignments:
        person_key = normalise_text(
            assignment.person_name
        )
        person = personnel_by_name.get(
            person_key
        )

        if person is None:
            report.errors.append(
                ValidationIssue(
                    code="UNKNOWN_PERSONNEL",
                    message=(
                        f"Unknown personnel: "
                        f"{assignment.person_name}."
                    ),
                )
            )
            continue

        is_manual_reserve = (
            normalise_text(assignment.role)
            in {"PT RESERVE", "RH RESERVE"}
        )

        if (
            not is_manual_reserve
            and not is_eligible_for_role(
                person=person,
                role=assignment.role,
                duty_date=assignment.duty_date,
                availability_entries=availability_entries,
            )
        ):
            report.errors.append(
                ValidationIssue(
                    code="INELIGIBLE_ASSIGNMENT",
                    message=(
                        f"{assignment.person_name} is not eligible for "
                        f"{assignment.role} on "
                        f"{assignment.duty_date.isoformat()}."
                    ),
                )
            )

        person_date_key = (
            person_key,
            assignment.duty_date,
        )

        if person_date_key in seen_person_dates:
            report.errors.append(
                ValidationIssue(
                    code="MULTIPLE_ASSIGNMENTS_SAME_DAY",
                    message=(
                        f"{assignment.person_name} has multiple duty "
                        f"assignments on "
                        f"{assignment.duty_date.isoformat()}."
                    ),
                )
            )
        else:
            seen_person_dates.add(
                person_date_key
            )

        if assignment.is_overnight:
            overnight_dates_by_person.setdefault(
                person_key,
                [],
            ).append(
                assignment.duty_date
            )

    minimum_gap = (
        max(0, overnight_min_break_days)
        + 1
    )

    for person_key, dates in overnight_dates_by_person.items():
        sorted_dates = sorted(dates)

        for previous, current in zip(
            sorted_dates,
            sorted_dates[1:],
        ):
            if (
                current - previous
            ).days < minimum_gap:
                person = personnel_by_name[
                    person_key
                ]

                report.errors.append(
                    ValidationIssue(
                        code="INSUFFICIENT_OVERNIGHT_BREAK",
                        message=(
                            f"{person.name} does not have "
                            f"{overnight_min_break_days} full day(s) "
                            f"between overnight duties on "
                            f"{previous.isoformat()} and "
                            f"{current.isoformat()}."
                        ),
                    )
                )

    # Weekly overnight cap.
    for person_key, dates in overnight_dates_by_person.items():
        week_counts: dict[
            tuple[int, int],
            int,
        ] = {}

        for current_date in dates:
            iso = current_date.isocalendar()
            key = (
                iso.year,
                iso.week,
            )
            week_counts[key] = (
                week_counts.get(key, 0)
                + 1
            )

        for (iso_year, iso_week), count in week_counts.items():
            if count > maximum_weekly_overnights:
                person = personnel_by_name[
                    person_key
                ]

                report.errors.append(
                    ValidationIssue(
                        code="WEEKLY_OVERNIGHT_LIMIT",
                        message=(
                            f"{person.name} has {count} overnight duties "
                            f"in ISO week {iso_year}-W{iso_week:02d}; "
                            f"maximum is {maximum_weekly_overnights}."
                        ),
                    )
                )

    # Manual-only people may legitimately appear if the assignment was
    # manually locked. Validation cannot infer provenance from Schedule alone,
    # so this rule is enforced at automatic generation time rather than here.

    return report
