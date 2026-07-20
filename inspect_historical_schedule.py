from collections import Counter
from pathlib import Path

from roster_engine.history import load_historical_schedule
from roster_engine.personnel import load_personnel


WORKBOOK_PATH = Path(
    "reference/Scheduling Roster 2026.xlsx"
)
WORKSHEET_NAME = "May-2026-Roster"


personnel = load_personnel(WORKBOOK_PATH)

schedule = load_historical_schedule(
    workbook_path=WORKBOOK_PATH,
    worksheet_name=WORKSHEET_NAME,
    personnel=personnel,
)

print(f"Historical assignments: {len(schedule.assignments)}")
print()

print("Assignments by role:")
for role, count in Counter(
    assignment.role
    for assignment in schedule.assignments
).most_common():
    print(f"{role}: {count}")

print()
print("Assignments by centre:")
for centre, count in Counter(
    assignment.centre
    for assignment in schedule.assignments
).most_common():
    print(f"{centre}: {count}")

print()
print("Historical points by person:")
points_by_person = Counter()

for assignment in schedule.assignments:
    points_by_person[assignment.person_name] += (
        assignment.points
    )

for person_name, points in points_by_person.most_common():
    print(f"{person_name}: {points:g}")
