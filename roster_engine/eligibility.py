from datetime import date

from roster_engine.models import AvailabilityEntry, Person


PT_ROLES = {
    "PT DM",
    "PT CS1",
    "PT CS2",
    "PT CS/B",
    "PT SB1",
    "PT SB2",
    "PT AE",
}

RH_ROLES = {
    "RH DM",
    "RH CS1",
    "RH SB1",
    "RH SB2",
    "RH AE",
}

BCF_ROLES = {
    "PT AE",
    "PT SB1",
    "PT SB2",
}

BLOCKING_REASONS = {
    "AL",
    "OL",
    "MA",
    "MC",
    "HL",
    "WISDOM",
    "SURGERY",
    "OUTPRO",
    "ORD",
}


def normalise_role(role: str) -> str:
    return " ".join(role.strip().upper().split())


def allowed_roles_for_person(
    person: Person,
) -> set[str]:
    if not person.is_ampt_valid:
        return set()

    if person.centre == "PT":
        if person.is_bcf:
            return set(BCF_ROLES)

        return set(PT_ROLES)

    if person.centre == "RH":
        return set(RH_ROLES)

    return set()


def is_person_unavailable(
    person: Person,
    duty_date: date,
    availability_entries: list[AvailabilityEntry],
) -> bool:
    person_name = person.name.strip().upper()

    return any(
        entry.person_name.strip().upper() == person_name
        and entry.unavailable_date == duty_date
        and entry.reason.strip().upper() in BLOCKING_REASONS
        for entry in availability_entries
    )


def has_left_unit(
    person: Person,
    duty_date: date,
) -> bool:
    if person.leaving_date is None:
        return False

    return duty_date >= person.leaving_date


def is_eligible_for_role(
    person: Person,
    role: str,
    duty_date: date,
    availability_entries: list[AvailabilityEntry],
) -> bool:
    normalised_role = normalise_role(role)

    if normalised_role not in allowed_roles_for_person(person):
        return False

    if is_person_unavailable(
        person,
        duty_date,
        availability_entries,
    ):
        return False

    if has_left_unit(person, duty_date):
        return False

    return True


def eligible_people_for_role(
    personnel: list[Person],
    role: str,
    duty_date: date,
    availability_entries: list[AvailabilityEntry],
) -> list[Person]:
    return [
        person
        for person in personnel
        if is_eligible_for_role(
            person=person,
            role=role,
            duty_date=duty_date,
            availability_entries=availability_entries,
        )
    ]