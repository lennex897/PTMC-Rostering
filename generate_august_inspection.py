from collections import Counter, defaultdict
from pathlib import Path

from roster_engine.availability import load_availability
from roster_engine.generator import (
    GenerationSettings,
    assignments_in_target_month,
    generate_roster,
)
from roster_engine.history import load_historical_schedule
from roster_engine.personnel import (
    load_personnel,
    normalise_text,
)


SCHEDULING_WORKBOOK = Path(
    "reference/Scheduling Roster 2026.xlsx"
)

LEAVE_WORKBOOK = Path(
    "reference/Anon_Leave_Off_Impt Dates Forecast.xlsx"
)

HISTORICAL_WORKSHEET = "May-2026-Roster"
LEAVE_WORKSHEET = "Aug 26"

TARGET_YEAR = 2026
TARGET_MONTH = 8


personnel = load_personnel(
    SCHEDULING_WORKBOOK
)

availability_entries = load_availability(
    workbook_path=LEAVE_WORKBOOK,
    worksheet_name=LEAVE_WORKSHEET,
)

historical_schedule = load_historical_schedule(
    workbook_path=SCHEDULING_WORKBOOK,
    worksheet_name=HISTORICAL_WORKSHEET,
    personnel=personnel,
)


#
# Check whether anonymised names match across both workbooks.
#
personnel_names = {
    normalise_text(person.name)
    for person in personnel
}

availability_names = {
    normalise_text(entry.person_name)
    for entry in availability_entries
}

matched_availability_names = (
    personnel_names & availability_names
)

unknown_availability_names = (
    availability_names - personnel_names
)


result = generate_roster(
    personnel=personnel,
    availability_entries=availability_entries,
    settings=GenerationSettings(
        year=TARGET_YEAR,
        month=TARGET_MONTH,
    ),
    historical_schedule=historical_schedule,
)

august_assignments = assignments_in_target_month(
    schedule=result.schedule,
    year=TARGET_YEAR,
    month=TARGET_MONTH,
)


print("=" * 72)
print("AUGUST 2026 ROSTER GENERATION")
print("=" * 72)
print()

print("Inputs")
print("-" * 72)
print(f"Personnel:                 {len(personnel)}")
print(
    "Availability entries:      "
    f"{len(availability_entries)}"
)
print(
    "People with leave entries: "
    f"{len(availability_names)}"
)
print(
    "Matched leave names:        "
    f"{len(matched_availability_names)}"
)
print(
    "Unmatched leave names:      "
    f"{len(unknown_availability_names)}"
)
print(
    "Historical assignments:    "
    f"{len(historical_schedule.assignments)}"
)
print()

if unknown_availability_names:
    print("Unmatched leave-workbook names")
    print("-" * 72)

    for name in sorted(unknown_availability_names):
        print(name)

    print()


print("Generation report")
print("-" * 72)
print(
    f"Requirements:              "
    f"{result.report.requirement_count}"
)
print(
    f"Generated assignments:     "
    f"{result.report.generated_assignment_count}"
)
print(
    f"Unfilled requirements:     "
    f"{result.report.unfilled_requirement_count}"
)
print(
    f"Completion rate:           "
    f"{result.report.completion_rate:.1%}"
)
print()


print("August assignments by role")
print("-" * 72)

assignments_by_role = Counter(
    assignment.role
    for assignment in august_assignments
)

for role, count in sorted(assignments_by_role.items()):
    print(f"{role:<12} {count:>3}")

print()


print("August assignments by centre")
print("-" * 72)

assignments_by_centre = Counter(
    assignment.centre
    for assignment in august_assignments
)

for centre, count in sorted(
    assignments_by_centre.items()
):
    print(f"{centre:<12} {count:>3}")

print()


august_points = Counter()
august_duties = Counter()
historical_points = Counter()

for assignment in august_assignments:
    august_points[assignment.person_name] += (
        assignment.points
    )
    august_duties[assignment.person_name] += 1

for assignment in historical_schedule.assignments:
    historical_points[assignment.person_name] += (
        assignment.points
    )


print("Workload by person")
print("-" * 72)
print(
    f"{'Person':<43}"
    f"{'Aug duties':>11}"
    f"{'Aug pts':>9}"
    f"{'May pts':>9}"
    f"{'Combined':>10}"
)

for person in sorted(
    personnel,
    key=lambda item: (
        item.centre,
        item.name,
    ),
):
    august_person_points = august_points[
        person.name
    ]
    historical_person_points = historical_points[
        person.name
    ]

    combined_points = (
        august_person_points
        + historical_person_points
    )

    print(
        f"{person.name:<43}"
        f"{august_duties[person.name]:>11}"
        f"{august_person_points:>9.1f}"
        f"{historical_person_points:>9.1f}"
        f"{combined_points:>10.1f}"
    )

print()


print("Unfilled requirements")
print("-" * 72)

if not result.unfilled_requirements:
    print("None")
else:
    unfilled_by_date = defaultdict(list)

    for requirement in result.unfilled_requirements:
        unfilled_by_date[
            requirement.duty_date
        ].append(requirement)

    for duty_date in sorted(unfilled_by_date):
        roles = ", ".join(
            requirement.role
            for requirement in unfilled_by_date[
                duty_date
            ]
        )

        print(f"{duty_date}: {roles}")

print()


print("Scheduler warnings")
print("-" * 72)

if not result.report.warnings:
    print("None")
else:
    for warning in result.report.warnings:
        print(f"- {warning}")

print()


#
# Independently verify that no generated August assignment
# conflicts with an imported availability entry.
#
availability_lookup = {
    (
        normalise_text(entry.person_name),
        entry.unavailable_date,
    ): entry.reason
    for entry in availability_entries
}

leave_conflicts = []

for assignment in august_assignments:
    reason = availability_lookup.get(
        (
            normalise_text(assignment.person_name),
            assignment.duty_date,
        )
    )

    if reason is not None:
        leave_conflicts.append(
            (
                assignment,
                reason,
            )
        )


print("Leave-conflict check")
print("-" * 72)

if not leave_conflicts:
    print("No generated assignment conflicts detected.")
else:
    for assignment, reason in leave_conflicts:
        print(
            f"{assignment.duty_date} | "
            f"{assignment.person_name} | "
            f"{assignment.role} | "
            f"{reason}"
        )

print()


print("Generated August roster")
print("-" * 72)

for assignment in sorted(
    august_assignments,
    key=lambda item: (
        item.duty_date,
        item.centre,
        item.role,
    ),
):
    print(
        f"{assignment.duty_date} | "
        f"{assignment.role:<9} | "
        f"{assignment.person_name:<43} | "
        f"{assignment.points:g} pts"
    )
