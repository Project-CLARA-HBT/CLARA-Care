# Implementation Plan: RAG Knowledge Pipeline (clara-care)

## Overview

This plan converts the approved design into incremental, coding-only steps organized as phase epics (P0 → P5) plus three cross-cutting epics (Admin API + Web, Safety-guardrail preservation, and checkpoints). Every step builds on the previous ones and ends by wiring the new capability into the system behind a feature flag, so no orphaned code is left unintegrated.

Languages: Python for `services/ml` and `services/api`; TypeScript (Next.js) for `apps/web`. Property tests use `hypothesis` (Python, ≥100 iterations) and `fast-check` (TypeScript web). Test sub-tasks are marked optional with `*` and may be skipped for a faster MVP; core implementation sub-tasks are never optional.

Build order honors shared-module-before-consumer: `config` flags and `schema` first, then `embedder`, `document_store`, `chunker`, RRF/`reranker`/`sparse_index`, then `hybrid_retriever`, then normalization, graph, eval, admin, and safety regression. Backward compatibility and medical-safety preservation are maintained throughout: all new flags default to legacy behavior.

## Tasks

- [x] 1. Epic P0 — Foundations (pgvector, schema, migrations, fail-loud embedding, config, self-check)
  - [x] 1.1 Add additive RAG_* feature flags and tuning settings to `services/ml/.../config.py`
    - Add `RAG_PERSISTENT_STORE_ENABLED` (false), `RAG_PERSISTENT_RETRIEVAL_ENABLED` (false), `RAG_INGESTION_ENABLED` (false), `RAG_ENTITY_NORMALIZATION_ENABLED` (false), `RAG_BIOMED_GRAPH_ENABLED`/`RAG_TRUST_TIER_RANKING_ENABLED` (false), `RAG_SEMANTIC_CACHE_ENABLED` (false), `RAG_EVAL_CI_ENABLED` (false)
    - Add `RAG_EMBEDDING_FAIL_LOUD` (true), `RAG_EMBEDDING_ALLOW_DEGRADED` (false), `RAG_EMBEDDING_DIM`, `RAG_ANN_INDEX_KIND`, `RAG_RERANKER_TIMEOUT_MS`, `min_results`, trust-floor settings
    - All defaults reproduce today's behavior exactly (purely additive)
    - _Requirements: 1.2, 2.3, 3.1, 3.2, 8.2, 10.3, 12.2_
  - [x] 1.2 Define `kb_*` SQLAlchemy models, DDL, and write-invariant validators in `rag/store/schema.py`
    - Models/DDL for `kb_source_registry`, `kb_documents`, `kb_chunks`, `kb_chunk_embeddings`, `kb_chunk_sparse_terms`, `kb_entities`, `kb_chunk_entities`, `kb_entity_edges`, `eval_set`, `eval_run_result`
    - `assert_embedding_dim(dim) == RAG_EMBEDDING_DIM`; `trust_tier ∈ {1,2,3,4}` validator; degraded-row guard helper; `model_id` discriminator on embedding rows
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 2.5_
  - [x]* 1.3 Write property test for embedding dimension invariant
    - **Property 11: Embedding dimension invariant**
    - **Validates: Requirements 1.3**
  - [x]* 1.4 Write unit tests for schema write-invariant validators
    - `trust_tier` rejection outside `{1,2,3,4}`; degraded-row guard; `model_id` presence
    - _Requirements: 1.4, 1.5, 2.5_
  - [x] 1.5 Implement additive, gated migration runner in `rag/store/migrations.py`
    - `CREATE EXTENSION IF NOT EXISTS vector` and `pg_trgm`; create `kb_*` tables; parameterize dense column as `vector(RAG_EMBEDDING_DIM)`; create ANN index per `RAG_ANN_INDEX_KIND` (HNSW/IVFFLAT); idempotent (`IF NOT EXISTS`); no destructive `ALTER`/`DROP` on existing tables
    - _Requirements: 1.1, 1.2, 1.6_
  - [x]* 1.6 Write integration test for additive, idempotent migration
    - Re-running migration is a no-op; pre-existing tables untouched (regression guard for additive-only schema changes)
    - _Requirements: 1.1, 1.6_
  - [x] 1.7 Replace silent 16-dim hash fallback with fail-loud / degraded-mode `Embedding_Client` in `rag/embedder.py`
    - Add `EmbeddingUnavailableError`; `embed_documents`/`embed_query` raise in production on API failure; return explicit `is_degraded=true` sentinel vectors only in non-prod when `RAG_EMBEDDING_ALLOW_DEGRADED`; remove `BgeM3EmbedderStub` from the production path; `EmbedBatchResult` carries per-vector degraded flags; assert model dimension via schema helper
    - _Requirements: 2.1, 2.2, 2.3_
  - [x]* 1.8 Write property test for degraded-mode fail-loud (production)
    - **Property 9: Degraded-mode fail-loud (production)**
    - **Validates: Requirements 2.1, 2.2**
  - [x]* 1.9 Write regression test that the 16-dim SHA-256 hash stub is unreachable on the production path
    - Replaces the legacy silent-degrade behavior with explicit fail-loud
    - _Requirements: 2.2_
  - [x] 1.10 Implement startup self-check in `rag/store/health.py` and wire into `services/ml` startup
    - Validate `vector` extension + `kb_*` tables exist before honoring any persistent flag; otherwise force the legacy in-memory path and log a descriptive error rather than failing requests
    - _Requirements: 3.4_
  - [x]* 1.11 Write unit test for self-check forcing legacy path when extension/tables absent
    - Regression: persistent flag on + infra missing must not crash the request path
    - _Requirements: 3.4_
  - [x] 1.12 Create backfill harness skeleton in `ingestion/backfill.py`
    - Watermark-driven entrypoint callable by scheduler/admin; no-op when `RAG_INGESTION_ENABLED` is false
    - _Requirements: 4.6_

