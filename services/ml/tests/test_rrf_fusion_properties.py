"""Property-based tests for RRF fusion monotonicity / corroboration.

Feature: rag-knowledge-pipeline, Property 13: RRF fusion monotonicity.

Design reference (design.md -> Correctness Properties):
    Property 13: RRF fusion monotonicity. For any two candidate lists, if chunk
    ``c`` ranks no worse than chunk ``c'`` in both lists, then
    ``rrf_score(c) >= rrf_score(c')``; a chunk corroborated by both lists never
    scores below the same chunk appearing in only one list at equal rank.

Requirement 7.4 (requirements.md -> Requirement 7, Acceptance Criteria #4):
    IF a chunk ranks no worse than another chunk in both candidate lists, THEN
    THE RRF_Fuser SHALL assign the first chunk a fused score greater than or
    equal to that of the second chunk, so that corroboration is never
    penalized.

Target: :func:`clara_ml.rag.retrieval.score_engine.rrf_fuse`.

``rrf_fuse`` is a pure function that returns an ordered (best-first)
*permutation* of the union of its two input lists; it does not expose the raw
fused scores. We therefore observe the property through the **output order**:
since the output is sorted by descending fused score, ``rrf_score(c) >=
rrf_score(c')`` is equivalent to ``position(c) <= position(c')`` in the fused
list.

Two complementary properties are exercised:

* *Monotonicity* -- generate two ranked lists (each a permutation of unique
  ids). For every pair of ids ``c``, ``c'`` that appear in BOTH lists where
  ``c`` ranks no worse than ``c'`` in each list (1-based
  ``rank_dense(c) <= rank_dense(c')`` and ``rank_sparse(c) <= rank_sparse(c')``),
  assert ``c`` is positioned no later than ``c'`` in the fused output.
* *Corroboration* -- controlled lists where ``both`` appears in BOTH lists at
  rank ``r`` while ``single`` appears in only ONE list at rank ``r`` (and even
  gets a *better* rank than ``both`` in the shared list). The corroborated id
  must still be positioned ahead of the single-list id: corroboration adds a
  positive reciprocal term, so it can only raise a score, never lower it.

Validates: Requirements 7.4.
"""

from __future__ import annotations

# Import the store package first so it fully initializes before score_engine is
# pulled in as a top-level import. score_engine -> embedder -> store.schema and
# store/__init__ -> hybrid_retriever -> score_engine form an import cycle that
# only resolves when ``clara_ml.rag.store`` loads first; doing so here keeps
# this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.rag.retrieval.score_engine import rrf_fuse

# A candidate is an (id, score) tuple. The score is generated purely to confirm
# rrf_fuse ranks by list *position*, not by these incoming scores.
_score = st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)


