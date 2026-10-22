# Consent-Drift & Concurrent Mutation Security Matrix (PH05)

## Executive Summary
This security specification details the threat models, invariant assertions, and concurrent isolation testing procedures governing versioned consent drift and multi-device revocation propagation in The CLARA Care.

## Threat Vectors & Invariant Assertions

### Vector 1: Policy Version Drift (Silent Bypass of Updated Risk Disclosures)
- **Threat:** When medical disclaimer or AI transparency policy is updated to address new regulatory requirements or clinical risks, clients holding valid prior consent might continue processing without informed re-acknowledgment.
- **Invariant:** `ensure_medical_disclaimer_consent` evaluates `accepted_version == required_medical_disclaimer_version()`. A mismatch unconditionally raises HTTP 403 / reconsent prompt.
- **Verification:** Verified by property test `test_compliance_consent_property.py`.

### Vector 2: Concurrent Grant & Revocation Race Condition
- **Threat:** Parallel requests from separate devices (e.g. mobile app withdrawing research consent while background web sync grants it) cause conflicting state.
- **Invariant:** All mutating operations in `clara_api.compliance.consent` call `acquire_consent_lock_anchor(db, user_id=user_id)`.
- **Lock Ordering:** `lock_hierarchy.py` mandates consent anchor acquisition before any child record modification, serializing transactions deterministically.

### Vector 3: Multi-Session Invalidation & Caching Drift
- **Threat:** Consent revocation recorded in PostgreSQL is bypassed by in-memory session caches or long-lived JWTs.
- **Invariant:** RAG inference and clinical chat handlers inspect live DB consent status (`has_consent`) or validate user policy epoch on every request rather than trusting stale JWT claims.

## Concurrent Test Matrix

| Test ID | Scenario | Concurrency Level | Expected Outcome | Mitigation Mechanism |
|---------|----------|-------------------|------------------|----------------------|
| CT-01 | Rapid grant followed by revoke | 50 threads / 1 user | Final status is revoked; ledger has 50 rows | Append-only ledger + lock anchor |
| CT-02 | Version bump under active session | Single user / new version | HTTP 403 on medical endpoints until re-accept | Dynamic version comparison |
| CT-03 | Purpose-specific revocation | Multiple purposes | Target purpose disabled, others unaffected | Purpose-namespaced keys |
| CT-04 | Family proxy attempt on adult | Unauthorized proxy | HTTP 403 Forbidden | Delegated authority evaluator |
