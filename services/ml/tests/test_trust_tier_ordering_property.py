"""Property-based tests for trust-tier + recency ranking (Property 21).

Feature: rag-knowledge-pipeline, Property 21: Trust-tier ordering.

Design reference (design.md -> Correctness Properties):
    Property 21: Trust-tier ordering. Among chunks with equal pre-tier
    relevance, a higher-authority chunk (lower tier number) ranks at least as
    high as a lower-authority chunk; ``trust_tier ∈ {1,2,3,4}`` for all
    persisted/surfaced rows.

Requirement 10.2 (requirements.md -> Requirement 10, Acceptance Criteria #2):
    Among retrieved chunks with equal pre-tier relevance, a higher-authority
    chunk (lower ``trust_tier`` number) ranks at least as high as a
    lower-authority chunk, with ``effective_date`` used as a recency signal.

Target: the trust-tier + recency re-rank added to
:class:`clara_ml.rag.store.hybrid_retriever.HybridRetriever` in task 8.4. The
pure ranking helper :meth:`HybridRetriever._apply_tier_recency_order` is
exercised directly (no DB), driven by a fused RRF order + a ``fused_scores``
map exactly as :meth:`HybridRetriever._fuse` invokes it. The surfaced-tier
guarantee is checked through :meth:`HybridRetriever._ranked_to_document`.

Sub-properties covered:

* PERMUTATION -- the re-rank only reorders; the output is a permutation of the
  input candidates (no chunk invented, none dropped).
* MONOTONICITY PRESERVED -- a chunk with a strictly higher fused (pre-tier)
  relevance always ranks ahead of a strictly lower one, regardless of tier or
  date; the tier/recency tie-break only touches equal-relevance chunks.
* TRUST-TIER ORDERING (Req 10.2) -- within an equal-relevance group the surfaced
  order is non-decreasing in (coerced) ``trust_tier``: a lower tier number
  ranks at least as high as a higher one.
* RECENCY + STABILITY -- within an equal-relevance, equal-tier tie the more
  recent ``effective_date`` ranks first and otherwise the original RRF order is
  preserved (the re-rank is stable).
* VALID SURFACED TIER -- every surfaced row carries ``trust_tier ∈ {1,2,3,4}``.

Validates: Requirements 10.2.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

# Import the store package first so it fully initializes before
# hybrid_retriever is pulled in. hybrid_retriever -> score_engine -> embedder ->
# store.schema and store/__init__ -> hybrid_retriever form an import cycle that
# only resolves cleanly when ``clara_ml.rag.store`` loads first; doing so here
# keeps this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.rag.store.hybrid_retriever import HybridRetriever
from clara_ml.rag.store.schema import VALID_TRUST_TIERS
from clara_ml.rag.store.sparse_index import RankedChunk

# Property tests run >= 100 iterations. Deadline disabled: the helper is pure
# but Hypothesis shrinking on the composite generator can exceed the default.
_PBT_SETTINGS = settings(max_examples=200, deadline=None)


def _retriever() -> HybridRetriever:
    """Build a retriever with the P4 tier ranking forced on.

    The dense/sparse/rerank collaborators are never touched by the pure ranking
    helpers under test, so opaque sentinels suffice; ``trust_tier_ranking=True``
    forces the tie-break on regardless of the global feature flag.
    """

    return HybridRetriever(
        embedder=object(),
        sparse_index=object(),
        reranker=object(),
        trust_tier_ranking=True,
    )


# Tiers mix the valid set with missing / out-of-range / non-int values so the
# coercion-to-{1,2,3,4} contract is exercised everywhere the helper sorts/surfaces.
_tier = st.one_of(
    st.integers(min_value=1, max_value=4),
    st.sampled_from([0, 5, -3, 99]),
    st.sampled_from(["1", "3", "bad", ""]),
    st.none(),
)

# effective_date varies across date objects, ISO strings and missing values so
# the recency signal (and the "undated sorts last" rule) is covered.
_eff_date = st.one_of(
    st.none(),
    st.dates(min_value=date(1990, 1, 1), max_value=date(2035, 12, 31)),
    st.dates(min_value=date(1990, 1, 1), max_value=date(2035, 12, 31)).map(lambda d: d.isoformat()),
)


@st.composite
def _ordered_with_scores(draw: st.DrawFn) -> tuple[list[RankedChunk], dict[int, float]]:
    """Generate a fused RRF order + matching ``fused_scores`` map.

    The candidates are grouped into ``equal-relevance`` tie groups: every chunk
    in a group shares one exact fused score, and the groups are laid out in the
    strictly-descending score order :func:`rrf_fuse` would produce. Group scores
    are drawn from distinct integers scaled to be > 1e-3 apart, comfortably above
    the helper's 1e-9 equal-score tolerance, so groups never collapse by accident
    and within-group scores are bit-identical. Within a group the chunks appear
    in an arbitrary "incoming RRF position" order, exercising the stable
    tie-break.
    """

    n_groups = draw(st.integers(min_value=1, max_value=5))
    raw = draw(
        st.lists(
            st.integers(min_value=1, max_value=10_000),
            min_size=n_groups,
            max_size=n_groups,
            unique=True,
        )
    )
    scores_desc = sorted((value / 10_000.0 for value in raw), reverse=True)

    ordered: list[RankedChunk] = []
    fused_scores: dict[int, float] = {}
    next_id = 0
    for group_score in scores_desc:
        group_size = draw(st.integers(min_value=1, max_value=4))
        for _ in range(group_size):
            chunk_id = next_id
            next_id += 1
            chunk = RankedChunk(
                chunk_id=chunk_id,
                score=group_score,
                retriever="dense",
                trust_tier=draw(_tier),
                meta={"effective_date": draw(_eff_date)},
            )
            ordered.append(chunk)
            fused_scores[chunk_id] = group_score
    return ordered, fused_scores


def _groups_in_output_order(
    result: list[RankedChunk], fused_scores: dict[int, float]
) -> dict[float, list[RankedChunk]]:
    """Bucket the re-ranked output by fused score, preserving output order."""

    groups: dict[float, list[RankedChunk]] = defaultdict(list)
    for chunk in result:
        groups[fused_scores[chunk.chunk_id]].append(chunk)
    return groups


# --------------------------------------------------------------------------- #
# Property 21a: permutation + monotonicity preserved + within-tie tier ordering
# --------------------------------------------------------------------------- #
@_PBT_SETTINGS
@given(data=_ordered_with_scores())
def test_property21_tier_ordering_among_equal_relevance(
    data: tuple[list[RankedChunk], dict[int, float]],
) -> None:
    """Lower trust_tier ranks at least as high within an equal-relevance tie.

    Validates: Requirements 10.2 (Property 21).
    """

    ordered, fused_scores = data
    result = _retriever()._apply_tier_recency_order(list(ordered), dict(fused_scores))

    # PERMUTATION: the re-rank only reorders -- no chunk invented or dropped.
    assert Counter(c.chunk_id for c in result) == Counter(c.chunk_id for c in ordered)

    # MONOTONICITY PRESERVED: output fused scores are non-increasing, so a chunk
    # with strictly higher pre-tier relevance never sinks below a lower one.
    out_scores = [fused_scores[c.chunk_id] for c in result]
    assert all(a >= b for a, b in zip(out_scores, out_scores[1:])), (
        f"tie-break broke fused-score monotonicity: {out_scores}"
    )

    # TRUST-TIER ORDERING: within each equal-relevance group the (coerced) tiers
    # are non-decreasing -- a lower tier number ranks at least as high.
    for score, chunks in _groups_in_output_order(result, fused_scores).items():
        tiers = [HybridRetriever._coerce_trust_tier(c.trust_tier) for c in chunks]
        assert tiers == sorted(tiers), (
            f"equal-relevance group (score={score}) not ordered by trust_tier: {tiers}"
        )


# --------------------------------------------------------------------------- #
# Property 21b: recency tie-break + stability within an equal tier
# --------------------------------------------------------------------------- #
@_PBT_SETTINGS
@given(data=_ordered_with_scores())
def test_property21_recency_and_stable_tiebreak(
    data: tuple[list[RankedChunk], dict[int, float]],
) -> None:
    """Equal relevance+tier ties prefer recency, then keep the original RRF order.

    The full re-rank key is ``(fused_rank, tier_asc, -date_ordinal, rrf_pos)``;
    within a group that means a stable sort of the *original* RRF order by
    ``(coerced_tier, -date_ordinal)``. Reconstructing that expected order and
    asserting equality validates both the recency signal and re-rank stability.

    Validates: Requirements 10.2 (Property 21).
    """

    ordered, fused_scores = data
    result = _retriever()._apply_tier_recency_order(list(ordered), dict(fused_scores))

    coerce = HybridRetriever._coerce_trust_tier
    ordinal = HybridRetriever._effective_date_ordinal

    output_groups = _groups_in_output_order(result, fused_scores)
    for score, output_chunks in output_groups.items():
        # The group's chunks in their original (incoming RRF) order.
        original_group = [c for c in ordered if fused_scores[c.chunk_id] == score]
        # Python's sort is stable, so equal (tier, -date) keys keep RRF order.
        expected = sorted(
            original_group,
            key=lambda c: (coerce(c.trust_tier), -ordinal((c.meta or {}).get("effective_date"))),
        )
        assert [c.chunk_id for c in output_chunks] == [c.chunk_id for c in expected], (
            f"recency/stability tie-break mismatch in group score={score}"
        )


# --------------------------------------------------------------------------- #
# Property 21c: every surfaced row carries trust_tier in {1,2,3,4}
# --------------------------------------------------------------------------- #
@_PBT_SETTINGS
@given(data=_ordered_with_scores())
def test_property21_surfaced_tier_always_valid(
    data: tuple[list[RankedChunk], dict[int, float]],
) -> None:
    """No surfaced Document carries a trust_tier outside {1,2,3,4}.

    Validates: Requirements 10.2 (Property 21).
    """

    ordered, _ = data
    retriever = _retriever()
    for chunk in ordered:
        document = retriever._ranked_to_document(chunk)
        assert document.metadata["trust_tier"] in VALID_TRUST_TIERS, (
            f"surfaced trust_tier {document.metadata['trust_tier']!r} not in {sorted(VALID_TRUST_TIERS)} "
            f"(raw tier was {chunk.trust_tier!r})"
        )


# --------------------------------------------------------------------------- #
# Concrete example / edge-case unit tests (pin specific behaviors).
# --------------------------------------------------------------------------- #
def _chunk(chunk_id: int, *, tier, score: float, eff=None) -> RankedChunk:
    return RankedChunk(
        chunk_id=chunk_id,
        score=score,
        retriever="dense",
        trust_tier=tier,
        meta={"effective_date": eff},
    )


def test_equal_relevance_lower_tier_outranks_higher_tier() -> None:
    # Same fused score; tier 3 listed first, tier 1 second.
    ordered = [_chunk(10, tier=3, score=0.5), _chunk(20, tier=1, score=0.5)]
    fused = {10: 0.5, 20: 0.5}
    result = _retriever()._apply_tier_recency_order(ordered, fused)
    # Lower tier (more authoritative) must be promoted ahead.
    assert [c.chunk_id for c in result] == [20, 10]


def test_higher_relevance_never_displaced_by_lower_tier() -> None:
    # Chunk 1 has STRICTLY higher fused relevance but a worse (higher) tier.
    ordered = [_chunk(1, tier=4, score=0.9), _chunk(2, tier=1, score=0.4)]
    fused = {1: 0.9, 2: 0.4}
    result = _retriever()._apply_tier_recency_order(ordered, fused)
    # Monotonicity wins: the higher-relevance chunk stays first despite its tier.
    assert [c.chunk_id for c in result] == [1, 2]


def test_equal_relevance_equal_tier_prefers_more_recent() -> None:
    ordered = [
        _chunk(1, tier=2, score=0.5, eff="2020-01-01"),
        _chunk(2, tier=2, score=0.5, eff="2024-06-01"),
        _chunk(3, tier=2, score=0.5, eff=None),
    ]
    fused = {1: 0.5, 2: 0.5, 3: 0.5}
    result = _retriever()._apply_tier_recency_order(ordered, fused)
    # Most recent first, undated last.
    assert [c.chunk_id for c in result] == [2, 1, 3]


def test_out_of_range_tier_coerced_and_demoted() -> None:
    # tier 99 (out of range) must be treated as lowest authority (4) and demoted.
    ordered = [_chunk(1, tier=99, score=0.5), _chunk(2, tier=2, score=0.5)]
    fused = {1: 0.5, 2: 0.5}
    result = _retriever()._apply_tier_recency_order(ordered, fused)
    assert [c.chunk_id for c in result] == [2, 1]


def test_single_candidate_returned_unchanged() -> None:
    ordered = [_chunk(7, tier=None, score=0.5)]
    result = _retriever()._apply_tier_recency_order(ordered, {7: 0.5})
    assert [c.chunk_id for c in result] == [7]
