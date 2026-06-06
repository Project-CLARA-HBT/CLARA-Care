"""SQLAlchemy models, DDL, and write-invariant validators for the ``kb_*`` corpus.

This module is the schema source of truth for the persistent RAG knowledge
pipeline (Epic P0, task 1.2). It defines the ORM models that mirror the
``Data Models`` section of ``design.md`` for the tables:

``kb_source_registry``, ``kb_documents``, ``kb_chunks``,
``kb_chunk_embeddings``, ``kb_chunk_sparse_terms``, ``kb_entities``,
``kb_chunk_entities``, ``kb_entity_edges``, ``eval_set`` and
``eval_run_result``.

Design constraints honoured here:

* **Import-safe.** Importing this module performs no database connection or
  side effect. Table creation, the ``vector``/``pg_trgm`` extensions, the ANN
  index and the FTS GIN index are owned by the gated migration runner
  (``migrations.py``, task 1.5).
* **pgvector-optional.** The dense embedding column uses pgvector's SQLAlchemy
  ``Vector`` type when the ``pgvector`` package is installed; otherwise it
  falls back to a self-contained ``UserDefinedType`` that emits a raw
  ``VECTOR(dim)`` column spec compatible with the migration DDL. See
  :func:`vector_column_type` and :data:`has_pgvector`.
* **Local declarative Base.** ``services/ml`` has no shared SQLAlchemy ``Base``
  (the ORM lives in ``services/api``), so this module defines its own
  :class:`Base` following the same SQLAlchemy 2.0 ``DeclarativeBase`` /
  ``Mapped`` / ``mapped_column`` style used by ``services/api``.

Pure validator helpers (easy to unit/property test) enforce the persisted-data
rules from ``design.md`` and Requirements 1.3, 1.4, 1.5, 2.5:

* :func:`assert_embedding_dim` — dimension must equal ``RAG_EMBEDDING_DIM``.
* :func:`validate_trust_tier` — ``trust_tier`` must be in ``{1, 2, 3, 4}``.
* :func:`guard_degraded_row` — reject ``is_degraded=True`` in production.
* :func:`require_model_id` — ``model_id`` is required on embedding rows.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType

from clara_ml.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Dense embedding dimension for the active model. text-embedding-3-large emits
# 3072 dims (labelled "bge-m3" in product copy). The authoritative value comes
# from settings.rag_embedding_dim (added by task 1.1); this default keeps the
# module import-safe and usable before that flag lands.
DEFAULT_EMBEDDING_DIM = 3072

# Authority tiers: 1 = regulator/label (highest authority) .. 4 = lowest.
VALID_TRUST_TIERS: frozenset[int] = frozenset({1, 2, 3, 4})

_PRODUCTION_ENV = "production"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class WriteInvariantError(ValueError):
    """Base class for all corpus write-invariant violations."""


class EmbeddingDimMismatchError(WriteInvariantError):
    """Raised when an embedding row's dimension != RAG_EMBEDDING_DIM."""


class InvalidTrustTierError(WriteInvariantError):
    """Raised when a trust_tier is outside the set {1, 2, 3, 4}."""


class DegradedEmbeddingNotAllowedError(WriteInvariantError):
    """Raised when a degraded embedding row is written in production."""


class MissingModelIdError(WriteInvariantError):
    """Raised when an embedding row is missing its model_id discriminator."""


# ---------------------------------------------------------------------------
# Pure validator helpers (no DB access)
# ---------------------------------------------------------------------------


def configured_embedding_dim() -> int:
    """Return the configured dense embedding dimension.

    Reads ``settings.rag_embedding_dim`` when present (task 1.1) and otherwise
    falls back to :data:`DEFAULT_EMBEDDING_DIM`, keeping the module usable
    regardless of build order.
    """

    value = getattr(settings, "rag_embedding_dim", DEFAULT_EMBEDDING_DIM)
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_EMBEDDING_DIM


def assert_embedding_dim(dim: int, *, expected: int | None = None) -> int:
    """Validate that ``dim`` equals the configured embedding dimension.

    Validates: Requirement 1.3 (embedding dimension invariant).

    Returns the validated dimension. Raises :class:`EmbeddingDimMismatchError`
    when ``dim`` does not match ``expected`` (defaults to the configured
    ``RAG_EMBEDDING_DIM``).
    """

    target = configured_embedding_dim() if expected is None else int(expected)
    try:
        actual = int(dim)
    except (TypeError, ValueError) as exc:
        raise EmbeddingDimMismatchError(
            f"embedding dimension must be an integer, got {dim!r}"
        ) from exc
    if actual != target:
        raise EmbeddingDimMismatchError(
            f"embedding dimension {actual} != RAG_EMBEDDING_DIM {target}"
        )
    return actual


