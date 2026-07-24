from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from roster_engine.database import get_supabase
from roster_engine.models import Person


PERSONNEL_TABLE = "roster_personnel"
PERSONNEL_ROLES_TABLE = "roster_personnel_roles"

PT_ROLES = {
    "PT DM", "PT CS1", "PT CS2", "PT CS/B", "PT SB1", "PT SB2", "PT AE",
}
RH_ROLES = {
    "RH DM", "RH CS1", "RH SB1", "RH SB2", "RH AE",
}
ROLES_BY_CENTRE = {"PT": PT_ROLES, "RH": RH_ROLES}


class PersonnelRepositoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersonnelRecord:
    id: str
    person: Person
    display_order: int = 0


def _parse_optional_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise PersonnelRepositoryError(f"Invalid leaving date: {value!r}") from exc
    raise PersonnelRepositoryError(f"Unsupported leaving-date value: {value!r}")


def _serialise_optional_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _normalise_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalise_centre(centre: str) -> str:
    value = _normalise_text(centre).upper()
    if value not in ROLES_BY_CENTRE:
        raise PersonnelRepositoryError("Centre must be either PT or RH.")
    return value


def _normalise_ampt_status(ampt_status: str) -> str:
    value = _normalise_text(ampt_status).upper()
    if value not in {"PASS", "FAIL"}:
        raise PersonnelRepositoryError("AMPT status must be PASS or FAIL.")
    return value


def _normalise_service_type(service_type: str | None) -> str | None:
    if service_type in (None, ""):
        return None
    value = _normalise_text(service_type).upper()
    if value not in {"CBT", "SVC"}:
        raise PersonnelRepositoryError("Service type must be CBT, SVC, or blank.")
    return value


def _normalise_role(role: str) -> str:
    return " ".join(role.strip().upper().split())


def _normalise_roles(roles: Iterable[str] | None) -> set[str]:
    if roles is None:
        return set()
    return {_normalise_role(role) for role in roles if str(role).strip()}


def _validate_name(name: str) -> str:
    value = _normalise_text(name)
    if not value:
        raise PersonnelRepositoryError("Personnel name cannot be empty.")
    return value


def _validate_roles_for_centre(*, centre: str, roles: Iterable[str]) -> set[str]:
    centre = _normalise_centre(centre)
    roles = _normalise_roles(roles)
    invalid = roles - ROLES_BY_CENTRE[centre]
    if invalid:
        raise PersonnelRepositoryError(
            f"Invalid {centre} roles: " + ", ".join(sorted(invalid))
        )
    return roles


def get_roles_for_centre(centre: str) -> list[str]:
    centre = _normalise_centre(centre)
    preferred = ["DM", "CS1", "CS2", "CS/B", "SB1", "SB2", "AE"]
    return [
        f"{centre} {role}"
        for role in preferred
        if f"{centre} {role}" in ROLES_BY_CENTRE[centre]
    ]


def _row_to_person(row: dict) -> Person:
    role_rows = row.get("roster_personnel_roles") or []
    eligible_roles = {
        _normalise_role(role_row["role"])
        for role_row in role_rows
        if role_row.get("role")
    }
    return Person(
        name=_normalise_text(row.get("name")),
        rank=_normalise_text(row.get("rank")),
        centre=_normalise_text(row.get("centre")).upper(),
        department=_normalise_text(row.get("department")),
        ampt_status=_normalise_text(row.get("ampt_status")).upper(),
        leaving_date=_parse_optional_date(row.get("leaving_date")),
        eligible_roles=eligible_roles,
        is_cover_fit=row.get("is_cover_fit") if row.get("is_cover_fit") is not None else None,
        is_active=bool(row.get("is_active", True)),
        service_type=_normalise_service_type(row.get("service_type")),
    )


def load_personnel_records(*, include_inactive: bool = False) -> list[PersonnelRecord]:
    client = get_supabase()
    query = (
        client.table(PERSONNEL_TABLE)
        .select(
            "id,name,rank,centre,department,ampt_status,service_type,"
            "leaving_date,is_active,display_order,is_cover_fit,"
            "roster_personnel_roles(role)"
        )
        .order("display_order")
        .order("name")
    )
    if not include_inactive:
        query = query.eq("is_active", True)

    try:
        response = query.execute()
    except Exception as exc:
        raise PersonnelRepositoryError("Unable to load personnel from Supabase.") from exc

    return [
        PersonnelRecord(
            id=str(row["id"]),
            person=_row_to_person(row),
            display_order=int(row.get("display_order", 0) or 0),
        )
        for row in (response.data or [])
    ]


def load_personnel_from_supabase(*, include_inactive: bool = False) -> list[Person]:
    return [
        record.person
        for record in load_personnel_records(include_inactive=include_inactive)
    ]