- [x] 2. Checkpoint — P0 foundations
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Epic P1 — Offline ingestion + chunking (connectors, cleaning, chunker, embed-once, orchestrator, scheduler)
  - [x] 3.1 Implement `Document_Store` write/UPSERT adapter in `rag/store/document_store.py` (shared persistence module)
    - `upsert_document`, `upsert_chunks`, `write_embeddings`, `write_sparse_terms`, `link_entities`, `content_hash_exists`, `transaction()`, `checkpoint()`; enforce schema validators (dim, trust_tier, degraded guard); parameterized SQL only
    - _Requirements: 1.3, 1.5, 2.5, 4.4, 15.2_
  - [x]* 3.2 Write unit tests for `Document_Store` write rejections
    - Dimension mismatch, out-of-range `trust_tier`, degraded-row rejection at the store boundary
    - _Requirements: 1.3, 1.5, 2.5_
  - [x] 3.3 Implement `Source_Connector` protocol and `RawRecord` in `ingestion/connectors/base.py`
    - `fetch(window, cursor) -> (list[RawRecord], next_cursor | None)`; carry `trust_tier`/`license_code`/`attribution` from registry
    - _Requirements: 6.1, 6.4, 6.5_
  - [x] 3.4 Implement API-first connectors: `pubmed_eutils`, `openfda`, `dailymed_spl`, `rxnorm`, `europepmc`
    - `pubmed_eutils` uses the already-wired NCBI E-utilities key; reuse `clients/drug_sources` patterns; API-only; cursor/window paging
    - _Requirements: 6.1, 6.4, 6.5_
  - [x] 3.5 Implement robots-respecting `vn_crawl` gap-fill connector in `ingestion/connectors/vn_crawl.py`
    - Respect `robots.txt` and configured allowed-domains list; only HTML path
    - _Requirements: 6.2_
  - [x]* 3.6 Write unit tests for `vn_crawl` robots.txt + allowed-domains enforcement
    - _Requirements: 6.2_
  - [x] 3.7 Implement `Cleaner` in `ingestion/cleaning.py`
    - Boilerplate/navigation strip; Vietnamese unicode normalize (reuse `nlp/unicode_utils`); PII redact (reuse `nlp/pii_filter.redact_pii`); produce deterministic `clean_text` used for both `content_hash` and chunking
    - _Requirements: 15.1, 4.2_
  - [x]* 3.8 Write property test for PII-free persisted text
    - **Property 22: PII-free persisted data**
    - **Validates: Requirements 15.1**
  - [x] 3.9 Implement `Structure_Aware_Chunker` in `ingestion/chunking.py`
    - `SECTION_TAXONOMY`; `detect_sections` tiling `[0,len)` gap-free (SPL sections / guideline headings); parent/child chunks; token windows with bounded overlap; full coverage; contiguous `ord`; section-bounded children; no empty chunks
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  - [x]* 3.10 Write property test for chunk coverage (no data loss)
    - **Property 1: Chunk coverage (no data loss)**
    - **Validates: Requirements 5.1**
  - [x]* 3.11 Write property test for chunk ordering and contiguity
    - **Property 2: Chunk ordering and contiguity**
    - **Validates: Requirements 5.2**
  - [x]* 3.12 Write property test for section-bounded child chunks
    - **Property 3: Section bounded**
    - **Validates: Requirements 5.3**
  - [x]* 3.13 Write property test for child token bound and overlap
    - **Property 4: Child token bound**
    - **Validates: Requirements 5.4**
  - [x]* 3.14 Write regression test that chunking preserves full content (no 520-character truncation)
    - Locks the replacement of the legacy 520-char blind cut
    - _Requirements: 5.1, 5.6_
  - [x] 3.15 Implement `EmbeddingBuilder` in `ingestion/embedding_builder.py`
    - Embed once per chunk batch (dense + bge-m3 sparse); production refuses to emit/persist degraded vectors; produce `EmbeddingRow` + `SparseTermRow`
    - _Requirements: 2.4, 4.4_
  - [x] 3.16 Implement `Ingestion_Orchestrator` in `ingestion/orchestrator.py`
    - fetch → clean → link (injected `EntityLinker`, no-op default for P1) → chunk → embed once → persist; idempotent (`content_hash` skip); resumable (watermark checkpoint per batch); atomic per document (`transaction()`); abort document on degraded embedding in production; emit `IngestionReport` where `fetched == inserted + updated + skipped + failed`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 2.4_
  - [x]* 3.17 Write property test for idempotent ingestion
    - **Property 5: Idempotent ingestion**
    - **Validates: Requirements 4.1, 4.2**
  - [x]* 3.18 Write property test for resumable ingestion
    - **Property 6: Resumable ingestion**
    - **Validates: Requirements 4.3**
  - [x]* 3.19 Write property test for atomic per-document persistence
    - **Property 7: Atomic per-document persistence**
    - **Validates: Requirements 4.4**
  - [x]* 3.20 Write property test for no degraded persistence in production
    - **Property 10: No degraded persistence**
    - **Validates: Requirements 2.4, 2.5**
  - [x] 3.21 Implement `Scheduler` in `ingestion/scheduler.py` and seed `Source_Registry`
    - Incremental schedule + per-source watermark management; seed `kb_source_registry` rows with `trust_tier`/`license_code`/`attribution`/`fetch_mode`
    - _Requirements: 4.6, 6.3_

