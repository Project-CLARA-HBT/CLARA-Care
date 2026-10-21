# Test Report: Multi-Tenant Organizations, Workspace Membership Invitations & RAG Retrieval Isolation

- **Phase:** PH04 (Multi-tenant organizations và workspaces)
- **Agent ID:** A04
- **Role:** ML + retrieval
- **Worktree:** `/dev/shm/clara_worktrees/PH04_A04`
- **Branch:** `phase/ph04-a04`
- **Base SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`
- **Status:** **PASS (100% of 204 unit & property tests passed)**

---

## 1. Executive Summary & Verification Objectives

This test suite and audit verify the enforcement of multi-tenant security boundaries and workspace membership invitation gating across the ML service and RAG knowledge store:
1. **Workspace Membership Invitation Gate:** Verifies that pending or invited memberships (`WorkspaceMembershipStatus.INVITED` / `PENDING`) are strictly blocked from invoking tenant-scoped ML inference (`HTTP 403`, `invitation_pending_unauthorized`). Expired, revoked, suspended, and unauthenticated tenant access attempts fail closed.
2. **Persistent RAG Store Partitioning:** Verifies that `KbSourceRegistry` and `KbDocument` maintain `tenant_id` partitioning with dedicated indexes (`idx_kb_source_registry_tenant`, `idx_kb_documents_tenant`). Ingested documents preserve tenant assignment.
3. **No Cross-Tenant Retrieval Leakage:** Verifies that both dense vector search (`HybridRetriever._dense_search`) and sparse BM25 search (`SparseIndex.build_search_statement`) filter queries so that Tenant A cannot access Tenant B knowledge or documents.
4. **Semantic Query Cache Isolation:** Verifies that `SemanticQueryCache` isolates both exact key matches and vector-similarity candidate matches by `tenant_id`. Querying identical text in Tenant B does not hit Tenant A's cached documents.
5. **Zero-PII / Zero-PHI Safety Invariant:** Verifies that tenant boundary rejection envelopes never reflect or leak patient names, emails, medical symptoms, or query payloads.
6. **Stateless OCR and ASR Audit:** Audits `services/ocr` and `services/asr` ensuring neither service caches or leaks cross-tenant images or audio transcriptions across requests.

---

## 2. Test Execution Details

### Suite 1: Dedicated Tenant & Workspace Retrieval Isolation Suite
- **Command:** `PYTHONPATH="services/ml/src:services/api/src:." python3 -m pytest -v evaluation/tests/test_tenant_rag_isolation.py`
- **Exit Code:** `0`
- **Results:** 32 passed, 0 failed, 1 warning (deprecation warning for starlette testclient)
- **Detailed Vector Breakdown:**
  - `test_sanitize_tenant_id_valid`: Valid alphanumeric tenant identifiers preserved.
  - `test_sanitize_tenant_id_rejects_insecure_identifiers` (5 parametrized vectors): Path traversal (`../etc/passwd`, `tenant/../../sub`), injection tokens (`tenant$id`, SQL separators), and oversized identifiers (>128 chars) rejected with `403 invalid_tenant_identifier`.
  - `test_public_untenanted_scope_admitted`: Empty/None tenant_id correctly scopes to public/global knowledge.
  - `test_active_membership_admitted`: Active workspace members admitted to tenant ML capabilities.
  - `test_pending_and_invited_memberships_blocked_403`: Pending and invited statuses fail closed with HTTP 403 `invitation_pending_unauthorized`.
  - `test_expired_invitation_blocked_403`: Expired invitations rejected with HTTP 403 `invitation_expired`.
  - `test_revoked_and_suspended_memberships_blocked_403`: Revoked/suspended memberships rejected with HTTP 403 `membership_revoked`.
  - `test_unauthenticated_tenant_access_blocked_403`: Requests specifying tenant_id without membership validation rejected with HTTP 403 `unauthenticated_tenant_access`.
  - `test_invitation_context_evaluation_with_expiry`: Timestamp-based expiration dynamically marks context expired and blocks.
  - `test_invitation_context_tenant_mismatch_blocked`: Invitation token for Tenant A rejected when used on Tenant B (`tenant_context_mismatch`).
  - `test_workspace_role_gating`: Role requirements enforced; unauthorized roles (guest) blocked, authorized roles (clinician/admin/owner) admitted.
  - `test_kb_source_registry_and_documents_schema_have_tenant_id`: Confirms ORM column definitions and indexes on `KbSourceRegistry` and `KbDocument`.
  - `test_ingest_document_preserves_tenant_id`: IngestDocument dataclass and persistence retain tenant_id.
  - `test_sparse_filters_tenant_scoping`: BM25 `SparseFilters` generates SQL joins with `kb_documents` filtering by `tenant_id`.
  - `test_retrieval_filters_tenant_projection`: Hybrid retrieval filters project tenant_id cleanly to sparse arm.
  - `test_dense_sql_contains_tenant_boundary`: Dense pgvector SQL joins `kb_documents` and enforces `(d.tenant_id IS NULL OR d.tenant_id = 'global' OR d.tenant_id = CAST(:tenant_id AS text))`.
  - `test_semantic_cache_tenant_isolation_exact_match`: Multi-tenant exact cache isolation verified; Tenant B cannot hit Tenant A cache.
  - `test_semantic_cache_tenant_isolation_vector_seam`: Vector similarity search within cache does not match across tenant boundaries.
  - `test_compose_tenant_cache_key`: Key composition prefixes deterministically.
  - `test_chat_routed_allows_active_tenant_membership`: HTTP endpoint `/v1/chat/routed` admits active tenant membership and passes tenant_id to pipeline.
  - `test_chat_routed_blocks_pending_invitation`: HTTP endpoint `/v1/chat/routed` returns 403 for pending invitation.
  - `test_chat_routed_blocks_expired_membership`: HTTP endpoint `/v1/chat/routed` returns 403 for expired membership.
  - `test_chat_routed_blocks_revoked_membership`: HTTP endpoint `/v1/chat/routed` returns 403 for revoked membership.
  - `test_rag_poc_blocks_unauthenticated_tenant_access`: HTTP endpoint `/v1/rag/poc` returns 403 for unverified tenant_id.
  - `test_rag_poc_allows_active_tenant`: HTTP endpoint `/v1/rag/poc` admits verified active tenant.
  - `test_tenant_boundary_error_zero_pii`: Confirms error detail payload does not leak patient names, emails, or medical queries.
  - `test_ocr_endpoint_stateless_no_cross_tenant_memory`: Static audit confirms zero global request/image caches in OCR adapter.
  - `test_asr_endpoint_stateless_no_cross_tenant_memory`: Static audit confirms zero stateful audio/transcript buffers in ASR adapter.

### Suite 2: Existing ML Router, Pipeline & Admin RAG Suites
- **Command:** `PYTHONPATH=services/ml/src python3 -m pytest -q services/ml/tests/test_router.py services/ml/tests/test_model_router.py services/ml/tests/test_rag_pipeline.py services/ml/tests/test_admin_rag_handlers.py services/ml/tests/test_task_9_9_wiring.py services/ml/tests/test_migration_idempotency.py services/ml/tests/test_schema_validators.py`
- **Exit Code:** `0`
- **Results:** 123 passed in 23.40s.

### Suite 3: Existing RAG Retriever, Document Store & Ingestion Properties
- **Command:** `PYTHONPATH=services/ml/src python3 -m pytest -q services/ml/tests/test_hybrid_retriever_provenance_property.py services/ml/tests/test_hybrid_retriever_query_only_embed_property.py services/ml/tests/test_document_store_rejections.py services/ml/tests/test_ingestion_atomic_property.py services/ml/tests/test_ingestion_backfill.py services/ml/tests/test_ingestion_idempotent_property.py services/ml/tests/test_ingestion_no_degraded_persistence_property.py`
- **Exit Code:** `0`
- **Results:** 49 passed in 11.22s.

---

## 3. Linting and Static Type Analysis

- **Ruff Check:**
  - `uvx ruff check services/ml/src/clara_ml/tenant_boundary.py services/ml/src/clara_ml/rag/store/schema.py services/ml/src/clara_ml/rag/store/document_store.py services/ml/src/clara_ml/rag/store/hybrid_retriever.py services/ml/src/clara_ml/rag/store/sparse_index.py services/ml/src/clara_ml/rag/store/cache.py services/ml/src/clara_ml/rag/pipeline.py services/ml/src/clara_ml/main.py evaluation/tests/test_tenant_rag_isolation.py`
  - **Exit Code:** `0` (All checks passed!)

- **Mypy Strict Type Check:**
  - `PYTHONPATH="services/ml/src:services/api/src:." uvx mypy services/ml/src/clara_ml/tenant_boundary.py services/ml/src/clara_ml/rag/store/schema.py services/ml/src/clara_ml/rag/store/document_store.py services/ml/src/clara_ml/rag/store/hybrid_retriever.py services/ml/src/clara_ml/rag/store/sparse_index.py services/ml/src/clara_ml/rag/store/cache.py services/ml/src/clara_ml/rag/pipeline.py evaluation/tests/test_tenant_rag_isolation.py --ignore-missing-imports`
  - **Exit Code:** `0` (Success: no issues found in 8 source files)

- **Path ACL Conformance:**
  - `git status --porcelain | python3 scripts/ci/check_agent_path_acl.py A04 PH04 -`
  - **Exit Code:** `0` (PATH ACL CHECKER — PASSED)
