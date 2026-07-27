from datetime import date

from roster_engine.cover_scheduler import _person_is_available
from roster_engine.eligibility import is_person_unavailable
from roster_engine.models import AvailabilityEntry, Person


def make_person() -> Person:
    return Person(
        name="CPL ROYSTON SEOW",
        rank="CPL",
        centre="PT",
        department="TEST",
        ampt_status="PASS",
        eligible_roles={"PT DM"},
        is_cover_fit=True,
    )


def make_entry(reason: str) -> AvailabilityEntry:
    return AvailabilityEntry(
        person_name="CPL ROYSTON SEOW",
        unavailable_date=date(2026, 8, 5),
        reason=reason,
    )


def test_serve_plus_blocks_automatic_duty() -> None:
    medic = make_person()

    assert is_person_unavailable(
        medic,
        date(2026, 8, 5),
        [make_entry("SERVE+")],
    )


def test_custom_code_blocks_automatic_duty() -> None:
    medic = make_person()

    assert is_person_unavailable(
        medic,
        date(2026, 8, 5),
        [make_entry("ANY CUSTOM CODE")],
    )


def test_serve_plus_blocks_automatic_cover() -> None:
    medic = make_person()

    assert not _person_is_available(
        person=medic,
        duty_date=date(2026, 8, 5),
        availability_entries=[
            make_entry("SERVE+")
        ],
    )


def test_different_date_is_not_blocked() -> None:
    medic = make_person()

    assert not is_person_unavailable(
        medic,
        date(2026, 8, 6),
        [make_entry("SERVE+")],
    )