- [x] 4. Checkpoint — P1 ingestion
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Epic P2 — Hybrid retrieval (RRF reuse, sparse/BM25, cross-encoder, hybrid retriever, flag-routed wiring)
  - [x] 5.1 Extend `RRF_Fuser` in `rag/retrieval/score_engine.py` reusing `_RRF_K=60` / `_RRF_BLEND=0.14`
    - `rrf_fuse(dense, sparse)`: `score(c) = Σ 1/(k + rank_L(c))`; output is a permutation of the union; corroboration never penalized
    - _Requirements: 7.2, 7.3, 7.4_
  - [x]* 5.2 Write property test for RRF fusion monotonicity
    - **Property 13: RRF fusion monotonicity**
    - **Validates: Requirements 7.4**
  - [x]* 5.3 Write property test for RRF set conservation
    - **Property 14: RRF set conservation**
    - **Validates: Requirements 7.3**
  - [x] 5.4 Implement `Sparse_Index` in `rag/store/sparse_index.py`
    - `tsvector` BM25 read (`ts_rank_cd`, language-aware `simple`/`english`) + bge-m3 sparse-term read; build BM25 query; parameterized SQL
    - _Requirements: 7.2, 7.5_
  - [x]* 5.5 Write property test for BM25 ranking sanity
    - **Property 15: BM25 ranking sanity**
    - **Validates: Requirements 7.5**
  - [x] 5.6 Add `cross_encoder` rerank strategy with timeout-safe fallback in `rag/retrieval/reranker.py`
    - Derive scores from `bge-reranker-v2-m3`; output permutation of input prefix (remainder appended in order); on timeout (`RAG_RERANKER_TIMEOUT_MS`) or error return original order; deterministic for same `(query, docs, strategy)`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  - [x]* 5.7 Write property test for reranker permutation and timeout-safety
    - **Property 16: Reranker permutation and timeout-safety**
    - **Validates: Requirements 8.1, 8.2**
  - [x] 5.8 Implement `Hybrid_Retriever` in `rag/store/hybrid_retriever.py`
    - Embed only the query (exactly one embedding call, no document re-embed); run dense ANN (pgvector) + sparse in parallel; RRF fuse; cross-encoder rerank top-N; attach provenance `{source, url, trust_tier, effective_date, RXCUI, lang}`; injected `QueryExpander` (no-op default for P2); return ≤ `top_k`; result set ⊆ union of candidates
    - _Requirements: 7.1, 7.2, 7.6, 7.7_
  - [x]* 5.9 Write property test for query-only embedding
    - **Property 12: Query-only embedding**
    - **Validates: Requirements 7.1**
  - [x]* 5.10 Write property test for citation / provenance integrity
    - **Property 20: Citation / provenance integrity**
    - **Validates: Requirements 7.6**
  - [x] 5.11 Wire flag-routed retrieval path + gap-fill into `rag/pipeline.py`
    - `RAG_PERSISTENT_RETRIEVAL_ENABLED` routing (legacy in-memory vs `Hybrid_Retriever`); exactly one deterministic path per query (no mixed embed-all / embed-query semantics); gap-fill via live connectors when below `min_results`/trust floor, then async persist; honor self-check forced-legacy
    - _Requirements: 3.1, 3.2, 3.3, 3.5_
  - [x]* 5.12 Write regression test that flag-off reproduces legacy in-memory retrieval and never mixes embedding semantics
    - _Requirements: 3.1, 3.3_

