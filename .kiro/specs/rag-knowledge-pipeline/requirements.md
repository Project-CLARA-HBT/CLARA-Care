# Requirements Document

## Introduction

This document formalizes the requirements for the **RAG Knowledge Pipeline** overhaul of clara-care, derived from the approved design (`design.md`). The feature replaces today's query-time, in-memory RAG flow (live per-query fetch, embed-every-document, 520-character truncation, silent 16-dimension hash fallback) with a defensible knowledge pipeline split into two planes:

- an **offline ingestion plane** (scheduled / background, off the request path) that fetches, cleans, entity-links, structure-aware chunks, embeds once, and persists a curated, normalized, Vietnamese-localized medical corpus; and
- an **online retrieval plane** (in-request, fast) that normalizes and expands the query, embeds **only the query**, runs hybrid dense + sparse search over a persistent pgvector index, fuses with RRF, reranks with a cross-encoder, and synthesizes with the LLM.

The work is delivered in six independently shippable, feature-flagged phases:

- **P0 — Foundations:** persistent pgvector corpus and schema, additive gated migrations, embedding-dimension invariant, fail-loud / explicit degraded-mode embedding, and feature-flagged backward compatibility.
- **P1 — Offline ingestion + chunking:** idempotent, resumable, atomic-per-document ingestion with API-first connectors, robots-respecting gap-fill crawl, source authority registry, and structure-aware full-coverage chunking.
- **P2 — Hybrid retrieval:** dense ANN plus real BM25 / bge-m3 sparse retrieval over the persistent index, RRF fusion reusing the existing scaffolding, query-only embedding, and cross-encoder reranking.
- **P3 — Entity normalization:** RxNorm/UMLS entity linking and recall-only synonym / VN↔EN query expansion.
- **P4 — Knowledge graph + provenance:** drug-interaction graph from `kb_entity_edges` and trust-tier / recency ranking as a FIDES-tightening input.
- **P5 — Eval, caching, hardening:** golden Vietnamese Q&A eval harness with recall@k / nDCG / faithfulness / citation-accuracy CI gating, persistent embedding cache, semantic query cache, and admin dashboards.

The rollout is **backward compatible behind feature flags**: when a persistent-path flag is off, the system behaves exactly as it does today. All existing **medical-safety guardrails are preserved unchanged** (DDI medium-floor, dosage/legal blocking, consent gate, emergency fast-path, FIDES CRITICAL blocking, admin RBAC). Persisted data is PII-free and complies with UMLS/SNOMED/RxNorm licensing and attribution. End-user-facing copy remains Vietnamese; this requirements document and internal identifiers are in English.

The requirements below are organized so they map cleanly to phases P0→P5 and so that each of the 28 numbered Correctness Properties in `design.md` traces to at least one acceptance-criterion clause (see the Property-to-Requirement Traceability appendix). Property-based testing is used; acceptance criteria are written to be precise and testable.

## Glossary

### Domain Terms

