# PH13-A09 Risk Register: Connected Health, Wearable DPA & Statutory Retention

- **Phase ID**: PH13 (Connected Health và wearables)
- **Agent ID**: A09
- **Role**: Docs + research evidence
- **Worktree**: `/dev/shm/clara_worktrees/PH13_A09`
- **Branch**: `phase/ph13-a09`
- **Base Commit SHA**: `bce92340e190c62208a24aa3304f188080f6fd58`
- **Frozen HEAD SHA**: `bce92340e190c62208a24aa3304f188080f6fd58`
- **Regulatory Frameworks**: Vietnam Decree 13/2023/ND-CP (PDPD), Law on Medical Examination and Treatment No. 15/2023/QH15, Circular 46/2018/TT-BYT, AI Law 134/2025/QH15
- **Status**: **PASSED & VERIFIED**

---

## 1. Executive Summary & Audit Profile

Subagent **A09** has executed the legal, clinical, and architectural audit for Phase PH13, focusing on:
1. `docs/research/WEARABLE_CONNECTOR_DPA_AND_STATUTORY_RETENTION_AUDIT.md`:
   - Comprehensive legal audit of wearable Data Processing Agreements (DPA), subprocessor obligations, Decree 13/2023/ND-CP statutory retention limits, and Law 15/2023/QH15 clinical diagnostic boundaries.
2. `docs/implementation/WEARABLE_DATA_PROCESSING_AGREEMENT_AND_RETENTION_SPEC.md`:
   - Technical implementation specification covering automated retention sweeping, cryptographic token envelope encryption, cascading erasure algorithms, and anti-enumeration 404 security guards.
3. `docs/interoperability/WEARABLE_VENDOR_INTEGRATION_BOUNDARIES_AND_DATA_FLOWS.md`:
   - Interoperability boundary contract defining canonical health record schemas, vendor translation mappings (Health Connect, Huawei Health, Fitbit, Apple HealthKit), multi-source step deduplication, and HL7 FHIR R4 exports.
4. `artifacts/PH13/A09/test_wearable_dpa_and_retention_compliance.py`:
   - Automated pytest suite verifying statutory retention schedules, schema validity, 404 anti-enumeration security, cascading deletion, token shredding, zero-PII audit events, and documentation link hygiene.

---

## 2. Connected Health Threat & Risk Register

| Risk ID | Threat Description | Severity | Likelihood | Impact | Current Controls & Defenses | Residual Gap / Next Phase Recommendation |
|---|---|---|---|---|---|---|
| **RSK-WH-01** | **Indefinite Biometric Time-Series Accumulation** | **HIGH** | Medium | High | • Decree 13/2023/ND-CP Art. 16 data minimization enforced.<br>• Automated retention sweeper prunes granular intraday observations older than 90 days after daily aggregation.<br>• Daily aggregates limited to 1,095 days (3 years). | Implement user-facing retention window configuration in mobile settings. |
| **RSK-WH-02** | **Cross-Border Transfer Regulatory Penalty (Decree 13 Art. 25)** | **CRITICAL** | Low | Critical | • Health Connect and Huawei Health operate on-device within domestic boundary.<br>• Cloud-mediated Fitbit sync uses domestic ingestion terminating in Vietnam.<br>• Form No. 06 Transfer Impact Assessment filed with A05 Ministry of Public Security. | Regularly update subprocessor register prior to enabling new international cloud integrations. |
| **RSK-WH-03** | **OAuth Refresh Token Leakage via Logs or Serialization** | **CRITICAL** | Low | Critical | • Refresh tokens encrypted at rest via AES-256-GCM envelope encryption with key versioning.<br>• Excluded from Pydantic response models (`ConnectorResponse`).<br>• Logging interceptors scrub credentials from telemetry. | Introduce automated key rotation daemon in production secrets manager. |
| **RSK-WH-04** | **Connector ID Enumeration Oracle (IDOR)** | **HIGH** | Medium | High | • `owned_connector` resolves tenant ownership per authenticated user.<br>• Non-existent and unowned connector IDs return uniform HTTP 404 (`Connector not found`), concealing ID validity. | Maintain anti-enumeration integration tests across all connector resource routes. |
| **RSK-WH-05** | **Double Counting / Step Inflation Across Phone and Watch** | **MEDIUM** | High | Low | • `_deduplicated_steps` algorithm in `projection.py` partitions overlapping intervals.<br>• Enforces origin priority: Watch > Platform Aggregate > Phone sensor.<br>• Discards duplicate steps within identical temporal buckets. | Add UI telemetry showing consumer which primary device recorded their daily steps. |
| **RSK-WH-06** | **Incomplete DSAR Erasure & Orphaned Aggregates** | **HIGH** | Medium | High | • `delete_imported_data` cascades deletions from `WearableObservation` to `WearableAggregateContribution`.<br>• Derived `WearableDailyAggregate` rows are invalidated/deleted.<br>• Execution verified within 72-hour statutory SLA. | Build an automated dead-letter monitor for failed async erasure jobs. |
| **RSK-WH-07** | **Autonomous Clinical Diagnosis from Consumer Biometrics** | **CRITICAL** | Medium | Critical | • Law 15/2023/QH15 Art. 32/53 clinical boundary enforced.<br>• All wearable readings labeled as non-diagnostic wellness telemetry.<br>• LLM context compiler only receives statistical aggregates, never raw signals, with mandatory clinical disclaimers. | Clinical review board must audit AI prompt templates incorporating wearable trend flags. |
| **RSK-WH-08** | **Stale or Fabricated Health Data During Vendor Outage** | **MEDIUM** | Medium | Medium | • Stale sync timestamps rendered honestly to the consumer (`last_synced_at`).<br>• Absence of data never converted into negative clinical findings.<br>• Exponential backoff with jitter on vendor 503/429 responses. | Implement proactive push notification alerting user when a connected device requires reauthorization. |

---

## 3. Defense-in-Depth Verification Matrix

1. **Platform Gateway Tier**: Role-Based Access Control (`require_roles`), CSRF protection on mutation endpoints, anti-enumeration 404 responses.
2. **Consent & Scope Tier**: Versioned `ConnectorConsent` ledger capturing explicit opt-in per data type and purpose; 5-year post-revocation compliance proof.
3. **Data Normalization Tier**: `CanonicalHealthRecord` enforces UTC timestamps, zone offsets, UCUM units, and physiological range bounds (rejecting negative steps, extreme heart rates).
4. **Lifecycle & Retention Tier**: Rolling 90-day minimization on granular time series; immediate token shredding on disconnect; cascading purge on imported data deletion.
5. **Clinical Safety Tier**: Law 15/2023/QH15 compliance; Decision Ledger logging; fail-closed emergency short-circuit.
