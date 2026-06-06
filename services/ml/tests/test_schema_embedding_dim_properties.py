"""Property-based tests for the embedding dimension invariant.

Feature: rag-knowledge-pipeline, Property 11: Embedding dimension invariant.

Design reference (design.md → Correctness Properties):
    Property 11: Embedding dimension invariant. Every persisted dense embedding
    has ``dim == RAG_EMBEDDING_DIM``; writes with mismatched dimensions are
    rejected.

Requirement 1.3 (requirements.md → Requirement 1, Acceptance Criteria #3):
    WHEN a dense embedding row is written, IF its dimension is not equal to
    ``RAG_EMBEDDING_DIM``, THEN THE Document_Store SHALL reject the write.

Target: :func:`clara_ml.rag.store.schema.assert_embedding_dim`.

Strategy: the configured dimension is read from the schema helper
:func:`clara_ml.rag.store.schema.configured_embedding_dim` (which mirrors
``settings.rag_embedding_dim``). We generate candidate dimensions *around* that
configured value as ``target + offset`` so both the equal case (offset 0) and a
dense band of not-equal cases are exercised, and assert:

* ``assert_embedding_dim(dim)`` returns ``dim`` IFF ``dim == configured`` and
* it raises :class:`EmbeddingDimMismatchError` otherwise.

A companion property feeds non-integer / un-coercible inputs (``None``, alpha
strings, lists, dicts, bare objects) and asserts they are likewise rejected
with :class:`EmbeddingDimMismatchError`.

Validates: Requirements 1.3.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.rag.store.schema import (
    EmbeddingDimMismatchError,
    assert_embedding_dim,
    configured_embedding_dim,
)

_CONFIGURED_DIM = configured_embedding_dim()

# Candidate integer dimensions clustered around the configured value. offset==0
# yields the equal case; every other offset yields a mismatch. The band is wide
# enough to include negative and zero dimensions (still integers, still
# mismatches) without drifting back onto the configured value.
_dim_offsets = st.integers(min_value=-_CONFIGURED_DIM - 50, max_value=512)

# Inputs that cannot be coerced to int via ``int(value)`` and therefore must be
# rejected. Each branch is constructed to be guaranteed un-coercible:
#   * None                     -> TypeError
#   * alpha-only, non-empty str-> ValueError ("abc" is never a valid int)
#   * list / dict              -> TypeError
#   * bare object()            -> TypeError
_non_int_inputs = st.one_of(
    st.none(),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8),
    st.lists(st.integers(), max_size=3),
    st.dictionaries(st.text(max_size=3), st.integers(), max_size=3),
    st.builds(object),
)


# Feature: rag-knowledge-pipeline, Property 11: Embedding dimension invariant
# Validates: Requirements 1.3
@settings(max_examples=200, deadline=None)
@given(offset=_dim_offsets)
def test_property11_assert_embedding_dim_accepts_iff_configured(offset: int) -> None:
    dim = _CONFIGURED_DIM + offset

    if dim == _CONFIGURED_DIM:
        # Equal case: returns the validated dimension unchanged.
        assert assert_embedding_dim(dim) == dim
    else:
        # Mismatch case: rejected.
        with pytest.raises(EmbeddingDimMismatchError):
            assert_embedding_dim(dim)


# Feature: rag-knowledge-pipeline, Property 11: Embedding dimension invariant
# Validates: Requirements 1.3
@settings(max_examples=200, deadline=None)
@given(value=_non_int_inputs)
def test_property11_assert_embedding_dim_rejects_non_int(value: object) -> None:
    with pytest.raises(EmbeddingDimMismatchError):
        assert_embedding_dim(value)  # type: ignore[arg-type]
