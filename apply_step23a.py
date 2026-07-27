from __future__ import annotations

import re
from pathlib import Path

PAGE = Path("pages/6_Cover_Planner.py")
REPOSITORY = Path("roster_engine/cover_repository.py")
SCHEDULER = Path("roster_engine/cover_scheduler.py")
FC_HELPER = Path("roster_engine/fc_manual_continuity.py")


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"Could not find {label}. No files were changed.")
    return text.replace(old, new, 1)


page = PAGE.read_text()
repository = REPOSITORY.read_text()
scheduler = SCHEDULER.read_text()
fc_helper = FC_HELPER.read_text()

page = re.sub(
    r'\nCATEGORY_LABELS = \{.*?\}\n\nCATEGORY_ORDER = \[.*?\]\n',
    '\n',
    page,
    count=1,
    flags=re.DOTALL,
)

page = re.sub(
    r'\ncover_types_by_category: dict\[str, list\[dict\]\] = \{\}\n.*?\ncover_repository =',
    '\ncover_repository =',
    page,
    count=1,
    flags=re.DOTALL,
)

page = replace_once(page, '        available_categories = [\n            category\n            for category in CATEGORY_ORDER\n            if cover_types_by_category.get(\n                category\n            )\n        ]\n\n        c1, c2, c3 = st.columns(3)\n        with c1:\n            requesting_unit = st.text_input(\n                "Requesting unit",\n                placeholder="e.g. 1 COY",\n                key="cover_requesting_unit",\n            )\n        with c2:\n            category = st.selectbox(\n                "Cover category",\n                options=available_categories,\n                format_func=lambda value: (\n                    CATEGORY_LABELS.get(\n                        value,\n                        value,\n                    )\n                ),\n                key="cover_category",\n            )\n\n        category_types = (\n            cover_types_by_category[\n                category\n            ]\n        )\n        type_by_id = {\n            str(row["id"]): row\n            for row in category_types\n        }\n        with c3:\n            selected_type_id = (\n                st.selectbox(\n                    "Cover type",\n                    options=list(type_by_id),\n                    format_func=lambda item_id: (\n                        str(\n                            type_by_id[\n                                item_id\n                            ]["cover_type"]\n                        )\n                    ),\n                    key=f"cover_type_{category}",\n                )\n            )\n        selected_type = type_by_id[\n            selected_type_id\n        ]\n', '        c1, c2 = st.columns(2)\n\n        with c1:\n            requesting_unit = st.text_input(\n                "Requesting unit",\n                placeholder="e.g. 1 COY",\n                key="cover_requesting_unit",\n            )\n\n        type_by_id = {\n            str(row["id"]): row\n            for row in active_cover_types\n        }\n\n        with c2:\n            selected_type_id = st.selectbox(\n                "Cover type",\n                options=list(type_by_id),\n                format_func=lambda item_id: str(\n                    type_by_id[item_id]["cover_type"]\n                ),\n                key="cover_type",\n            )\n\n        selected_type = type_by_id[selected_type_id]\n', "flat Add Requirement selector")
page = page.replace('        if category == "FC":\n', '        if cover_type == "FC":\n', 1)

page = replace_once(
    page,
    '                    "cover_category": (\n                        category\n                    ),\n',
    '                    "cover_category": (\n                        cover_type\n                    ),\n',
    "requirement legacy category mirror",
)

page = re.sub(
    r'        for item in requirements:\n'
    r'            category = str\(\n'
    r'                item\["cover_category"\]\n'
    r'            \)\n\n',
    '        for item in requirements:\n',
    page,
    count=1,
)

page = re.sub(
    r'                    "Category": \(.*?\),\n'
    r'                    "Cover": \(\n'
    r'                        item\["cover_type"\]\n'
    r'                    \),',
    '                    "Cover type": (\n                        item["cover_type"]\n                    ),',
    page,
    count=1,
    flags=re.DOTALL,
)

page = replace_once(
    page,
    '        key = (\n            slot.requesting_unit,\n            slot.cover_category,\n            slot.cover_type,\n',
    '        key = (\n            slot.requesting_unit,\n            slot.cover_type,\n',
    "daily preview grouping",
)

page = re.sub(
    r'                "Category": CATEGORY_LABELS\.get\(.*?\),\n'
    r'                "Cover": slot\.cover_type,',
    '                "Cover type": slot.cover_type,',
    page,
    count=1,
    flags=re.DOTALL,
)

page = re.sub(
    r'                    "Category": \(.*?\),\n'
    r'                    "Cover": \(\n'
    r'                        row\["cover_type"\]\n'
    r'                    \),',
    '                    "Cover type": (\n                        row["cover_type"]\n                    ),',
    page,
    count=1,
    flags=re.DOTALL,
)