- **RXCUI**: RxNorm Concept Unique Identifier; the stable identifier RxNorm assigns to a normalized drug concept (ingredient, brand, or clinical drug).
- **CUI**: UMLS Concept Unique Identifier; the stable identifier the UMLS Metathesaurus assigns to a clinical concept across source vocabularies.
- **UMLS / UTS**: Unified Medical Language System; UTS (UMLS Terminology Services) is the licensed API surface for RxNorm, the UMLS Metathesaurus, and VSAC.
- **SPL**: Structured Product Labeling; the standardized format for U.S. drug labels (e.g., DailyMed) with canonical sections such as Indications, Contraindications, Drug Interactions, Boxed Warning, and Dosage.
- **BM25**: A bag-of-words ranking function using term frequency, inverse document frequency, and length normalization; realized here via Postgres full-text search (`tsvector` / `ts_rank_cd`).
- **RRF**: Reciprocal Rank Fusion; combines multiple ranked candidate lists into one using the score `1 / (k + rank)`. The existing fusion contract uses constants `_RRF_K = 60` and `_RRF_BLEND = 0.14`.
- **HNSW**: Hierarchical Navigable Small World; a graph-based approximate-nearest-neighbor (ANN) index supported by pgvector, used for low-latency dense retrieval with strong recall.
- **pgvector**: A Postgres extension providing a `vector` column type and ANN index types (HNSW, IVFFLAT) for dense embedding search.
- **cross-encoder**: A reranking model (here `bge-reranker-v2-m3`) that jointly scores a (query, document) pair, used to reorder fused candidates by relevance.
- **chunk parent-child**: The two-level chunk structure where a parent chunk represents a document section and child chunks represent token-bounded windows within that section, linked by `parent_id` / `parent_ord`.
- **trust tier**: An integer authority ranking in `{1, 2, 3, 4}` (1 = regulator/label, highest authority) attached to sources, documents, and chunks, used for ranking and as a FIDES input.
- **degraded-mode**: An explicit, flagged fallback embedding state (`is_degraded = true`) permitted only in non-production environments; it replaces the old silent 16-dimension SHA-256 hash fallback.
- **FIDES**: The claim-verification component (`factcheck/fides_lite.py`) that produces verdicts and blocks answers on CRITICAL / contradiction findings.
- **DDI**: Drug-Drug Interaction; surfaced by CareGuard with a severity floor of "medium" and openFDA free-text-derived severity capped at "high".

### Quality / Metric Terms

- **recall@k**: The fraction of gold-relevant documents retrieved within the top `k` results.
- **nDCG@k**: Normalized Discounted Cumulative Gain at `k`; a rank-sensitive retrieval quality metric.
- **faithfulness**: The fraction of answer claims supported by retrieved context.
- **citation accuracy**: The fraction of answer citations that resolve to gold-required source ids/urls.

### System / Component Names

- **Knowledge_Pipeline**: The overall RAG pipeline (`rag/pipeline.py`) that routes between legacy in-memory and persistent paths and orchestrates synthesis and guardrails.
- **Document_Store**: The persistence adapter (`rag/store/`) that owns schema, gated migrations, and UPSERTs of documents, chunks, embeddings, sparse terms, and entity links.
- **Embedding_Client**: The embedding client (`rag/embedder.py`) producing dense vectors (and bge-m3 sparse terms) with fail-loud / degraded-mode behavior.
- **Ingestion_Orchestrator**: The offline orchestrator (`ingestion/orchestrator.py`) driving fetch → clean → link → chunk → embed → persist, idempotently and resumably.
- **Scheduler**: The incremental ingestion scheduler (`ingestion/scheduler.py`) that triggers runs using per-source watermarks.
- **Structure_Aware_Chunker**: The chunker (`ingestion/chunking.py`) producing full-coverage, section-aware parent/child chunks.
- **Source_Connector**: A source connector (`ingestion/connectors/`) fetching records API-first, with `vn_crawl` as the only robots-respecting HTML path.
- **Source_Registry**: The authoritative source list (`kb_source_registry`) holding trust tier, license, attribution, fetch mode, and watermark.
- **Hybrid_Retriever**: The online retriever (`rag/store/hybrid_retriever.py`) running dense ANN + sparse/BM25 over the persistent index, fusing and reranking.
- **RRF_Fuser**: The fusion function (`rag/retrieval/score_engine.py`) reusing the existing RRF scaffolding.
- **Sparse_Index**: The sparse/BM25 read/write layer (`rag/store/sparse_index.py`) over `tsvector` and bge-m3 sparse terms.
- **Cross_Encoder_Reranker**: The reranker (`rag/retrieval/reranker.py`) extended with a `cross_encoder` strategy.
- **Entity_Linker**: The RxNorm/UMLS linker (`rag/normalize/entity_linker.py`) mapping mentions to RXCUI/CUI plus synonyms.
- **Query_Expander**: The expander (`rag/normalize/query_expander.py`) performing recall-only synonym and VN↔EN expansion.
- **GraphRAG_Engine**: The graph-walk component (`rag/graphrag.py`) loading edges from `kb_entity_edges`.
- **Eval_Harness**: The evaluation harness (`rag/eval/`) computing metrics and enforcing CI gates.
- **Cache_Layer**: The persistent embedding cache and semantic query cache (`rag/store/cache.py`).
- **Admin_API**: The RBAC-protected admin endpoints (`services/api/.../admin_rag.py`) proxied to `services/ml`.
- **Admin_Web_Surface**: The Vietnamese admin web pages (`apps/web/app/admin/rag-ingestion`, `rag-eval`, `knowledge-sources`).
- **Cleaner**: The normalizer (`ingestion/cleaning.py`) performing boilerplate strip, Vietnamese unicode normalization, and PII redaction.
- **Safety_Guardrails**: The preserved guardrail set (CareGuard DDI floor, dosage/legal blocking, consent gate, emergency fast-path, FIDES verdicts).

