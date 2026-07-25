from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from supabase import Client

from roster_engine.roster_rules import (
    RosterRule,
    RosterRules,
)


RULES_TABLE = "roster_rules"


@dataclass(frozen=True)
class EditableRosterRule:
    key: str
    group: str
    value_type: str
    value: int | float | bool | str | tuple[str, ...]
    description: str | None
    is_active: bool
    display_order: int


class RosterRulesRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_rules(
        self,
        *,
        include_inactive: bool = False,
    ) -> list[RosterRule]:
        query = (
            self.supabase
            .table(RULES_TABLE)
            .select(
                "rule_key,rule_group,value_type,"
                "integer_value,float_value,boolean_value,"
                "text_value,string_list_value,"
                "description,is_active,display_order"
            )
            .order("rule_group")
            .order("display_order")
            .order("rule_key")
        )

        if not include_inactive:
            query = query.eq("is_active", True)

        response = query.execute()

        if response is None:
            raise RuntimeError(
                "Supabase returned no response while loading roster rules."
            )

        return [
            self._row_to_rule(row)
            for row in (response.data or [])
        ]

    def list_editable_rules(
        self,
    ) -> list[EditableRosterRule]:
        return [
            EditableRosterRule(
                key=rule.key,
                group=rule.group,
                value_type=rule.value_type,
                value=rule.value,
                description=rule.description,
                is_active=rule.is_active,
                display_order=rule.display_order,
            )
            for rule in self.list_rules(
                include_inactive=True
            )
        ]

    def load_rules(
        self,
    ) -> RosterRules:
        """
        Load active rules and overlay them on safe defaults.

        Important:
        - Missing rule row -> use Python safe default.
        - Inactive rule row -> use a behavior-specific disabled value.
          This prevents disabling a rule from silently falling back to an
          enabled default.
        """
        rows = self.list_rules(
            include_inactive=True
        )

        defaults = RosterRules().as_dict()
        values = dict(defaults)

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

        for rule in rows:
            if rule.key not in values:
                continue

            if rule.is_active:
                values[rule.key] = rule.value
            elif rule.key in disabled_values:
                values[rule.key] = disabled_values[
                    rule.key
                ]

        return RosterRules(
            **values
        )

    def update_rule(
        self,
        *,
        rule_key: str,
        value: int | float | bool | str | tuple[str, ...] | list[str],
        is_active: bool,
    ) -> None:
        current = self.get_rule(
            rule_key
        )

        payload = {
            "integer_value": None,
            "float_value": None,
            "boolean_value": None,
            "text_value": None,
            "string_list_value": None,
            "is_active": bool(is_active),
        }

        if current.value_type == "integer":
            payload["integer_value"] = int(
                value
            )
        elif current.value_type == "float":
            payload["float_value"] = float(
                value
            )
        elif current.value_type == "boolean":
            payload["boolean_value"] = bool(
                value
            )
        elif current.value_type == "text":
            payload["text_value"] = str(
                value
            )
        elif current.value_type == "string_list":
            payload["string_list_value"] = [
                str(item).strip().upper()
                for item in value
                if str(item).strip()
            ]
        else:
            raise ValueError(
                f"Unsupported roster rule type: "
                f"{current.value_type!r}"
            )

        (
            self.supabase
            .table(RULES_TABLE)
            .update(payload)
            .eq("rule_key", rule_key)
            .execute()
        )

    def get_rule(
        self,
        rule_key: str,
    ) -> RosterRule:
        response = (
            self.supabase
            .table(RULES_TABLE)
            .select(
                "rule_key,rule_group,value_type,"
                "integer_value,float_value,boolean_value,"
                "text_value,string_list_value,"
                "description,is_active,display_order"
            )
            .eq("rule_key", rule_key)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            raise ValueError(
                f"Roster rule {rule_key!r} was not found."
            )

        return self._row_to_rule(
            rows[0]
        )

    @staticmethod
    def _row_to_rule(
        row: dict,
    ) -> RosterRule:
        value_type = str(
            row.get("value_type")
            or ""
        ).strip().lower()

        value: Any

        if value_type == "integer":
            value = int(
                row["integer_value"]
            )
        elif value_type == "float":
            value = float(
                row["float_value"]
            )
        elif value_type == "boolean":
            value = bool(
                row["boolean_value"]
            )
        elif value_type == "text":
            value = str(
                row["text_value"]
            )
        elif value_type == "string_list":
            raw = (
                row.get("string_list_value")
                or []
            )

            if not isinstance(raw, list):
                raise ValueError(
                    "string_list_value must be a JSON array."
                )

            value = tuple(
                str(item).strip().upper()
                for item in raw
                if str(item).strip()
            )
        else:
            raise ValueError(
                f"Unsupported roster rule value type: "
                f"{value_type!r}"
            )

        return RosterRule(
            key=str(
                row["rule_key"]
            ).strip(),
            group=str(
                row["rule_group"]
            ).strip(),
            value_type=value_type,
            value=value,
            description=(
                str(row["description"]).strip()
                if row.get("description")
                else None
            ),
            is_active=bool(
                row.get("is_active", True)
            ),
            display_order=int(
                row.get("display_order", 0)
                or 0
            ),
        )
