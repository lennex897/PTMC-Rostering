from __future__ import annotations

from pathlib import Path

EXPORTER_PATH = Path("roster_engine/exporter.py")

OLD_BLOCK = '# Fixed personnel blocks in the current Scheduling Roster workbook template.\n# These are intentionally bounded so synchronisation never inserts/deletes rows\n# and therefore cannot shift the summary/formula sections below them.\nPERSONNEL_BLOCKS = {\n    "PT": range(5, 42),   # rows 5-41 inclusive\n    "RH": range(52, 72),  # rows 52-71 inclusive\n}\n'
NEW_BLOCK = '# Base personnel blocks in the current Scheduling Roster workbook template.\n#\n# Export may expand these blocks dynamically when Supabase contains more\n# personnel than the original template. Rows are inserted immediately after\n# the relevant personnel block and template formatting/formulas are copied.\nBASE_PERSONNEL_BLOCKS = {\n    "PT": (5, 41),   # rows 5-41 inclusive\n    "RH": (52, 71),  # rows 52-71 inclusive\n}\n\nBASE_PERSONNEL_CAPACITY = {\n    centre: end_row - start_row + 1\n    for centre, (start_row, end_row)\n    in BASE_PERSONNEL_BLOCKS.items()\n}\n'
SYNC_DOC_OLD = "    Synchronise PT/RH personnel names from Supabase into the fixed Excel blocks.\n\n    Existing exact/unique legacy matches retain their rows so any legitimate\n    template availability entries remain attached to the same person.\n    Rows belonging to personnel no longer in the target month's Supabase pool\n    are reused for unmatched/new personnel, and their date-grid cells are\n    cleared before reuse.\n\n    No rows are inserted or deleted.\n"
SYNC_DOC_NEW = "    Synchronise PT/RH personnel names from Supabase into the Excel blocks.\n\n    Existing exact/unique legacy matches retain their rows so any legitimate\n    template availability entries remain attached to the same person.\n    Rows belonging to personnel no longer in the target month's Supabase pool\n    are reused for unmatched/new personnel, and their date-grid cells are\n    cleared before reuse.\n\n    If a centre exceeds the original template capacity, the personnel block is\n    expanded dynamically before synchronisation. This keeps Supabase as the\n    source of truth instead of imposing a fixed Excel manpower limit.\n"
HELPERS = '\n\ndef _copy_inserted_personnel_row(\n    worksheet: Worksheet,\n    *,\n    source_row: int,\n    target_row: int,\n) -> None:\n    """Copy formatting/formulas from an existing personnel row into a new row."""\n    from openpyxl.formula.translate import Translator\n\n    source_height = worksheet.row_dimensions[source_row].height\n    if source_height is not None:\n        worksheet.row_dimensions[target_row].height = source_height\n\n    for column_number in range(1, worksheet.max_column + 1):\n        source_cell = worksheet.cell(\n            row=source_row,\n            column=column_number,\n        )\n        target_cell = worksheet.cell(\n            row=target_row,\n            column=column_number,\n        )\n\n        if source_cell.has_style:\n            target_cell._style = copy(source_cell._style)\n\n        if source_cell.number_format:\n            target_cell.number_format = source_cell.number_format\n\n        if source_cell.alignment:\n            target_cell.alignment = copy(source_cell.alignment)\n\n        if source_cell.protection:\n            target_cell.protection = copy(source_cell.protection)\n\n        if source_cell.font:\n            target_cell.font = copy(source_cell.font)\n\n        if source_cell.fill:\n            target_cell.fill = copy(source_cell.fill)\n\n        if source_cell.border:\n            target_cell.border = copy(source_cell.border)\n\n        if (\n            isinstance(source_cell.value, str)\n            and source_cell.value.startswith("=")\n        ):\n            try:\n                target_cell.value = Translator(\n                    source_cell.value,\n                    origin=source_cell.coordinate,\n                ).translate_formula(\n                    target_cell.coordinate\n                )\n            except Exception:\n                target_cell.value = source_cell.value\n        else:\n            target_cell.value = None\n\n\ndef _shift_formula_row_references(\n    formula: str,\n    *,\n    pt_extra: int,\n    rh_extra: int,\n) -> str:\n    """Translate template row references before dynamic row insertion."""\n    import re\n\n    if not formula.startswith("="):\n        return formula\n\n    def shifted_row(row_number: int) -> int:\n        if row_number < 42:\n            return row_number\n        if row_number < 72:\n            return row_number + pt_extra\n        return row_number + pt_extra + rh_extra\n\n    reference_pattern = re.compile(\n        r"(?P<col1>\\$?[A-Z]{1,3}\\$?)"\n        r"(?P<row1>\\d+)"\n        r"(?:"\n        r":(?P<col2>\\$?[A-Z]{1,3}\\$?)"\n        r"(?P<row2>\\d+)"\n        r")?"\n    )\n\n    def replace_reference(match):\n        col1 = match.group("col1")\n        row1 = int(match.group("row1"))\n        col2 = match.group("col2")\n        row2_text = match.group("row2")\n\n        if col2 is None or row2_text is None:\n            return f"{col1}{shifted_row(row1)}"\n\n        row2 = int(row2_text)\n\n        if row2 == 41 and row1 <= 41:\n            new_row1 = shifted_row(row1)\n            new_row2 = 41 + pt_extra\n        elif row2 == 71 and row1 >= 52:\n            new_row1 = row1 + pt_extra\n            new_row2 = 71 + pt_extra + rh_extra\n        else:\n            new_row1 = shifted_row(row1)\n            new_row2 = shifted_row(row2)\n\n        return f"{col1}{new_row1}:{col2}{new_row2}"\n\n    return reference_pattern.sub(\n        replace_reference,\n        formula,\n    )\n\n\ndef _prepare_dynamic_personnel_blocks(\n    worksheet: Worksheet,\n    *,\n    pt_count: int,\n    rh_count: int,\n) -> dict[str, range]:\n    """Expand PT/RH personnel blocks if Supabase manpower exceeds the template."""\n    pt_start, pt_base_end = BASE_PERSONNEL_BLOCKS["PT"]\n    rh_base_start, rh_base_end = BASE_PERSONNEL_BLOCKS["RH"]\n\n    pt_extra = max(\n        0,\n        pt_count - BASE_PERSONNEL_CAPACITY["PT"],\n    )\n    rh_extra = max(\n        0,\n        rh_count - BASE_PERSONNEL_CAPACITY["RH"],\n    )\n\n    if pt_extra == 0 and rh_extra == 0:\n        return {\n            "PT": range(pt_start, pt_base_end + 1),\n            "RH": range(rh_base_start, rh_base_end + 1),\n        }\n\n    # openpyxl moves cells on insert_rows(), but does not translate formulas\n    # elsewhere in the worksheet. Rewrite them before inserting rows.\n    for row in worksheet.iter_rows():\n        for cell in row:\n            if (\n                isinstance(cell.value, str)\n                and cell.value.startswith("=")\n            ):\n                cell.value = _shift_formula_row_references(\n                    cell.value,\n                    pt_extra=pt_extra,\n                    rh_extra=rh_extra,\n                )\n\n    if pt_extra:\n        pt_insert_at = pt_base_end + 1\n        worksheet.insert_rows(\n            pt_insert_at,\n            amount=pt_extra,\n        )\n\n        for offset in range(pt_extra):\n            _copy_inserted_personnel_row(\n                worksheet,\n                source_row=pt_base_end,\n                target_row=pt_insert_at + offset,\n            )\n\n    rh_start = rh_base_start + pt_extra\n    rh_end_before_extra = rh_base_end + pt_extra\n\n    if rh_extra:\n        rh_insert_at = rh_end_before_extra + 1\n        worksheet.insert_rows(\n            rh_insert_at,\n            amount=rh_extra,\n        )\n\n        for offset in range(rh_extra):\n            _copy_inserted_personnel_row(\n                worksheet,\n                source_row=rh_end_before_extra,\n                target_row=rh_insert_at + offset,\n            )\n\n    return {\n        "PT": range(\n            pt_start,\n            pt_base_end + pt_extra + 1,\n        ),\n        "RH": range(\n            rh_start,\n            rh_base_end + pt_extra + rh_extra + 1,\n        ),\n    }\n\n'
OLD_LOOP = '    final_rows: dict[str, int] = {}\n\n    for centre, row_range in PERSONNEL_BLOCKS.items():\n        people = by_centre[centre]\n        available_rows = list(row_range)\n        if len(people) > len(available_rows):\n            raise ValueError(\n                f"{centre} personnel count ({len(people)}) exceeds "\n                f"the Excel template capacity ({len(available_rows)})."\n            )\n        existing_by_row = {\n'
NEW_LOOP = '    final_rows: dict[str, int] = {}\n\n    personnel_blocks = _prepare_dynamic_personnel_blocks(\n        worksheet,\n        pt_count=len(by_centre["PT"]),\n        rh_count=len(by_centre["RH"]),\n    )\n\n    for centre, row_range in personnel_blocks.items():\n        people = by_centre[centre]\n        available_rows = list(row_range)\n\n        existing_by_row = {\n'