## Requirements

### Requirement 1: Persistent Corpus and Schema (P0)

**User Story:** As a platform engineer, I want a persistent pgvector corpus with additive, gated schema migrations and a fixed embedding dimension, so that documents are embedded once and stored durably without disrupting existing tables.

#### Acceptance Criteria

1. WHEN the gated schema migration runs, THE Document_Store SHALL create the `kb_*` corpus tables and the `vector` and `pg_trgm` extensions additively, without altering or dropping any existing table.
2. THE Document_Store SHALL parameterize the dense embedding column type as `vector(RAG_EMBEDDING_DIM)` via migration, using the dimension configured for the active embedding model.
3. WHEN a dense embedding row is written, IF its dimension is not equal to `RAG_EMBEDDING_DIM`, THEN THE Document_Store SHALL reject the write.
4. THE Document_Store SHALL store a `model_id` discriminator on every embedding row so that a future model swap coexists without dimension ambiguity.
5. WHEN a document row or chunk row is persisted, IF its `trust_tier` is outside the set `{1, 2, 3, 4}`, THEN THE Document_Store SHALL reject the write.
6. WHERE `RAG_ANN_INDEX_KIND` selects HNSW or IVFFLAT, THE Document_Store SHALL create the corresponding ANN index on `kb_chunk_embeddings.embedding` during migration.

### Requirement 2: Fail-Loud / Degraded-Mode Embedding (P0)

**User Story:** As a clinical-safety owner, I want embedding failures to fail loudly instead of silently degrading to a 16-dimension hash, so that retrieval quality can never collapse undetected in production.

#### Acceptance Criteria

1. IF the embedding API fails WHILE `environment` is `production`, THEN THE Embedding_Client SHALL raise `EmbeddingUnavailableError`.
2. WHILE `environment` is `production`, THE Embedding_Client SHALL produce only model-dimensioned vectors and SHALL NOT return a 16-dimension SHA-256 hash vector or any sentinel vector on any code path.
3. WHERE `environment` is non-production AND `RAG_EMBEDDING_ALLOW_DEGRADED` is true, IF the embedding API fails, THEN THE Embedding_Client SHALL return explicit sentinel vectors with each result flagged `is_degraded = true`.
4. IF a degraded embedding is produced during ingestion WHILE `environment` is `production`, THEN THE Ingestion_Orchestrator SHALL abort the current document and persist no embedding row for it.
5. WHILE `environment` is `production`, THE Document_Store SHALL hold no `kb_chunk_embeddings` row with `is_degraded = true`.

### Requirement 3: Feature-Flagged Backward-Compatible Rollout and Cutover (P0)

**User Story:** As a release manager, I want every new capability behind a feature flag with a deterministic path selection, so that the legacy in-memory pipeline keeps serving traffic and cutover is safe and reversible.

#### Acceptance Criteria

