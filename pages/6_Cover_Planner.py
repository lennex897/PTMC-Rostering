from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from math import ceil

import streamlit as st

from roster_engine.database import get_supabase


COVER_TYPES = {
    "NON_FC": {
        "IPPT": 0.5, "SOC": 0.5, "ER": 0.5, "CC": 0.5, "8KM": 0.5,
        "HG": 1.0, "BIC": 1.0, "12KM": 1.0, "BTP": 1.5,
    },
    "FC": {"FC": 1.0},
    "GP": {"GP": 1.0},
    "GX": {
        "SP": 0.5, "SFT": 0.5, "EMCOOL EXCHANGE": 0.5,
        "RP": 1.0, "SV": 1.0, "MMU": 1.0, "EP": 1.0,
    },
}

CATEGORY_LABELS = {
    "NON_FC": "Non-FC",
    "FC": "FC",
    "GX": "GX",
    "GP": "GP",
}
SESSION_OPTIONS = ["AM", "PM", "FULL_DAY"]
SESSION_LABELS = {"AM": "AM", "PM": "PM", "FULL_DAY": "Full day"}

st.set_page_config(page_title="Cover Planner", page_icon="🩺", layout="wide")
st.title("Cover Planner")
st.caption(
    "Enter monthly cover requirements. Personnel assignments will be "
    "performed later by the roster generator."
)


def month_start(value: date) -> date:
    return value.replace(day=1)


def month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def dates_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


@st.cache_data(ttl=30)
def load_roster_months() -> list[dict[str, object]]:
    response = (
        get_supabase()
        .table("roster_months")
        .select("id,month_start,status")
        .order("month_start", desc=True)
        .execute()
    )
    months = []
    for row in response.data or []:
        raw = row.get("month_start")
        if not raw:
            continue
        parsed = raw if isinstance(raw, date) else date.fromisoformat(str(raw))
        months.append({
            "id": str(row["id"]),
            "month_start": month_start(parsed),
            "status": str(row.get("status") or "draft"),
        })
    return months


@st.cache_data(ttl=15)
def load_cover_requirements(roster_month_id: str) -> list[dict[str, object]]:
    response = (
        get_supabase()
        .table("roster_cover_requirements")
        .select(
            "id,roster_month_id,requesting_unit,cover_category,cover_type,"
            "session,start_date,end_date,personnel_required,mandatory,remarks"
        )
        .eq("roster_month_id", roster_month_id)
        .order("start_date")
        .order("requesting_unit")
        .execute()
    )
    return list(response.data or [])


def requirement_dates(row: dict[str, object]) -> list[date]:
    return dates_between(
        date.fromisoformat(str(row["start_date"])),
        date.fromisoformat(str(row["end_date"])),
    )


def point_value(row: dict[str, object]) -> float:
    return float(
        COVER_TYPES.get(str(row["cover_category"]), {}).get(
            str(row["cover_type"]), 0.0
        )
    )


try:
    roster_months = load_roster_months()
except Exception as exc:
    st.error(f"Unable to load roster months: {exc}")
    st.stop()

if not roster_months:
    st.warning("Create a roster month before adding cover requirements.")
    st.stop()

stored_month = st.session_state.get("selected_roster_month")
default_index = 0
if stored_month:
    for index, item in enumerate(roster_months):
        if item["month_start"].isoformat() == str(stored_month):
            default_index = index
            break

selected_month_record = st.selectbox(
    "Roster month",
    options=roster_months,
    index=default_index,
    format_func=lambda item: item["month_start"].strftime("%b %y"),
)
selected_month = selected_month_record["month_start"]
selected_month_end = month_end(selected_month)
roster_month_id = selected_month_record["id"]
st.session_state["selected_roster_month"] = selected_month.isoformat()

try:
    requirements = load_cover_requirements(roster_month_id)
except Exception as exc:
    st.error(
        "Unable to load cover requirements. Run the cover planner SQL migration "
        f"first.\n\n{exc}"
    )
    st.stop()

