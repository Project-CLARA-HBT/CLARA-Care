"""Property-based tests for citation / provenance integrity.

Feature: rag-knowledge-pipeline, Property 20: Citation / provenance integrity.

Design reference (design.md -> Correctness Properties):
    Property 20: Citation / provenance integrity. Every chunk surfaced to
    synthesis carries ``{source, url, trust_tier, effective_date}``; every
    citation in the answer resolves to a retrieved chunk's id/url (no dangling
    citations).

Requirement 7.6 (requirements.md -> Requirement 7, Acceptance Criteria #6):
    WHEN returning results to synthesis, THE Hybrid_Retriever SHALL attach
    provenance metadata ``{source, url, trust_tier, effective_date, RXCUI,
    lang}`` to every returned Document, and every citation in the produced
    answer SHALL resolve to a retrieved chunk's id or url.

Target: :class:`clara_ml.rag.store.hybrid_retriever.HybridRetriever` — its
``retrieve`` maps every fused/reranked candidate to a ``Document`` that carries
the six provenance keys (``HybridRetriever._ranked_to_document``).

Strategy: this test drives the retriever entirely through injected seams so no
database, network or real model is touched:

* A **counting/echoing embedder** records ``embed_query`` calls and echoes the
  query length back as the (otherwise ignored) query vector — confirming exactly
  one embedding call is made per retrieval (no document is re-embedded).
* A **fake dense store** (injected ``dense_search`` seam) and a **fake sparse
  index** (``.search``) each return ``RankedChunk`` rows whose provenance is
  fixed by the generator, so the *source of truth* for every chunk's provenance
  is known up-front.
* The **real** :class:`~clara_ml.rag.retrieval.reranker.NeuralReranker` runs in
  its ``cross_encoder`` strategy with an injected deterministic scorer, so the
  full fuse -> rerank -> trim pipeline executes without any network call.

Each chunk id maps to exactly one provenance bundle (as in the real corpus a
``chunk_id`` is one persisted row), so dense and sparse candidates that share an
id share identical provenance. The property asserts that **every** surfaced
``Document``:

* is traceable to a real candidate chunk (its id is in the dense ∪ sparse union;
  no fabricated chunk),
* carries all six provenance keys, well-formed (``trust_tier ∈ {1,2,3,4}``,
  ``source``/``url`` present), and
* its provenance values equal *exactly* the bundle of the candidate row it came
  from (no provenance is fabricated, swapped, or dropped).

Both the task-5.8 pass-through ranking and the P4 trust-tier ranking
(``trust_tier_ranking=True``) are exercised; provenance integrity must hold for
either ordering.

Validates: Requirements 7.6.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from hypothesis import given, settings
from hypothesis import strategies as st

# Import the store package first so it fully initializes before the retriever /
# reranker modules are pulled in. ``store/__init__`` -> hybrid_retriever ->
# score_engine -> embedder -> store.schema form an import cycle that only
# resolves cleanly when ``clara_ml.rag.store`` loads first; doing so here keeps
# this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.retrieval.reranker import NeuralReranker
from clara_ml.rag.store.hybrid_retriever import HybridRetriever
from clara_ml.rag.store.sparse_index import RankedChunk

# The six provenance keys Requirement 7.6 mandates on every surfaced Document.
PROVENANCE_KEYS = frozenset({"source", "url", "trust_tier", "effective_date", "RXCUI", "lang"})

# Property tests run >= 100 iterations; deadline disabled because the in-process
# rerank/fuse loop timing is environment-dependent and not what we assert on.
_PBT_SETTINGS = settings(max_examples=150, deadline=None)


# --------------------------------------------------------------------------- #
# Injected test doubles (no DB / network / real model)
# --------------------------------------------------------------------------- #
class CountingEmbedder:
    """Counting/echoing embedder: records ``embed_query`` calls, embeds nothing else.

    ``embed_query`` echoes the query length into a fixed-width vector so the
    dense arm has a vector to (ignore and) pass through, while ``embed_batch``
    raises — proving the retriever never re-embeds a document at query time.
    """

    def __init__(self) -> None:
        self.embed_query_calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.embed_query_calls += 1
        return [float(len(str(text or "")))] * 8

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover
        raise AssertionError("HybridRetriever must not embed documents at query time")


class FakeSparseIndex:
    """Fake sparse arm returning pre-built ``RankedChunk`` rows verbatim."""

    def __init__(self, rows: list[RankedChunk]) -> None:
        self._rows = list(rows)

    def search(self, query, *, top_k=50, lang=None, filters=None, **_kw):  # noqa: ANN001, ARG002
        return list(self._rows)


def _deterministic_scorer(query: str, documents: Sequence[Document]) -> Mapping[str, float]:  # noqa: ARG001
    """Injected cross-encoder scorer: deterministic relevance keyed by chunk id.

    Driving the rerank order off the numeric ``doc.id`` keeps ordering fully
    deterministic (so the test is reproducible) while still reordering the
    candidates — provenance must survive whatever permutation the reranker picks.
    """

    return {doc.id: float(int(doc.id)) for doc in documents}


def _make_reranker() -> NeuralReranker:
    return NeuralReranker(
        enabled=True,
        strategy="cross_encoder",
        cross_encoder_scorer=_deterministic_scorer,
        cache_enabled=False,
        top_n=64,
        timeout_ms=5_000,
    )


# --------------------------------------------------------------------------- #
# Generators
# --------------------------------------------------------------------------- #
_SOURCES = ["pubmed", "openfda", "dailymed", "who", "byt", "dav", "rxnorm"]
_LANGS = ["vi", "en"]
_slug = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=12)
_rxcui = st.lists(st.integers(min_value=0, max_value=99_999).map(str), max_size=3, unique=True)
_eff_date = st.one_of(st.none(), st.dates().map(lambda d: d.isoformat()))


@st.composite
def _scenario(draw: st.DrawFn):
    """Build a retrieval scenario with a known provenance source-of-truth.

    Returns ``(dense_rows, sparse_rows, provenance_by_id, candidate_ids, top_k,
    tier_ranking)`` where each ``chunk_id`` maps to exactly one provenance
    bundle, and the dense/sparse arms are (independently permuted, independently
    truncated) subsets of one shared chunk pool — so overlapping, disjoint and
    empty-arm cases are all reachable.
    """
    ids = draw(
        st.lists(st.integers(min_value=1, max_value=9_999), min_size=1, max_size=8, unique=True)
    )

    provenance_by_id: dict[int, dict] = {}
    fields_by_id: dict[int, dict] = {}
    for cid in ids:
        source = draw(st.sampled_from(_SOURCES))
        url = f"https://example.org/{draw(_slug)}"
        trust_tier = draw(st.sampled_from([1, 2, 3, 4]))
        effective_date = draw(_eff_date)
        rxcui = draw(_rxcui)
        lang = draw(st.sampled_from(_LANGS))

        # The bundle the surfaced Document MUST carry (Requirement 7.6).
        provenance_by_id[cid] = {
            "source": source,
            "url": url,
            "trust_tier": trust_tier,
            "effective_date": effective_date,
            "RXCUI": rxcui,
            "lang": lang,
        }
        # How that bundle is laid out on the persisted chunk row: provenance
        # lives in meta_json; trust_tier + lang are structural columns.
        fields_by_id[cid] = {
            "trust_tier": trust_tier,
            "lang": lang,
            "meta": {
                "source": source,
                "url": url,
                "effective_date": effective_date,
                "RXCUI": rxcui,
            },
            "document_id": cid * 10,
            "section_path": f"sec/{cid}",
            "section_type": draw(st.sampled_from(["body", "warnings", "interactions", ""])),
            "text": draw(st.text(min_size=0, max_size=40)),
        }

    def _chunk(cid: int, *, retriever: str, score: float) -> RankedChunk:
        f = fields_by_id[cid]
        return RankedChunk(
            chunk_id=cid,
            score=score,
            retriever=retriever,
            document_id=f["document_id"],
            section_path=f["section_path"],
            section_type=f["section_type"],
            lang=f["lang"],
            trust_tier=f["trust_tier"],
            text=f["text"],
            meta=dict(f["meta"]),
        )

    dense_perm = draw(st.permutations(ids))
    sparse_perm = draw(st.permutations(ids))
    dense_ids = dense_perm[: draw(st.integers(min_value=0, max_value=len(ids)))]
    sparse_ids = sparse_perm[: draw(st.integers(min_value=0, max_value=len(ids)))]

    dense_rows = [
        _chunk(cid, retriever="dense", score=draw(st.floats(0.0, 1.0))) for cid in dense_ids
    ]
    sparse_rows = [
        _chunk(cid, retriever="bm25", score=draw(st.floats(0.0, 10.0))) for cid in sparse_ids
    ]

    candidate_ids = {str(cid) for cid in (*dense_ids, *sparse_ids)}
    top_k = draw(st.integers(min_value=1, max_value=len(ids) + 2))
    tier_ranking = draw(st.booleans())
    return dense_rows, sparse_rows, provenance_by_id, candidate_ids, top_k, tier_ranking


# --------------------------------------------------------------------------- #
# Property 20: citation / provenance integrity
# --------------------------------------------------------------------------- #
# Feature: rag-knowledge-pipeline, Property 20: Citation / provenance integrity
# Validates: Requirements 7.6
@_PBT_SETTINGS
@given(
    scenario=_scenario(),
    query=st.text(min_size=1, max_size=24).filter(lambda value: bool(value.strip())),
)
def test_property20_every_result_carries_traceable_provenance(scenario, query: str) -> None:
    dense_rows, sparse_rows, provenance_by_id, candidate_ids, top_k, tier_ranking = scenario

    embedder = CountingEmbedder()

    def dense_search(q_vec, n, filters):  # noqa: ANN001, ARG001
        return list(dense_rows)

    retriever = HybridRetriever(
        embedder=embedder,
        sparse_index=FakeSparseIndex(sparse_rows),
        reranker=_make_reranker(),
        dense_search=dense_search,
        query_expander=None,
        trust_tier_ranking=tier_ranking,
    )

    results = retriever.retrieve(query, top_k)

    # Exactly one embedding call (only the query is embedded; no doc re-embed).
    assert embedder.embed_query_calls == 1

    # At most top_k surfaced, and never more candidates than exist.
    assert len(results) <= top_k

    seen_ids: list[str] = []
    for doc in results:
        seen_ids.append(doc.id)
        md = doc.metadata

        # Traceable to a real candidate chunk — no fabricated provenance.
        assert doc.id in candidate_ids, (
            f"surfaced id {doc.id!r} is not in the dense∪sparse candidate union {candidate_ids}"
        )

        # Complete: all six provenance keys present (no provenance dropped).
        assert PROVENANCE_KEYS <= md.keys(), (
            f"missing provenance keys {PROVENANCE_KEYS - md.keys()} on Document {doc.id}"
        )

        expected = provenance_by_id[int(doc.id)]
        # Values match the candidate row they came from (no provenance swapped).
        assert md["source"] == expected["source"]
        assert md["url"] == expected["url"]
        assert md["trust_tier"] == expected["trust_tier"]
        assert md["effective_date"] == expected["effective_date"]
        assert md["RXCUI"] == expected["RXCUI"]
        assert md["lang"] == expected["lang"]

        # Well-formed: trust_tier in the authority domain; source/url present.
        assert md["trust_tier"] in {1, 2, 3, 4}
        assert md["source"] != ""
        assert md["url"] != ""

    # No chunk is surfaced twice (fusion dedupes by id; rerank is a permutation).
    assert len(seen_ids) == len(set(seen_ids))
    # The whole result set is contained in the candidate union (no fabrication).
    assert set(seen_ids) <= candidate_ids


# --------------------------------------------------------------------------- #
# Concrete example / edge-case unit tests (complement the property test).
# --------------------------------------------------------------------------- #
def _retriever_for(dense_rows, sparse_rows, *, tier_ranking=False) -> HybridRetriever:
    def dense_search(q_vec, n, filters):  # noqa: ANN001, ARG001
        return list(dense_rows)

    return HybridRetriever(
        embedder=CountingEmbedder(),
        sparse_index=FakeSparseIndex(sparse_rows),
        reranker=_make_reranker(),
        dense_search=dense_search,
        query_expander=None,
        trust_tier_ranking=tier_ranking,
    )


def test_provenance_keys_always_present_even_when_meta_incomplete() -> None:
    """A chunk with no provenance in meta still gets all six keys (defaults)."""
    bare = RankedChunk(chunk_id=7, score=1.0, retriever="dense", lang="", meta={})
    retriever = _retriever_for([bare], [])

    [doc] = retriever.retrieve("aspirin", top_k=5)
    md = doc.metadata
    assert PROVENANCE_KEYS <= md.keys()
    assert md["source"] == ""
    assert md["url"] == ""
    assert md["effective_date"] is None
    assert md["RXCUI"] == []
    assert md["lang"] == ""


def test_rxcui_lowercase_meta_key_is_honored() -> None:
    """RXCUI provenance falls back to a lowercase ``rxcui`` meta key."""
    row = RankedChunk(
        chunk_id=11,
        score=1.0,
        retriever="dense",
        lang="en",
        trust_tier=2,
        meta={"source": "rxnorm", "url": "https://r/1", "rxcui": ["1191"]},
    )
    [doc] = _retriever_for([row], []).retrieve("warfarin", top_k=3)
    assert doc.metadata["RXCUI"] == ["1191"]


def test_lang_falls_back_to_meta_when_column_empty() -> None:
    """When the chunk's ``lang`` column is empty, provenance uses ``meta['lang']``."""
    row = RankedChunk(
        chunk_id=21,
        score=1.0,
        retriever="dense",
        lang="",
        trust_tier=1,
        meta={"source": "byt", "url": "https://b/1", "lang": "vi"},
    )
    [doc] = _retriever_for([row], []).retrieve("paracetamol", top_k=3)
    assert doc.metadata["lang"] == "vi"