1. WHERE `RAG_PERSISTENT_RETRIEVAL_ENABLED` is false, THE Knowledge_Pipeline SHALL use the legacy in-memory retriever with live fetch and produce retrieval behavior equivalent to the pre-change system.
2. WHERE `RAG_PERSISTENT_RETRIEVAL_ENABLED` is true, THE Knowledge_Pipeline SHALL consult the persistent store first and use live connector fetch only as a gap-fill fallback.
3. WHEN handling a single query, THE Knowledge_Pipeline SHALL select exactly one retrieval path and SHALL NOT combine embed-every-document and embed-query-only behavior within that query.
4. IF a persistent-path flag is enabled WHILE the `vector` extension or `kb_*` tables are absent, THEN THE Knowledge_Pipeline SHALL force the legacy in-memory path and log a descriptive error rather than failing the request.
5. WHEN persistent retrieval returns fewer than `min_results` results or all results fall below the configured trust floor, THE Knowledge_Pipeline SHALL trigger live connector gap-fill, serve the results, and asynchronously persist the new content.

### Requirement 4: Offline Ingestion — Idempotent, Resumable, Atomic, Scheduled (P1)

**User Story:** As a data engineer, I want offline ingestion that is idempotent, resumable, and atomic per document, so that re-runs and crashes never corrupt or duplicate the corpus.

#### Acceptance Criteria

1. WHEN ingestion runs a second time over identical upstream data, THE Ingestion_Orchestrator SHALL insert zero new chunks and SHALL report `skipped` equal to `fetched`.
2. WHEN a record's `content_hash` already exists for its source and external id, THE Ingestion_Orchestrator SHALL skip the record, using a `content_hash` that is deterministic over the normalized clean text.
3. IF ingestion is interrupted, THEN upon restart THE Ingestion_Orchestrator SHALL resume from the persisted watermark and SHALL reprocess no record already committed, eventually persisting the same corpus as an uninterrupted run.
4. IF a failure occurs while persisting a document, THEN THE Ingestion_Orchestrator SHALL leave either all of that document's chunks, embeddings, and entity links committed or none of them.
5. WHEN an ingestion run completes, THE Ingestion_Orchestrator SHALL emit an `IngestionReport` in which `fetched` equals `inserted + updated + skipped + failed`.
6. WHEN a scheduled incremental ingestion triggers, THE Scheduler SHALL start the run from the per-source watermark recorded in the Source_Registry.

### Requirement 5: Structure-Aware Chunking with Full Coverage (P1)

**User Story:** As a retrieval engineer, I want structure-aware chunking that preserves full document coverage, so that no clinical content is lost the way the old 520-character truncation lost it.

#### Acceptance Criteria

1. WHEN chunking a clean document, THE Structure_Aware_Chunker SHALL produce chunk spans `[char_start, char_end)` whose union covers every non-whitespace character of the clean text at least once.
2. THE Structure_Aware_Chunker SHALL assign `ord` values `0..n-1` with no gaps or duplicates, and every child chunk SHALL reference an existing parent `ord`.
3. THE Structure_Aware_Chunker SHALL ensure every child chunk lies entirely within its parent section span, crosses no section boundary, and carries a `section_type` within `SECTION_TAXONOMY`.
4. THE Structure_Aware_Chunker SHALL produce child chunks each with `token_count` less than or equal to `max_child_tokens`, and adjacent child windows SHALL overlap by at most `overlap_tokens`.
5. WHEN the document is an SPL label, THE Structure_Aware_Chunker SHALL split on canonical SPL sections; WHEN the document is a guideline, THE Structure_Aware_Chunker SHALL split on the heading hierarchy into parent and child chunks.
6. THE Structure_Aware_Chunker SHALL produce no chunk whose text is empty after trimming.

### Requirement 6: Source Connectors, Gap-Fill Crawl, and Authority Registry (P1)

**User Story:** As a content curator, I want API-first source connectors with a robots-respecting gap-fill crawl and an authority registry, so that the corpus is sourced legally and tagged with provenance and trust.

#### Acceptance Criteria

