from pathlib import Path

ELIGIBILITY = Path("roster_engine/eligibility.py")
COVER = Path("roster_engine/cover_scheduler.py")

if not ELIGIBILITY.exists() or not COVER.exists():
    raise SystemExit(
        "Run this script from the PTMC-Rostering repository root."
    )

eligibility = ELIGIBILITY.read_text()
cover = COVER.read_text()

old_eligibility = """def is_person_unavailable(
    person: Person,
    duty_date: date,
    availability_entries: list[AvailabilityEntry],
) -> bool:
    person_name = person.name.strip().upper()
    return any(
        entry.person_name.strip().upper() == person_name
        and entry.unavailable_date == duty_date
        and entry.reason.strip().upper() in BLOCKING_REASONS
        for entry in availability_entries
    )
"""

new_eligibility = """def is_person_unavailable(
    person: Person,
    duty_date: date,
    availability_entries: list[AvailabilityEntry],
) -> bool:
    \"\"\"
    Any plotted availability entry blocks automatic scheduling on that date,
    regardless of code.

    Manual locked duties/covers remain the explicit override path because
    they are applied outside automatic eligibility.
    \"\"\"
    person_name = person.name.strip().upper()

    return any(
        entry.person_name.strip().upper() == person_name
        and entry.unavailable_date == duty_date
        for entry in availability_entries
    )
"""

if old_eligibility not in eligibility:
    raise SystemExit(
        "Could not find the expected is_person_unavailable() block."
    )

eligibility = eligibility.replace(
    old_eligibility,
    new_eligibility,
    1,
)

old_cover = """    for entry in availability_entries:
        if (
            _normalise(entry.person_name) == person_name
            and entry.unavailable_date == duty_date
            and _normalise(entry.reason) in BLOCKING_REASONS
        ):
            return False
"""

new_cover = """    for entry in availability_entries:
        if (
            _normalise(entry.person_name) == person_name
            and entry.unavailable_date == duty_date
        ):
            return False
"""

if old_cover not in cover:
    raise SystemExit(
        "Could not find the expected cover availability block."
    )

cover = cover.replace(
    old_cover,
    new_cover,
    1,
)

compile(eligibility, str(ELIGIBILITY), "exec")
compile(cover, str(COVER), "exec")

for path, content in (
    (ELIGIBILITY, eligibility),
    (COVER, cover),
):
    backup = path.with_suffix(".py.step21b_backup")

    if not backup.exists():
        backup.write_text(
            path.read_text()
        )

    path.write_text(
        content
    )

print("Step 21B applied successfully.")
print("Any availability entry now blocks automatic duties and covers.")
