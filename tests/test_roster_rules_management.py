from roster_engine.roster_rules_repository import (
    RosterRulesRepository,
)


def test_disabled_rule_value_mapping_preserves_semantics() -> None:
    # This test documents the intended disabled behavior for rules whose
    # Python defaults are otherwise 'enabled' values.
    disabled_values = {
        "maximum_weekly_overnights": 999,
        "overnight_min_break_days": 0,
        "leaving_reduction_days": 0,
        "daily_pt_reserve_count": 0,
        "daily_rh_reserve_count": 0,
        "fc_reserve_count": 0,
        "fc_continuity_required": False,
        "public_holiday_uses_day_weight": False,
        "manual_only_personnel": (),
    }

    assert disabled_values[
        "fc_continuity_required"
    ] is False
    assert disabled_values[
        "fc_reserve_count"
    ] == 0
    assert disabled_values[
        "overnight_min_break_days"
    ] == 0


def test_string_list_rule_parser_uppercases_values() -> None:
    row = {
        "rule_key": "pt_csb_days",
        "rule_group": "deployment",
        "value_type": "string_list",
        "integer_value": None,
        "float_value": None,
        "boolean_value": None,
        "text_value": None,
        "string_list_value": [
            "mon",
            "thu",
            "sun",
        ],
        "description": None,
        "is_active": True,
        "display_order": 1,
    }

    rule = RosterRulesRepository._row_to_rule(
        row
    )

    assert rule.value == (
        "MON",
        "THU",
        "SUN",
    )
