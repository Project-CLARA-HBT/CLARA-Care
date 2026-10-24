# PH11-A09 Risk Register & FHIR Security Assessment

- **Phase:** PH11 (FHIR R4 interoperability production profiles)
- **Agent:** A09 (Docs + research evidence)
- **Worktree:** `/dev/shm/clara_worktrees/PH11_A09`
- **Branch:** `phase/ph11-a09`
- **Base Commit SHA:** `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
- **Frozen HEAD SHA:** `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
- **Status:** **PASSED**
- **Date:** 2026-10-24

---

## 1. Executive Summary & Audit Profile

Subagent **A09** completed the **FHIR auth scopes and endpoint security documentation and audit** for Phase PH11 across:
1. `docs/interoperability/FHIR_SMART_AUTH_SCOPES_AND_ENDPOINT_SECURITY.md` (SMART-on-FHIR OAuth2/OIDC specification, scope matrix, discovery endpoint, CapabilityStatement conformance).
2. `docs/implementation/FHIR_ENDPOINT_SECURITY_ARCHITECTURE.md` (FastAPI gateway pipeline, scheme disambiguation, OCC concurrency, rate limits, audit events).
3. `docs/research/FHIR_AUTH_SECURITY_THREAT_MODEL_AND_AUDIT.md` (STRIDE threat analysis, formal invariant proofs).
4. `artifacts/PH11/A09/test_fhir_auth_scopes_and_security.py` (Focused test suite verifying parser, RBAC/ABAC mapping, anti-prescribing guard, discovery configuration, docs hygiene).

---

## 2. FHIR Interoperability Threat & Risk Register

| Risk ID | Threat Description | Severity | Likelihood | Impact | Current Controls & Defenses | Residual Gap / Next Phase Recommendation |
|---|---|---|---|---|---|---|
| **RSK-FHIR-01** | **Cross-Tenant Resource Probing & Enumeration (IDOR)** | **CRITICAL** | High | Critical | • `resolve_profile_scope` verifies account ownership or active `FamilyAccessGrant`.<br>• Uniform HTTP 404 (`scope_forbidden`) emitted for missing and unpermitted profiles alike, preventing enumeration. | Enforce row-level security (RLS) policies in PostgreSQL across all tenant-partitioned clinical tables. |
| **RSK-FHIR-02** | **Scope Smuggling & Prescribing Privilege Escalation** | **CRITICAL** | Medium | Critical | • SMART scope intersection engine checks actor role against scope capability.<br>• Prescribing hard-guard rejects `MedicationRequest.c` for any non-doctor persona.<br>• Self-reported medications emit exclusively as `MedicationStatement`. | Add automated runtime linting for outbound FHIR bundles to ensure no prescription orders leak from unverified sources. |
| **RSK-FHIR-03** | **Bearer Scheme Downgrade to Cookie Session (CSRF Bypass)** | **HIGH** | Medium | High | • `_has_bearer_scheme` performs case-insensitive scheme matching.<br>• If Bearer scheme is chosen, authentication binds strictly to the Bearer credential.<br>• Invalid, expired, or malformed Bearer tokens fail immediately with 401; zero fallback to cookie session. | Maintain strict integration tests in CI verifying that bad Bearer headers never trigger cookie-authenticated state mutations. |
| **RSK-FHIR-04** | **Replay of Stolen or Revoked Access Tokens** | **HIGH** | Low | High | • Every access token contains a cryptographic `jti` identifier.<br>• User logout or credential revocation registers the `jti` in a distributed Redis denylist with TTL matching token expiry.<br>• `_reject_if_revoked` checks denylist on every protected route. | Ensure multi-region Redis replication maintains low-latency cache sync for instantaneous revocation propagation. |
| **RSK-FHIR-05** | **Denial of Service via Bloated Bundles or Deep Recursion** | **HIGH** | Medium | High | • Hard bundle bounds enforced: `MAX_BUNDLE_BYTES = 1,000,000`, `MAX_ENTRIES = 500`, `MAX_DEPTH = 20`, `MAX_STRING = 20,000`.<br>• Rate limiting at reverse proxy: 60 req/min for consumers, 300 req/min for system clients. | Implement stream-based JSON parsing for prospective FHIR batch exports to conserve worker memory. |
| **RSK-FHIR-06** | **PHI/PII Leakage in Telemetry & Audit Trails** | **HIGH** | Medium | High | • OpenTelemetry metrics and Prometheus counters capture only numerical counts, tenant IDs, endpoints, and HTTP status codes.<br>• Zero patient identifiers, prompt strings, or medical terms in telemetry labels. | Enforce CI regex scanner on all new metrics declarations to block sensitive label names. |
| **RSK-FHIR-07** | **TOCTOU Race Condition on Concurrent Resource Mutation** | **MEDIUM** | Medium | Medium | • Optimistic Concurrency Control (OCC) requires `If-Match` header with current version `ETag`.<br>• Mismatched versions reject modification with HTTP 412 (`Precondition Failed`). | Validate database-level row locking semantics under high concurrency in load tests. |

---

## 3. Defense-in-Depth Verification Matrix

1. **Network & Transport Tier:** TLS 1.3 enforced; external spoofed headers (`X-Tenant-ID`, `X-User-Role`) stripped at ingress; mTLS mandatory for backend system clients.
2. **Authentication Gateway Tier:** RFC 7235 Bearer extraction; dual-key overlap decoding; Redis `jti` denylist validation; strict CSRF boundary.
3. **Authorization & RBAC Tier:** `require_roles("normal", "doctor", "researcher", "admin")`; administrative access barred from PHI (`platform_root_cannot_read_phi: true`).
4. **ABAC & Profile Scope Tier:** `resolve_profile_scope` validates profile ownership and family access grants; purpose of use validation (`self_care`, `clinician_handoff`, etc.).
5. **SMART Scope Tier:** Granular v1/v2 scope syntax validation; prescription hard-guard prevents unauthorized order generation.
6. **Data & Concurrency Tier:** `If-Match` ETag validation prevents lost updates; 1 MB / 500 entry bounds prevent resource exhaustion; immutable `AuditEvent` and `Provenance` records emitted.
