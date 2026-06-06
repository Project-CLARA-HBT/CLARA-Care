"""Unit tests for the ``kb_*`` schema write-invariant validators (task 1.4).

Targets the pure validator helpers in
``clara_ml.rag.store.schema`` that enforce the persisted-data rules from
``design.md``:

* :func:`validate_trust_tier` — Requirement 1.5 (trust_tier domain {1,2,3,4}).
* :func:`guard_degraded_row` — Requirements 2.4 / 2.5 (no degraded persistence
  in production).
* :func:`require_model_id` — Requirement 1.4 (model_id discriminator present).
* :func:`validate_embedding_row` — combined invariants (Requirements 1.3, 1.4,
  2.5).

These are table-driven/parametrized unit tests (this is a unit-test task, not a
property task).
"""

from __future__ import annotations

import pytest

from clara_ml.rag.store.schema import (
    DegradedEmbeddingNotAllowedError,
    EmbeddingDimMismatchError,
    InvalidTrustTierError,
    MissingModelIdError,
    WriteInvariantError,
    guard_degraded_row,
    require_model_id,
    validate_embedding_row,
    validate_trust_tier,
)

# ---------------------------------------------------------------------------
# validate_trust_tier — Requirement 1.5
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", [1, 2, 3, 4])
def test_validate_trust_tier_accepts_valid_domain(tier: int) -> None:
    assert validate_trust_tier(tier) == tier


def test_validate_trust_tier_accepts_int_like_string() -> None:
    # int("3") succeeds; the validator coerces numeric strings.
    assert validate_trust_tier("3") == 3


@pytest.mark.parametrize("tier", [0, 5, -1, 99, 100])
def test_validate_trust_tier_rejects_out_of_range(tier: int) -> None:
    with pytest.raises(InvalidTrustTierError):
        validate_trust_tier(tier)


@pytest.mark.parametrize("tier", [True, False])
def test_validate_trust_tier_rejects_booleans(tier: bool) -> None:
    # Booleans are ints in Python; they must be rejected explicitly even though
    # bool(True) == 1 would otherwise sneak into the valid set.
    with pytest.raises(InvalidTrustTierError):
        validate_trust_tier(tier)


@pytest.mark.parametrize("tier", [None, "high", "", "abc", [1], {}])
def test_validate_trust_tier_rejects_non_integer(tier: object) -> None:
    with pytest.raises(InvalidTrustTierError):
        validate_trust_tier(tier)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("tier", "expected"),
    [(1.0, 1), (2.5, 2), (3.9, 3)],
)
def test_validate_trust_tier_coerces_in_range_floats(tier: float, expected: int) -> None:
    # Numeric inputs are coerced via int(); in-range results are accepted.
    assert validate_trust_tier(tier) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize("tier", [0.5, 0.99, 5.9])
def test_validate_trust_tier_rejects_floats_coercing_out_of_range(tier: float) -> None:
    with pytest.raises(InvalidTrustTierError):
        validate_trust_tier(tier)  # type: ignore[arg-type]


def test_invalid_trust_tier_error_is_write_invariant_error() -> None:
    assert issubclass(InvalidTrustTierError, WriteInvariantError)
    with pytest.raises(WriteInvariantError):
        validate_trust_tier(7)


# ---------------------------------------------------------------------------
# guard_degraded_row — Requirements 2.4 / 2.5
# ---------------------------------------------------------------------------


def test_guard_degraded_row_rejects_degraded_in_production() -> None:
    with pytest.raises(DegradedEmbeddingNotAllowedError):
        guard_degraded_row(True, environment="production")


@pytest.mark.parametrize("environment", ["Production", "PRODUCTION", "  production  "])
def test_guard_degraded_row_production_match_is_case_and_whitespace_insensitive(
    environment: str,
) -> None:
    with pytest.raises(DegradedEmbeddingNotAllowedError):
        guard_degraded_row(True, environment=environment)


@pytest.mark.parametrize("environment", ["development", "staging", "test", "dev", ""])
def test_guard_degraded_row_allows_degraded_outside_production(environment: str) -> None:
    assert guard_degraded_row(True, environment=environment) is True


@pytest.mark.parametrize("environment", ["production", "development", "staging"])
def test_guard_degraded_row_allows_non_degraded_everywhere(environment: str) -> None:
    # A non-degraded row is always permitted, including in production.
    assert guard_degraded_row(False, environment=environment) is False


def test_guard_degraded_row_coerces_truthy_flag_in_production() -> None:
    # Truthy non-bool degraded marker should still trip the production guard.
    with pytest.raises(DegradedEmbeddingNotAllowedError):
        guard_degraded_row(1, environment="production")  # type: ignore[arg-type]


def test_guard_degraded_row_returns_bool() -> None:
    assert guard_degraded_row(0, environment="development") is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# require_model_id — Requirement 1.4
# ---------------------------------------------------------------------------


def test_require_model_id_returns_value_unchanged() -> None:
    assert require_model_id("text-embedding-3-large") == "text-embedding-3-large"


def test_require_model_id_trims_surrounding_whitespace() -> None:
    assert require_model_id("  bge-m3  ") == "bge-m3"


@pytest.mark.parametrize("model_id", [None, "", "   ", "\t", "\n"])
def test_require_model_id_rejects_blank_or_none(model_id: object) -> None:
    with pytest.raises(MissingModelIdError):
        require_model_id(model_id)


def test_missing_model_id_error_is_write_invariant_error() -> None:
    assert issubclass(MissingModelIdError, WriteInvariantError)
    with pytest.raises(WriteInvariantError):
        require_model_id(None)


# ---------------------------------------------------------------------------
# validate_embedding_row — combined invariants (Requirements 1.3, 1.4, 2.5)
# ---------------------------------------------------------------------------


def test_validate_embedding_row_returns_normalized_values() -> None:
    result = validate_embedding_row(
        dim=8,
        model_id="  text-embedding-3-large  ",
        is_degraded=False,
        expected_dim=8,
        environment="production",
    )
    assert result == {
        "dim": 8,
        "model_id": "text-embedding-3-large",
        "is_degraded": False,
    }


def test_validate_embedding_row_allows_degraded_in_non_production() -> None:
    result = validate_embedding_row(
        dim=8,
        model_id="bge-m3",
        is_degraded=True,
        expected_dim=8,
        environment="development",
    )
    assert result["is_degraded"] is True


def test_validate_embedding_row_rejects_dim_mismatch() -> None:
    with pytest.raises(EmbeddingDimMismatchError):
        validate_embedding_row(
            dim=7,
            model_id="bge-m3",
            expected_dim=8,
            environment="development",
        )


def test_validate_embedding_row_rejects_missing_model_id() -> None:
    with pytest.raises(MissingModelIdError):
        validate_embedding_row(
            dim=8,
            model_id="   ",
            expected_dim=8,
            environment="development",
        )


def test_validate_embedding_row_rejects_degraded_in_production() -> None:
    with pytest.raises(DegradedEmbeddingNotAllowedError):
        validate_embedding_row(
            dim=8,
            model_id="bge-m3",
            is_degraded=True,
            expected_dim=8,
            environment="production",
        )
