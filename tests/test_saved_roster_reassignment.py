from roster_engine.generated_roster_repository import (
    GeneratedRosterRepository,
)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, row):
        self.row = row
        self.payload = None

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        row = dict(self.row)
        row.update(self.payload or {})
        return FakeResponse([row])


class FakeClient:
    def __init__(self, row):
        self.query = FakeQuery(row)

    def table(self, _name):
        return self.query


def test_update_assignment_person_updates_saved_assignment() -> None:
    row = {
        "id": "a1",
        "generation_id": "g1",
        "roster_month_id": "m1",
        "assignment_date": "2026-08-06",
        "assignment_kind": "DUTY",
        "centre": "PT",
        "role_name": "PT DM",
        "requesting_unit": None,
        "cover_category": None,
        "cover_type": None,
        "session": "FULL_DAY",
        "personnel_id": "old-id",
        "person_name": "OLD PERSON",
        "points": 1.0,
        "is_overnight": True,
        "is_locked": False,
        "is_reserve": False,
        "cover_requirement_id": None,
    }

    repository = GeneratedRosterRepository(
        FakeClient(row)
    )

    updated = repository.update_assignment_person(
        assignment_id="a1",
        personnel_id="new-id",
        person_name="NEW PERSON",
    )

    assert updated.personnel_id == "new-id"
    assert updated.person_name == "NEW PERSON"
