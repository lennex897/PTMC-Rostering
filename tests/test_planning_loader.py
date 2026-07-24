from roster_engine.planning_loader import PlanningContext


def test_planning_context_has_expected_fields() -> None:
    field_names = {
        field.name
        for field in PlanningContext.__dataclass_fields__.values()
    }

    assert field_names == {
        "roster_month",
        "personnel",
        "availability_entries",
        "cover_types",
        "cover_requirements",
        "cover_slots",
        "manual_assignments",
        "duty_interests",
    }