1. WHEN fetching from any source other than the Vietnamese gap-fill crawl, THE Source_Connector SHALL use the source's API rather than HTML scraping.
2. WHILE performing the Vietnamese gap-fill crawl, THE Source_Connector SHALL respect `robots.txt` and the configured allowed-domains list.
3. THE Source_Registry SHALL record `trust_tier`, `license_code`, `attribution`, `fetch_mode`, and `last_watermark` for each source.
4. WHEN producing a record, THE Source_Connector SHALL carry the `trust_tier`, `license_code`, and `attribution` from the Source_Registry into that record.
5. WHEN fetching a window, THE Source_Connector SHALL return the fetched records together with a next cursor (or `None` when exhausted) to support resumable ingestion.

### Requirement 7: Hybrid Retrieval over the Persistent Index (P2)

**User Story:** As a user asking a clinical question, I want fast hybrid retrieval over the persistent index that embeds only my query, so that answers are grounded in the curated corpus without per-query document re-embedding.

#### Acceptance Criteria

1. WHEN an online retrieval call is made, THE Hybrid_Retriever SHALL issue exactly one embedding request, embedding only the query, and SHALL embed no document at query time.
2. WHEN retrieving, THE Hybrid_Retriever SHALL run dense ANN search (pgvector HNSW/IVFFLAT) and sparse BM25 search (`tsvector` plus bge-m3 sparse terms) and fuse the ranked lists with the RRF_Fuser reusing constants `_RRF_K = 60` and `_RRF_BLEND = 0.14`.
3. WHEN fusing candidate lists, THE RRF_Fuser SHALL output a permutation of the union of the dense and sparse candidates, adding no fabricated chunk and dropping no candidate.
4. IF a chunk ranks no worse than another chunk in both candidate lists, THEN THE RRF_Fuser SHALL assign the first chunk a fused score greater than or equal to that of the second chunk, so that corroboration is never penalized.
5. WHEN a query term with favorable corpus IDF appears with higher term frequency in chunk A than in chunk B that lacks the term, THE Sparse_Index SHALL rank chunk A at least as high as chunk B.
6. WHEN returning results to synthesis, THE Hybrid_Retriever SHALL attach provenance metadata `{source, url, trust_tier, effective_date, RXCUI, lang}` to every returned Document, and every citation in the produced answer SHALL resolve to a retrieved chunk's id or url.
7. THE Hybrid_Retriever SHALL return at most `top_k` Documents sorted by fused-then-reranked score descending, with the result set contained within the union of the dense and sparse candidates.

### Requirement 8: Cross-Encoder Reranking (P2)

**User Story:** As a retrieval engineer, I want a cross-encoder reranker with timeout-safe fallback, so that relevance improves without risking latency or result loss.

#### Acceptance Criteria

1. WHEN reranking, THE Cross_Encoder_Reranker SHALL output a permutation of its input prefix, inventing no document and dropping no document, with any remainder appended in original order.
2. IF the reranker exceeds `RAG_RERANKER_TIMEOUT_MS` or raises an error, THEN THE Cross_Encoder_Reranker SHALL return the original input order.
3. WHERE the strategy is `cross_encoder`, THE Cross_Encoder_Reranker SHALL derive scores from the `bge-reranker-v2-m3` model.
4. WHEN reranking the same query and documents with the same strategy, THE Cross_Encoder_Reranker SHALL produce the same ordering.

### Requirement 9: Medical Entity Normalization and Recall-Only Query Expansion (P3)

**User Story:** As a Vietnamese-speaking user, I want drug and condition mentions normalized to RxNorm/UMLS and my query expanded with synonyms and VN↔EN translations, so that retrieval recall improves without losing my original intent.

#### Acceptance Criteria

1. WHEN linking entities in a text, THE Entity_Linker SHALL return only `LinkedEntity` objects that each carry a non-empty `rxcui` or `cui` and whose canonical name or one of whose synonyms occurs (normalized) in that text.
2. WHEN expanding a query, THE Query_Expander SHALL produce a term set that contains every original query term as a subset (recall-only expansion).
3. WHEN expanding a query, THE Query_Expander SHALL ensure every added term traces to a `LinkedEntity` or the curated VN↔EN lexicon.
4. IF the UTS API is unavailable, THEN THE Entity_Linker SHALL use cached entities and otherwise return an empty expansion that preserves the original query terms.

