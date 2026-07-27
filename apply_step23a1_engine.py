from pathlib import Path

REPOSITORY = Path("roster_engine/cover_repository.py")
FC_HELPER = Path("roster_engine/fc_manual_continuity.py")

repository = REPOSITORY.read_text()
fc_helper = FC_HELPER.read_text()

old_repository_fc = '                if requirement.cover_category == "FC":\n'
new_repository_fc = '                if requirement.cover_type == "FC":\n'

if old_repository_fc not in repository:
    raise SystemExit(
        "Could not find FC reserve category check in cover_repository.py."
    )

repository = repository.replace(
    old_repository_fc,
    new_repository_fc,
    1,
)

old_requirement_parser = (
    '            cover_category=str(row.get("cover_category") or "").upper(),\n'
)
new_requirement_parser = (
    '            cover_category=str(\n'
    '                row.get("cover_category")\n'
    '                or row.get("cover_type")\n'
    '                or ""\n'
    '            ).upper(),\n'
)

if old_requirement_parser in repository:
    repository = repository.replace(
        old_requirement_parser,
        new_requirement_parser,
        1,
    )

old_fc_helper = """    return (
        normalise(requirement.cover_category) == "FC"
        and normalise(requirement.cover_type) == "FC"
    )
"""
new_fc_helper = """    return normalise(requirement.cover_type) == "FC"
"""

if old_fc_helper not in fc_helper:
    raise SystemExit(
        "Could not find is_active_fc_requirement() implementation."
    )

fc_helper = fc_helper.replace(
    old_fc_helper,
    new_fc_helper,
    1,
)

compile(repository, str(REPOSITORY), "exec")
compile(fc_helper, str(FC_HELPER), "exec")

for path, content in (
    (REPOSITORY, repository),
    (FC_HELPER, fc_helper),
):
    backup = path.with_suffix(".py.step23a1_backup")
    if not backup.exists():
        backup.write_text(path.read_text())
    path.write_text(content)

print("Step 23A.1 engine patch applied successfully.")
