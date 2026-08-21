"""Sparse / BM25 read layer over the persistent corpus (task 5.4).

This module is the ``Sparse_Index`` component from ``design.md`` / Requirement 7.
It provides the *sparse* half of hybrid retrieval (the dense half lives in
``hybrid_retriever.py``, task 5.8) over two complementary lexical signals that
were persisted offline by the ingestion plane:

* **Real BM25 via Postgres full-text search.** ``kb_chunks.fts`` is a
  language-aware ``tsvector`` (``'simple'`` for Vietnamese to avoid English
  stemming artifacts, ``'english'`` for English content). :meth:`SparseIndex.search`
  builds a ``tsquery`` from the sanitized query terms and ranks matching chunks
  with ``ts_rank_cd(fts, tsquery)`` — i.e. real term-frequency /
  inverse-document-frequency / cover-density length normalization, not the
  naive token-overlap the legacy in-memory path used (Requirement 7.5,
  Property 15).
* **bge-m3 learned-sparse terms.** ``kb_chunk_sparse_terms`` stores
  ``(term, weight)`` rows emitted by bge-m3. :meth:`SparseIndex.sparse_term_search`
  sums the weights of the matching terms per chunk and ranks by that total.

Design constraints honoured here (mirroring ``document_store.py``):

* **Import-safe.** Importing this module opens no database connection and runs
  no DDL. The index is constructed with a dependency-injected session factory
  (a :class:`~sqlalchemy.orm.sessionmaker` or any zero-arg callable returning a
  :class:`~sqlalchemy.orm.Session`), so a live database is required only when a
  read method actually executes. Unit tests can exercise the pure helpers and
  compile the SQL without a live Postgres.
* **Parameterized SQL only.** The raw user query string is *never* interpolated
  into SQL. Query terms are sanitized by the pure :func:`build_tsquery_terms`
  helper and passed to Postgres' ``to_tsquery`` as a bound parameter; the
  language configuration is drawn from a strict allow-list and bound as a
  ``regconfig`` cast. Sparse-term matching uses a bound ``IN (...)`` list.
* **SQL building is testable without a DB.** The statement constructors
  (:meth:`SparseIndex.build_search_statement` and
  :meth:`SparseIndex.build_sparse_term_statement`) return SQLAlchemy
  selectables that can be ``.compile()``-d in a unit test, and the tokenization
  / sanitization / ranking-sanity helpers are pure functions.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, bindparam, cast, func, literal, select
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from clara_ml.rag.store.schema import KbChunk, KbChunkSparseTerm

__all__ = [
    "RankedChunk",
    "SparseFilters",
    "SparseIndex",
    "build_tsquery_terms",
    "to_tsquery_string",
    "ts_config_for_lang",
    "term_frequency",
    "bm25_sanity_holds",
]


# ---------------------------------------------------------------------------
# Result + filter dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RankedChunk:
    """A single sparse-retrieval hit.

    ``chunk_id`` and ``score`` are the contract every sparse path returns;
    higher ``score`` ranks first. The remaining fields carry the provenance the
    online :class:`Hybrid_Retriever` (task 5.8) needs to fuse, rerank and cite
    (Requirement 7.6). ``retriever`` tags which sparse signal produced the row
    (``"bm25"`` or ``"sparse_terms"``).
    """

    chunk_id: int
    score: float
    retriever: str = "bm25"
    document_id: int | None = None
    section_path: str = ""
    section_type: str = ""
    lang: str = ""
    trust_tier: int | None = None
    text: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SparseFilters:
    """Optional read filters shared by the BM25 and sparse-term paths.

    ``lang`` doubles as the language hint for the FTS configuration when no
    explicit ``lang`` argument is passed to :meth:`SparseIndex.search`.
    ``trust_tier_max`` keeps only chunks whose ``trust_tier`` number is ``<=``
    the floor (lower number == higher authority), mirroring the dense path's
    ``tier_floor`` filter in ``design.md``.
    """

    lang: str | None = None
    trust_tier_max: int | None = None
    section_type: str | None = None
    document_id: int | None = None


# ---------------------------------------------------------------------------
# Pure, DB-free helpers (unit-testable without Postgres)
# ---------------------------------------------------------------------------

# Vietnamese diacritics live in the U+00C0..U+1EF9 range; keep them so the
# 'simple' FTS configuration can index Vietnamese surface forms verbatim.
_TOKEN_RE = re.compile(r"[0-9a-zA-ZÀ-ỹ]+")

# tsquery operators / punctuation that must never reach to_tsquery as a lexeme.
_TSQUERY_RESERVED = set("&|!()<>:*'\\\"")

_VI_LANG_CODES = {"vi", "vie", "vn", "vietnamese", "tiếng việt", "tieng viet"}
_EN_LANG_CODES = {"en", "eng", "english"}


def ts_config_for_lang(lang: str | None) -> str:
    """Return the Postgres FTS configuration name for ``lang``.

    ``'english'`` for English content; ``'simple'`` for Vietnamese (and as the
    safe default) so English stemming never mangles Vietnamese surface forms.
    This matches the ingestion-side ``fts`` maintenance in ``design.md``.
    """

    code = str(lang or "").strip().lower()
    if code in _EN_LANG_CODES:
        return "english"
    # Vietnamese, unknown, or empty -> 'simple' (stem-free, diacritics-safe).
    return "simple"


def build_tsquery_terms(query: str, *, min_length: int = 1) -> list[str]:
    """Tokenize and sanitize ``query`` into safe ``tsquery`` lexemes.

    Pure and DB-free so it is unit-testable in isolation. The pipeline is:

    1. Unicode-normalize (NFC) so composed/decomposed Vietnamese forms compare
       equal.
    2. Extract alphanumeric (incl. Vietnamese-diacritic) runs, dropping every
       ``tsquery`` operator and punctuation character.
    3. Lower-case, drop tokens shorter than ``min_length`` and any token that
       still contains a reserved operator (defence in depth).
    4. De-duplicate while preserving first-seen order (stable, deterministic).

    The returned tokens contain only ``[0-9a-zà-ỹ]`` characters, so they are
    safe to assemble into a ``tsquery`` string and bind as a parameter.
    """

    normalized = unicodedata.normalize("NFC", str(query or ""))
    seen: set[str] = set()
    terms: list[str] = []
    for match in _TOKEN_RE.findall(normalized):
        token = match.lower().strip()
        if len(token) < min_length:
            continue
        if any(char in _TSQUERY_RESERVED for char in token):
            continue
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def to_tsquery_string(terms: Sequence[str], *, mode: str = "or") -> str:
    """Join sanitized ``terms`` into a ``to_tsquery`` input string.

    ``mode='or'`` (default) joins with ``' | '`` for recall — a chunk matching
    any query term is a candidate, and ``ts_rank_cd`` then orders by real BM25
    signal. ``mode='and'`` joins with ``' & '`` for precision. Returns ``""``
    when there are no terms (callers treat this as "no query").
    """

    cleaned = [t for t in (str(term).strip() for term in terms) if t]
    if not cleaned:
        return ""
    joiner = " & " if str(mode).lower() == "and" else " | "
    return joiner.join(cleaned)


def term_frequency(term: str, text: str) -> int:
    """Count whole-token occurrences of ``term`` in ``text`` (pure helper).

    Tokenization matches :func:`build_tsquery_terms` so the count reflects the
    lexemes the FTS layer would index. Used to reason about Property 15 (BM25
    ranking sanity) in unit tests without a live database.
    """

    needle = unicodedata.normalize("NFC", str(term or "")).lower().strip()
    if not needle:
        return 0
    # Recount against the raw token stream (build_tsquery_terms de-duplicates).
    normalized = unicodedata.normalize("NFC", str(text or ""))
    return sum(1 for tok in _TOKEN_RE.findall(normalized) if tok.lower() == needle)


def bm25_sanity_holds(score_with_term: float, score_without_term: float) -> bool:
    """Return whether the Property 15 ordering invariant holds.

    A chunk that contains a favorable-IDF query term with higher term frequency
    must rank *at least as high* as a chunk lacking the term. Expressed purely
    as ``score_with_term >= score_without_term`` so tests can assert the
    relationship that the ``ts_rank_cd`` ordering is expected to satisfy.
    """

    return float(score_with_term) >= float(score_without_term)


# ---------------------------------------------------------------------------
# SparseIndex
# ---------------------------------------------------------------------------


class SparseIndex:
    """Read adapter for the sparse / BM25 retrieval signals.

    Parameters
    ----------
    session_factory:
        A zero-argument callable returning a new :class:`~sqlalchemy.orm.Session`
        — typically a :class:`~sqlalchemy.orm.sessionmaker` or ``services/api``'s
        ``SessionLocal``. Injected (as in :class:`DocumentStore`) so the index
        never owns engine lifecycle and stays import-safe / unit-testable.

    Each read method accepts an optional ``session`` keyword; when supplied the
    query runs on the caller-owned session, otherwise the index opens and closes
    its own short-lived read session.
    """

    #: Default number of candidates a single sparse list contributes to fusion.
    DEFAULT_TOP_K = 50

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        if not callable(session_factory):
            raise TypeError(
                "session_factory must be a zero-argument callable returning a Session"
            )
        self._session_factory = session_factory

    # -- construction helpers ------------------------------------------------

    @classmethod
    def from_engine(cls, engine: Engine) -> SparseIndex:
        """Build an index from a SQLAlchemy ``Engine`` (no connection opened)."""

        factory = sessionmaker(bind=engine, expire_on_commit=False)
        return cls(factory)

    # -- session plumbing ----------------------------------------------------

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def _read(self, session: Session | None, work: Callable[[Session], Any]) -> Any:
        if session is not None:
            return work(session)
        with self._session() as managed:
            return work(managed)

    # -- statement builders (DB-free; compile-testable) ----------------------

    @staticmethod
    def _apply_filters(stmt: Select, filters: SparseFilters | None) -> Select:
        if filters is None:
            return stmt
        if filters.trust_tier_max is not None:
            stmt = stmt.where(KbChunk.trust_tier <= int(filters.trust_tier_max))
        if filters.section_type:
            stmt = stmt.where(KbChunk.section_type == str(filters.section_type))
        if filters.document_id is not None:
            stmt = stmt.where(KbChunk.document_id == int(filters.document_id))
        return stmt

    def build_search_statement(
        self,
        ts_query_text: str,
        *,
        config: str,
        top_k: int,
        filters: SparseFilters | None = None,
        mode: str = "or",  # noqa: ARG002 - kept for caller symmetry / future AND ranking
    ) -> Select:
        """Return the parameterized BM25 ``SELECT`` (no execution).

        The query string and the FTS configuration are both passed as bound
        parameters (the config via a ``regconfig`` cast), so nothing from the
        user query is interpolated into SQL. The ranking expression is the real
        ``ts_rank_cd(fts, tsquery)`` — IDF / TF-saturation / cover-density
        length normalization — satisfying Property 15.
        """

        tsquery = func.to_tsquery(
            cast(literal(config), REGCONFIG),
            bindparam("ts_query", value=ts_query_text),
        )
        score_expr = func.ts_rank_cd(KbChunk.fts, tsquery)

        stmt: Select = (
            select(
                KbChunk.id.label("chunk_id"),
                score_expr.label("score"),
                KbChunk.document_id.label("document_id"),
                KbChunk.section_path.label("section_path"),
                KbChunk.section_type.label("section_type"),
                KbChunk.lang.label("lang"),
                KbChunk.trust_tier.label("trust_tier"),
                KbChunk.meta_json.label("meta_json"),
                KbChunk.text.label("text"),
            )
            .where(KbChunk.fts.op("@@")(tsquery))
        )
        stmt = self._apply_filters(stmt, filters)
        # Deterministic tie-break on chunk id keeps ordering stable for equal ranks.
        stmt = stmt.order_by(score_expr.desc(), KbChunk.id.asc()).limit(int(top_k))
        return stmt

    def build_sparse_term_statement(
        self,
        terms: Sequence[str],
        *,
        top_k: int,
        filters: SparseFilters | None = None,
    ) -> Select:
        """Return the parameterized bge-m3 sparse-term ``SELECT`` (no execution).

        Sums ``kb_chunk_sparse_terms.weight`` over the matching terms per chunk
        and ranks chunks by that total descending. The term list is bound via an
        expanding ``IN (...)`` parameter (never interpolated).
        """

        total_weight = func.coalesce(func.sum(KbChunkSparseTerm.weight), 0.0)
        stmt: Select = (
            select(
                KbChunk.id.label("chunk_id"),
                total_weight.label("score"),
                KbChunk.document_id.label("document_id"),
                KbChunk.section_path.label("section_path"),
                KbChunk.section_type.label("section_type"),
                KbChunk.lang.label("lang"),
                KbChunk.trust_tier.label("trust_tier"),
                KbChunk.meta_json.label("meta_json"),
                KbChunk.text.label("text"),
            )
            .join(KbChunkSparseTerm, KbChunkSparseTerm.chunk_id == KbChunk.id)
            .where(KbChunkSparseTerm.term.in_(bindparam("sparse_terms", value=list(terms), expanding=True)))
            .group_by(
                KbChunk.id,
                KbChunk.document_id,
                KbChunk.section_path,
                KbChunk.section_type,
                KbChunk.lang,
                KbChunk.trust_tier,
                KbChunk.meta_json,
                KbChunk.text,
            )
        )
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.order_by(total_weight.desc(), KbChunk.id.asc()).limit(int(top_k))
        return stmt

    # -- row mapping ---------------------------------------------------------

    @staticmethod
    def _row_to_ranked_chunk(row: Any, *, retriever: str) -> RankedChunk:
        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        return RankedChunk(
            chunk_id=int(row.chunk_id),
            score=float(row.score) if row.score is not None else 0.0,
            retriever=retriever,
            document_id=int(row.document_id) if row.document_id is not None else None,
            section_path=str(row.section_path or ""),
            section_type=str(row.section_type or ""),
            lang=str(row.lang or ""),
            trust_tier=int(row.trust_tier) if row.trust_tier is not None else None,
            text=str(row.text or ""),
            meta=dict(meta),
        )

    # -- public read methods -------------------------------------------------

    def search(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        lang: str | None = None,
        filters: SparseFilters | None = None,
        mode: str = "or",
        session: Session | None = None,
    ) -> list[RankedChunk]:
        """BM25-style full-text search ranked by ``ts_rank_cd``.

        Builds a ``tsquery`` from the sanitized query terms and ranks matching
        chunks by real Postgres BM25 signal. The FTS configuration is chosen
        from ``lang`` (falling back to ``filters.lang``): ``'english'`` for
        English, ``'simple'`` for Vietnamese / unknown. Returns at most
        ``top_k`` :class:`RankedChunk` rows sorted by score descending; an empty
        list when ``top_k <= 0`` or the query has no usable terms.
        """

        if top_k <= 0:
            return []
        terms = build_tsquery_terms(query)
        if not terms:
            return []
        ts_query_text = to_tsquery_string(terms, mode=mode)
        if not ts_query_text:
            return []

        effective_lang = lang if lang is not None else (filters.lang if filters else None)
        config = ts_config_for_lang(effective_lang)
        stmt = self.build_search_statement(
            ts_query_text, config=config, top_k=top_k, filters=filters, mode=mode
        )

        def work(s: Session) -> list[RankedChunk]:
            rows = s.execute(stmt).all()
            return [self._row_to_ranked_chunk(row, retriever="bm25") for row in rows]

        return self._read(session, work)

    def sparse_term_search(
        self,
        query_terms: Iterable[str],
        *,
        top_k: int = DEFAULT_TOP_K,
        filters: SparseFilters | None = None,
        session: Session | None = None,
    ) -> list[RankedChunk]:
        """bge-m3 sparse-term scoring: rank chunks by summed matching weight.

        Normalizes ``query_terms`` with the same sanitizer used for FTS, then
        sums ``kb_chunk_sparse_terms.weight`` over the matching terms per chunk
        and ranks by the total. Returns at most ``top_k`` :class:`RankedChunk`
        rows (``retriever='sparse_terms'``); an empty list when ``top_k <= 0``
        or no usable terms remain.
        """

        if top_k <= 0:
            return []
        # Sanitize each provided term; flatten any multi-word inputs into lexemes.
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in query_terms:
            for token in build_tsquery_terms(raw):
                if token not in seen:
                    seen.add(token)
                    normalized.append(token)
        if not normalized:
            return []

        stmt = self.build_sparse_term_statement(normalized, top_k=top_k, filters=filters)

        def work(s: Session) -> list[RankedChunk]:
            rows = s.execute(stmt).all()
            return [self._row_to_ranked_chunk(row, retriever="sparse_terms") for row in rows]

        return self._read(session, work)