- [x] 6. Checkpoint — P2 hybrid retrieval
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Epic P3 — Entity normalization (UMLS client, entity linker, query expander, wiring)
  - [x] 7.1 Implement `umls_client` (UTS) in `rag/normalize/umls_client.py`
    - License-aware, cached RxNorm/UMLS/VSAC lookups; graceful behavior on rate-limit/unauthorized
    - _Requirements: 9.4, 15.3_
  - [x] 7.2 Implement `Entity_Linker` in `rag/normalize/entity_linker.py`
    - Map mentions → RXCUI/CUI with synonyms (brand/generic, VN/EN); soundness (canonical name or a synonym occurs normalized in the text); non-empty `rxcui` or `cui`; cache-idempotent; cached fallback when UTS unavailable
    - _Requirements: 9.1, 9.4_
  - [x]* 7.3 Write property test for entity-link soundness
    - **Property 19: Entity-link soundness**
    - **Validates: Requirements 9.1**
  - [x] 7.4 Implement `Query_Expander` in `rag/normalize/query_expander.py`
    - Recall-only superset (`set(original) ⊆ set(expanded.terms)`); VN↔EN + brand↔generic; every added term traces to a `LinkedEntity` or the curated VN↔EN lexicon; empty expansion preserves original terms when UTS unavailable
    - _Requirements: 9.2, 9.3, 9.4_
  - [x]* 7.5 Write property test for synonym-expansion soundness (recall-only)
    - **Property 18: Synonym-expansion soundness (recall-only)**
    - **Validates: Requirements 9.2, 9.3**
  - [x] 7.6 Wire `Entity_Linker` into ingestion and `Query_Expander` into online query
    - Inject linker into `Ingestion_Orchestrator`; inject expander into `Hybrid_Retriever` via `rag/pipeline.py`; gated behind `RAG_ENTITY_NORMALIZATION_ENABLED`
    - _Requirements: 9.1, 9.2_

