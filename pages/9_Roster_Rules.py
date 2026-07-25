from __future__ import annotations

import streamlit as st

from roster_engine.database import get_supabase
from roster_engine.roster_rules_repository import (
    RosterRulesRepository,
)


st.set_page_config(
    page_title="Roster Rules",
    page_icon="⚙️",
    layout="wide",
)

st.title("Roster Rules")
st.caption(
    "Edit machine-readable generator rules and choose which rules are enforced."
)


GROUP_LABELS = {
    "overnight": "Overnight",
    "points": "Points",
    "deployment": "Deployment",
    "cover": "Cover",
    "reserve": "Reserve",
    "personnel": "Personnel",
}


@st.cache_data(ttl=15)
def load_rules():
    return RosterRulesRepository(
        get_supabase()
    ).list_editable_rules()


def clear_rule_cache() -> None:
    load_rules.clear()


def render_value_control(
    rule,
):
    key = rule.key

    if rule.value_type == "boolean":
        return st.toggle(
            "Value",
            value=bool(rule.value),
            key=f"value_{key}",
        )

    if rule.value_type == "integer":
        return int(
            st.number_input(
                "Value",
                value=int(rule.value),
                step=1,
                key=f"value_{key}",
            )
        )

    if rule.value_type == "float":
        return float(
            st.number_input(
                "Value",
                value=float(rule.value),
                step=0.5,
                key=f"value_{key}",
            )
        )

    if rule.value_type == "string_list":
        current = list(
            rule.value
            if isinstance(
                rule.value,
                tuple,
            )
            else ()
        )

        text_value = st.text_input(
            "Values",
            value=", ".join(current),
            help=(
                "Comma-separated values. "
                "Weekdays use MON,TUE,WED,THU,FRI,SAT,SUN."
            ),
            key=f"value_{key}",
        )

        return tuple(
            item.strip().upper()
            for item in text_value.split(",")
            if item.strip()
        )

    return st.text_input(
        "Value",
        value=str(rule.value),
        key=f"value_{key}",
    )


try:
    rules = load_rules()
except Exception as exc:
    st.error(
        f"Unable to load roster rules: {exc}"
    )
    st.stop()


if not rules:
    st.info(
        "No machine-readable roster rules exist yet."
    )
    st.stop()


grouped: dict[str, list] = {}

for rule in rules:
    grouped.setdefault(
        rule.group,
        [],
    ).append(rule)


for group_name in [
    "overnight",
    "deployment",
    "points",
    "cover",
    "reserve",
    "personnel",
]:
    group_rules = grouped.get(
        group_name,
        [],
    )

    if not group_rules:
        continue

    st.subheader(
        GROUP_LABELS.get(
            group_name,
            group_name.title(),
        )
    )

    for rule in group_rules:
        with st.container(border=True):
            c1, c2 = st.columns(
                [3, 1]
            )

            with c1:
                st.markdown(
                    f"**{rule.key.replace('_', ' ').title()}**"
                )

                if rule.description:
                    st.caption(
                        rule.description
                    )

            with c2:
                enforced = st.toggle(
                    "Enforced",
                    value=rule.is_active,
                    key=f"active_{rule.key}",
                )

            value = render_value_control(
                rule
            )

            if st.button(
                "Save rule",
                type="primary",
                use_container_width=True,
                key=f"save_{rule.key}",
            ):
                try:
                    RosterRulesRepository(
                        get_supabase()
                    ).update_rule(
                        rule_key=rule.key,
                        value=value,
                        is_active=enforced,
                    )
                except Exception as exc:
                    st.error(
                        f"Unable to save rule: {exc}"
                    )
                else:
                    clear_rule_cache()
                    st.success(
                        "Rule updated."
                    )
                    st.rerun()

    st.divider()


st.caption(
    "Changes apply to future PlanningContext loads and generated rosters. "
    "Previously saved roster generations remain unchanged."
)