### Requirement 10: Knowledge Graph and Trust-Tier / Recency Ranking (P4)

**User Story:** As a clinical-safety owner, I want a drug-interaction knowledge graph and authority-aware ranking, so that higher-authority and more recent evidence ranks higher and tightens claim verification.

#### Acceptance Criteria

1. THE GraphRAG_Engine SHALL load drug-interaction and contraindication edges from `kb_entity_edges` rather than from a static JSON file.
2. WHEN two chunks have equal pre-tier relevance, THE Hybrid_Retriever SHALL rank the higher-authority chunk (lower `trust_tier` number) at least as high as the lower-authority chunk, and all persisted rows SHALL have `trust_tier` within `{1, 2, 3, 4}`.
3. WHERE `RAG_TRUST_TIER_RANKING_ENABLED` is true, THE Knowledge_Pipeline SHALL provide `trust_tier` and recency to FIDES as inputs that can only tighten and never loosen a blocking verdict.
4. WHEN ranking candidates, THE Hybrid_Retriever SHALL use document `effective_date` as a recency signal.

### Requirement 11: Evaluation Harness and CI Gate (P5)

**User Story:** As an engineering lead, I want a golden Vietnamese Q&A eval harness wired into CI, so that retrieval and answer quality are measured and regressions are blocked.

#### Acceptance Criteria

1. WHEN the eval harness runs, THE Eval_Harness SHALL write exactly one `eval_run_result` row per `qid` containing `recall@k`, `nDCG@k`, `faithfulness`, `citation_acc`, and `latency_ms`.
2. THE Eval_Harness SHALL produce `recall@k`, `nDCG@k`, `faithfulness`, and `citation_acc` values each within the closed interval `[0, 1]`.
3. IF `recall@k` falls below the configured floor OR persistent hybrid `recall@k` falls below the legacy in-memory baseline on the same golden set, THEN THE Eval_Harness SHALL fail the CI gate.
4. WHEN a run completes, THE Eval_Harness SHALL record a `config_json` snapshot of the flag and model configuration and SHALL leave the corpus unmodified.
5. WHEN an administrator opens the eval dashboard, THE Admin_Web_Surface SHALL display `recall@k`, `nDCG@k`, `faithfulness`, and `citation_acc` trends across runs in Vietnamese.

### Requirement 12: Caching — Persistent Embedding Cache and Semantic Query Cache (P5)

**User Story:** As a platform engineer, I want persistent embedding and semantic query caches, so that repeated embeddings are deterministic and live API dependence is reduced.

#### Acceptance Criteria

1. WHEN a text is embedded twice under the same `model_id`, THE Cache_Layer SHALL return a byte-identical vector on the second read.
2. WHERE `RAG_SEMANTIC_CACHE_ENABLED` is true, THE Cache_Layer SHALL serve a cached answer or candidate set for a query that is semantically equivalent to a previously cached query.
3. WHEN an online query embedding is requested, THE Cache_Layer SHALL serve a cached vector when present before issuing a live embedding request.

### Requirement 13: Admin RBAC Endpoints and Vietnamese Admin Surfaces (P1–P5)

**User Story:** As an administrator, I want RBAC-protected endpoints and Vietnamese admin pages to manage ingestion and evaluation, so that operations are controlled and observable.

#### Acceptance Criteria

1. IF a request to any `/admin/rag/*` endpoint presents a non-admin token, THEN THE Admin_API SHALL respond with HTTP 403; IF the request presents no token, THEN THE Admin_API SHALL respond with HTTP 401.
2. THE Admin_API SHALL expose ingestion run and status, source listing and update, eval run and results, and corpus stats endpoints, each behind the `require_roles("admin")` dependency and proxied to `services/ml`.
3. WHEN an administrator opens the ingestion page, THE Admin_Web_Surface SHALL present ingestion triggering, per-source watermarks, and degraded-mode alerts in Vietnamese.
4. THE Admin_API SHALL introduce no unauthenticated public endpoint.

