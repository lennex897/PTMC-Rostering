from pathlib import Path
import ast


def _load_helper():
    source = Path(
        "pages/6_Cover_Planner.py"
    ).read_text()

    tree = ast.parse(source)

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "legacy_category_for_type"
        ):
            module = ast.Module(
                body=[node],
                type_ignores=[],
            )
            namespace = {}
            exec(
                compile(
                    module,
                    "<helper>",
                    "exec",
                ),
                namespace,
            )
            return namespace[
                "legacy_category_for_type"
            ]

    raise AssertionError(
        "legacy_category_for_type() not found"
    )


def test_fc_maps_to_legacy_fc_category():
    helper = _load_helper()
    assert helper("FC") == "FC"


def test_gp_and_gx_keep_legacy_categories():
    helper = _load_helper()
    assert helper("GP") == "GP"
    assert helper("GX") == "GX"


def test_other_cover_types_use_non_fc_legacy_category():
    helper = _load_helper()
    assert helper("MEDICAL COVER") == "NON_FC"
    assert helper("OTHER") == "NON_FC"
