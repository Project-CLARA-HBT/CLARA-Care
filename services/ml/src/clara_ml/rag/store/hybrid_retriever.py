"""Online hybrid retriever over the persistent corpus (task 5.8).

This module is the ``Hybrid_Retriever`` component from ``design.md`` /
Requirement 7 (P2). It is the *online* half of the retrieval split: the offline
ingestion plane embeds documents **once** and persists dense vectors
(``kb_chunk_embeddings``), BM25 ``tsvector`` and bge-m3 sparse terms; at query
time this retriever embeds **only the query** and fuses two logically parallel
retrieval arms over that persistent index:

* **Dense ANN** via pgvector cosine distance (``embedding <=> :qvec``) over
  ``kb_chunk_embeddings`` JOIN ``kb_chunks`` (:meth:`HybridRetriever._dense_search`).
* **Sparse / BM25** via the injected :class:`~clara_ml.rag.store.sparse_index.SparseIndex`
  (real ``ts_rank_cd`` BM25, language-aware).

The two candidate lists are fused with the existing Reciprocal Rank Fusion
scaffolding (:func:`~clara_ml.rag.retrieval.score_engine.rrf_fuse`, reusing
``_RRF_K=60``) and the fused top-N is reranked by the injected cross-encoder
reranker. The result is a list of :class:`~clara_ml.rag.retrieval.domain.Document`
objects whose metadata carries the provenance downstream guardrails / FIDES and
citations need — ``{source, url, trust_tier, effective_date, RXCUI, lang}`` — so
the existing safety layer is unchanged.

Design constraints honoured here (mirroring ``document_store.py`` /
``sparse_index.py``):

* **Query-only embedding (Property 12).** :meth:`HybridRetriever.retrieve`
  makes *exactly one* ``embed_query`` call and never re-embeds any document at
  query time. (The cross-encoder reranker owns its own model / embedder; it does
  not call this retriever's embedder.)
* **No fabrication (Property 20 / Req 7.7).** The returned set is always a
  subset of the union of the dense and sparse candidates — fusion and reranking
  only reorder/trim, they never invent chunks.
* **Provenance integrity (Property 20 / Req 7.6).** Every returned ``Document``
  carries the six provenance keys, mapped from the persisted chunk row, so the
  downstream FIDES / citation path stays unchanged.
* **Import-safe & DB-injected.** Importing this module opens no database
  connection and runs no DDL. The dense arm is backed by an injected
  ``session_factory`` (a :class:`~sqlalchemy.orm.sessionmaker` or any zero-arg
  callable returning a :class:`~sqlalchemy.orm.Session`); a live database is
  required only when :meth:`HybridRetriever._dense_search` actually executes.
* **Parameterized, compile-testable SQL.** The dense statement is built with
  :func:`sqlalchemy.text` and bound parameters (the query vector, the optional
  trust-tier floor and the optional filters). pgvector-only operators
  (``<=>``, ``::vector``) live inside the opaque text fragment, so the statement
  can be constructed and compiled in a unit test without a live pgvector.
* **Optional query expander.** A :class:`Query_Expander` is *injected* and is
  ``None`` (no-op) for P2; P3 supplies the real one. When present it produces
  the canonical query that is embedded and the expanded terms used for sparse
  search; it never changes the embed-once-the-query guarantee.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from clara_ml.config import settings
from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.retrieval.score_engine import RRF_K, rrf_fuse
from clara_ml.rag.store.schema import VALID_TRUST_TIERS
from clara_ml.rag.store.sparse_index import RankedChunk, SparseFilters, SparseIndex

if TYPE_CHECKING:  # pragma: no cover - typing-only imports (no runtime cost)
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

    from clara_ml.rag.embedder import HttpEmbeddingClient
    from clara_ml.rag.retrieval.reranker import NeuralReranker

__all__ = [
    "RetrievalFilters",
    "HybridRetriever",
]


# Authority default for chunks whose ``trust_tier`` is missing / out of range.
# Lower number == higher authority, so an unverified tier defaults to the
# *lowest* authority (4) and can never out-rank a known-authoritative chunk
# (Requirement 10.2).
_LOWEST_AUTHORITY_TIER = max(VALID_TRUST_TIERS)

# Absolute tolerance for treating two RRF fused scores as "equal". RRF score
# gaps between genuinely distinct ranks are orders of magnitude larger than this
# (for k=60 the smallest adjacent-rank delta is ~1e-4), so this only absorbs
# floating-point summation noise and never merges genuinely different scores.
_RRF_SCORE_TOL = 1e-9


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RetrievalFilters:
    """Optional online retrieval filters shared by the dense and sparse arms.

    ``trust_tier_max`` keeps only chunks whose ``trust_tier`` number is ``<=``
    the floor (lower number == higher authority), mirroring the dense path's
    ``tier_floor`` predicate in ``design.md``. ``lang`` doubles as the language
    hint for the BM25 FTS configuration. All fields default to ``None`` meaning
    "no constraint".
    """

    trust_tier_max: int | None = None
    lang: str | None = None
    section_type: str | None = None
    document_id: int | None = None

    def to_sparse_filters(self) -> SparseFilters:
        """Project onto the :class:`SparseFilters` shape the BM25 arm consumes."""

        return SparseFilters(
            lang=self.lang,
            trust_tier_max=self.trust_tier_max,
            section_type=self.section_type,
            document_id=self.document_id,
        )


# A dense-search seam: ``(q_vec, n, filters) -> iterable of row-like objects``
# (or RankedChunk). Injectable for tests / alternative backends; when ``None``
# the retriever runs its own parameterized pgvector SQL via ``session_factory``.
DenseSearchFn = Callable[[Sequence[float], int, "RetrievalFilters | None"], Iterable[Any]]


# Parameterized dense ANN statement. pgvector-only operators (``<=>`` and the
# ``::vector`` cast) live inside this opaque text fragment so the statement is
# constructable / compile-testable without a live pgvector, and nothing from the
# query is interpolated — the vector and every filter are bound parameters.
_DENSE_SQL = text(
    """
    SELECT c.id            AS chunk_id,
           1 - (e.embedding <=> CAST(:qvec AS vector)) AS score,
           c.document_id   AS document_id,
           c.section_path  AS section_path,
           c.section_type  AS section_type,
           c.lang          AS lang,
           c.trust_tier    AS trust_tier,
           c.meta_json     AS meta_json,
           c.text          AS text
    FROM kb_chunk_embeddings e
    JOIN kb_chunks c ON c.id = e.chunk_id
    WHERE (CAST(:tier_floor AS integer) IS NULL OR c.trust_tier <= CAST(:tier_floor AS integer))
      AND (CAST(:lang_filter AS text) IS NULL OR c.lang = CAST(:lang_filter AS text))
      AND (CAST(:section_type AS text) IS NULL OR c.section_type = CAST(:section_type AS text))
      AND (CAST(:document_id AS bigint) IS NULL OR c.document_id = CAST(:document_id AS bigint))
    ORDER BY e.embedding <=> CAST(:qvec AS vector)
    LIMIT :n
    """
)


class HybridRetriever:
    """Hybrid dense + sparse retriever over the persistent pgvector corpus.

    Parameters
    ----------
    embedder:
        The embedding client. Only :meth:`embed_query` is used (exactly once per
        :meth:`retrieve` call) — documents are never re-embedded online.
    sparse_index:
        The injected :class:`SparseIndex` providing the BM25 / bge-m3 sparse arm.
    reranker:
        The cross-encoder reranker (``rag.retrieval.reranker.NeuralReranker``);
        its ``rerank`` reorders the fused candidates and never invents/drops one.
    session_factory:
        Zero-argument callable returning a :class:`~sqlalchemy.orm.Session`, used
        by the dense arm to run the pgvector ANN query. Optional when a
        ``dense_search`` seam is injected instead (e.g. in unit tests).
    dense_search:
        Optional injected dense-search seam ``(q_vec, n, filters) -> rows`` that
        bypasses the SQL execution (used by tests / alternative backends).
    query_expander:
        Optional injected expander (``rag.normalize.query_expander``). ``None``
        (default) is the P2 no-op; P3 supplies the real one.
    candidate_n:
        How many candidates each arm contributes to fusion (default 50).
    trust_tier_ranking:
        Tri-state override for the P4 trust-tier + recency tie-break (task 8.4).
        ``None`` (default) defers to ``settings.rag_trust_tier_ranking_enabled``;
        ``True``/``False`` force it on/off (used by tests). When disabled the
        retriever behaves exactly as in task 5.8 — the fused order is the pure
        RRF order and ``trust_tier`` provenance is passed through untouched.
    """

    DEFAULT_CANDIDATE_N = 50

    def __init__(
        self,
        *,
        embedder: "HttpEmbeddingClient",
        sparse_index: SparseIndex,
        reranker: "NeuralReranker",
        session_factory: Callable[[], "Session"] | None = None,
        dense_search: DenseSearchFn | None = None,
        query_expander: Any | None = None,
        candidate_n: int = DEFAULT_CANDIDATE_N,
        trust_tier_ranking: bool | None = None,
    ) -> None:
        if session_factory is not None and not callable(session_factory):
            raise TypeError(
                "session_factory must be a zero-argument callable returning a Session"
            )
        if dense_search is not None and not callable(dense_search):
            raise TypeError("dense_search must be a callable (q_vec, n, filters) -> rows")
        self._embedder = embedder
        self._sparse_index = sparse_index
        self._reranker = reranker
        self._session_factory = session_factory
        self._dense_search_fn = dense_search
        self._query_expander = query_expander
        self._candidate_n = max(1, int(candidate_n))
        self._trust_tier_ranking = trust_tier_ranking

    # -- construction helpers ------------------------------------------------

    @classmethod
    def from_engine(
        cls,
        engine: "Engine",
        *,
        embedder: "HttpEmbeddingClient",
        reranker: "NeuralReranker",
        sparse_index: SparseIndex | None = None,
        query_expander: Any | None = None,
        candidate_n: int = DEFAULT_CANDIDATE_N,
        trust_tier_ranking: bool | None = None,
    ) -> "HybridRetriever":
        """Build a retriever from a SQLAlchemy ``Engine`` (no connection opened)."""

        factory = sessionmaker(bind=engine, expire_on_commit=False)
        return cls(
            embedder=embedder,
            sparse_index=sparse_index or SparseIndex(factory),
            reranker=reranker,
            session_factory=factory,
            query_expander=query_expander,
            candidate_n=candidate_n,
            trust_tier_ranking=trust_tier_ranking,
        )

    # -- public retrieval ----------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int,
        *,
        filters: RetrievalFilters | None = None,
    ) -> list[Document]:
        """Online hybrid retrieval over the persistent index.

        Flow (Requirements 7.1, 7.2, 7.6, 7.7):

        1. Expand the query (no-op for P2) to derive the canonical query string
           and the sparse-search terms.
        2. Embed **only** the query — exactly one :meth:`embed_query` call; no
           document is re-embedded (Property 12).
        3. Run the dense ANN arm and the sparse / BM25 arm (logically parallel;
           executed sequentially here — neither depends on the other's output).
        4. Fuse the two ranked lists with RRF (``rrf_fuse``, reusing ``_RRF_K``).
           When the P4 trust-tier ranking is enabled (task 8.4), apply a stable
           tier + recency tie-break over the fused order: among chunks with
           *equal* fused score, the higher-authority chunk (lower ``trust_tier``)
           ranks at least as high, with more recent ``effective_date`` breaking
           further ties. The tie-break never reorders chunks that already differ
           in fused score, so RRF monotonicity is preserved.
        5. Cross-encoder rerank the fused candidates and return at most ``top_k``.

        Returns at most ``top_k`` :class:`Document` objects, each carrying
        provenance metadata, and the returned set is always a subset of the
        union of the dense and sparse candidates (no fabrication). Returns ``[]``
        for a non-positive ``top_k`` or an empty query (no embedding call is made
        in those short-circuit cases).
        """

        if top_k <= 0 or not str(query or "").strip():
            return []

        lang_hint = self._lang_hint(query, filters)
        canonical_query, sparse_query_text = self._expand(query, lang_hint)

        # (2) Embed ONLY the query — exactly one embedding call (Property 12).
        q_vec = self._embedder.embed_query(canonical_query)

        # (3) Two logically parallel arms over the persistent index.
        dense = self._dense_search(q_vec, self._candidate_n, filters=filters)
        sparse = self._sparse_search(sparse_query_text, n=self._candidate_n, filters=filters)

        # (4) RRF fusion over (chunk_id, score) candidates. The dense arm is
        # passed first so it wins representative selection on id collisions.
        fused_chunks = self._fuse(dense, sparse)

        # (5) Cross-encoder rerank the fused candidate Documents, then trim.
        documents = [self._ranked_to_document(rc) for rc in fused_chunks]
        rerank_result = self._reranker.rerank(query, documents, top_k=top_k)
        ranked_docs = list(getattr(rerank_result, "documents", documents))
        return ranked_docs[:top_k]

    # -- query expansion (P3 seam; no-op for P2) -----------------------------

    def _expand(self, query: str, lang_hint: str) -> tuple[str, str]:
        """Return ``(canonical_query, sparse_query_text)``.

        With no expander injected (P2) both are the original query. When a P3
        expander is present, the canonical query is embedded and the union of
        expanded terms drives the sparse arm. The expander is additive
        (recall-only) and never alters the single-embedding guarantee.
        """

        expander = self._query_expander
        if expander is None:
            return query, query
        expanded = expander.expand(query, lang=lang_hint)
        canonical = str(getattr(expanded, "canonical", "") or query)
        terms = list(getattr(expanded, "terms", []) or [])
        sparse_text = " ".join(str(term) for term in terms if str(term).strip()) or query
        return canonical, sparse_text

    @staticmethod
    def _lang_hint(query: str, filters: RetrievalFilters | None) -> str:
        """Resolve a coarse language hint ('vi' | 'en') for expansion / FTS.

        Prefers an explicit ``filters.lang``; otherwise detects Vietnamese by the
        presence of Vietnamese-specific diacritics, defaulting to English.
        """

        if filters is not None and filters.lang:
            return str(filters.lang)
        normalized = unicodedata.normalize("NFC", str(query or ""))
        for char in normalized:
            if "\u00c0" <= char <= "\u1ef9" and char.lower() != char.upper():
                # Vietnamese diacritic range (composed Latin + extended-additional).
                if char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    return "vi"
        return "en"

    # -- dense arm -----------------------------------------------------------

    def _dense_search(
        self,
        q_vec: Sequence[float],
        n: int,
        *,
        filters: RetrievalFilters | None,
    ) -> list[RankedChunk]:
        """Dense ANN search via pgvector cosine distance.

        Executes the parameterized statement::

            SELECT c.id, 1 - (e.embedding <=> :qvec) AS score, ...
            FROM kb_chunk_embeddings e JOIN kb_chunks c ON c.id = e.chunk_id
            WHERE (:tier_floor IS NULL OR c.trust_tier <= :tier_floor) AND ...
            ORDER BY e.embedding <=> :qvec     -- HNSW / IVFFLAT ANN index
            LIMIT :n;

        and maps rows to :class:`RankedChunk` (``retriever='dense'``) ranked by
        cosine similarity descending. When a ``dense_search`` seam is injected it
        is used instead of the SQL (tests / alternative backends). Returns ``[]``
        when neither a seam nor a ``session_factory`` is configured.
        """

        if n <= 0:
            return []
        if self._dense_search_fn is not None:
            rows = self._dense_search_fn(q_vec, n, filters)
            return [self._row_to_ranked_chunk(row) for row in rows]
        if self._session_factory is None:
            return []

        params = {
            "qvec": self._format_vector(q_vec),
            "tier_floor": filters.trust_tier_max if filters else None,
            "lang_filter": filters.lang if filters else None,
            "section_type": filters.section_type if filters else None,
            "document_id": filters.document_id if filters else None,
            "n": int(n),
        }

        with self._session() as session:
            rows = session.execute(_DENSE_SQL, params).all()
        return [self._row_to_ranked_chunk(row) for row in rows]

    def build_dense_statement(self):  # noqa: ANN201 - SQLAlchemy TextClause
        """Return the parameterized dense ANN statement (no execution).

        Exposed so the SQL can be ``.compile()``-d in a unit test without a live
        pgvector — the pgvector-only operators are opaque inside the text clause.
        """

        return _DENSE_SQL

    @staticmethod
    def _format_vector(vector: Sequence[float]) -> str:
        """Render a dense vector as pgvector's ``[a,b,c]`` text form for binding."""

        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    @contextmanager
    def _session(self) -> Iterator["Session"]:
        if self._session_factory is None:  # pragma: no cover - guarded by caller
            raise RuntimeError("HybridRetriever has no session_factory for dense search")
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    # -- sparse arm ----------------------------------------------------------

    def _sparse_search(
        self,
        query_text: str,
        *,
        n: int,
        filters: RetrievalFilters | None,
    ) -> list[RankedChunk]:
        """BM25 / bge-m3 sparse search via the injected :class:`SparseIndex`."""

        if n <= 0:
            return []
        sparse_filters = filters.to_sparse_filters() if filters is not None else None
        lang = filters.lang if filters is not None else None
        return self._sparse_index.search(
            query_text,
            top_k=n,
            lang=lang,
            filters=sparse_filters,
        )

    # -- fusion --------------------------------------------------------------

    def _fuse(self, dense: list[RankedChunk], sparse: list[RankedChunk]) -> list[RankedChunk]:
        """Fuse the dense and sparse arms with RRF, returning ranked chunks.

        Builds ``(chunk_id, score)`` candidate lists and delegates to the shared
        :func:`rrf_fuse` (reusing ``_RRF_K=60``). The fused id order is then
        mapped back to the originating :class:`RankedChunk` (dense wins on id
        collision, matching ``rrf_fuse``'s first-seen representative). The result
        is exactly the union of the two arms reordered — no fabricated chunks.

        When the P4 trust-tier ranking is enabled (task 8.4) a stable tier +
        recency tie-break is layered on top of the fused order via
        :meth:`_apply_tier_recency_order`. When it is disabled (the default) the
        return value is the pure RRF order, identical to task 5.8.
        """

        by_id: dict[int, RankedChunk] = {}
        for rc in sparse:
            by_id.setdefault(rc.chunk_id, rc)
        for rc in dense:
            by_id[rc.chunk_id] = rc  # dense representative wins on collision

        dense_pairs = [(rc.chunk_id, rc.score) for rc in dense]
        sparse_pairs = [(rc.chunk_id, rc.score) for rc in sparse]
        fused_pairs = rrf_fuse(dense_pairs, sparse_pairs, k=RRF_K)

        ordered: list[RankedChunk] = []
        for pair in fused_pairs:
            chunk_id = pair[0]
            chunk = by_id.get(chunk_id)
            if chunk is not None:
                ordered.append(chunk)

        if not self._tier_ranking_enabled():
            return ordered

        fused_scores = self._rrf_scores(dense, sparse, k=RRF_K)
        return self._apply_tier_recency_order(ordered, fused_scores)

    # -- trust-tier + recency ranking (P4, task 8.4) -------------------------

    def _tier_ranking_enabled(self) -> bool:
        """Whether the P4 trust-tier + recency tie-break is active.

        Defers to ``settings.rag_trust_tier_ranking_enabled`` unless an explicit
        override was injected at construction. Disabled by default so the
        retrieval order matches task 5.8 exactly.
        """

        if self._trust_tier_ranking is None:
            return bool(settings.rag_trust_tier_ranking_enabled)
        return bool(self._trust_tier_ranking)

    @staticmethod
    def _rrf_scores(
        dense: list[RankedChunk],
        sparse: list[RankedChunk],
        *,
        k: int,
    ) -> dict[int, float]:
        """Recompute the RRF fused score per ``chunk_id`` (mirrors ``rrf_fuse``).

        Uses the identical ``score(c) = Σ 1/(k + rank_L(c))`` formula (1-based
        rank within each list) so the scores are consistent with the order
        :func:`rrf_fuse` produced. These scores are used *only* to identify
        equal-score tie groups for the tier/recency tie-break — fusion ordering
        itself still comes from :func:`rrf_fuse`.
        """

        scores: dict[int, float] = {}
        for ranked_list in (dense, sparse):
            for rank, rc in enumerate(ranked_list, start=1):
                scores[rc.chunk_id] = scores.get(rc.chunk_id, 0.0) + 1.0 / float(k + rank)
        return scores

    def _apply_tier_recency_order(
        self,
        ordered: list[RankedChunk],
        fused_scores: dict[int, float],
    ) -> list[RankedChunk]:
        """Stable trust-tier + recency tie-break over the RRF order (Req 10.2/10.4).

        Each chunk is assigned a dense ``fused_rank`` derived from the canonical
        RRF order, where chunks with *equal* fused score share a rank. A stable
        sort by the key

            ``(fused_rank, trust_tier_asc, -effective_date_ordinal, rrf_pos)``

        then guarantees:

        * **Monotonicity preserved (Property 13).** A chunk with a strictly
          higher fused score gets a strictly smaller ``fused_rank`` and therefore
          always sorts ahead of any lower-scored chunk, *regardless* of tier or
          date. The tie-break can only reorder chunks that are already tied on
          fused score.
        * **Trust-tier ordering (Property 21 / Req 10.2).** Among equal-fused
          chunks the higher-authority chunk (lower ``trust_tier`` number) ranks
          at least as high.
        * **Recency (Req 10.4).** Remaining ties prefer the more recent
          ``effective_date``; undated chunks sort last within their group.
        * **Determinism.** The final ``rrf_pos`` component falls back to the
          original RRF position so fully-tied chunks keep a stable, reproducible
          order.
        """

        if len(ordered) < 2:
            return ordered

        # Dense fused_rank: walk the (descending-score) RRF order and bump the
        # rank only when the fused score actually changes. Equal scores -> same
        # rank -> eligible to be reordered by the tier/recency tie-break.
        fused_rank: dict[int, int] = {}
        rank = 0
        prev_score: float | None = None
        for chunk in ordered:
            score = fused_scores.get(chunk.chunk_id, 0.0)
            if prev_score is None or not math.isclose(
                score, prev_score, rel_tol=0.0, abs_tol=_RRF_SCORE_TOL
            ):
                rank += 1
                prev_score = score
            fused_rank[chunk.chunk_id] = rank

        decorated = list(enumerate(ordered))
        decorated.sort(
            key=lambda item: (
                fused_rank[item[1].chunk_id],
                self._coerce_trust_tier(item[1].trust_tier),
                -self._effective_date_ordinal((item[1].meta or {}).get("effective_date")),
                item[0],
            )
        )
        return [chunk for _, chunk in decorated]

    @staticmethod
    def _coerce_trust_tier(value: Any) -> int:
        """Coerce a raw ``trust_tier`` into the valid ``{1,2,3,4}`` set.

        Lower number == higher authority. Any missing / non-integer / out-of-range
        value is mapped to the lowest authority (4) so unverified provenance can
        never out-rank a known-authoritative chunk and every surfaced row carries
        a ``trust_tier`` in ``{1,2,3,4}`` (Req 10.2).
        """

        try:
            tier = int(value)
        except (TypeError, ValueError):
            return _LOWEST_AUTHORITY_TIER
        return tier if tier in VALID_TRUST_TIERS else _LOWEST_AUTHORITY_TIER

    @staticmethod
    def _effective_date_ordinal(value: Any) -> float:
        """Return a sortable recency ordinal for ``effective_date`` (larger == newer).

        Accepts :class:`datetime.date`/:class:`datetime.datetime` objects or
        ISO-8601 date / datetime strings. Missing or unparseable values return
        ``-inf`` so undated chunks sort *after* dated ones within an equal
        relevance + tier tie group (Req 10.4 prefers the more recent document).
        """

        if isinstance(value, date):  # also matches datetime (subclass of date)
            try:
                return float(value.toordinal())
            except (ValueError, OverflowError):
                return float("-inf")
        text_value = str(value or "").strip()
        if not text_value:
            return float("-inf")
        try:
            return float(date.fromisoformat(text_value[:10]).toordinal())
        except ValueError:
            pass
        try:
            return float(datetime.fromisoformat(text_value).toordinal())
        except ValueError:
            return float("-inf")

    # -- row / document mapping ----------------------------------------------

    @staticmethod
    def _row_to_ranked_chunk(row: Any) -> RankedChunk:
        """Map a dense SQL row (or row-like / RankedChunk) to a RankedChunk.

        Mirrors :meth:`SparseIndex._row_to_ranked_chunk` so the dense arm yields
        the same candidate shape the fusion + provenance mapping expects.
        """

        if isinstance(row, RankedChunk):
            return row
        meta = getattr(row, "meta_json", None)
        meta = meta if isinstance(meta, dict) else {}
        document_id = getattr(row, "document_id", None)
        trust_tier = getattr(row, "trust_tier", None)
        score = getattr(row, "score", None)
        return RankedChunk(
            chunk_id=int(row.chunk_id),
            score=float(score) if score is not None else 0.0,
            retriever="dense",
            document_id=int(document_id) if document_id is not None else None,
            section_path=str(getattr(row, "section_path", "") or ""),
            section_type=str(getattr(row, "section_type", "") or ""),
            lang=str(getattr(row, "lang", "") or ""),
            trust_tier=int(trust_tier) if trust_tier is not None else None,
            text=str(getattr(row, "text", "") or ""),
            meta=dict(meta),
        )

    def _ranked_to_document(self, chunk: RankedChunk) -> Document:
        """Map a persisted chunk to the ``Document`` domain shape with provenance.

        The metadata always carries the six provenance keys downstream guardrails
        / FIDES and citations rely on — ``{source, url, trust_tier,
        effective_date, RXCUI, lang}`` (Property 20 / Requirement 7.6) — sourced
        from the chunk's ``meta_json`` plus the row's structural columns. The
        ``Document.id`` is ``str(chunk_id)`` so downstream identity is stable.

        When the P4 trust-tier ranking is enabled (task 8.4) the surfaced
        ``trust_tier`` is coerced into ``{1,2,3,4}`` (Req 10.2); otherwise it is
        passed through unchanged to keep the task 5.8 provenance contract intact.
        """

        meta = dict(chunk.meta or {})
        rxcui = meta.get("RXCUI", meta.get("rxcui", []))
        trust_tier: Any = chunk.trust_tier
        if self._tier_ranking_enabled():
            trust_tier = self._coerce_trust_tier(trust_tier)
        provenance = {
            "source": meta.get("source", ""),
            "url": meta.get("url", ""),
            "trust_tier": trust_tier,
            "effective_date": meta.get("effective_date"),
            "RXCUI": rxcui,
            "lang": chunk.lang or meta.get("lang", ""),
        }
        metadata: dict[str, Any] = dict(meta)
        metadata.update(provenance)
        metadata["chunk_id"] = chunk.chunk_id
        metadata["document_id"] = chunk.document_id
        metadata["section_path"] = chunk.section_path
        metadata["section_type"] = chunk.section_type
        metadata["retriever"] = chunk.retriever
        metadata["score"] = float(chunk.score)
        return Document(id=str(chunk.chunk_id), text=chunk.text, metadata=metadata)