- [x] 8. Epic P4 — Knowledge graph + provenance (edges, graphrag from DB, trust-tier/recency ranking)
  - [x] 8.1 Populate `kb_entity_edges` from RxNorm/UMLS relationships + label signals
    - Implement `ingestion/graph_builder.py` and `rag/store/graph_store.py`; edges carry `relation`/`weight`/`provenance`; UPSERT with conflict handling
    - _Requirements: 10.1_
  - [x] 8.2 Modify `GraphRAG_Engine` in `rag/graphrag.py` to load edges from `kb_entity_edges`
    - Replace static-JSON edge load with DB load via `graph_store`
    - _Requirements: 10.1_
  - [x]* 8.3 Write regression test that graphrag loads edges from the DB (not the static JSON file)
    - _Requirements: 10.1_
  - [x] 8.4 Add trust-tier + recency ranking in `rag/store/hybrid_retriever.py`
    - Among chunks with equal pre-tier relevance, rank lower `trust_tier` number at least as high; use `effective_date` as a recency signal; ensure all surfaced rows have `trust_tier ∈ {1,2,3,4}`
    - _Requirements: 10.2, 10.4_
  - [x]* 8.5 Write property test for trust-tier ordering
    - **Property 21: Trust-tier ordering**
    - **Validates: Requirements 10.2**
  - [x] 8.6 Provide `trust_tier` + recency to FIDES as a tighten-only input in `rag/pipeline.py`
    - Behind `RAG_TRUST_TIER_RANKING_ENABLED`; inputs can only tighten, never loosen, a blocking verdict
    - _Requirements: 10.3_