def validate_trust_tier(tier: int) -> int:
    """Validate that ``tier`` is one of ``{1, 2, 3, 4}``.

    Validates: Requirement 1.5 / 10.2 (trust-tier domain).

    Returns the validated tier. Raises :class:`InvalidTrustTierError` otherwise.
    """

    try:
        # Reject bools explicitly: ``True``/``False`` are ints in Python.
        if isinstance(tier, bool):
            raise ValueError
        value = int(tier)
    except (TypeError, ValueError) as exc:
        raise InvalidTrustTierError(
            f"trust_tier must be an integer in {sorted(VALID_TRUST_TIERS)}, got {tier!r}"
        ) from exc
    if value not in VALID_TRUST_TIERS:
        raise InvalidTrustTierError(
            f"trust_tier {value} outside allowed set {sorted(VALID_TRUST_TIERS)}"
        )
    return value


def _current_environment(environment: str | None) -> str:
    env = environment if environment is not None else getattr(settings, "environment", "development")
    return str(env or "").strip().lower()


def guard_degraded_row(is_degraded: bool, *, environment: str | None = None) -> bool:
    """Reject degraded embedding rows when running in production.

    Validates: Requirements 2.4 / 2.5 (no degraded persistence in production).

    Returns the (boolean) degraded flag when allowed. Raises
    :class:`DegradedEmbeddingNotAllowedError` when ``is_degraded`` is true and
    the effective environment is ``production``.
    """

    degraded = bool(is_degraded)
    if degraded and _current_environment(environment) == _PRODUCTION_ENV:
        raise DegradedEmbeddingNotAllowedError(
            "refusing to persist a degraded embedding row while environment='production'"
        )
    return degraded


def require_model_id(model_id: Any) -> str:
    """Ensure an embedding row carries a non-empty ``model_id`` discriminator.

    Validates: Requirement 1.4 (model_id discriminator on every embedding row).

    Returns the trimmed model id. Raises :class:`MissingModelIdError` when it is
    missing or blank.
    """

    text = "" if model_id is None else str(model_id).strip()
    if not text:
        raise MissingModelIdError("embedding row requires a non-empty model_id")
    return text


