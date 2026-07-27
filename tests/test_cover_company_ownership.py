from roster_engine.cover_scheduler import cover_owner_centre


def test_company_ownership_mapping():
    assert cover_owner_centre("A COY") == "PT"
    assert cover_owner_centre("W COY") == "PT"
    assert cover_owner_centre("1 COY") == "RH"
    assert cover_owner_centre("1ST COY") == "RH"
    assert cover_owner_centre("7TH COY") == "RH"