- [x] 9. Epic P5 — Eval + caching + hardening (golden set, metrics, harness/CI gate, caches, scheduling, stats)
  - [x] 9.1 Seed golden VN Q&A `eval_set` in `rag/eval/golden_set.py`
    - Load/curate `eval_set` rows (`question_vi`, `expected_rxcui`, `relevant_doc_ids`, `must_cite`, `category`)
    - _Requirements: 11.1_
  - [x] 9.2 Implement metrics in `rag/eval/metrics.py`
    - `recall@k`, `nDCG@k`, `faithfulness`, `citation_acc` — each bounded in `[0,1]`
    - _Requirements: 11.2_
  - [x]* 9.3 Write unit tests for metric bounds in `[0,1]`
    - _Requirements: 11.2_
  - [x] 9.4 Implement `Eval_Harness` + CI gate in `rag/eval/harness.py`
    - Write exactly one `eval_run_result` row per `qid`; record `config_json` snapshot; leave corpus unmodified; fail CI gate when `recall@k` < floor OR persistent hybrid `recall@k` < legacy in-memory baseline on the same set
    - _Requirements: 11.1, 11.3, 11.4_
  - [x]* 9.5 Write property test for retrieval recall floor
    - **Property 17: Retrieval recall floor**
    - **Validates: Requirements 11.3**
  - [x] 9.6 Implement `Cache_Layer` in `rag/store/cache.py`
    - Persistent embedding cache (byte-identical re-read per `model_id`); semantic query cache gated by `RAG_SEMANTIC_CACHE_ENABLED`
    - _Requirements: 12.1, 12.2_
  - [x]* 9.7 Write property test for embedding determinism (cache)
    - **Property 8: Embedding determinism (cache)**
    - **Validates: Requirements 12.1**
  - [x] 9.8 Wire embedding cache into `Embedding_Client.embed_query` (cache-first) in `rag/embedder.py`
    - Serve a cached vector when present before issuing a live embedding request
    - _Requirements: 12.3_
  - [x] 9.9 Wire semantic query cache + scheduled incremental ingestion + stats source
    - Semantic-cache lookup in `rag/pipeline.py`; scheduled incremental wiring in `ingestion/scheduler.py`; corpus/degraded stats aggregation (docs, chunks, degraded count, coverage)
    - _Requirements: 12.2, 4.6_

- [x] 10. Epic — Admin API + Web (RBAC endpoints + Vietnamese admin surfaces)
  - [x] 10.1 Implement RBAC `/admin/rag/*` endpoints in `services/api/.../admin_rag.py` and register in router
    - Ingestion run/status, sources list/update, eval run/results, corpus stats; each behind `require_roles("admin")`; proxied to `services/ml`; introduce no unauthenticated public endpoint
    - _Requirements: 13.1, 13.2, 13.4_
  - [x]* 10.2 Write property test for RBAC on admin endpoints
    - **Property 23: RBAC on admin endpoints**
    - **Validates: Requirements 13.1**
  - [x] 10.3 Build Vietnamese rag-ingestion admin page (`apps/web/app/admin/rag-ingestion/page.tsx`)
    - Trigger/monitor ingestion jobs, per-source watermarks, degraded-mode alerts; all copy in Vietnamese
    - _Requirements: 13.3_
  - [x] 10.4 Build Vietnamese rag-eval admin page (`apps/web/app/admin/rag-eval/page.tsx`)
    - Display `recall@k` / `nDCG@k` / `faithfulness` / `citation_acc` trends across runs; all copy in Vietnamese
    - _Requirements: 11.5_
  - [x]* 10.5 Write fast-check property test for eval-dashboard data transform / role-gated UI state
    - TypeScript property test (`fast-check`) for trend-aggregation transform and admin-only UI gating
    - _Requirements: 11.5, 13.1_
  - [x] 10.6 Extend knowledge-sources admin page (`apps/web/app/admin/knowledge-sources/page.tsx`)
    - Surface `source_registry` `trust_tier`/`license_code`/`attribution`/`enabled` toggles; Vietnamese copy
    - _Requirements: 13.2, 15.3_

- [x] 11. Epic — Safety-guardrail preservation regression suite
  - [x] 11.1 Build guardrail preservation golden-output harness
    - Capture pre-flag baseline decisions and compare flag-off vs flag-on for DDI floor, dosage/legal block, consent gate, emergency fast-path, FIDES CRITICAL, and admin RBAC; assert no behavioral drift
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  - [x]* 11.2 Write property test for DDI medium-floor preserved
    - **Property 24: DDI medium-floor preserved**
    - **Validates: Requirements 14.1**
  - [x]* 11.3 Write property test for dosage / legal block preserved
    - **Property 25: Dosage / legal block preserved**
    - **Validates: Requirements 14.2**
  - [x]* 11.4 Write property test for consent gate preserved
    - **Property 26: Consent gate preserved**
    - **Validates: Requirements 14.3**
  - [x]* 11.5 Write property test for emergency fast-path preserved
    - **Property 27: Emergency fast-path preserved**
    - **Validates: Requirements 14.4**
  - [x]* 11.6 Write property test for FIDES CRITICAL block preserved
    - **Property 28: FIDES CRITICAL block preserved**
    - **Validates: Requirements 14.5**

