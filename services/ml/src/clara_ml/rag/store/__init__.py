"""Persistent RAG store package (P0/P2).

Owns the pgvector-backed corpus schema (``schema.py``), the gated migration
runner (``migrations.py`` — task 1.5), the write/UPSERT adapter
(``document_store.py`` — task 3.1) and the online hybrid retriever
(``hybrid_retriever.py`` — task 5.8).

The schema layer (``schema.py``, task 1.2) and the gated migration runner
(``migrations.py``, task 1.5) are defined here. Importing this package performs
no database side effects: the migration runner derives its DDL purely and only
touches the database when invoked with an engine.
"""

from clara_ml.rag.store.cache import (  # noqa: F401
    CacheBackend,
    EmbeddingCache,
    InMemoryCacheBackend,
    JsonFileCacheBackend,
    SemanticQueryCache,
    cosine_similarity,
    normalize_text,
)
from clara_ml.rag.store.corpus_stats import (  # noqa: F401
    CorpusStats,
    CorpusStatsSource,
)
from clara_ml.rag.store.document_store import (  # noqa: F401
    ChunkEntityLink,
    ChunkRow,
    DocumentStore,
    EmbeddingRow,
    IngestDocument,
    SparseTermRow,
)
from clara_ml.rag.store.graph_store import (  # noqa: F401
    EdgeInput,
    EntityEdge,
    EntityInput,
    GraphStore,
)
from clara_ml.rag.store.hybrid_retriever import (  # noqa: F401
    HybridRetriever,
    RetrievalFilters,
)
from clara_ml.rag.store.migrations import (  # noqa: F401
    MigrationConfigError,
    MigrationResult,
    migration_sql,
    run_migrations,
)
from clara_ml.rag.store.schema import (  # noqa: F401
    DEFAULT_EMBEDDING_DIM,
    VALID_TRUST_TIERS,
    Base,
    DegradedEmbeddingNotAllowedError,
    EmbeddingDimMismatchError,
    EvalRunResult,
    EvalSet,
    InvalidTrustTierError,
    KbChunk,
    KbChunkEmbedding,
    KbChunkEntity,
    KbChunkSparseTerm,
    KbDocument,
    KbEntity,
    KbEntityEdge,
    KbSourceRegistry,
    MissingModelIdError,
    WriteInvariantError,
    assert_embedding_dim,
    configured_embedding_dim,
    guard_degraded_row,
    has_pgvector,
    require_model_id,
    validate_embedding_row,
    validate_trust_tier,
    vector_column_type,
)
from clara_ml.rag.store.sparse_index import (  # noqa: F401
    RankedChunk,
    SparseFilters,
    SparseIndex,
    bm25_sanity_holds,
    build_tsquery_terms,
    term_frequency,
    to_tsquery_string,
    ts_config_for_lang,
)

__all__ = [
    "Base",
    "DEFAULT_EMBEDDING_DIM",
    "VALID_TRUST_TIERS",
    "ChunkEntityLink",
    "ChunkRow",
    "DocumentStore",
    "EmbeddingRow",
    "IngestDocument",
    "SparseTermRow",
    "DegradedEmbeddingNotAllowedError",
    "EmbeddingDimMismatchError",
    "EvalRunResult",
    "EvalSet",
    "InvalidTrustTierError",
    "KbChunk",
    "KbChunkEmbedding",
    "KbChunkEntity",
    "KbChunkSparseTerm",
    "KbDocument",
    "KbEntity",
    "KbEntityEdge",
    "KbSourceRegistry",
    "MigrationConfigError",
    "MigrationResult",
    "MissingModelIdError",
    "WriteInvariantError",
    "RankedChunk",
    "SparseFilters",
    "SparseIndex",
    "HybridRetriever",
    "RetrievalFilters",
    "EdgeInput",
    "EntityEdge",
    "EntityInput",
    "GraphStore",
    "CacheBackend",
    "EmbeddingCache",
    "InMemoryCacheBackend",
    "JsonFileCacheBackend",
    "SemanticQueryCache",
    "cosine_similarity",
    "normalize_text",
    "CorpusStats",
    "CorpusStatsSource",
    "bm25_sanity_holds",
    "build_tsquery_terms",
    "term_frequency",
    "to_tsquery_string",
    "ts_config_for_lang",
    "assert_embedding_dim",
    "configured_embedding_dim",
    "guard_degraded_row",
    "has_pgvector",
    "migration_sql",
    "require_model_id",
    "run_migrations",
    "validate_embedding_row",
    "validate_trust_tier",
    "vector_column_type",
]
