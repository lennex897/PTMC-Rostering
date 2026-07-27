from pathlib import Path

COVER = Path("roster_engine/cover_scheduler.py")
PLANNING = Path("roster_engine/planning_generation.py")
PAGE = Path("pages/1_Generate_Roster.py")


def replace_once(
    text: str,
    old: str,
    new: str,
    label: str,
) -> str:
    if old not in text:
        raise SystemExit(
            f"Could not find {label}. No files changed."
        )

    return text.replace(
        old,
        new,
        1,
    )


cover = COVER.read_text()
planning = PLANNING.read_text()
page = PAGE.read_text()


# ---------------------------------------------------------------------------
# cover_scheduler.py
# ---------------------------------------------------------------------------

cover = replace_once(
    cover,
    """def _sessions_conflict(first: str, second: str) -> bool:
    first = _normalise(first)
    second = _normalise(second)

    if "FULL_DAY" in {first, second}:
        return True

    return first == second


""",
    """def _sessions_conflict(first: str, second: str) -> bool:
    first = _normalise(first)
    second = _normalise(second)

    if "FULL_DAY" in {first, second}:
        return True

    return first == second


def cover_owner_centre(
    requesting_unit: str,
) -> str | None:
    import re

    unit = _normalise(
        requesting_unit
    )

    if re.match(
        r"^[A-W]\\s+COY\\b",
        unit,
    ):
        return "PT"

    if re.match(
        r"^[1-7](?:ST|ND|RD|TH)?\\s+COY\\b",
        unit,
    ):
        return "RH"

    return None


def _is_short_cover(
    slot: DailyCoverSlot,
) -> bool:
    return _normalise(
        slot.session
    ) in {
        "AM",
        "PM",
    }


def _service_type(
    person: Person,
) -> str:
    return _normalise(
        person.service_type
        or ""
    )


def _preferred_cover_candidates(
    *,
    candidates: list[Person],
    slot: DailyCoverSlot,
) -> list[Person]:
    cbt = [
        person
        for person in candidates
        if _service_type(
            person
        ) == "CBT"
    ]

    if cbt:
        return cbt

    legacy = [
        person
        for person in candidates
        if _service_type(
            person
        ) not in {
            "CBT",
            "SVC",
        }
    ]

    if legacy:
        return legacy

    if _is_short_cover(
        slot
    ):
        return [
            person
            for person in candidates
            if _service_type(
                person
            ) == "SVC"
        ]

    return []


""",
    "cover helper section",
)

cover = replace_once(
    cover,
    """def _candidate_sort_key(
    *,
    person: Person,
    historical_schedule: Schedule | None,
    locked_duties: list[Assignment],
    existing_cover_assignments: list[CoverAssignment],
) -> tuple[float, str]:
    return (
        _current_workload_points(
            person=person,
            historical_schedule=historical_schedule,
            locked_duties=locked_duties,
            existing_cover_assignments=existing_cover_assignments,
        ),
        _normalise(person.name),
    )
""",
    """def _candidate_sort_key(
    *,
    person: Person,
    slot: DailyCoverSlot,
    historical_schedule: Schedule | None,
    locked_duties: list[Assignment],
    existing_cover_assignments: list[CoverAssignment],
) -> tuple[int, float, str]:
    owner = cover_owner_centre(
        slot.requesting_unit
    )

    centre_priority = (
        0
        if (
            owner is not None
            and _normalise(
                person.centre
            ) == owner
        )
        else 1
    )

    return (
        centre_priority,
        _current_workload_points(
            person=person,
            historical_schedule=historical_schedule,
            locked_duties=locked_duties,
            existing_cover_assignments=existing_cover_assignments,
        ),
        _normalise(
            person.name
        ),
    )
""",
    "cover sort key",
)

cover = replace_once(
    cover,
    """    candidates = sorted(
        candidates,
        key=lambda person: _candidate_sort_key(
            person=person,
            historical_schedule=historical_schedule,
            locked_duties=locked_duties,
            existing_cover_assignments=result.assignments,
        ),
    )
""",
    """    candidates = _preferred_cover_candidates(
        candidates=candidates,
        slot=slot,
    )

    candidates = sorted(
        candidates,
        key=lambda person: _candidate_sort_key(
            person=person,
            slot=slot,
            historical_schedule=historical_schedule,
            locked_duties=locked_duties,
            existing_cover_assignments=result.assignments,
        ),
    )
""",
    "normal cover selection",
)

cover = replace_once(
    cover,
    """            pool = sorted(
                pool,
                key=lambda person: _candidate_sort_key(
                    person=person,
                    historical_schedule=historical_schedule,
                    locked_duties=locked_duties,
                    existing_cover_assignments=result.assignments,
                ),
            )
""",
    """            pool = _preferred_cover_candidates(
                candidates=pool,
                slot=slot,
            )

            pool = sorted(
                pool,
                key=lambda person: _candidate_sort_key(
                    person=person,
                    slot=slot,
                    historical_schedule=historical_schedule,
                    locked_duties=locked_duties,
                    existing_cover_assignments=result.assignments,
                ),
            )
""",
    "FC cover selection",
)


# ---------------------------------------------------------------------------
# planning_generation.py
# ---------------------------------------------------------------------------

planning = replace_once(
    planning,
    "from roster_engine.cover_scheduler import CoverAssignment, generate_cover_assignments\n",
    """from roster_engine.cover_scheduler import (
    CoverAssignment,
    cover_owner_centre,
    generate_cover_assignments,
)
""",
    "planning import",
)