def test_trust_tier_coerced_into_domain_when_tier_ranking_enabled() -> None:
    """With P4 tier ranking on, an out-of-range trust_tier is coerced to {1..4}."""
    row = RankedChunk(
        chunk_id=31,
        score=1.0,
        retriever="dense",
        lang="en",
        trust_tier=99,  # out of the {1,2,3,4} domain
        meta={"source": "web_crawl", "url": "https://w/1"},
    )
    [doc] = _retriever_for([row], [], tier_ranking=True).retrieve("ibuprofen", top_k=3)
    assert doc.metadata["trust_tier"] in {1, 2, 3, 4}


def test_shared_chunk_id_surfaces_single_consistent_provenance() -> None:
    """A chunk corroborated by both arms surfaces once with one provenance bundle."""
    dense = RankedChunk(
        chunk_id=41,
        score=0.9,
        retriever="dense",
        lang="en",
        trust_tier=1,
        meta={"source": "openfda", "url": "https://f/41", "RXCUI": ["42"]},
    )
    sparse = RankedChunk(
        chunk_id=41,
        score=5.0,
        retriever="bm25",
        lang="en",
        trust_tier=1,
        meta={"source": "openfda", "url": "https://f/41", "RXCUI": ["42"]},
    )
    results = _retriever_for([dense], [sparse]).retrieve("metformin", top_k=5)
    assert [d.id for d in results] == ["41"]
    md = results[0].metadata
    assert md["source"] == "openfda"
    assert md["url"] == "https://f/41"
    assert md["RXCUI"] == ["42"]
    assert md["trust_tier"] == 1