- [x] 12. Backend checkpoint
  - Run `ruff` plus `services/ml` and `services/api` test suites (including `hypothesis` property tests); confirm guardrail preservation tests pass. Ensure all tests pass, ask the user if questions arise.

- [x] 13. Final checkpoint
  - Run lint and the API / ML / web / mobile test suites; confirm `recall@k` is not regressed vs the legacy in-memory baseline (eval gate). Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional tests (property, unit, integration, regression) and can be skipped for a faster MVP; core implementation tasks are never optional.
- Each task references specific requirement clauses for traceability; property-test tasks additionally cite their design Property number (1–28).
- All 28 Correctness Properties are mapped: P1→3.10, P2→3.11, P3→3.12, P4→3.13, P5→3.17, P6→3.18, P7→3.19, P8→9.7, P9→1.8, P10→3.20, P11→1.3, P12→5.9, P13→5.2, P14→5.3, P15→5.5, P16→5.7, P17→9.5, P18→7.5, P19→7.3, P20→5.10, P21→8.5, P22→3.8, P23→10.2, P24→11.2, P25→11.3, P26→11.4, P27→11.5, P28→11.6.
- Behavior-replacing changes carry explicit regression tests: embedder fail-loud (1.9), chunking vs 520-char truncation (3.14), flag-off legacy equivalence (5.12), graphrag DB-vs-JSON (8.3), and the full guardrail preservation suite (11.x).
- Shared modules are built before their consumers (`config`/`schema` → `embedder`/`document_store`/`chunker` → RRF/`reranker`/`sparse_index` → `hybrid_retriever` → normalization → graph → eval → admin), enabling per-area parallelism.
- Backward compatibility is preserved: every flag defaults to legacy behavior, migrations are additive/idempotent, and a startup self-check forces the legacy path when persistent infrastructure is absent.
- Same-file tasks are serialized into different waves to avoid write conflicts: `pipeline.py` (5.11, 7.6, 8.6, 9.9), `embedder.py` (1.7, 9.8), `hybrid_retriever.py` (5.8, 8.4), `orchestrator.py` (3.16, 7.6), `scheduler.py` (3.21, 9.9).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.5", "1.7", "1.10", "1.12", "3.1", "3.3"] },
    { "id": 2, "tasks": ["1.3", "1.4", "1.6", "1.8", "1.9", "1.11", "3.2", "3.4", "3.5", "3.7", "3.9"] },
    { "id": 3, "tasks": ["3.6", "3.8", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15"] },
    { "id": 4, "tasks": ["3.16", "5.1", "5.4", "5.6"] },
    { "id": 5, "tasks": ["3.17", "3.18", "3.19", "3.20", "3.21", "5.2", "5.3", "5.5", "5.7", "5.8"] },
    { "id": 6, "tasks": ["5.9", "5.10", "5.11", "7.1"] },
    { "id": 7, "tasks": ["5.12", "7.2", "7.4", "8.4"] },
    { "id": 8, "tasks": ["7.3", "7.5", "7.6", "8.1", "8.5"] },
    { "id": 9, "tasks": ["8.2", "8.6", "9.1", "9.2", "9.6"] },
    { "id": 10, "tasks": ["8.3", "9.3", "9.4", "9.7", "9.8", "10.1"] },
    { "id": 11, "tasks": ["9.5", "9.9", "10.2", "10.3", "10.4", "10.6", "11.1"] },
    { "id": 12, "tasks": ["10.5", "11.2", "11.3", "11.4", "11.5", "11.6"] }
  ]
}
```
