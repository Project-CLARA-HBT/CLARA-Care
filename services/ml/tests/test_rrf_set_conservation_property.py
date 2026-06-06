"""Property-based tests for RRF set conservation.

Feature: rag-knowledge-pipeline, Property 14: RRF set conservation.

Design reference (design.md -> Correctness Properties):
    Property 14: RRF set conservation. The fused output is exactly a
    permutation of the union of dense and sparse candidates -- no fabricated or
    dropped chunks.

Requirement 7.3 (requirements.md -> Requirement 7, Acceptance Criteria #3):
    WHEN fusing candidate lists, THE RRF_Fuser SHALL output a permutation of the
    union of the dense and sparse candidates, adding no fabricated chunk and
    dropping no candidate.

Target: :func:`clara_ml.rag.retrieval.score_engine.rrf_fuse`.

``rrf_fuse`` is a pure function that returns an ordered (best-first) list of
the *representative* candidate object for each distinct id seen across the two
input lists. The identity of a candidate is its ``.id`` (Document) or first
tuple element (``(id, score)``), normalized to ``str`` -- exactly what
``rrf_fuse`` does internally via ``_candidate_id``.

Set conservation is observed purely through the **set of ids** in the output:

* No candidate is dropped -- every id in ``dense`` or ``sparse`` is present.
* No candidate is fabricated -- every output id came from an input list.
* No duplicates -- a chunk that appears in BOTH lists (corroboration) is not
  penalized by being dropped, nor duplicated; it appears exactly once.
* The output is a *permutation* of that union -- its length equals the number
  of distinct ids, and every output element is an object taken verbatim from
  the inputs (never a synthesized candidate).

Both overlapping and disjoint input lists are exercised.

Validates: Requirements 7.3.
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

from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.retrieval.score_engine import rrf_fuse

# A candidate is an (id, score) tuple. The score is generated purely to confirm
# rrf_fuse conserves the candidate *set* irrespective of these incoming scores.
_score = st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)


@st.composite
def _overlapping_lists(
    draw: st.DrawFn,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Two best-first ranked lists drawn from a shared id pool.

    Each list is an independently permuted, independently truncated subset of
    one shared pool, so the lists overlap to varying degrees: fully shared ids,
    ids unique to one list, and (by chance) disjoint draws are all reachable.
    Either list may also be empty, exercising the empty-input edge case.
    """
    pool = draw(
        st.lists(st.integers(min_value=0, max_value=99), min_size=0, max_size=8, unique=True)
    )

    dense_perm = draw(st.permutations(pool))
    sparse_perm = draw(st.permutations(pool))
    dense_len = draw(st.integers(min_value=0, max_value=len(pool)))
    sparse_len = draw(st.integers(min_value=0, max_value=len(pool)))

    dense = [(cid, draw(_score)) for cid in dense_perm[:dense_len]]
    sparse = [(cid, draw(_score)) for cid in sparse_perm[:sparse_len]]
    return dense, sparse


