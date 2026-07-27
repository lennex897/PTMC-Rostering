from pathlib import Path

PAGE = Path("pages/6_Cover_Planner.py")

if not PAGE.exists():
    raise SystemExit(
        "Run this from the PTMC-Rostering repository root."
    )

text = PAGE.read_text()

helper_marker = "def month_start(value: date) -> date:\n"

helper_code = '''def legacy_category_for_type(
    cover_type: str,
) -> str:
    """
    Compatibility only for the old Supabase CHECK constraint.

    Cover category is no longer part of app behaviour. The legacy database
    column must still contain one of its historical allowed values until the
    schema is cleaned up in Step 23B.
    """
    value = " ".join(
        cover_type.strip().upper().split()
    )

    if value in {
        "FC",
        "GP",
        "GX",
    }:
        return value

    return "NON_FC"


'''

if "def legacy_category_for_type(" not in text:
    if helper_marker not in text:
        raise SystemExit(
            "Could not find month_start() insertion point."
        )
    text = text.replace(
        helper_marker,
        helper_code + helper_marker,
        1,
    )

old_requirement = '''                    "cover_category": (
                        cover_type
                    ),
'''

new_requirement = '''                    "cover_category": (
                        legacy_category_for_type(
                            cover_type
                        )
                    ),
'''

if old_requirement in text:
    text = text.replace(
        old_requirement,
        new_requirement,
        1,
    )
elif "legacy_category_for_type(" not in text:
    raise SystemExit(
        "Could not find cover requirement legacy category payload."
    )

old_type_payload = '''                "category": normalised_type,
                "cover_type": normalised_type,
'''

new_type_payload = '''                "category": legacy_category_for_type(
                    normalised_type
                ),
                "cover_type": normalised_type,
'''

count = text.count(old_type_payload)
if count < 2:
    raise SystemExit(
        f"Expected 2 cover type payloads, found {count}."
    )

text = text.replace(
    old_type_payload,
    new_type_payload,
    2,
)

compile(
    text,
    str(PAGE),
    "exec",
)

backup = PAGE.with_suffix(
    ".py.step23a2_backup"
)

if not backup.exists():
    backup.write_text(
        PAGE.read_text()
    )

PAGE.write_text(
    text
)

print("Step 23A.2 applied successfully.")
print(
    "Legacy category values now satisfy the existing Supabase CHECK constraint."
)
