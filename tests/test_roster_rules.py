from roster_engine.roster_rules import (
    RosterRules,
)
from roster_engine.roster_rules_repository import (
    RosterRulesRepository,
)


def test_default_roster_rules_match_current_policy_baseline() -> None:
    rules = RosterRules()

    assert rules.maximum_weekly_overnights == 3
    assert rules.overnight_min_break_days == 1
    assert rules.fc_reserve_count == 2
    assert rules.fc_continuity_required is True
    assert rules.fc_swap_points == 0.5

    assert rules.pt_csb_days == (
        "MON",
        "THU",
        "SUN",
    )

    assert rules.rh_sb2_deployment_days == (
        "MON",
        "THU",
        "SUN",
    )

    assert rules.daily_pt_reserve_count == 1
    assert rules.daily_rh_reserve_count == 1

    assert "TAN JUN HONG JUDAH" in rules.manual_only_personnel
    assert "LAM KAI JUE" in rules.manual_only_personnel


def test_row_to_rule_parses_string_list() -> None:
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
        "description": "test",
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


def test_row_to_rule_parses_float() -> None:
    row = {
        "rule_key": "fc_swap_points",
        "rule_group": "cover",
        "value_type": "float",
        "integer_value": None,
        "float_value": 0.5,
        "boolean_value": None,
        "text_value": None,
        "string_list_value": None,
        "description": None,
        "is_active": True,
        "display_order": 1,
    }

    rule = RosterRulesRepository._row_to_rule(
        row
    )

    assert rule.value == 0.5