def validate_embedding_row(
    *,
    dim: int,
    model_id: Any,
    is_degraded: bool = False,
    expected_dim: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """Validate the full set of write invariants for a dense embedding row.

    Combines :func:`assert_embedding_dim`, :func:`require_model_id` and
    :func:`guard_degraded_row`. Returns a normalized dict of validated values.
    Validates: Requirements 1.3, 1.4, 2.5.
    """

    return {
        "dim": assert_embedding_dim(dim, expected=expected_dim),
        "model_id": require_model_id(model_id),
        "is_degraded": guard_degraded_row(is_degraded, environment=environment),
    }


# ---------------------------------------------------------------------------
# Dense vector column type (pgvector-optional)
# ---------------------------------------------------------------------------

try:  # pragma: no cover - exercised indirectly via has_pgvector
    from pgvector.sqlalchemy import Vector as _PgVector

    has_pgvector = True
except Exception:  # ImportError or any pgvector import-time failure
    _PgVector = None
    has_pgvector = False


class _FallbackVector(UserDefinedType):
    """Minimal stand-in for pgvector's ``Vector`` when the package is absent.

    Emits a raw ``VECTOR(dim)`` column spec so DDL produced from these models
    (and the migration in task 1.5) stays compatible with the pgvector
    extension installed in the database. Bind/result processors round-trip a
    Python ``list[float]`` to/from pgvector's ``[a,b,c]`` text form so the
    fallback is usable even without the native adapter.
    """

    cache_ok = True

    def __init__(self, dim: int | None = None) -> None:
        self.dim = None if dim is None else int(dim)

    def get_col_spec(self, **_kw: Any) -> str:
        if self.dim is None:
            return "VECTOR"
        return f"VECTOR({self.dim})"

    def bind_processor(self, dialect):  # noqa: ANN001 - SQLAlchemy hook
        def process(value: Any) -> str | None:
            if value is None:
                return None
            return "[" + ",".join(str(float(v)) for v in value) + "]"

        return process

    def result_processor(self, dialect, coltype):  # noqa: ANN001 - SQLAlchemy hook
        def process(value: Any) -> list[float] | None:
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                return [float(v) for v in value]
            text = str(value).strip().strip("[]")
            if not text:
                return []
            return [float(part) for part in text.split(",")]

        return process


def vector_column_type(dim: int | None = None):
    """Return a SQLAlchemy column type for a dense ``vector(dim)`` column.

    Uses pgvector's native ``Vector`` type when available, otherwise the
    self-contained :class:`_FallbackVector`. ``dim`` defaults to the configured
    embedding dimension.
    """

    resolved = configured_embedding_dim() if dim is None else int(dim)
    if has_pgvector and _PgVector is not None:
        return _PgVector(resolved)
    return _FallbackVector(resolved)


# ---------------------------------------------------------------------------
# Declarative base (local to services/ml — no shared Base exists here)
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for the ``kb_*`` corpus and eval tables."""


# Special indexes (ANN HNSW/IVFFLAT on kb_chunk_embeddings.embedding, GIN on
# kb_chunks.fts, GIN trigram on kb_entities.canonical_name) and the
# vector/pg_trgm extensions are intentionally NOT declared here. They require
# extension-aware DDL and are owned by the gated migration runner (task 1.5).
# The b-tree / unique indexes below mirror the design.md DDL.


class KbSourceRegistry(Base):
    """Authoritative source list with authority tier, license and watermark."""

    __tablename__ = "kb_source_registry"
    __table_args__ = (
        CheckConstraint("trust_tier BETWEEN 1 AND 4", name="ck_kb_source_registry_trust_tier"),
        Index("idx_kb_source_registry_tier", "trust_tier"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    trust_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    fetch_mode: Mapped[str] = mapped_column(Text, nullable=False, default="api", server_default="api")
    license_code: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    attribution: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    robots_respect: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_watermark: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    last_run_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["KbDocument"]] = relationship(
        "KbDocument", back_populates="source", cascade="all, delete-orphan"
    )


class KbDocument(Base):
    """One row per source document with provenance and idempotency hash."""

    __tablename__ = "kb_documents"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_kb_documents_source_external"),
        CheckConstraint("trust_tier BETWEEN 1 AND 4", name="ck_kb_documents_trust_tier"),
        Index("idx_kb_documents_hash", "content_hash"),
        Index("idx_kb_documents_tier_date", "trust_tier", "effective_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kb_source_registry.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    title: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    url: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    lang: Mapped[str] = mapped_column(Text, nullable=False, default="en", server_default="en")
    doc_type: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    trust_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    effective_date: Mapped[Any | None] = mapped_column(Date, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    ingested_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    source: Mapped[KbSourceRegistry] = relationship("KbSourceRegistry", back_populates="documents")
    chunks: Mapped[list["KbChunk"]] = relationship(
        "KbChunk", back_populates="document", cascade="all, delete-orphan"
    )


class KbChunk(Base):
    """Structure-aware chunk with parent-child links and a FTS tsvector."""

    __tablename__ = "kb_chunks"
    __table_args__ = (
        CheckConstraint("trust_tier BETWEEN 1 AND 4", name="ck_kb_chunks_trust_tier"),
        Index("idx_kb_chunks_document", "document_id", "ord"),
        Index("idx_kb_chunks_parent", "parent_id"),
        Index("idx_kb_chunks_section", "section_type"),
        # idx_kb_chunks_fts (GIN on fts) is created by the migration runner.
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("kb_chunks.id", ondelete="CASCADE"), nullable=True
    )
    chunk_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    section_path: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    section_type: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    char_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lang: Mapped[str] = mapped_column(Text, nullable=False, default="en", server_default="en")
    trust_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    fts: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[KbDocument] = relationship("KbDocument", back_populates="chunks")
    parent: Mapped["KbChunk | None"] = relationship(
        "KbChunk", remote_side="KbChunk.id", back_populates="children"
    )
    children: Mapped[list["KbChunk"]] = relationship(
        "KbChunk", back_populates="parent", cascade="all, delete-orphan"
    )
    embedding: Mapped["KbChunkEmbedding | None"] = relationship(
        "KbChunkEmbedding", back_populates="chunk", uselist=False, cascade="all, delete-orphan"
    )
    sparse_terms: Mapped[list["KbChunkSparseTerm"]] = relationship(
        "KbChunkSparseTerm", back_populates="chunk", cascade="all, delete-orphan"
    )
    entity_links: Mapped[list["KbChunkEntity"]] = relationship(
        "KbChunkEntity", back_populates="chunk", cascade="all, delete-orphan"
    )


class KbChunkEmbedding(Base):
    """Dense embedding row: one per chunk, carrying the model_id discriminator."""

    __tablename__ = "kb_chunk_embeddings"
    # idx_kb_chunk_emb_hnsw / ivfflat ANN index is created by the migration runner.

    chunk_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kb_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[Any] = mapped_column(vector_column_type(), nullable=False)
    is_degraded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    chunk: Mapped[KbChunk] = relationship("KbChunk", back_populates="embedding")


class KbChunkSparseTerm(Base):
    """Learned-lexical (bge-m3) sparse term -> weight row for a chunk."""

    __tablename__ = "kb_chunk_sparse_terms"
    __table_args__ = (
        Index("idx_kb_sparse_chunk", "chunk_id"),
        Index("idx_kb_sparse_term", "term"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kb_chunks.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)

    chunk: Mapped[KbChunk] = relationship("KbChunk", back_populates="sparse_terms")


class KbEntity(Base):
    """RxNorm / UMLS normalized entity (the moat core)."""

    __tablename__ = "kb_entities"
    __table_args__ = (
        UniqueConstraint("cui", "rxcui", "canonical_name", name="uq_kb_entities_identity"),
        Index("idx_kb_entities_rxcui", "rxcui"),
        Index("idx_kb_entities_cui", "cui"),
        # idx_kb_entities_name_trgm (GIN trgm) is created by the migration runner.
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cui: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    rxcui: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    synonyms_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_vocab: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    chunk_links: Mapped[list["KbChunkEntity"]] = relationship(
        "KbChunkEntity", back_populates="entity", cascade="all, delete-orphan"
    )


class KbChunkEntity(Base):
    """Chunk <-> entity mention link (composite primary key)."""

    __tablename__ = "kb_chunk_entities"
    __table_args__ = (Index("idx_kb_chunk_entities_entity", "entity_id"),)

    chunk_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kb_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kb_entities.id", ondelete="CASCADE"), primary_key=True
    )
    mention_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )

    chunk: Mapped[KbChunk] = relationship("KbChunk", back_populates="entity_links")
    entity: Mapped[KbEntity] = relationship("KbEntity", back_populates="chunk_links")


class KbEntityEdge(Base):
    """Drug-interaction / contraindication graph edge for graphrag (P4)."""

    __tablename__ = "kb_entity_edges"
    __table_args__ = (
        UniqueConstraint(
            "source_entity", "target_entity", "relation", name="uq_kb_entity_edges_triple"
        ),
        Index("idx_kb_entity_edges_source", "source_entity"),
        Index("idx_kb_entity_edges_target", "target_entity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_entity: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kb_entities.id", ondelete="CASCADE"), nullable=False
    )
    target_entity: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kb_entities.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, server_default="0.5")
    provenance: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvalSet(Base):
    """Golden Vietnamese Q&A evaluation item."""

    __tablename__ = "eval_set"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    qid: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    question_vi: Mapped[str] = mapped_column(Text, nullable=False)
    question_en: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    expected_rxcui: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    relevant_doc_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    gold_answer_vi: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    must_cite: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    category: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    results: Mapped[list["EvalRunResult"]] = relationship(
        "EvalRunResult", back_populates="eval_item", cascade="all, delete-orphan"
    )


class EvalRunResult(Base):
    """Per-question metrics for a single eval harness execution."""

    __tablename__ = "eval_run_result"
    __table_args__ = (Index("idx_eval_run_result_run", "run_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    qid: Mapped[str] = mapped_column(
        Text, ForeignKey("eval_set.qid", ondelete="CASCADE"), nullable=False
    )
    recall_at_k: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    ndcg_at_k: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    faithfulness: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    citation_acc: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    latency_ms: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    eval_item: Mapped[EvalSet] = relationship("EvalSet", back_populates="results")
