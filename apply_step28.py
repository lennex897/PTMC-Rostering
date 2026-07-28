from pathlib import Path

REQUIREMENTS = Path("roster_engine/requirements.py")

if not REQUIREMENTS.exists():
    raise SystemExit(
        "Run this from the PTMC-Rostering repository root."
    )

text = REQUIREMENTS.read_text()

old_block = '    if settings.include_pt_core_roles:\n        for role in PT_CORE_OVERNIGHT_ROLES:\n            requirements.append(\n                DutyRequirement(\n                    duty_date=duty_date,\n                    role=role,\n                    centre="PT",\n                    is_overnight=True,\n                    points=overnight_points,\n                )\n            )\n'
new_block = '    if settings.include_pt_core_roles:\n        # Mon / Thu / Sun use the CS/B staffing pattern.\n        #\n        # On those days PT CS2 and PT SB1 are intentionally omitted because\n        # PT CS/B replaces that part of the overnight team. The separate\n        # include_pt_csb block below then adds PT CS/B.\n        if weekday in pt_csb_days:\n            pt_core_roles = (\n                "PT DM",\n                "PT CS1",\n                "PT AE",\n            )\n        else:\n            pt_core_roles = (\n                "PT DM",\n                "PT CS1",\n                "PT CS2",\n                "PT SB1",\n                "PT AE",\n            )\n\n        for role in pt_core_roles:\n            requirements.append(\n                DutyRequirement(\n                    duty_date=duty_date,\n                    role=role,\n                    centre="PT",\n                    is_overnight=True,\n                    points=overnight_points,\n                )\n            )\n'

if old_block not in text:
    raise SystemExit(
        "Could not find the PT core overnight requirement block. "
        "No file was changed."
    )

text = text.replace(
    old_block,
    new_block,
    1,
)

compile(
    text,
    str(REQUIREMENTS),
    "exec",
)

backup = REQUIREMENTS.with_suffix(
    ".py.step28_backup"
)

if not backup.exists():
    backup.write_text(
        REQUIREMENTS.read_text()
    )

REQUIREMENTS.write_text(
    text
)

print("Step 28 applied successfully.")
print(
    "Mon/Thu/Sun now omit PT CS2 and PT SB1; "
    "PT CS/B is added by the existing CS/B rule."
)
