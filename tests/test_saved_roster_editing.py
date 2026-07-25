from roster_engine.generated_roster_repository import (
    GeneratedRosterRepository,
)


def test_generation_status_rejects_unknown_value_before_query() -> None:
    class FakeClient:
        pass

    repository = GeneratedRosterRepository(
        FakeClient()
    )

    try:
        repository.set_generation_status(
            generation_id="g1",
            status="invalid",
        )
    except ValueError as exc:
        assert "Unsupported generation status" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError for invalid status."
        )
