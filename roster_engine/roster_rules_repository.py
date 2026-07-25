from __future__ import annotations

from typing import Any

from supabase import Client

from roster_engine.roster_rules import (
    RosterRule,
    RosterRules,
)


RULES_TABLE = "roster_rules"


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

    def load_rules(
        self,
    ) -> RosterRules:
        """
        Load active rules and overlay them on safe defaults.

        Unknown keys are ignored here so new rules may be introduced in
        Supabase before the Python model is upgraded.
        """
        rows = self.list_rules(
            include_inactive=False
        )

        defaults = RosterRules().as_dict()

        values = dict(defaults)

        for rule in rows:
            if rule.key not in values:
                continue

            values[rule.key] = rule.value

        return RosterRules(
            **values
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
                f"Unsupported roster rule value type: {value_type!r}"
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
