from datetime import date

from roster_engine.duty_interest_repository import (
    DutyInterest,
)


def test_any_role_interest_applies_to_any_overnight_role() -> None:
    interest = DutyInterest(
        id="i1",
        roster_month_id="m1",
        personnel_id="p1",
        person_name="CPL TEST",
        centre="PT",
        interest_date=date(2026, 8, 4),
        preferred_role=None,
    )

    assert interest.applies_to_role("PT DM")
    assert interest.applies_to_role("PT SB1")


def test_specific_interest_applies_only_to_matching_role() -> None:
    interest = DutyInterest(
        id="i1",
        roster_month_id="m1",
        personnel_id="p1",
        person_name="CPL TEST",
        centre="RH",
        interest_date=date(2026, 8, 4),
        preferred_role="RH SB1",
    )

    assert interest.applies_to_role("RH SB1")
    assert not interest.applies_to_role("PT SB1")
