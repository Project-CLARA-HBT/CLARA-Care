# Risk Register: Phase PH00 — Agent A03 (Domain + GLHS Services)

**Phase:** PH00
**Agent:** A03
**Role:** Domain + GLHS services
**Worktree:** `/dev/shm/clara_worktrees/PH00_A03`
**Branch:** `phase/ph00-a03`
**Base Ground-Truth SHA:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
**Evaluation Date:** 2026-10-21

---

## 1. Safety and Security Invariants Overview

The CLARA architecture relies on six invariant locks enforced at the Domain, GLHS, Core RBAC, and Compliance layers:
1. **RBAC & Admin Privilege Lock:** `require_roles(...)` evaluates caller identity and role. `admin` has implicit access; non-authorized roles receive HTTP 403 Forbidden.
2. **CSRF Enforcement Lock:** Enforced on all mutating verbs (`POST`, `PUT`, `PATCH`, `DELETE`) for cookie-authenticated sessions; Bearer token exemption requires valid, non-revoked cryptographic credentials.
3. **Consent Gate & Versioning Lock:** Health queries and data modifications require active, versioned user consent (`ensure_medical_disclaimer_consent`, `PhrConsentService`).
4. **Emergency Red-Flag Fast-Path Lock:** Deterministic symptom triage halts automated diagnostic pathways immediately upon detecting life-threatening presentations.
5. **GLHS Linearizable OCC State Commit Lock:** Multi-phase dynamic 2PL and OCC prevents stale writes, race conditions, and uncommitted phantom state across clinical entity partitions.
6. **No-PII Telemetry & Cryptographic Non-Repudiation Lock:** Redaction of all patient identifiers from log streams, metrics, and error responses; provider inference receipts cryptographically verified.

---

## 2. Identified Risks and Gaps Matrix

| Risk ID | Severity | Category | Component | Description & Forensic Evidence | Blast Radius & Potential Impact | Mitigation / Remediation Proposal |
|---|---|---|---|---|---|---|
| **RSK-A03-001** | High (P1) | Security / Route Classification | `core.route_inventory` | `/api/v1/auth/callback` is unauthenticated and CSRF-exempt in `main.py:137`, but omitted from `INTENTIONAL_PUBLIC_ROUTES` in `route_inventory.py:106`. Causes deny-by-default boundary test failure. | Route inventory check fails CI. Potential drift between CSRF-exempt list and public route inventory. | Add `("POST", "/api/v1/auth/callback")` to `INTENTIONAL_PUBLIC_ROUTES` in `core/route_inventory.py` during PH01 or scheduled fix. |
| **RSK-A03-002** | High (P1) | Concurrency / Data Integrity | `glhs.lock_hierarchy` | `test_acquire_canonical_glhs_locks_strict_total_order` expects policy version `"glhs.v1"` when acquiring locks with a `policy_domain`, but `gateway.py:154` returns `"commitloop.v1"`. | Domain policy versioning inconsistency between commitment subsystem and baseline GLHS tests. | Unify domain policy version resolution: update lock hierarchy test or harmonize `get_effective_policy_version` fallback. |
| **RSK-A03-003** | Medium (P2) | Code Quality / Regression | `glhs.gateway` | `test_orm_rejects_canonical_assertion_content_mutation` asserts exact regex `'canonical row content is immutable'`, whereas the ORM event listener in `models.py` produces `'GLHS ledger rows are immutable (canonical row content protection): semantic_key'`. | Test failure in CI due to modified error message text; logic itself is fully sound and functional. | Update the pytest regex matcher in `test_glhs_gateway.py` to match `'GLHS ledger rows are immutable'`. |
| **RSK-A03-004** | High (P1) | Clinical State / Replay | `glhs.gateway` | `test_reference_case_late_evidence_conflict_and_reviewed_resolution` fails on historical snapshot conflict reconstruction (found 0 conflicts, expected 1). | As-of point-in-time replay may incorrectly resolve historical conflicts if later reviewed assertions alter historical projection. | Audit `compile_thss` conflict projection logic to ensure `as_of` / `known_at` filtering strictly ignores future resolutions. |
| **RSK-A03-005** | Medium (P2) | Performance / Toolchain | CI Test Runner | Test suite execution against disk-backed SQLite can encounter severe fsync latency / kernel wait (`jbd2_log_wait_commit`) under containerization. | CI build timeouts (>120s) and test run intermittency. | Ensure all test runs enforce `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/test.db"` (in-memory/tmpfs). |
| **RSK-A03-006** | Medium (P2) | Schema Consistency | `core.bootstrap_admin` | Warning logged during test fixture setup: `'version_no' is an invalid keyword argument for PhrProfile`. | Startup admin seeding emits warnings; profile versioning field name may have changed. | Verify `PhrProfile` model schema against `bootstrap_admin.py` seeding logic to remove stale `version_no` kwargs. |
| **RSK-A03-007** | Critical (P0) | Security / Defense-in-Depth | `compliance.dsar` | DSAR delete mutation removes patient data. Any flaw in owner identity checking or CSRF could lead to unauthorized erasure. | Irreversible clinical data deletion. | Hardened by `test_compliance_dsar_csrf.py` and `test_compliance_rbac_flags.py`. Ensure soft-delete / tombstone audit ledger is strictly maintained in PostgreSQL. |
| **RSK-A03-008** | High (P1) | Compliance / Privacy | `compliance.consent` | Consent revocation is append-only, but client query caching could serve stale personalized data post-revocation. | Processing personal health data without active consent. | Handled by `invalidate_projection_graph` and lock acquisition in `core.consent:ensure_medical_disclaimer_consent`. Verified in `test_compliance_consent_property.py`. |

---

## 3. Defense-in-Depth and Verification Safeguards

1. **Deny-by-Default Authorization:** Every route registered in FastAPI is inspected at runtime via `build_route_inventory(app)`. Unclassified public routes immediately fail security testing.
2. **Double-Mount Compatibility:** Stale client bundles accessing `/api/v1/api/v1/*` are transparently routed without double-incrementing auth counters or bypassing CSRF middleware.
3. **Fail-Closed Gateways:** GLHS commitment transitions reject un-attested, un-versioned, or out-of-order changes (`GlhsInvariantError`), ensuring patient safety cannot be corrupted by malformed payloads.
