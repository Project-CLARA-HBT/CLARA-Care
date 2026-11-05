# Wearable & Connected Health Security Threat Model

**Document Status:** Sealed Security Architecture & Wearable Threat Model · Subagent PH13_A08  
**Repository Branch:** `phase/ph13-a08`  
**Base Commit SHA:** `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`  
**Classification:** High-Risk Clinical Decision Support / Personal Health Information (PHI)  
**Review Owner:** Security + Privacy Subagent (PH13 / A08)  
**Date:** November 2026  
**Scope:** Connected Health & Wearable Ingestion Pipeline, Mobile-to-Cloud Connector Protocol (Android Health Connect, Huawei Health, Fitbit OAuth), Out-of-Order Batch Replay Immunity, Clock Drift & Timestamp Tampering Hard-Guards, Envelope Encryption of OAuth Tokens, and Cross-Profile Isolation.

---

## 1. Executive Summary & Core Security Invariants

CLARA-Care integrates external health and wearable telemetry (steps, resting heart rate, sleep architecture, blood pressure, oxygen saturation, and body weight) into the Vietnamese longitudinal health platform ("LifeMap"). Telemetry originates from diverse edge environments: consumer smartphones, physical smartwatches, third-party vendor cloud APIs, and intermittent local Bluetooth bridges. 

Because wearable telemetry operates outside CLARA's controlled perimeter, inputs must be treated as untrusted external claims. A compromised device, an altered local clock, a network-intercepted batch, or an insecure OAuth callback could otherwise compromise patient clinical baselines, trigger false emergency escalations, or leak authentication tokens.

The following six security invariants are regression-locked across all Connected Health surfaces:

### Invariant 1: Ingestion Idempotency & Batch Replay Immunity
> **Every wearable import batch MUST supply a client-generated `idempotency_key` and be bound to an immutable `payload_hash` (SHA-256). An identical re-submission returns the previous committed batch response without duplicating observations or distorting longitudinal aggregates.**
>
> If a client re-submits a previously processed `idempotency_key` with modified record content (payload hash mismatch), the ingestion engine MUST reject the transaction with HTTP 409 Conflict (`detail="Idempotency key was already used for another payload"`). Stale or out-of-order batches MUST NEVER silently overwrite newer observation versions or resurrect tombstoned records.

### Invariant 2: Valid-Time vs System-Time Decoupling & Anti-Clock-Drift Hard-Guards
> **Device-asserted timestamps (`observed_start`, `observed_end`) represent Valid Time and are strictly distinguished from server-generated System Time (`ingested_at`, `committed_at`, `created_at`).**
>
> All incoming records MUST enforce:
> 1. Strict chronological ordering (`observed_end >= observed_start`). Negative interval spans are rejected immediately during schema validation (HTTP 422).
> 2. Finite numeric bounds and valid ISO 8601 UTC offsets (`Z` or `±HH:MM`).
> 3. Anti-future drift: Observations asserting timestamps > 15 minutes into the server's future are quarantined as anomalous drift.
> 4. Anti-retroactive drift: Records asserting timestamps earlier than the patient's account creation or exceeding the allowable sync window (30 days default) are flagged to prevent baseline poisoning.

### Invariant 3: OAuth Token Envelope Encryption & Zero-Exposure Serialization
> **Third-party credentials (Fitbit OAuth access/refresh tokens, PKCE verifiers) MUST be envelope-encrypted at rest (`token_ciphertext` as binary, `token_key_version` metadata) using authenticated symmetric encryption (AES-256-GCM / ChaCha20-Poly1305).**
>
> 1. Plaintext tokens MUST NEVER appear in database tables, application logs, exception traces, or API responses.
> 2. The public `ConnectorResponse` schema strictly excludes cryptographic token fields.
> 3. Disconnection (`disconnect()`) or consent revocation MUST immediately purge `token_ciphertext` and `token_key_version`, permanently disabling background sync.

### Invariant 4: Profile Scope Isolation & Anti-Enumeration Constant-Time Enforcement
> **Every connector account, observation, sync cursor, and OAuth transaction is strictly profile-scoped (`profile_id` foreign key). Access to a connector or batch import MUST verify that the authenticated caller owns the referenced profile.**
>
> Unauthorized cross-profile access attempts MUST return HTTP 404 Not Found (`detail="Connector not found"`), never HTTP 403 Forbidden, to prevent profile or connector ID enumeration across tenants.

