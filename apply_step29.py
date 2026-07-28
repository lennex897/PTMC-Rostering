from pathlib import Path

REPOSITORY = Path("roster_engine/cover_repository.py")

if not REPOSITORY.exists():
    raise SystemExit(
        "Run this from the PTMC-Rostering repository root."
    )

text = REPOSITORY.read_text()

old = '''    if value in {
        "FC",
        "GP",
        "GX",
    }:
        return value

    return "NON_FC"
'''

new = '''    # "$FC" is the user-facing FC cover type used in the Cover Planner.
    # Internally it must still route through the FC category so that FC
    # continuity, FC reserves, and FC-specific scheduling rules apply.
    if value in {
        "FC",
        "$FC",
    }:
        return "FC"

    if value in {
        "GP",
        "GX",
    }:
        return value

    return "NON_FC"
'''

if old not in text:
    raise SystemExit(
        "Could not find classify_cover_category() mapping. "
        "No file was changed."
    )

text = text.replace(
    old,
    new,
    1,
)

compile(
    text,
    str(REPOSITORY),
    "exec",
)

backup = REPOSITORY.with_suffix(
    ".py.step29_backup"
)

if not backup.exists():
    backup.write_text(
        REPOSITORY.read_text()
    )

REPOSITORY.write_text(
    text
)

print("Step 29 applied successfully.")
print("$FC now derives backend cover_category='FC'.")
