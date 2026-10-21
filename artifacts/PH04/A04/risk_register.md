# Risk Register: Multi-Tenant Organizations, Workspace Membership Invitations & RAG Retrieval Isolation

- **Phase:** PH04 (Multi-tenant organizations và workspaces)
- **Agent ID:** A04
- **Role:** ML + retrieval
- **Worktree:** `/dev/shm/clara_worktrees/PH04_A04`
- **Branch:** `phase/ph04-a04`
- **Base SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`

---

## 1. Risk Assessment Matrix

| Risk ID | Vulnerability / Threat Vector | Severity | Likelihood | Impact | Mitigation / Architectural Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH04-A04-01** | **Cross-Tenant Knowledge Retrieval Leakage:** A user from Tenant A queries the persistent RAG store and retrieves clinical documents or protocols belonging exclusively to Tenant B. | Critical | High | Exposure of confidential hospital/clinic clinical guidelines, patient cohorts, or internal policies across organizational boundaries. | `KbDocument` and `KbSourceRegistry` schemas explicitly store `tenant_id`. Both dense pgvector ANN SQL (`_DENSE_SQL`) and sparse BM25 statement builders (`_apply_filters`) join `kb_documents` and enforce strict filtering: only `tenant_id == current_tenant` or `tenant_id IS NULL / 'global'` are visible. | **Mitigated** |
| **RR-PH04-A04-02** | **Pending / Revoked Invitation Privilege Escalation:** An unaccepted invitation token or pending invitation allows an unverified user to invoke tenant ML inference models. | High | Medium | Unauthorized compute consumption and premature exposure of tenant workspace context to recipients who have not consented or completed onboarding. | `enforce_workspace_ml_membership` mandates that membership status must be strictly `ACTIVE`. Any `INVITED`, `PENDING`, `EXPIRED`, `REVOKED`, or `SUSPENDED` status fails closed with HTTP 403 (`invitation_pending_unauthorized`, etc.). | **Mitigated** |
| **RR-PH04-A04-03** | **Cross-Tenant Semantic Cache Collision & Poisoning:** Identical queries from Tenant A and Tenant B share an unpartitioned semantic query cache or vector similarity candidates, returning Tenant A's cached response to Tenant B. | High | Medium | Direct cross-tenant data leakage via cached retrieval documents and vector similarity matches. | `SemanticQueryCache` partitions both exact normalized keys and vector-similarity candidate entries by `tenant_id` (`exact_key = f"{tenant_id}::{norm}"`). Vector similarity searches filter candidates strictly by matching tenant scope. | **Mitigated** |
| **RR-PH04-A04-04** | **Tenant Identifier Path Traversal & Injection:** An adversary submits malicious `tenant_id` payloads (e.g. `../../etc/passwd`, SQL injection strings, or arbitrary symbols) to bypass boundaries. | High | Low | Potential SQL tampering, cache key confusion, or directory traversal. | `sanitize_tenant_id` validates tenant identifiers against strict alphanumeric regex `^[A-Za-z0-9_\-\.]{1,128}$` and rejects path separators (`/`, `\`, `..`) with HTTP 403 `invalid_tenant_identifier`. | **Mitigated** |
| **RR-PH04-A04-05** | **Cross-Tenant Invitation Scope Hopping:** An invitation context minted for Tenant A is passed in requests to Tenant B's endpoints. | High | Low | Cross-tenant boundary circumvention. | `WorkspaceInvitationContext` validates that `invitation_context.tenant_id == requested_tenant_id`, raising `tenant_context_mismatch` if they diverge. | **Mitigated** |
| **RR-PH04-A04-06** | **Zero-PII / Zero-PHI Disclosure in Error Responses:** Rejection of tenant boundary violations leaks recipient email, patient name, or sensitive diagnostic queries in the error envelope. | Critical | Low | Violation of HIPAA, GDPR, and CLARA zero-PII privacy invariants. | `TenantBoundaryError` returns standardized, constant-time error codes (`invitation_pending_unauthorized`, `membership_revoked`, etc.) and fixed detail strings without reflecting patient names, emails, or user queries. | **Mitigated** |
| **RR-PH04-A04-07** | **Stateless Adapter Data Retention (OCR / ASR):** Audio recordings or prescription image buffers persist across requests and are accessible to other tenants. | Critical | Low | Cross-tenant document and voice leakage. | OCR and ASR service adapters operate strictly in-memory per request without global disk persistence, inter-request memory caching, or cross-tenant session sharing. Verified via static inspection and unit tests. | **Mitigated** |

---

## 2. Invariants Maintained

1. **Fail-Closed by Default:** Any tenant context specified without valid, authenticated, active membership verification fails closed with HTTP 403.
2. **Double-Partitioned Retrieval:** Both dense vector search and sparse lexical search enforce the tenant boundary in SQL before candidates reach fusion or reranking.
3. **No-PII Error Handling:** Error responses carry only machine error codes and static descriptions, never dynamic user input.
4. **Deterministic Migration & Schema Compatibility:** Added `tenant_id` columns and indexes on `kb_source_registry` and `kb_documents` maintain backward compatibility with existing migrations and un-tenanted global records.