def get_personnel_record(personnel_id: str) -> PersonnelRecord:
    client = get_supabase()
    try:
        response = (
            client.table(PERSONNEL_TABLE)
            .select(
                "id,name,rank,centre,department,ampt_status,service_type,"
                "leaving_date,is_active,display_order,is_cover_fit,"
                "roster_personnel_roles(role)"
            )
            .eq("id", personnel_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise PersonnelRepositoryError("Unable to load personnel record.") from exc

    rows = response.data or []
    if not rows:
        raise PersonnelRepositoryError("Personnel record was not found.")

    row = rows[0]
    return PersonnelRecord(
        id=str(row["id"]),
        person=_row_to_person(row),
        display_order=int(row.get("display_order", 0) or 0),
    )


def create_person(
    *,
    name: str,
    rank: str,
    centre: str,
    department: str,
    ampt_status: str,
    service_type: str | None = None,
    is_cover_fit: bool | None = None,
    leaving_date: date | None = None,
    display_order: int = 0,
    eligible_roles: Iterable[str] | None = None,
) -> str:
    normalised_name = _validate_name(name)
    normalised_centre = _normalise_centre(centre)
    normalised_ampt = _normalise_ampt_status(ampt_status)
    normalised_service_type = _normalise_service_type(service_type)
    normalised_roles = _validate_roles_for_centre(
        centre=normalised_centre,
        roles=eligible_roles or [],
    )

    if display_order < 0:
        raise PersonnelRepositoryError("Display order cannot be negative.")

    payload = {
        "name": normalised_name,
        "rank": _normalise_text(rank),
        "centre": normalised_centre,
        "department": _normalise_text(department),
        "ampt_status": normalised_ampt,
        "service_type": normalised_service_type,
        "is_cover_fit": is_cover_fit,
        "leaving_date": _serialise_optional_date(leaving_date),
        "is_active": True,
        "display_order": int(display_order),
    }

    client = get_supabase()
    try:
        response = client.table(PERSONNEL_TABLE).insert(payload).execute()
    except Exception as exc:
        raise PersonnelRepositoryError(
            "Unable to create personnel. Check that the name is not already in use."
        ) from exc

    rows = response.data or []
    if not rows or not rows[0].get("id"):
        raise PersonnelRepositoryError("Supabase did not return the new personnel ID.")

    personnel_id = str(rows[0]["id"])
    try:
        replace_person_roles(
            personnel_id=personnel_id,
            centre=normalised_centre,
            eligible_roles=normalised_roles,
        )
    except Exception:
        try:
            client.table(PERSONNEL_TABLE).delete().eq("id", personnel_id).execute()
        except Exception:
            pass
        raise

    return personnel_id


def update_person(
    *,
    personnel_id: str,
    name: str,
    rank: str,
    centre: str,
    department: str,
    ampt_status: str,
    service_type: str | None,
    is_cover_fit: bool | None,
    leaving_date: date | None,
    display_order: int,
    eligible_roles: Iterable[str] | None = None,
) -> None:
    normalised_name = _validate_name(name)
    normalised_centre = _normalise_centre(centre)
    normalised_ampt = _normalise_ampt_status(ampt_status)
    normalised_service_type = _normalise_service_type(service_type)
    normalised_roles = _validate_roles_for_centre(
        centre=normalised_centre,
        roles=eligible_roles or [],
    )

    if display_order < 0:
        raise PersonnelRepositoryError("Display order cannot be negative.")

    payload = {
        "name": normalised_name,
        "rank": _normalise_text(rank),
        "centre": normalised_centre,
        "department": _normalise_text(department),
        "ampt_status": normalised_ampt,
        "service_type": normalised_service_type,
        "is_cover_fit": is_cover_fit,
        "leaving_date": _serialise_optional_date(leaving_date),
        "display_order": int(display_order),
    }

    client = get_supabase()
    try:
        response = (
            client.table(PERSONNEL_TABLE)
            .update(payload)
            .eq("id", personnel_id)
            .execute()
        )
    except Exception as exc:
        raise PersonnelRepositoryError(
            "Unable to update personnel. Check that the name is not already in use."
        ) from exc

    if not response.data:
        raise PersonnelRepositoryError("Personnel record was not found.")

    replace_person_roles(
        personnel_id=personnel_id,
        centre=normalised_centre,
        eligible_roles=normalised_roles,
    )


def replace_person_roles(
    *,
    personnel_id: str,
    centre: str,
    eligible_roles: Iterable[str],
) -> None:
    normalised_centre = _normalise_centre(centre)
    normalised_roles = _validate_roles_for_centre(
        centre=normalised_centre,
        roles=eligible_roles,
    )

    client = get_supabase()

    try:
        client.table(PERSONNEL_ROLES_TABLE).delete().eq(
            "personnel_id", personnel_id
        ).execute()

        if not normalised_roles:
            return

        client.table(PERSONNEL_ROLES_TABLE).insert(
            [
                {"personnel_id": personnel_id, "role": role}
                for role in sorted(normalised_roles)
            ]
        ).execute()
    except Exception as exc:
        raise PersonnelRepositoryError("Unable to update personnel roles.") from exc


def deactivate_person(personnel_id: str) -> None:
    _set_active_status(personnel_id=personnel_id, is_active=False)


def reactivate_person(personnel_id: str) -> None:
    _set_active_status(personnel_id=personnel_id, is_active=True)


def _set_active_status(*, personnel_id: str, is_active: bool) -> None:
    client = get_supabase()

    try:
        response = (
            client.table(PERSONNEL_TABLE)
            .update({"is_active": is_active})
            .eq("id", personnel_id)
            .execute()
        )
    except Exception as exc:
        action = "reactivate" if is_active else "deactivate"
        raise PersonnelRepositoryError(f"Unable to {action} personnel.") from exc

    if not response.data:
        raise PersonnelRepositoryError("Personnel record was not found.")