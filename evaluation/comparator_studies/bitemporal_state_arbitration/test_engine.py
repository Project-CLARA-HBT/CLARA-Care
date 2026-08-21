from datetime import UTC, datetime, timedelta

from evaluation.comparator_studies.bitemporal_state_arbitration.capabilities import (
    UNSUPPORTED_BY_METHOD,
    unsupported_operation,
)
from evaluation.comparator_studies.bitemporal_state_arbitration.engine import (
    ArbitrationEvent,
    arbitrate,
)


def test_governance_operations_are_explicitly_unsupported() -> None:
    assert unsupported_operation("consent_versioned_gst_write")["status"] == UNSUPPORTED_BY_METHOD


T0 = datetime(2026, 1, 1, tzinfo=UTC)


def event(
    identifier: str,
    value: str,
    *,
    relation: str = "SUPPORT",
    target: str | None = None,
    known: int = 0,
):
    return ArbitrationEvent(
        identifier, "medication:x", value, T0, None, T0 + timedelta(days=known), 1, relation, target
    )


def test_operators_preserve_history_and_conflict() -> None:
    result = arbitrate(
        [event("a", "10"), event("b", "20", relation="BRANCH-CONFLICT", target="a")],
        valid_at=T0,
        known_at=T0,
    )
    assert result.active_ids == ("a", "b")
    assert result.conflict_ids == ("a", "b")
    assert result.historical_ids == ("a", "b")


def test_refine_and_supersede_require_active_target() -> None:
    result = arbitrate(
        [event("a", "10"), event("b", "12", relation="REFINE", target="a")],
        valid_at=T0,
        known_at=T0,
    )
    assert result.active_ids == ("b",)
    assert result.superseded_ids == ("a",)


def test_supersede_closes_target_and_activates_successor() -> None:
    result = arbitrate(
        [event("a", "10"), event("b", "20", relation="SUPERSEDE", target="a")],
        valid_at=T0,
        known_at=T0,
    )
    assert result.active_ids == ("b",)
    assert result.superseded_ids == ("a",)


def test_known_at_hides_later_ingestion() -> None:
    result = arbitrate(
        [event("a", "10"), event("b", "12", relation="REFINE", target="a", known=1)],
        valid_at=T0,
        known_at=T0,
    )
    assert result.active_ids == ("a",)


def test_support_adds_history_without_parallel_active_candidate() -> None:
    result = arbitrate(
        [event("a", "10"), event("support", "10", target="a")],
        valid_at=T0,
        known_at=T0,
    )
    assert result.active_ids == ("a",)
    assert result.historical_ids == ("a", "support")


def test_equal_authority_values_in_different_slots_do_not_conflict() -> None:
    first = event("a", "10")
    second = ArbitrationEvent("b", "observation:y", "20", T0, None, T0, 1)
    result = arbitrate([first, second], valid_at=T0, known_at=T0)
    assert result.active_ids == ("a", "b")
    assert result.conflict_ids == ()
