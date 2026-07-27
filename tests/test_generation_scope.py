from roster_engine.planning_generation import _normalise_generation_scope


def test_scope_normalisation():
    assert _normalise_generation_scope("Both centres") == "BOTH"
    assert _normalise_generation_scope("PT only") == "PT"
    assert _normalise_generation_scope("RH only") == "RH"