@st.composite
def _two_ranked_lists(draw: st.DrawFn) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Generate two best-first ranked lists of unique (id, score) candidates.

    A shared pool of unique integer ids is drawn; each list is an independently
    permuted, independently truncated subset of that pool. Truncation lets some
    ids appear in only one list (exercising the "present in both" filter) while
    permutation varies the per-list ranks.
    """
    pool = draw(st.lists(st.integers(min_value=0, max_value=99), min_size=2, max_size=7, unique=True))

    dense_perm = draw(st.permutations(pool))
    sparse_perm = draw(st.permutations(pool))
    dense_len = draw(st.integers(min_value=1, max_value=len(pool)))
    sparse_len = draw(st.integers(min_value=1, max_value=len(pool)))

    dense = [(cid, draw(_score)) for cid in dense_perm[:dense_len]]
    sparse = [(cid, draw(_score)) for cid in sparse_perm[:sparse_len]]
    return dense, sparse


@st.composite
def _corroboration_lists(
    draw: st.DrawFn,
) -> tuple[int, int, list[tuple[int, float]], list[tuple[int, float]]]:
    """Build controlled lists isolating corroboration at a shared rank ``r``.

    ``single`` sits at rank ``r`` in the dense list and appears in no other
    list. ``both`` sits at rank ``r`` in the sparse list AND at rank ``r + 1``
    in the dense list (a strictly *worse* dense rank than ``single``). So
    ``single`` out-ranks ``both`` in the only list they share, yet ``both`` is
    corroborated by both lists. The reciprocal contribution from the sparse
    list must push ``both`` ahead of ``single`` regardless.
    """
    r = draw(st.integers(min_value=1, max_value=5))
    fillers_needed = (r - 1) + (r - 1)
    ids = draw(
        st.lists(
            st.integers(min_value=0, max_value=200),
            min_size=fillers_needed + 2,
            max_size=fillers_needed + 2,
            unique=True,
        )
    )
    both_id, single_id = ids[0], ids[1]
    dense_fillers = ids[2 : 2 + (r - 1)]
    sparse_fillers = ids[2 + (r - 1) : 2 + 2 * (r - 1)]

    # dense: [fillers...](r-1) + single(rank r) + both(rank r+1)
    dense_ids = [*dense_fillers, single_id, both_id]
    # sparse: [fillers...](r-1) + both(rank r)
    sparse_ids = [*sparse_fillers, both_id]

    dense = [(cid, draw(_score)) for cid in dense_ids]
    sparse = [(cid, draw(_score)) for cid in sparse_ids]
    return both_id, single_id, dense, sparse


def _positions(fused: list[tuple[int, float]]) -> dict[str, int]:
    """Map each fused candidate's id (normalized to str, as rrf_fuse does) to
    its 0-based position in the fused output."""
    return {str(candidate[0]): index for index, candidate in enumerate(fused)}


# Feature: rag-knowledge-pipeline, Property 13: RRF fusion monotonicity
# Validates: Requirements 7.4
@settings(max_examples=300, deadline=None)
@given(lists=_two_ranked_lists())
def test_property13_rrf_fusion_monotonicity(
    lists: tuple[list[tuple[int, float]], list[tuple[int, float]]],
) -> None:
    dense, sparse = lists
    fused = rrf_fuse(dense, sparse)
    position = _positions(fused)

    rank_dense = {str(cid): rank for rank, (cid, _) in enumerate(dense, start=1)}
    rank_sparse = {str(cid): rank for rank, (cid, _) in enumerate(sparse, start=1)}

    # Only ids present in BOTH lists have a defined rank in each list.
    both_present = sorted(set(rank_dense) & set(rank_sparse))

    for c in both_present:
        for c_prime in both_present:
            if c == c_prime:
                continue
            # c ranks no worse than c' in BOTH lists (smaller rank == better).
            if rank_dense[c] <= rank_dense[c_prime] and rank_sparse[c] <= rank_sparse[c_prime]:
                # Equivalent to rrf_score(c) >= rrf_score(c'): c is positioned
                # no later than c' in the score-descending fused output.
                assert position[c] <= position[c_prime], (
                    f"id {c} ranks no worse than {c_prime} in both lists "
                    f"(dense {rank_dense[c]}<={rank_dense[c_prime]}, "
                    f"sparse {rank_sparse[c]}<={rank_sparse[c_prime]}) "
                    f"but was fused later (pos {position[c]} > {position[c_prime]})"
                )


# Feature: rag-knowledge-pipeline, Property 13: RRF fusion monotonicity
# Validates: Requirements 7.4
@settings(max_examples=300, deadline=None)
@given(scenario=_corroboration_lists())
def test_property13_corroboration_never_penalized(
    scenario: tuple[int, int, list[tuple[int, float]], list[tuple[int, float]]],
) -> None:
    both_id, single_id, dense, sparse = scenario
    fused = rrf_fuse(dense, sparse)
    position = _positions(fused)

    both_key = str(both_id)
    single_key = str(single_id)

    assert both_key in position
    assert single_key in position
    # The id corroborated by BOTH lists at rank r outranks the id present in
    # only ONE list at the same rank r, even though the single-list id had a
    # better rank in the one list they share. Corroboration is never penalized.
    assert position[both_key] < position[single_key], (
        f"corroborated id {both_id} (in both lists) should fuse ahead of "
        f"single-list id {single_id}, but positions were "
        f"{position[both_key]} vs {position[single_key]}"
    )