page = replace_once(page, '    a1, a2, a3, a4 = (\n        st.columns(4)\n    )\n\n    with a1:\n        new_category = st.selectbox(\n            "Category",\n            options=CATEGORY_ORDER,\n            format_func=lambda value: (\n                CATEGORY_LABELS[value]\n            ),\n            key=(\n                "new_cover_type_category"\n            ),\n        )\n    with a2:\n        new_name = st.text_input(\n            "Cover type",\n            key="new_cover_type_name",\n        )\n\n    with a3:\n        new_points = st.number_input(\n', '    a1, a2, a3 = (\n        st.columns(3)\n    )\n\n    with a1:\n        new_name = st.text_input(\n            "Cover type",\n            key="new_cover_type_name",\n        )\n\n    with a2:\n        new_points = st.number_input(\n', "Add Cover Type controls")
page = page.replace('    with a4:\n        new_session_label = (\n', '    with a3:\n        new_session_label = (\n', 1)
page = replace_once(page, '            payload = {\n                "category": new_category,\n                "cover_type": (\n                    new_name\n                    .strip()\n                    .upper()\n                ),\n', '            normalised_type = new_name.strip().upper()\n\n            payload = {\n                "category": normalised_type,\n                "cover_type": normalised_type,\n', "new type payload")
page = page.replace(
    '"The same category/type may already exist.\\n\\n"',
    '"The same cover type may already exist.\\n\\n"',
    1,
)

page = re.sub(
    r'                format_func=lambda item_id: \(\n'
    r'.*?f"\{type_lookup\[item_id\]\[\'cover_type\'\]\}"\n'
    r'                \),',
    '                format_func=lambda item_id: (\n'
    '                    f"{type_lookup[item_id][\'cover_type\']}"\n'
    '                ),',
    page,
    count=1,
    flags=re.DOTALL,
)

page = re.sub(
    r'        e1, e2, e3, e4 = \(\n'
    r'            st\.columns\(4\)\n'
    r'        \)\n\n'
    r'        with e1:\n'
    r'            current_category = str\(.*?\n'
    r'        with e2:\n'
    r'            edit_name = st\.text_input\(',
    '        e1, e2, e3 = (\n'
    '            st.columns(3)\n'
    '        )\n\n'
    '        with e1:\n'
    '            edit_name = st.text_input(',
    page,
    count=1,
    flags=re.DOTALL,
)

page = page.replace('        with e3:\n            edit_points = (\n', '        with e2:\n            edit_points = (\n', 1)
page = page.replace('        with e4:\n            edit_session_label = (\n', '        with e3:\n            edit_session_label = (\n', 1)
page = replace_once(page, '                payload = {\n                    "category": (\n                        edit_category\n                    ),\n                    "cover_type": (\n                        edit_name\n                        .strip()\n                        .upper()\n                    ),\n', '                normalised_type = edit_name.strip().upper()\n\n                payload = {\n                    "category": normalised_type,\n                    "cover_type": normalised_type,\n', "edit type payload")

repository = repository.replace(
    '                if requirement.cover_category == "FC":\n',
    '                if requirement.cover_type == "FC":\n',
    1,
)
repository = repository.replace(
    '            cover_category=str(row.get("cover_category") or "").upper(),\n',
    '            cover_category=str(\n'
    '                row.get("cover_category")\n'
    '                or row.get("cover_type")\n'
    '                or ""\n'
    '            ).upper(),\n',
    1,
)

scheduler = scheduler.replace(
    '_normalise(assignment.cover_category) == "FC"',
    '_normalise(assignment.cover_type) == "FC"',
)
scheduler = scheduler.replace(
    '_normalise(slot.cover_category) == "FC"',
    '_normalise(slot.cover_type) == "FC"',
)

fc_helper = replace_once(
    fc_helper,
    '    return (\n        normalise(requirement.cover_category) == "FC"\n        and normalise(requirement.cover_type) == "FC"\n    )\n',
    '    return normalise(requirement.cover_type) == "FC"\n',
    "FC manual continuity identity",
)

compile(page, str(PAGE), "exec")
compile(repository, str(REPOSITORY), "exec")
compile(scheduler, str(SCHEDULER), "exec")
compile(fc_helper, str(FC_HELPER), "exec")

for path, content in (
    (PAGE, page),
    (REPOSITORY, repository),
    (SCHEDULER, scheduler),
    (FC_HELPER, fc_helper),
):
    backup = path.with_suffix(".py.step23a_backup")
    if not backup.exists():
        backup.write_text(path.read_text())
    path.write_text(content)

print("Step 23A applied successfully.")
print("Cover type is now the app-level source of truth.")