def main() -> None:
    if not EXPORTER_PATH.exists():
        raise SystemExit(
            f"Could not find {EXPORTER_PATH}. "
            "Run this script from the PTMC-Rostering repository root."
        )

    text = EXPORTER_PATH.read_text()

    if (
        "BASE_PERSONNEL_BLOCKS" in text
        and "_prepare_dynamic_personnel_blocks" in text
    ):
        print("Dynamic Excel capacity patch is already applied.")
        return

    missing = []
    if OLD_BLOCK not in text:
        missing.append("PERSONNEL_BLOCKS block")
    if SYNC_DOC_OLD not in text:
        missing.append("sync_personnel_rows docstring")
    if OLD_LOOP not in text:
        missing.append("fixed-capacity sync loop")

    if missing:
        raise SystemExit(
            "Exporter layout differs from the expected version. "
            "No file was changed. Missing markers: "
            + ", ".join(missing)
        )

    text = text.replace(OLD_BLOCK, NEW_BLOCK, 1)
    text = text.replace(SYNC_DOC_OLD, SYNC_DOC_NEW, 1)

    marker = "def sync_personnel_rows(\n"
    position = text.find(marker)
    if position < 0:
        raise SystemExit(
            "Could not locate sync_personnel_rows(). No file was changed."
        )

    text = text[:position] + HELPERS + text[position:]
    text = text.replace(OLD_LOOP, NEW_LOOP, 1)

    compile(text, str(EXPORTER_PATH), "exec")

    backup_path = EXPORTER_PATH.with_suffix(
        ".py.step18_3_backup"
    )
    if not backup_path.exists():
        backup_path.write_text(
            EXPORTER_PATH.read_text()
        )

    EXPORTER_PATH.write_text(text)

    print("Patched roster_engine/exporter.py successfully.")
    print(f"Backup saved to {backup_path}")
    print(
        "The exporter will now expand PT/RH personnel blocks dynamically."
    )


if __name__ == "__main__":
    main()
