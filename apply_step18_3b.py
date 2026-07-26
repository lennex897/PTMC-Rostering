from __future__ import annotations

import re
from pathlib import Path

EXPORTER_PATH = Path("roster_engine/exporter.py")
NEW_CONSTANTS = 'BASE_PERSONNEL_BLOCKS = {\n    "PT": (5, 41),\n    "RH": (52, 71),\n}\n\nBASE_PERSONNEL_CAPACITY = {\n    centre: end_row - start_row + 1\n    for centre, (start_row, end_row)\n    in BASE_PERSONNEL_BLOCKS.items()\n}\n'
HELPERS = '\ndef _copy_inserted_personnel_row(\n    worksheet: Worksheet,\n    *,\n    source_row: int,\n    target_row: int,\n) -> None:\n    from openpyxl.formula.translate import Translator\n\n    source_height = worksheet.row_dimensions[source_row].height\n    if source_height is not None:\n        worksheet.row_dimensions[target_row].height = source_height\n\n    for column_number in range(1, worksheet.max_column + 1):\n        source_cell = worksheet.cell(row=source_row, column=column_number)\n        target_cell = worksheet.cell(row=target_row, column=column_number)\n\n        if source_cell.has_style:\n            target_cell._style = copy(source_cell._style)\n\n        target_cell.number_format = source_cell.number_format\n        target_cell.alignment = copy(source_cell.alignment)\n        target_cell.protection = copy(source_cell.protection)\n        target_cell.font = copy(source_cell.font)\n        target_cell.fill = copy(source_cell.fill)\n        target_cell.border = copy(source_cell.border)\n\n        if (\n            isinstance(source_cell.value, str)\n            and source_cell.value.startswith("=")\n        ):\n            try:\n                target_cell.value = Translator(\n                    source_cell.value,\n                    origin=source_cell.coordinate,\n                ).translate_formula(target_cell.coordinate)\n            except Exception:\n                target_cell.value = source_cell.value\n        else:\n            target_cell.value = None\n\n\ndef _shift_formula_row_references(\n    formula: str,\n    *,\n    pt_extra: int,\n    rh_extra: int,\n) -> str:\n    import re\n\n    if not formula.startswith("="):\n        return formula\n\n    reference_pattern = re.compile(\n        r"(?P<col1>\\$?[A-Z]{1,3}\\$?)"\n        r"(?P<row1>\\d+)"\n        r"(?:"\n        r":(?P<col2>\\$?[A-Z]{1,3}\\$?)"\n        r"(?P<row2>\\d+)"\n        r")?"\n    )\n\n    def shifted_row(row_number: int) -> int:\n        if row_number < 42:\n            return row_number\n        if row_number < 72:\n            return row_number + pt_extra\n        return row_number + pt_extra + rh_extra\n\n    def replacement(match) -> str:\n        col1 = match.group("col1")\n        row1 = int(match.group("row1"))\n        col2 = match.group("col2")\n        row2_text = match.group("row2")\n\n        if col2 is None or row2_text is None:\n            return f"{col1}{shifted_row(row1)}"\n\n        row2 = int(row2_text)\n\n        if row2 == 41 and row1 <= 41:\n            new_row1 = shifted_row(row1)\n            new_row2 = 41 + pt_extra\n        elif row2 == 71 and row1 >= 52:\n            new_row1 = row1 + pt_extra\n            new_row2 = 71 + pt_extra + rh_extra\n        else:\n            new_row1 = shifted_row(row1)\n            new_row2 = shifted_row(row2)\n\n        return f"{col1}{new_row1}:{col2}{new_row2}"\n\n    return reference_pattern.sub(replacement, formula)\n\n\ndef _prepare_dynamic_personnel_blocks(\n    worksheet: Worksheet,\n    *,\n    pt_count: int,\n    rh_count: int,\n) -> dict[str, range]:\n    pt_start, pt_base_end = BASE_PERSONNEL_BLOCKS["PT"]\n    rh_base_start, rh_base_end = BASE_PERSONNEL_BLOCKS["RH"]\n\n    pt_extra = max(\n        0,\n        pt_count - BASE_PERSONNEL_CAPACITY["PT"],\n    )\n    rh_extra = max(\n        0,\n        rh_count - BASE_PERSONNEL_CAPACITY["RH"],\n    )\n\n    if pt_extra == 0 and rh_extra == 0:\n        return {\n            "PT": range(pt_start, pt_base_end + 1),\n            "RH": range(rh_base_start, rh_base_end + 1),\n        }\n\n    for row in worksheet.iter_rows():\n        for cell in row:\n            if (\n                isinstance(cell.value, str)\n                and cell.value.startswith("=")\n            ):\n                cell.value = _shift_formula_row_references(\n                    cell.value,\n                    pt_extra=pt_extra,\n                    rh_extra=rh_extra,\n                )\n\n    if pt_extra:\n        insert_at = pt_base_end + 1\n        worksheet.insert_rows(insert_at, amount=pt_extra)\n\n        for offset in range(pt_extra):\n            _copy_inserted_personnel_row(\n                worksheet,\n                source_row=pt_base_end,\n                target_row=insert_at + offset,\n            )\n\n    rh_start = rh_base_start + pt_extra\n    rh_end_before_extra = rh_base_end + pt_extra\n\n    if rh_extra:\n        insert_at = rh_end_before_extra + 1\n        worksheet.insert_rows(insert_at, amount=rh_extra)\n\n        for offset in range(rh_extra):\n            _copy_inserted_personnel_row(\n                worksheet,\n                source_row=rh_end_before_extra,\n                target_row=insert_at + offset,\n            )\n\n    return {\n        "PT": range(\n            pt_start,\n            pt_base_end + pt_extra + 1,\n        ),\n        "RH": range(\n            rh_start,\n            rh_base_end + pt_extra + rh_extra + 1,\n        ),\n    }\n\n\n'