expanded_slots = 0
fc_daily_counts: dict[date, int] = defaultdict(int)
for requirement in requirements:
    quantity = int(requirement["personnel_required"])
    days = requirement_dates(requirement)
    expanded_slots += len(days) * quantity
    if requirement["cover_category"] == "FC":
        for current_date in days:
            fc_daily_counts[current_date] += quantity

derived_fc_reserves = sum(ceil(count / 2) for count in fc_daily_counts.values())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Requirements", len(requirements))
m2.metric("Active cover slots", expanded_slots)
m3.metric("Derived FC reserves", derived_fc_reserves)
m4.metric("Total generated slots", expanded_slots + derived_fc_reserves)

st.divider()
add_tab, planner_tab, daily_tab = st.tabs(
    ["Add requirement", "Planner table", "Daily requirement preview"]
)

with add_tab:
    st.subheader("New cover requirement")
    with st.form("add_cover_requirement_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            requesting_unit = st.text_input("Requesting unit", placeholder="e.g. 1 COY")
        with c2:
            category = st.selectbox(
                "Cover category",
                options=list(COVER_TYPES),
                format_func=lambda value: CATEGORY_LABELS[value],
            )
        with c3:
            cover_type = st.selectbox("Cover type", options=list(COVER_TYPES[category]))

        d1, d2, d3, d4 = st.columns(4)
        with d1:
            start_date = st.date_input(
                "Start date", value=selected_month,
                min_value=selected_month, max_value=selected_month_end,
                format="DD/MM/YYYY",
            )
        with d2:
            end_date = st.date_input(
                "End date", value=start_date,
                min_value=selected_month, max_value=selected_month_end,
                format="DD/MM/YYYY",
            )
        with d3:
            session = st.selectbox(
                "Session", options=SESSION_OPTIONS, index=2,
                format_func=lambda value: SESSION_LABELS[value],
            )
        with d4:
            personnel_required = st.number_input(
                "Personnel required", min_value=1, max_value=20, value=1, step=1
            )

        mandatory = st.checkbox("Mandatory requirement", value=True)
        remarks = st.text_area("Remarks", placeholder="Optional operational details")

        points = COVER_TYPES[category][cover_type]
        day_count = (end_date - start_date).days + 1 if end_date >= start_date else 0
        st.info(
            f"{cover_type}: {points:g} point(s) per assigned cover. "
            f"This creates {day_count * int(personnel_required)} active slot(s)."
        )
        submitted = st.form_submit_button(
            "Add cover requirement", type="primary", use_container_width=True
        )

    if submitted:
        if not requesting_unit.strip():
            st.error("Requesting unit is required.")
        elif end_date < start_date:
            st.error("End date cannot be before start date.")
        else:
            payload = {
                "roster_month_id": roster_month_id,
                "requesting_unit": requesting_unit.strip().upper(),
                "cover_category": category,
                "cover_type": cover_type,
                "session": session,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "personnel_required": int(personnel_required),
                "mandatory": bool(mandatory),
                "remarks": remarks.strip() or None,
            }
            try:
                get_supabase().table("roster_cover_requirements").insert(payload).execute()
            except Exception as exc:
                st.error(f"Unable to add requirement: {exc}")
            else:
                load_cover_requirements.clear()
                st.success("Cover requirement added.")
                st.rerun()

with planner_tab:
    st.subheader(f"Cover requirements — {selected_month:%B %Y}")
    if not requirements:
        st.info("No cover requirements have been added.")
    else:
        rows = []
        for item in requirements:
            category = str(item["cover_category"])
            quantity = int(item["personnel_required"])
            days = len(requirement_dates(item))
            rows.append({
                "ID": item["id"],
                "Unit": item["requesting_unit"],
                "Category": CATEGORY_LABELS.get(category, category),
                "Cover": item["cover_type"],
                "Session": SESSION_LABELS.get(str(item["session"]), str(item["session"])),
                "Start": date.fromisoformat(str(item["start_date"])),
                "End": date.fromisoformat(str(item["end_date"])),
                "Qty/day": quantity,
                "Points": point_value(item),
                "Active slots": days * quantity,
                "Mandatory": bool(item["mandatory"]),
                "Remarks": item.get("remarks") or "",
            })
        st.dataframe(
            rows, use_container_width=True, hide_index=True,
            height=min(700, 90 + len(rows) * 35),
            column_config={
                "ID": None,
                "Start": st.column_config.DateColumn("Start", format="DD MMM"),
                "End": st.column_config.DateColumn("End", format="DD MMM"),
                "Points": st.column_config.NumberColumn("Points", format="%.1f"),
                "Mandatory": st.column_config.CheckboxColumn("Mandatory"),
            },
        )

        st.divider()
        st.subheader("Delete requirement")
        requirement_by_id = {str(item["id"]): item for item in requirements}
        delete_id = st.selectbox(
            "Select requirement",
            options=list(requirement_by_id),
            format_func=lambda item_id: (
                f"{requirement_by_id[item_id]['requesting_unit']} — "
                f"{requirement_by_id[item_id]['cover_type']} — "
                f"{requirement_by_id[item_id]['start_date']} to "
                f"{requirement_by_id[item_id]['end_date']}"
            ),
        )
        confirm_delete = st.checkbox("Confirm deletion")
        if st.button("Delete selected requirement", disabled=not confirm_delete):
            try:
                get_supabase().table("roster_cover_requirements").delete().eq(
                    "id", delete_id
                ).execute()
            except Exception as exc:
                st.error(f"Unable to delete requirement: {exc}")
            else:
                load_cover_requirements.clear()
                st.success("Cover requirement deleted.")
                st.rerun()

with daily_tab:
    st.subheader("Daily expanded requirement preview")
    st.caption(
        "FC reserve slots are derived automatically as ceil(active FC / 2)."
    )

    preview_date = st.date_input(
        "Preview date", value=selected_month,
        min_value=selected_month, max_value=selected_month_end,
        format="DD/MM/YYYY", key="cover_daily_preview_date",
    )

    daily_rows = []
    active_fc = 0
    for item in requirements:
        if preview_date not in requirement_dates(item):
            continue
        quantity = int(item["personnel_required"])
        if item["cover_category"] == "FC":
            active_fc += quantity
        daily_rows.append({
            "Date": preview_date,
            "Unit": item["requesting_unit"],
            "Category": CATEGORY_LABELS.get(str(item["cover_category"]), str(item["cover_category"])),
            "Cover": item["cover_type"],
            "Session": SESSION_LABELS.get(str(item["session"]), str(item["session"])),
            "Slots": quantity,
            "Points each": point_value(item),
            "Mandatory": bool(item["mandatory"]),
            "Derived": False,
        })

    reserve_count = ceil(active_fc / 2) if active_fc else 0
    if reserve_count:
        daily_rows.append({
            "Date": preview_date,
            "Unit": "SHARED FC RESERVE",
            "Category": "FC",
            "Cover": "FC RESERVE",
            "Session": "Full day",
            "Slots": reserve_count,
            "Points each": 0.0,
            "Mandatory": True,
            "Derived": True,
        })

    active_slots = sum(int(row["Slots"]) for row in daily_rows if not row["Derived"])
    reserve_slots = sum(int(row["Slots"]) for row in daily_rows if row["Derived"])
    p1, p2, p3 = st.columns(3)
    p1.metric("Active cover slots", active_slots)
    p2.metric("FC reserve slots", reserve_slots)
    p3.metric("Total personnel needed", active_slots + reserve_slots)

    if not daily_rows:
        st.info("No cover requirements fall on this date.")
    else:
        st.dataframe(
            daily_rows, use_container_width=True, hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
                "Points each": st.column_config.NumberColumn("Points", format="%.1f"),
                "Mandatory": st.column_config.CheckboxColumn("Mandatory"),
                "Derived": st.column_config.CheckboxColumn("Derived"),
            },
        )