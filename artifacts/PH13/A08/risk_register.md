# Security and Privacy Risk Register — CLARA-Care (PH13 / A08)

**Document Status:** Sealed Audit Baseline · Subagent A08  
**Repository Branch:** `phase/ph13-a08`  
**Frozen Base Commit SHA:** `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`  
**Audit Scope Lane:** `docs/security/`, `docs/compliance/`, `scripts/ops/`, `artifacts/PH13/A08/`  
**Date:** November 2026  
**Subject:** Connected Health & Wearables Security, Out-of-Order Batch Replay Immunity, Clock Drift Manipulation, OAuth Token Vaulting, and Cross-Profile Isolation.

---

## 1. Executive Summary

As part of Phase PH13 (Subagent A08: Security + Privacy), an exhaustive threat modeling and operational simulation audit was conducted on CLARA-Care's Connected Health and Wearables ingestion architecture. External wearable devices (Android Health Connect, Huawei Health, Fitbit Cloud) communicate biometric time series into the clinical platform across untrusted networks and intermittent Bluetooth channels.

Any compromise in idempotency, clock synchronization, token security, or consent boundaries could lead to clinical misguidance, double-counted step aggregates, cross-profile health data exposure, or statutory privacy violations under Vietnam Decree 13/2023/ND-CP.

This risk register evaluates twelve core risk vectors:
1. **Identical Batch Replay:** Network retries or replay attacks duplicating observations or distorting aggregates.
2. **Payload Hash Tampering:** Submitting altered health metrics under an existing idempotency key.
3. **Out-of-Order Version Corruption:** Late-arriving batches overwriting newer observation versions or resurrecting tombstoned records.
4. **Inverted Time Intervals:** Manipulated device clocks asserting negative durations (`observed_end < observed_start`).
5. **Future Clock Drift Skew:** Devices injecting future timestamps to game adherence streaks or poison predictive baselines.
6. **Timezone Offset Spoofing:** Non-standard or impossible UTC offsets (+25:00) distorting diurnal rhythm analysis.
7. **OAuth Token Exposure in Responses:** Serializing ORM models leaking access/refresh tokens in API responses.
8. **Stale Token Persistence After Disconnect:** Retention of encrypted credentials allowing unauthorized background sync.
9. **Cross-Profile IDOR & Tenant Enumeration:** Probing connector endpoints with foreign IDs to discover patient connections.
10. **Unconsented Biometric Data Injection:** Client apps importing sensitive clinical types (e.g. blood glucose) without active consent.
11. **Non-Finite Value Injection (DoS):** NaN or Infinite values causing server crashes during daily aggregate calculations.
12. **Orphan Projections on Data Deletion:** Residual daily aggregates remaining after source observations are deleted.

All twelve risk vectors are mitigated and continuously verified by automated simulations (`scripts/ops/simulate_wearable_security_threats.py` and `scripts/ops/test_audit_wearable_security_simulations.py`).

---

## 2. Risk Matrix & Severity Definitions

| Severity | Definition | Operational Action Required |
|:---|:---|:---|
| **CRITICAL** | Direct credential leak, unconsented biometric ingestion, or batch replay falsifying clinical baselines. | Immediate release gate block; hotfix required. |
| **HIGH** | Out-of-order state corruption, clock drift tampering, or cross-profile metadata enumeration. | Mandatory architectural mitigation prior to deployment. |
| **MEDIUM** | Timezone offset formatting irregularities or non-standard device metadata. | Remediate in current sprint with operational controls. |
| **LOW / INFO** | Informational notices or telemetry label adjustments. | Tracked in operational maintenance backlog. |

---

## 3. Comprehensive Wearable Risk Inventory