def main() -> None:
    if not EXPORTER_PATH.exists():
        raise SystemExit(
            f"Could not find {EXPORTER_PATH}. "
            "Run this from the PTMC-Rostering repository root."
        )

    text = EXPORTER_PATH.read_text()

    if (
        "BASE_PERSONNEL_BLOCKS" in text
        and "_prepare_dynamic_personnel_blocks" in text
    ):
        print("Dynamic capacity patch is already applied.")
        return

    original = text

    block_pattern = re.compile(
        r'PERSONNEL_BLOCKS\s*=\s*\{\s*'
        r'"PT"\s*:\s*range\(5\s*,\s*42\)\s*,\s*'
        r'"RH"\s*:\s*range\(52\s*,\s*72\)\s*,?\s*'
        r'\}',
        re.MULTILINE,
    )

    text, count = block_pattern.subn(
        NEW_CONSTANTS.rstrip(),
        text,
        count=1,
    )

    if count != 1:
        raise SystemExit(
            "Could not find PERSONNEL_BLOCKS. No file was changed."
        )

    sync_marker = re.search(
        r'^def\s+sync_personnel_rows\s*\(',
        text,
        flags=re.MULTILINE,
    )

    if sync_marker is None:
        raise SystemExit(
            "Could not find sync_personnel_rows(). No file was changed."
        )

    text = (
        text[:sync_marker.start()]
        + HELPERS
        + text[sync_marker.start():]
    )

    loop_pattern = re.compile(
        r'(?P<indent>[ \t]*)for\s+centre\s*,\s*row_range\s+in\s+'
        r'PERSONNEL_BLOCKS\.items\(\)\s*:\s*\n'
        r'(?P=indent)[ \t]+people\s*=\s*by_centre\[centre\]\s*\n'
        r'(?P=indent)[ \t]+available_rows\s*=\s*list\(row_range\)\s*\n',
        flags=re.MULTILINE,
    )

    replacement = (
        '    personnel_blocks = _prepare_dynamic_personnel_blocks(\n'
        '        worksheet,\n'
        '        pt_count=len(by_centre["PT"]),\n'
        '        rh_count=len(by_centre["RH"]),\n'
        '    )\n'
        '\n'
        '    for centre, row_range in personnel_blocks.items():\n'
        '        people = by_centre[centre]\n'
        '        available_rows = list(row_range)\n'
    )

    text, count = loop_pattern.subn(
        replacement,
        text,
        count=1,
    )

    if count != 1:
        raise SystemExit(
            "Could not find fixed personnel-block loop. No file was changed."
        )

    capacity_pattern = re.compile(
        r'\n[ \t]+if\s+len\(people\)\s*>\s*len\(available_rows\)\s*:\s*\n'
        r'(?:[ \t]+.*\n){1,8}?'
        r'[ \t]+\)\s*\n',
        flags=re.MULTILINE,
    )

    text, count = capacity_pattern.subn(
        "\n",
        text,
        count=1,
    )

    if count != 1:
        raise SystemExit(
            "Could not remove old capacity guard. No file was changed."
        )

    compile(text, str(EXPORTER_PATH), "exec")

    backup = EXPORTER_PATH.with_suffix(
        ".py.step18_3b_backup"
    )

    if not backup.exists():
        backup.write_text(original)

    EXPORTER_PATH.write_text(text)

    print("Patched roster_engine/exporter.py successfully.")
    print(f"Backup: {backup}")
    print("PT/RH personnel blocks now expand dynamically.")


if __name__ == "__main__":
    main()