### Requirement 14: Safety-Guardrail Preservation (Cross-Cutting)

**User Story:** As a clinical-safety owner, I want every existing medical-safety guardrail preserved unchanged, so that the pipeline overhaul never weakens patient protections.

#### Acceptance Criteria

1. WHEN CareGuard flags a medication pair, THE Safety_Guardrails SHALL surface a DDI severity no lower than "medium" and SHALL cap openFDA free-text-derived severity at "high".
2. IF a query triggers dosage blocking or `legal_guard` blocking under the legacy system, THEN THE Safety_Guardrails SHALL produce the same block decision after the pipeline change.
3. IF a self-medication flow has no recorded consent, THEN THE Safety_Guardrails SHALL block the flow identically to the current consent-gate behavior.
4. WHEN a query is classified as an emergency, THE Safety_Guardrails SHALL take the emergency fast-path before any retrieval or synthesis change can alter routing.
5. IF an answer and evidence combination yields a CRITICAL or contradiction FIDES verdict under the legacy system, THEN THE Safety_Guardrails SHALL produce the same blocking verdict, with `trust_tier` and recency able only to tighten the verdict.

### Requirement 15: PII-Free Persistence and Data Licensing / Attribution Compliance (Cross-Cutting)

**User Story:** As a compliance owner, I want persisted data to be PII-free and licensed content properly attributed, so that the corpus meets privacy and UMLS/SNOMED/RxNorm licensing obligations.

#### Acceptance Criteria

1. WHEN a chunk is persisted, THE Cleaner SHALL redact personally identifiable information so that the persisted `kb_chunks.text` matches no phone, identifier, or email pattern defined in `nlp/pii_filter`.
2. THE Document_Store SHALL persist no raw phone number, personal identifier, or email value in any corpus table.
3. WHEN content derived from UMLS, SNOMED, or RxNorm is persisted or surfaced, THE Knowledge_Pipeline SHALL record and honor the required `license_code` and `attribution` from the Source_Registry.

## Property-to-Requirement Traceability

The table below maps each of the 28 Correctness Properties in `design.md` to the requirement clause(s) it validates, so that every property resolves to at least one acceptance criterion.

| Property | Title | Validates Requirement(s) |
|----------|-------|--------------------------|
| 1 | Chunk coverage (no data loss) | 5.1 |
| 2 | Chunk ordering and contiguity | 5.2 |
| 3 | Section bounded | 5.3 |
| 4 | Child token bound | 5.4 |
| 5 | Idempotent ingestion | 4.1, 4.2 |
| 6 | Resumable ingestion | 4.3 |
| 7 | Atomic per-document persistence | 4.4 |
| 8 | Embedding determinism (cache) | 12.1 |
| 9 | Degraded-mode fail-loud (production) | 2.1, 2.2 |
| 10 | No degraded persistence | 2.4, 2.5 |
| 11 | Embedding dimension invariant | 1.3 |
| 12 | Query-only embedding | 7.1 |
| 13 | RRF fusion monotonicity | 7.4 |
| 14 | RRF set conservation | 7.3 |
| 15 | BM25 ranking sanity | 7.5 |
| 16 | Reranker permutation and timeout-safety | 8.1, 8.2 |
| 17 | Retrieval recall floor | 11.3 |
| 18 | Synonym-expansion soundness (recall-only) | 9.2, 9.3 |
| 19 | Entity-link soundness | 9.1 |
| 20 | Citation / provenance integrity | 7.6 |
| 21 | Trust-tier ordering | 10.2 |
| 22 | PII-free persisted data | 15.1 |
| 23 | RBAC on admin endpoints | 13.1 |
| 24 | DDI medium-floor preserved | 14.1 |
| 25 | Dosage / legal block preserved | 14.2 |
| 26 | Consent gate preserved | 14.3 |
| 27 | Emergency fast-path preserved | 14.4 |
| 28 | FIDES CRITICAL block preserved | 14.5 |