planning = replace_once(
    planning,
    """def generate_roster_from_planning(
    *,
    planning: PlanningContext,
    settings: GenerationSettings,
    historical_schedule: Schedule | None = None,
    role_priorities: tuple[RolePriority, ...] | None = None,
) -> PlanningGenerationResult:
    rules = planning.roster_rules

    requirements = generate_month_requirements(
        year=settings.year,
        month=settings.month,
        settings=settings.requirement_settings,
        rules=rules,
    )
""",
    """def _normalise_generation_scope(
    generation_scope: str,
) -> str:
    scope = _normalise(
        generation_scope
    )

    aliases = {
        "BOTH": "BOTH",
        "BOTH CENTRES": "BOTH",
        "PT": "PT",
        "PT ONLY": "PT",
        "RH": "RH",
        "RH ONLY": "RH",
    }

    if scope not in aliases:
        raise ValueError(
            f"Unsupported generation scope: {generation_scope!r}."
        )

    return aliases[
        scope
    ]


def _requirement_in_scope(
    requirement: DutyRequirement,
    scope: str,
) -> bool:
    return (
        scope == "BOTH"
        or _normalise(
            requirement.centre
        ) == scope
    )


def _cover_slot_in_scope(
    slot: DailyCoverSlot,
    scope: str,
) -> bool:
    if scope == "BOTH":
        return True

    return (
        cover_owner_centre(
            slot.requesting_unit
        )
        == scope
    )


def generate_roster_from_planning(
    *,
    planning: PlanningContext,
    settings: GenerationSettings,
    historical_schedule: Schedule | None = None,
    role_priorities: tuple[RolePriority, ...] | None = None,
    generation_scope: str = "BOTH",
) -> PlanningGenerationResult:
    rules = planning.roster_rules

    scope = _normalise_generation_scope(
        generation_scope
    )

    all_requirements = generate_month_requirements(
        year=settings.year,
        month=settings.month,
        settings=settings.requirement_settings,
        rules=rules,
    )

    requirements = [
        requirement
        for requirement in all_requirements
        if _requirement_in_scope(
            requirement,
            scope,
        )
    ]
""",
    "planning generation function",
)

planning = replace_once(
    planning,
    """    manual_duties, manual_reserves, manual_covers = (
        _split_locked_manual_assignments(
            planning.manual_assignments
        )
    )

    locked_duties, remaining_requirements = _apply_locked_duties(
""",
    """    manual_duties, manual_reserves, manual_covers = (
        _split_locked_manual_assignments(
            planning.manual_assignments
        )
    )

    if scope != "BOTH":
        manual_duties = [
            assignment
            for assignment in manual_duties
            if _normalise(
                assignment.centre
                or ""
            ) == scope
        ]

        manual_reserves = [
            assignment
            for assignment in manual_reserves
            if _normalise(
                assignment.centre
                or ""
            ) == scope
        ]

    scoped_cover_slots = [
        slot
        for slot in planning.cover_slots
        if _cover_slot_in_scope(
            slot,
            scope,
        )
    ]

    scoped_requirement_ids = {
        slot.cover_requirement_id
        for slot in scoped_cover_slots
        if slot.cover_requirement_id
        is not None
    }

    if scope != "BOTH":
        manual_covers = [
            assignment
            for assignment in manual_covers
            if (
                assignment.cover_requirement_id
                in scoped_requirement_ids
            )
        ]

    locked_duties, remaining_requirements = _apply_locked_duties(
""",
    "planning scope filtering",
)

planning = replace_once(
    planning,
    "        cover_slots=planning.cover_slots,\n",
    "        cover_slots=scoped_cover_slots,\n",
    "scoped cover slots",
)


# ---------------------------------------------------------------------------
# pages/1_Generate_Roster.py
# ---------------------------------------------------------------------------

if '"Generation scope"' not in page:
    button_marker = """if st.button(
    "Generate roster",
"""

    if button_marker not in page:
        raise SystemExit(
            "Could not find Generate roster button. No files changed."
        )

    scope_ui = """generation_scope_label = st.radio(
    "Generation scope",
    options=[
        "Both centres",
        "PT only",
        "RH only",
    ],
    horizontal=True,
    help=(
        "PT only generates PT duties and A-W COY covers. "
        "RH only generates RH duties and 1ST-7TH COY covers."
    ),
)

generation_scope = {
    "Both centres": "BOTH",
    "PT only": "PT",
    "RH only": "RH",
}[generation_scope_label]

st.caption(
    "Cover priority: CBT first; correct-centre CBT preferred. "
    "SVC is used only for AM/PM short covers when CBT cannot fill the slot."
)

"""

    page = page.replace(
        button_marker,
        scope_ui + button_marker,
        1,
    )

page = replace_once(
    page,
    """        result = generate_roster_from_planning(
            planning=planning,
            settings=GenerationSettings(
                year=selected_month.year,
                month=selected_month.month,
            ),
        )
""",
    """        result = generate_roster_from_planning(
            planning=planning,
            settings=GenerationSettings(
                year=selected_month.year,
                month=selected_month.month,
            ),
            generation_scope=generation_scope,
        )
""",
    "generator call",
)


# Compile before changing any application files.
compile(
    cover,
    str(COVER),
    "exec",
)
compile(
    planning,
    str(PLANNING),
    "exec",
)
compile(
    page,
    str(PAGE),
    "exec",
)

for path, new_text in (
    (
        COVER,
        cover,
    ),
    (
        PLANNING,
        planning,
    ),
    (
        PAGE,
        page,
    ),
):
    backup = path.with_suffix(
        ".py.step20_clean_backup"
    )

    if not backup.exists():
        backup.write_text(
            path.read_text()
        )

    path.write_text(
        new_text
    )

print(
    "Step 20 clean patch applied successfully."
)
