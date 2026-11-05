# Wearable Data Processing Agreement & Retention Technical Specification

- **Phase ID**: PH13 (Connected Health và wearables)
- **Agent ID**: A09
- **Role**: Docs + research evidence
- **Target Subsystem**: `services/api/src/clara_api/connected_health/`
- **Applicable Statutes**: Decree 13/2023/ND-CP, Law 15/2023/QH15, Circular 46/2018/TT-BYT
- **Status**: **ACTIVE IMPLEMENTATION SPECIFICATION**

---

## 1. Architectural Ingestion & Processing Boundaries

The Connected Health module provides a hardened boundary between external hardware/operating systems (Health Connect, Huawei Health, Fitbit, Wear OS) and CLARA's internal clinical domain (LifeMap, PHR, Clinical Decision Support).

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. DEVICE OR CLOUD ADAPTER (Mobile Client / Backend Worker)                 │
│    • Health Connect / Huawei Health: Read locally on Android.               │
│    • Fitbit Web API: Cloud worker fetches via authenticated OAuth 2.0 PKCE. │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. CONTROL PLANE AUTHENTICATION & CONSENT CHECK                             │
│    • Verify profile scope and active consent (ConnectorConsent).            │
│    • Reject ingestion if connector status is paused, revoked, or unowned.   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. CANONICAL NORMALIZATION & VALIDATION (CanonicalHealthRecord)             │
│    • Validate schema version, UTC timestamps, zone offsets (+07:00).        │
│    • Enforce physiological boundaries (e.g., HR 20-300 bpm, SpO2 50-100%).  │
│    • Verify payload checksum (sha256 raw_hash).                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. IDEMPOTENT PERSISTENCE & DEDUPLICATION (WearableObservation)             │
│    • Primary Key: (connector_id, data_origin, provider_record_id, version). │
│    • Replay detection: Duplicate batches yield HTTP 200 without re-insert.  │
├─────────────────────────────────────────────────────────────────────────────┤
│ 5. DETERMINISTIC DAILY AGGREGATION (WearableDailyAggregate)                 │
│    • Step deduplication (avoiding double counting phone + watch).          │
│    • Statistical rollups (resting HR, sleep duration, average SpO2).        │
│    • Contributing observations tracked in WearableAggregateContribution.   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 6. LIFEMAP PROJECTION & OUTBOX EVENT                                        │
│    • Non-diagnostic tagging; zero-PII audit event emitted to outbox.        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Retention Sweeper Specification & Automated Execution

In accordance with Decree 13/2023/ND-CP Article 16.3 (Storage Limitation), granular physiological time series must not be retained indefinitely. CLARA operates an automated retention sweeper (`run_wearable_retention_sweep`).

### 2.1 Retention Boundaries

1. **Transit Payloads (`ConnectorImportBatch`)**:
   - Retention: Maximum 7 days.
   - Action: The raw batch content is erased post-ingestion. Only the hash (`payload_hash`), record counts, and cursor pointers are retained for replay audit defense.

2. **Intraday Granular Observations (`WearableObservation`)**:
   - Retention: 90-day rolling window from `observed_end`.
   - Condition: Observations older than 90 days are deleted **if and only if** they have been compiled into confirmed `WearableDailyAggregate` records.
   - Deletion Procedure:
     ```sql
     DELETE FROM wearable_observations
     WHERE observed_end < NOW() - INTERVAL '90 days'
       AND id IN (
           SELECT observation_id
           FROM wearable_aggregate_contributions
       );
     ```

3. **Daily Aggregates (`WearableDailyAggregate`)**:
   - Retention: 1,095 days (3 years).
   - Customization: Users may select a 1-year, 2-year, or 3-year rolling horizon in profile settings.
   - Deletion Procedure: Aggregates exceeding the configured retention threshold are deleted during the nightly maintenance window.

4. **Consent Records (`ConnectorConsent`)**:
   - Retention: 1,825 days (5 years) post `revoked_at`.
   - Legal Basis: Decree 13/2023/ND-CP Article 38 statutory defense proof for past processing.

5. **Security & Connector Audit Events (`ConnectorAuditEvent`)**:
   - Retention: 3,650 days (10 years).
   - Requirement: 100% PII-free; only stores connector IDs, event types, timestamps, and metric counts.

---

## 3. Cryptographic Token Vault Specification

Cloud-mediated connectors (such as Fitbit Web API) require long-lived refresh tokens. To guarantee compliance with Decree 13 Article 13 (Technical Safeguards) and ISO/IEC 27001:

1. **Envelope Encryption Architecture**:
   - Encryption Algorithm: `AES-256-GCM` with a 96-bit initialization vector (IV) and 128-bit authentication tag.
   - Key Management: The Master Key Encryption Key (KEK) is stored in a dedicated KMS / Hardware Security Module (HSM).
   - Key Versioning: Every encrypted token stored in `ConnectorAccount.token_ciphertext` includes an explicit `token_key_version` integer column, facilitating cryptographic rotation without service downtime.

2. **Zero-Token Leakage Invariants**:
   - Token values are marked sensitive and excluded from Pydantic schema representations (`ConnectorResponse`).
   - Logging filters strip authorization codes, tokens, and client secrets from standard output and telemetry.
   - `DELETE /api/v1/connectors/{id}` immediately sets `token_ciphertext = NULL` and `token_key_version = NULL`.