### Invariant 5: Complete Tombstone Cascading & Immediate Downstream Invalidation
> **When a wearable record is deleted at the source (Health Connect deletion record or explicit client tombstone), the platform MUST record an append-only `WearableObservationVersion` and set `is_active = False`.**
>
> Deletion of imported connector data (`DELETE /api/v1/connectors/{id}/imported-data`) MUST atomically delete all underlying observations and invalidate all dependent daily aggregates (`WearableDailyAggregate`), preventing orphan or corrupted projections.

### Invariant 6: No-PII Telemetry & Audit Integrity
> **Audit events (`ConnectorAuditEvent`) record event types, timestamps, and aggregate counts (accepted, upserted, tombstoned) without capturing PHI, raw biometric values, patient names, or authentication secrets.**

---

## 2. System Architecture & Wearable Data Flow

The Connected Health data pipeline spans client device adapters, the FastAPI control plane, database persistence, and downstream GLHS/LifeMap mirrors:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT / EDGE ADAPTER LAYER                               │
│  Android Health Connect (Kotlin Bridge)  │  Huawei Health (HMS)  │  Fitbit OAuth Cloud │
└────────────────────────────────────────┬───────────────────────────────────────────────┘
                                         │ Encrypted HTTPS Payload (JSON Batch)
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI CONNECTED HEALTH CONTROL PLANE                            │
│  • RBAC & Bearer Token Authentication (`require_roles("normal", ...)`                 │
│  • Connector Ownership & Profile Scope Resolution (`owned_connector`)                 │
│  • Active Consent Verification (`active_consent` check: granted data types)            │
│  • Canonical Schema & Bound Validation (`CanonicalHealthRecord`, `CanonicalHealthValue`)│
└────────────────────────────────────────┬───────────────────────────────────────────────┘
                                         │ Validated Batch
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        INGESTION & DEDUPLICATION ENGINE                                │
│  • Idempotency Check: `ConnectorImportBatch(idempotency_key, payload_hash)`            │
│  • Observation Upsert & Versioning: `WearableObservation`, `WearableObservationVersion` │
│  • Tombstone Application: sets `is_active=False`, `deleted_at=timestamp`               │
│  • Sync Cursor Update: `ConnectorSyncCursor(cursor=payload.cursor)`                    │
└──────────────────┬─────────────────────────────────────────────────┬───────────────────┘
                   │                                                 │
                   ▼                                                 ▼
┌──────────────────────────────────────┐          ┌──────────────────────────────────────┐
│       DOWNSTREAM PROJECTIONS         │          │            AUDIT LEDGER              │
│  • Steps Daily Aggregates            │          │  • ConnectorAuditEvent               │
│  • GLHS Evidence Mirroring           │          │  • Event: "connector.import_committed"│
│  • LifeMap Intelligence Projection   │          │  • No-PII / No-Secret Metadata       │
└──────────────────────────────────────┘          └──────────────────────────────────────┘
```

---

## 3. STRIDE Threat Analysis & Enforced Controls

| Threat Category | Specific Threat Description | Affected Surface / Component | Enforced Technical Control | Code Anchor & Evidence |
|---|---|---|---|---|
| **Spoofing (S)** | Malicious client spoofs connector ID or claims another user's device. | `POST /connectors/device`, `POST /connectors/{id}/imports` | Connector ownership check `owned_connector()` filters by `user_id`. Mismatch raises uniform HTTP 404. | `connected_health/service.py:46-56` |
| **Spoofing (S)** | Attacker intercepts or forges OAuth callback state in Fitbit authorization. | `GET /connectors/fitbit/callback` | SHA-256 hashed state verification in `ConnectorOAuthTransaction` with expiry check (`expires_at`) and single-use `consumed_at`. | `models.py:3851-3866` |
| **Tampering (T)** | Attacker replays identical batch to duplicate steps or falsify metrics. | `POST /connectors/{id}/imports` | `ConnectorImportBatch` unique check on `idempotency_key`. Identical hash returns cached response (`replay=True`). | `connected_health/ingestion.py:108-120` |
| **Tampering (T)** | Attacker alters payload under identical idempotency key to evade detection. | `POST /connectors/{id}/imports` | SHA-256 canonical payload hash comparison (`previous.payload_hash != digest`). Returns HTTP 409 Conflict. | `connected_health/ingestion.py:114-119` |
| **Tampering (T)** | Out-of-order stale update overwrites newer version or resurrects tombstone. | `WearableObservation` upsert | `version_no` auto-incrementing; observation versions archived in `WearableObservationVersion`. | `connected_health/ingestion.py:165-189` |
| **Tampering (T)** | Clock drift manipulation: future timestamp injection or negative intervals. | `CanonicalHealthRecord` | Interval check `observed_end >= observed_start`; UTC offset regex validation; anomaly quarantine. | `connected_health/schemas.py:158-159` |
| **Repudiation (R)** | User or client denies uploading false wearable records or revoking consent. | `ConnectorAuditEvent` | Every authorization, pause, resume, sync, import, disconnect, and delete creates an immutable audit row with UTC timestamp and actor ID. | `connected_health/service.py:89-107` |
| **Information Disclosure (I)** | OAuth access/refresh tokens leaked via API response or database dump. | `ConnectorAccount`, `serialize_connector` | `token_ciphertext` is binary encrypted data; `serialize_connector` only returns public metadata; schemas forbid extra token fields. | `connected_health/service.py:70-87`, `models.py:3653` |
| **Information Disclosure (I)** | Application logs or exception stack traces log raw Bearer tokens or payloads. | Logging & Telemetry | No tokens in audit logs; `_payload_hash` hashes full payload without logging raw JSON; sanitized error handlers. | `connected_health/ingestion.py:29-34` |
| **Denial of Service (D)** | Attacker uploads huge batches with non-finite values (NaN/Infinity) or deep payloads. | Ingestion API | Pydantic limits: `records` max 500, `tombstones` max 500; `math.isfinite` check on all numeric values. | `connected_health/schemas.py:102, 215-216` |
| **Elevation of Privilege (E)** | Client submits data types not consented to by the user (e.g., ECG or glucose). | `POST /connectors/{id}/imports` | Active consent check: `requested_types.issubset(granted_types)`. Unconsented types trigger immediate HTTP 403 Forbidden. | `connected_health/ingestion.py:98-105` |

---

## 4. Deep-Dive Attack Scenarios & Mitigations

### 4.1 Scenario 1: Out-of-Order Wearable Batch Replay

#### Attack Mechanism
A mobile device loses network connectivity during a morning run. It buffers Batch A (07:00–08:00, 3,500 steps). At 12:00, it uploads Batch B (08:00–12:00, 4,000 steps). Due to cellular retries, Batch A is re-transmitted at 13:00, or an adversary on a public Wi-Fi network captures Batch A's HTTP request and replays it.

#### Security Mitigations & Verifications
1. **Identical Replay Detection:**
   The server computes `digest = _payload_hash(payload)`. If `(connector_id, idempotency_key)` exists and `previous.payload_hash == digest`, the server immediately returns `ConnectorImportResponse(replay=True, accepted_count=batch.accepted_count, ...)` without touching database rows or triggering redundant projection recomputations.
2. **Tampered Payload Rejection:**
   If the adversary modifies a step count inside Batch A but reuses the same `idempotency_key`, the server detects `previous.payload_hash != digest` and raises `HTTPException(status_code=409, detail="Idempotency key was already used for another payload")`.
3. **Out-of-Order Version Integrity:**
   When an observation has already been tombstoned (`is_active = False`), any subsequent out-of-order update to the same `(connector_id, data_origin, provider_record_id)` creates an explicit new version (`WearableObservationVersion`) with `version_no + 1` and logs an audit trail, preventing silent corruption of clinical history.

### 4.2 Scenario 2: Clock Drift Manipulation & Timestamp Tampering

#### Attack Mechanism
An adversary alters their mobile system clock to the year 2035 to trigger simulated future notifications, unlock gamified badges, or poison longitudinal baseline averages. Alternatively, an adversary sets the clock backwards to inject backdated physiological metrics (e.g. low heart rate) to contest medical or insurance records.

#### Security Mitigations & Verifications
1. **Chronological Validity Guard:**
   `CanonicalHealthRecord` enforces `observed_end >= observed_start`. Any inverted interval (`observed_end < observed_start`) fails Pydantic schema validation immediately with HTTP 422 Unprocessable Entity.
2. **Time-Zone Rigor:**
   All datetime fields must be timezone-aware (`tzinfo is not None`). `zone_offset_start` and `zone_offset_end` must match the strict pattern `^(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)$`. Non-existent offsets (e.g., `+25:00`) are rejected.
3. **Anti-Future Skew Quarantine:**
   The ingestion engine bounds `observed_start` against the server's current UTC time. Any record claiming an `observed_start > now + 15 minutes` is flagged with quality flag `["clock_drift_future_quarantine"]` and excluded from definitive LifeMap baselines.
4. **Valid Time vs System Time Invariant:**
   Regardless of what the device asserts for `observed_start` or `provider_updated_at`, the server's `committed_at`, `created_at`, and audit timestamps are strictly server-side `datetime.now(UTC)` and cannot be forged.

### 4.3 Scenario 3: Token Leakage & Credential Exposure

#### Attack Mechanism
1. A developer accidentally logs the connector payload or authorization headers.
2. A vulnerability in an admin status endpoint serializes the full `ConnectorAccount` ORM model, exposing OAuth refresh tokens.
3. A user disconnects their wearable, but the server retains active OAuth refresh tokens, allowing unauthorized synchronization to continue in the background.

#### Security Mitigations & Verifications
1. **Zero Token Plaintext Storage:**
   The `ConnectorAccount` model defines `token_ciphertext: LargeBinary` and `token_key_version: String(64)`. Plaintext tokens are NEVER stored in columns named `token`, `access_token`, or `refresh_token`.
2. **Clean Serialization Boundaries:**
   `serialize_connector(db, connector)` maps ORM models to `ConnectorResponse`, which strictly exposes: `id`, `provider`, `display_label`, `status`, `data_types`, `purposes`, `last_synced_at`, `created_at`, `updated_at`. `token_ciphertext` is never mapped.
3. **Immediate Post-Disconnect Token Purge:**
   Upon calling `disconnect()` or `delete_imported_data()`, the server executes:
   ```python
   connector.token_ciphertext = None
   connector.token_key_version = None
   ```
   Any subsequent attempt to invoke cloud sync raises HTTP 409 Conflict (`detail="Connector must be reauthorized before sync"`).
4. **Constant-Time Anti-Enumeration Isolation:**
   When user A attempts to query or manipulate connector B owned by user C, `owned_connector()` returns HTTP 404 Not Found rather than HTTP 403 Forbidden. This ensures an attacker cannot determine whether a connector ID exists.

---

## 5. Automated Verification & Regression Safeguards

The companion operational test harness `scripts/ops/simulate_wearable_security_threats.py` and unit test suite `scripts/ops/test_audit_wearable_security_simulations.py` simulate and verify all 12 security threat conditions:
1. `PASS`: Identical batch replay returns cached 200 response with `idempotent_replay=True`.
2. `PASS`: Tampered batch with duplicate idempotency key is blocked with 409 Conflict.
3. `PASS`: Negative timestamp duration (`observed_end < observed_start`) fails schema validation with 422.
4. `PASS`: Invalid timezone offset (`+25:00` or malformed) fails schema validation with 422.
5. `PASS`: Future timestamp skew beyond allowable threshold is quarantined.
6. `PASS`: Unconsented data type import is blocked with 403 Forbidden.
7. `PASS`: Non-finite metric values (NaN/Infinity) are rejected with 422.
8. `PASS`: Disconnecting connector permanently clears `token_ciphertext` and `token_key_version`.
9. `PASS`: `serialize_connector` never leaks token ciphertext or secrets.
10. `PASS`: Cross-profile connector access returns 404 Not Found (anti-enumeration).
11. `PASS`: Data deletion cascades to observations and invalidates daily aggregates.
12. `PASS`: Audit logs capture batch counts without PHI or authentication credentials.
