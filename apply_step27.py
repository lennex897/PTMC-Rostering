from pathlib import Path

REPOSITORY = Path("roster_engine/cover_repository.py")
SCHEDULER = Path("roster_engine/cover_scheduler.py")
FC_HELPER = Path("roster_engine/fc_manual_continuity.py")
PLANNER = Path("pages/6_Cover_Planner.py")

for path in (REPOSITORY, SCHEDULER, FC_HELPER, PLANNER):
    if not path.exists():
        raise SystemExit(
            f"Missing {path}. Run this from the repository root."
        )

repository = REPOSITORY.read_text()
scheduler = SCHEDULER.read_text()
fc_helper = FC_HELPER.read_text()
planner = PLANNER.read_text()

classification_marker = 'COVER_REQUIREMENTS_TABLE = "roster_cover_requirements"\n\n\n'
classification_helper = '''COVER_REQUIREMENTS_TABLE = "roster_cover_requirements"


def classify_cover_category(
    cover_type: str | None,
) -> str:
    value = " ".join(
        str(cover_type or "")
        .strip()
        .upper()
        .split()
    )

    if value in {"FC", "GP", "GX"}:
        return value

    return "NON_FC"


'''

if "def classify_cover_category(" not in repository:
    if classification_marker not in repository:
        raise SystemExit("Could not find repository constants.")
    repository = repository.replace(
        classification_marker,
        classification_helper,
        1,
    )

repository = repository.replace(
    '            category=str(row.get("category") or "").upper(),\n'
    '            cover_type=str(row.get("cover_type") or "").upper(),\n',
    '            category=classify_cover_category(\n'
    '                str(row.get("cover_type") or "")\n'
    '            ),\n'
    '            cover_type=str(row.get("cover_type") or "").upper(),\n',
    1,
)

if '            cover_category=str(row.get("cover_category") or "").upper(),\n' in repository:
    repository = repository.replace(
        '            cover_category=str(row.get("cover_category") or "").upper(),\n',
        '            cover_category=classify_cover_category(\n'
        '                str(row.get("cover_type") or "")\n'
        '            ),\n',
        1,
    )
else:
    repository = repository.replace(
        '            cover_category=str(\n'
        '                row.get("cover_category")\n'
        '                or row.get("cover_type")\n'
        '                or ""\n'
        '            ).upper(),\n',
        '            cover_category=classify_cover_category(\n'
        '                str(row.get("cover_type") or "")\n'
        '            ),\n',
        1,
    )

repository = repository.replace(
    '                if requirement.cover_type == "FC":\n',
    '                if requirement.cover_category == "FC":\n',
)

scheduler = scheduler.replace(
    '_normalise(assignment.cover_type) == "FC"',
    '_normalise(assignment.cover_category) == "FC"',
)
scheduler = scheduler.replace(
    '_normalise(slot.cover_type) == "FC"',
    '_normalise(slot.cover_category) == "FC"',
)

# Preserve FC SWAP as a cover type check.
scheduler = scheduler.replace(
    '_normalise(assignment.cover_category) == "FC SWAP"',
    '_normalise(assignment.cover_type) == "FC SWAP"',
)

# Remove redundant exact-FC-type guard if present in the active FC router.
scheduler = scheduler.replace(
    '            and _normalise(slot.cover_category) == "FC"\n'
    '            and not slot.is_reserve\n'
    '            and _normalise(slot.cover_category) == "FC"\n',
    '            and _normalise(slot.cover_category) == "FC"\n'
    '            and not slot.is_reserve\n',
)

fc_helper = fc_helper.replace(
    '    return normalise(requirement.cover_type) == "FC"\n',
    '    return normalise(requirement.cover_category) == "FC"\n',
)

old_import = 'from roster_engine.cover_repository import CoverRepository\n'
new_import = '''from roster_engine.cover_repository import (
    CoverRepository,
    classify_cover_category,
)
'''

if old_import in planner:
    planner = planner.replace(old_import, new_import, 1)

# Keep existing compatibility helper if present, but delegate to canonical classifier.
start = planner.find("def legacy_category_for_type(")
if start >= 0:
    end = planner.find("\ndef ", start + 5)
    if end > start:
        planner = (
            planner[:start]
            + '''def legacy_category_for_type(
    cover_type: str,
) -> str:
    return classify_cover_category(
        cover_type
    )

'''
            + planner[end + 1:]
        )

planner = planner.replace(
    'legacy_category_for_type(\n                            cover_type\n                        )',
    'classify_cover_category(\n                            cover_type\n                        )',
)
planner = planner.replace(
    'legacy_category_for_type(\n                    normalised_type\n                )',
    'classify_cover_category(\n                    normalised_type\n                )',
)
planner = planner.replace(
    'legacy_category_for_type(\n                            edit_cover_type\n                        )',
    'classify_cover_category(\n                            edit_cover_type\n                        )',
)

compile(repository, str(REPOSITORY), "exec")
compile(scheduler, str(SCHEDULER), "exec")
compile(fc_helper, str(FC_HELPER), "exec")
compile(planner, str(PLANNER), "exec")

for path, content in (
    (REPOSITORY, repository),
    (SCHEDULER, scheduler),
    (FC_HELPER, fc_helper),
    (PLANNER, planner),
):
    backup = path.with_suffix(".py.step27_backup")
    if not backup.exists():
        backup.write_text(path.read_text())
    path.write_text(content)

print("Step 27 applied successfully.")
print("Cover Category is now automatic backend metadata.")
print("FC continuity routes through cover_category == 'FC' again.")