@st.composite
def _disjoint_lists(
    draw: st.DrawFn,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Two best-first ranked lists whose id sets are guaranteed disjoint.

    A single pool of unique ids is split into two halves so that no id appears
    in both lists. This isolates the "pure union" case: the fused set must be
    exactly the concatenation of both id sets, with nothing merged away.
    """
    pool = draw(
        st.lists(st.integers(min_value=0, max_value=199), min_size=0, max_size=10, unique=True)
    )
    split = draw(st.integers(min_value=0, max_value=len(pool)))
    dense_ids = draw(st.permutations(pool[:split]))
    sparse_ids = draw(st.permutations(pool[split:]))

    dense = [(cid, draw(_score)) for cid in dense_ids]
    sparse = [(cid, draw(_score)) for cid in sparse_ids]
    return dense, sparse


def _ids(candidates: list[tuple[int, float]]) -> list[str]:
    """Normalized (str) ids of a candidate list, mirroring rrf_fuse identity."""
    return [str(cid) for cid, _ in candidates]


def _assert_set_conservation(
    dense: list[tuple[int, float]],
    sparse: list[tuple[int, float]],
) -> None:
    """Core Property 14 assertions shared by the overlapping/disjoint cases."""
    fused = rrf_fuse(dense, sparse)
    fused_ids = [str(candidate[0]) for candidate in fused]

    dense_ids = _ids(dense)
    sparse_ids = _ids(sparse)
    union = set(dense_ids) | set(sparse_ids)

    # No duplicates: every distinct id appears exactly once in the output.
    assert len(fused_ids) == len(set(fused_ids)), (
        f"fused output contains duplicate ids: {fused_ids}"
    )
    # Set conservation: output id set == union of input id sets (no dropped,
    # no fabricated). Corroborated ids (in both lists) survive as a single item.
    assert set(fused_ids) == union, (
        f"fused id set {set(fused_ids)} != union of inputs {union} "
        f"(dropped={union - set(fused_ids)}, fabricated={set(fused_ids) - union})"
    )
    # Permutation: length equals the number of distinct ids in the union.
    assert len(fused_ids) == len(union), (
        f"fused length {len(fused_ids)} != union size {len(union)}"
    )
    # Representatives are objects taken verbatim from the inputs, never invented.
    inputs_by_id: dict[str, object] = {}
    for candidate in (*sparse, *dense):  # dense last so it wins id collisions
        inputs_by_id[str(candidate[0])] = candidate
    for candidate in fused:
        cid = str(candidate[0])
        assert candidate is inputs_by_id[cid], (
            f"fused candidate for id {cid} is not the verbatim input object"
        )


# Feature: rag-knowledge-pipeline, Property 14: RRF set conservation
# Validates: Requirements 7.3
@settings(max_examples=200, deadline=None)
@given(lists=_overlapping_lists())
def test_property14_set_conservation_overlapping(
    lists: tuple[list[tuple[int, float]], list[tuple[int, float]]],
) -> None:
    dense, sparse = lists
    _assert_set_conservation(dense, sparse)


# Feature: rag-knowledge-pipeline, Property 14: RRF set conservation
# Validates: Requirements 7.3
@settings(max_examples=200, deadline=None)
@given(lists=_disjoint_lists())
def test_property14_set_conservation_disjoint(
    lists: tuple[list[tuple[int, float]], list[tuple[int, float]]],
) -> None:
    dense, sparse = lists
    _assert_set_conservation(dense, sparse)
    # For disjoint inputs the union is exactly the two id sets combined; every
    # candidate from both lists must survive fusion with nothing merged away.
    fused_ids = {str(candidate[0]) for candidate in rrf_fuse(dense, sparse)}
    assert fused_ids == set(_ids(dense)) | set(_ids(sparse))


# Feature: rag-knowledge-pipeline, Property 14: RRF set conservation
# Validates: Requirements 7.3
@settings(max_examples=200, deadline=None)
@given(lists=_overlapping_lists())
def test_property14_corroborated_ids_appear_exactly_once(
    lists: tuple[list[tuple[int, float]], list[tuple[int, float]]],
) -> None:
    """A chunk present in BOTH lists is neither dropped nor duplicated.

    Corroboration must never be penalized: an id appearing in both the dense
    and sparse lists shows up exactly once in the fused output (count == 1),
    never zero (dropped) and never twice (duplicated).
    """
    dense, sparse = lists
    shared = set(_ids(dense)) & set(_ids(sparse))
    fused_ids = [str(candidate[0]) for candidate in rrf_fuse(dense, sparse)]

    for cid in shared:
        assert fused_ids.count(cid) == 1, (
            f"corroborated id {cid} (in both lists) appears "
            f"{fused_ids.count(cid)} times in fused output, expected exactly 1"
        )


# ---------------------------------------------------------------------------
# Concrete example/edge-case unit tests (Document candidates + boundaries).
# These complement the property tests by pinning specific behaviors and by
# exercising the Document branch of rrf_fuse's identity resolution.
# ---------------------------------------------------------------------------


def _doc(doc_id: str) -> Document:
    return Document(id=doc_id, text=f"text-{doc_id}", metadata={})


def test_disjoint_documents_union_is_conserved() -> None:
    dense = [_doc("a"), _doc("b")]
    sparse = [_doc("c"), _doc("d")]
    fused = rrf_fuse(dense, sparse)

    assert {d.id for d in fused} == {"a", "b", "c", "d"}
    assert len(fused) == 4


def test_fully_overlapping_documents_dedupe_to_single_set() -> None:
    dense = [_doc("a"), _doc("b"), _doc("c")]
    # Same ids surfaced by the sparse list (corroboration on every chunk).
    sparse = [_doc("c"), _doc("b"), _doc("a")]
    fused = rrf_fuse(dense, sparse)

    assert sorted(d.id for d in fused) == ["a", "b", "c"]
    assert len(fused) == 3  # no duplicates despite appearing in both lists


def test_id_collision_keeps_dense_representative() -> None:
    dense_a = _doc("a")
    sparse_a = _doc("a")
    fused = rrf_fuse([dense_a], [sparse_a])

    assert len(fused) == 1
    # Dense list wins when ids collide (first-seen representative).
    assert fused[0] is dense_a


def test_empty_inputs_conserve_the_union() -> None:
    only_dense = rrf_fuse([_doc("a"), _doc("b")], [])
    assert {d.id for d in only_dense} == {"a", "b"}

    only_sparse = rrf_fuse([], [_doc("x")])
    assert {d.id for d in only_sparse} == {"x"}

    assert rrf_fuse([], []) == []