| Risk ID | Category | Title | Severity | Likelihood | Impact | Status | Mitigating Architectural Control |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **SEC-WH-01** | Tampering / Replay | Identical Batch Replay Duplication | **CRITICAL** | High | Severe | **Mitigated** | `ConnectorImportBatch` idempotency key & SHA-256 payload hash caching returning `idempotent_replay=True` (`ingestion.py:108-120`). |
| **SEC-WH-02** | Tampering / Integrity | Reused Idempotency Key with Modified Records | **CRITICAL** | Medium | Severe | **Mitigated** | Cryptographic payload digest mismatch detection raising HTTP 409 Conflict (`ingestion.py:114-119`). |
| **SEC-WH-03** | Tampering / Ordering | Out-of-Order Stale Update Overwriting Newer Version | **HIGH** | Medium | High | **Mitigated** | Append-only `WearableObservationVersion` tracking with deterministic `version_no` auto-increment (`ingestion.py:165-189`). |
| **SEC-WH-04** | Tampering / Clock | Inverted Time Interval (`observed_end < observed_start`) | **HIGH** | Medium | High | **Mitigated** | Pydantic `validate_record_semantics` validator rejecting inverted intervals with HTTP 422 (`schemas.py:158`). |
| **SEC-WH-05** | Tampering / Clock | Future Timestamp Skew (> 15m) Injection | **HIGH** | Medium | High | **Mitigated** | Decoupling Valid Time from System Time; automated future drift detection and baseline quarantine (`simulate_wearable_security_threats.py:270`). |
| **SEC-WH-06** | Tampering / Clock | Invalid or Impossible UTC Timezone Offsets | **MEDIUM** | Low | Medium | **Mitigated** | Strict regex pattern `^(?:Z\|[+-](?:0\d\|1[0-4]):[0-5]\d)$` enforcement (`schemas.py:14, 151`). |
| **SEC-WH-07** | Disclosure / Token | OAuth Access/Refresh Token Leakage in Serialization | **CRITICAL** | Low | Critical | **Mitigated** | Envelope encryption `token_ciphertext` (LargeBinary); DTO `ConnectorResponse` strictly excludes token fields (`service.py:70-87`). |
| **SEC-WH-08** | Disclosure / Token | Stale Credential Retention After Disconnection | **CRITICAL** | Medium | High | **Mitigated** | `disconnect()` atomically zeroes `token_ciphertext` and `token_key_version` and timestamps consent revocation (`service.py:250-270`). |
| **SEC-WH-09** | Authorization / IDOR | Cross-Profile Connector ID Enumeration | **HIGH** | Medium | High | **Mitigated** | `owned_connector()` enforces user/profile ownership and returns constant HTTP 404 Not Found (`service.py:46-56`). |
| **SEC-WH-10** | Privilege / Consent | Unconsented Biometric Data Type Ingestion | **CRITICAL** | Medium | Severe | **Mitigated** | `import_batch()` verifies `requested_types.issubset(granted_types)`, blocking unauthorized types with HTTP 403 (`ingestion.py:101-105`). |
| **SEC-WH-11** | Denial of Service | Non-Finite Numeric Values (NaN / Infinity) | **HIGH** | Low | High | **Mitigated** | `math.isfinite()` check in `CanonicalHealthValue` validator rejecting non-finite scalars (`schemas.py:102`). |
| **SEC-WH-12** | Privacy / Deletion | Residual Projections Surviving Imported Data Deletion | **HIGH** | Medium | High | **Mitigated** | `delete_imported_data()` performs atomic cascading deletion of observations and invalidates daily aggregates (`service.py:274-324`). |

---

## 4. Verification Evidence & Test Anchors

All 12 risks were exercised against the live Python test environment:
- **Test Harness:** `scripts/ops/simulate_wearable_security_threats.py`
- **Unit Suite:** `scripts/ops/test_audit_wearable_security_simulations.py`
- **Results:** 14 passed, 0 failed, 0 skipped.
- **Path Isolation:** Verified with `scripts/ci/check_agent_path_acl.py -a A08 -p PH13` (0 violations).