---

## 4. Deletion Cascade & DSAR Erasure Algorithm

The deletion of imported wearable data is an atomic, auditable operation executed under `DELETE /api/v1/connectors/{id}/imported-data`:

```python
def delete_imported_data(db: Session, *, connector: ConnectorAccount, user: User) -> ImportedDataDeletionResponse:
    # Step 1: Identify all observations associated with this connector
    observation_ids = list(
        db.execute(
            select(WearableObservation.id).where(WearableObservation.connector_id == connector.id)
        ).scalars()
    )

    # Step 2: Locate all aggregate rows that incorporated these observations
    aggregate_ids: set[int] = set()
    if observation_ids:
        aggregate_ids = set(
            db.execute(
                select(WearableAggregateContribution.aggregate_id).where(
                    WearableAggregateContribution.observation_id.in_(observation_ids)
                )
            ).scalars()
        )
        # Step 3: Physically delete observations (contributions cascade via foreign key)
        db.execute(
            delete(WearableObservation).where(WearableObservation.connector_id == connector.id)
        )

    # Step 4: Invalidate dependent daily aggregates to prevent stale/corrupt projections
    if aggregate_ids:
        db.execute(
            delete(WearableDailyAggregate).where(WearableDailyAggregate.id.in_(aggregate_ids))
        )

    # Step 5: Record tamper-evident, PII-free audit event
    audit(
        db,
        connector=connector,
        actor_user_id=user.id,
        event_type="connector.imported_data_deleted",
        metadata={
            "deleted_observation_count": len(observation_ids),
            "invalidated_aggregate_count": len(aggregate_ids),
        },
    )
    db.commit()

    return ImportedDataDeletionResponse(
        connector_id=str(connector.id),
        deleted_observations=len(observation_ids),
        invalidated_aggregates=len(aggregate_ids),
    )
```

### 4.1 Invariant Validation
- **Projection Invalidation**: Unlike simple soft deletion, aggregates derived from deleted sources are eradicated to ensure LifeMap queries never present obsolete or unverified metric totals.
- **Audit Defensibility**: The audit log preserves the operational receipt (`deleted_observation_count`, `invalidated_aggregate_count`) confirming execution of the data subject's right to erasure under Decree 13 Article 16.

---

## 5. Security Access Control & Anti-Enumeration Guards

1. **Role-Based Access Control (RBAC)**:
   - Consumer endpoints (`GET /connectors`, `POST /connectors/device`, `POST /connectors/{id}/imports`) require roles: `normal`, `researcher`, `doctor`, or `admin`.
   - Admin status aggregation (`GET /connectors/status-adapter`) strictly requires `admin` role.
2. **Anti-Enumeration 404 Guard**:
   - Access to individual connectors is verified via `owned_connector(db, connector_id=connector_id, user=user)`.
   - If a connector exists but belongs to a different profile/user, the API intentionally returns `404 Not Found` rather than `403 Forbidden`. This prevents malicious actors from enumerating valid connector IDs across the tenancy.
3. **Cross-Tenant Isolation**:
   - Connectors and observations are strictly partitioned by `profile_id` and `user_id`. Queries across tenant boundaries without matching user scope fail closed.

---

## 6. Zero-PII Telemetry & Outbox Message Sanitization

System observability, logging, and asynchronous event distribution must never expose Protected Health Information (PHI) or personal identifiers:

| Telemetry / Event Field | Permitted Content | Strictly Prohibited Content |
|---|---|---|
| `event_type` | Standard enumeration (e.g. `connector.created`, `connector.sync_requested`) | User names, emails, medical conditions |
| `connector_id` | Opaque integer or UUID | Hardware serial numbers, IMEI |
| `provider` | Provider string (`health_connect`, `fitbit`) | User credentials, account handles |
| `status` | State string (`connected`, `healthy`, `error`) | Raw diagnostic error traces containing PHI |
| `metadata.counts` | Integer counts of observations or aggregates | Actual biometric readings (heart rate, glucose) |
| `metadata.error_class`| Categorical error (e.g. `RATE_LIMIT_EXCEEDED`, `EXPIRED_TOKEN`) | Raw response payloads or authorization headers |

---

## 7. HTTP API Error Handling Contract

| HTTP Status | Error Scenario | Client Recovery Guidance |
|---|---|---|
| **400 Bad Request** | Invalid payload, non-finite scalar, invalid time-zone format | Inspect schema definition; ensure valid UTC ISO-8601 formatting. |
| **401 Unauthorized** | Missing or expired JWT session token | Re-authenticate via authentication gateway. |
| **403 Forbidden** | User role insufficient to perform administrative operation | Access restricted to administrators. |
| **404 Not Found** | Connector ID does not exist or belongs to another profile | Anti-enumeration response. Check connector ID. |
| **409 Conflict** | State transition invalid (e.g. trying to pause an already disconnected connector) | Refresh connector status before retrying. |
| **422 Unprocessable** | Ingestion timestamp in the future or interval mismatch (`end < start`) | Ensure client clock synchronization with NTP. |
| **503 Service Unavail**| Third-party vendor API unavailable or rate-limited | Apply exponential backoff with jitter; display stale data indicator. |
