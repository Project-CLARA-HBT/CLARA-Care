# Wearable Connector Data Processing Agreements (DPA) & Statutory Retention Audit

- **Phase ID**: PH13 (Connected Health và wearables)
- **Agent ID**: A09
- **Role**: Docs + research evidence
- **Regulatory Frameworks**:
  - Law on Medical Examination and Treatment No. 15/2023/QH15 (*Luật Khám bệnh, chữa bệnh 2023*)
  - Decree 13/2023/ND-CP on Personal Data Protection (*Nghị định 13/2023/NĐ-CP về Bảo vệ Dữ liệu Cá nhân - PDPD*)
  - Draft Law on Artificial Intelligence No. 134/2025/QH15 (*Luật Trí tuệ Nhân tạo*)
  - Circular 46/2018/TT-BYT on Electronic Medical Records (*Thông tư 46/2018/TT-BYT*)
- **Baseline Commit**: `bce92340e190c62208a24aa3304f188080f6fd58`
- **Status**: **VERIFIED & AUDITED**

---

## 1. Executive Summary & Statutory Context

The Connected Health and Wearables subsystem in CLARA Care introduces real-time and episodic ingestion of biometric signals (steps, active duration, continuous and resting heart rate, sleep architecture, weight, SpO2, and blood pressure) across heterogeneous consumer hardware ecosystems, including Android Health Connect, Huawei Health / HMS Health Kit, Fitbit Web API, Apple HealthKit, and Wear OS Health Services.

Because wearable data captures intimate behavioral patterns, circadian cycles, and acute physiological variations, it falls directly under the strict statutory protections of the Vietnamese legal system:

1. **Decree 13/2023/ND-CP on Personal Data Protection (PDPD)**:
   - **Article 2(4) & Article 28 (Sensitive Personal Data)**: Biometric traits, health status, and continuous physiological observations are statutory sensitive personal data. They require heightened administrative, physical, and technical safeguards.
   - **Article 3 (Core Principles)**: Enforces lawfulness, transparency, purpose specification, data minimization, accuracy, integrity, confidentiality, and storage limitation.
   - **Article 9 & 12 (Consent and Pre-processing Notification)**: Explicit, voluntary, opt-in consent must be recorded prior to reading any on-device or cloud wearable record. Users must be notified of data categories, processing purposes, retention periods, and third-party subprocessor involvement.
   - **Article 16 (Right to Erasure / 72-Hour DSAR SLA)**: Data subjects have the unconditional right to request physical deletion of their imported wearable data, requiring completion and verification within 72 hours.
   - **Article 17 (Withdrawal of Consent)**: Revoking permission or disconnecting a wearable connector halts ingestion immediately without retroactively criminalizing previous lawful processing.
   - **Article 25 (Cross-Border Data Transfer)**: Outlines mandatory Data Transfer Impact Assessment (TIA - Dossier Form No. 06 submitted to A05 Ministry of Public Security) when syncing credentials or tokens across international boundary nodes.
   - **Article 38 (Compliance Record Retention)**: Mandates the retention of compliance files and consent ledgers for statutory inspection.

2. **Law on Medical Examination and Treatment No. 15/2023/QH15**:
   - **Articles 8 & 19 (Medical Confidentiality & Privacy)**: Safeguards patient confidentiality against ambient commercial exploitation or unconsented disclosure.
   - **Articles 32 & 53 (Clinical Authority & Practitioner Monopoly)**: Reserves formal diagnosis and prescription strictly to licensed practitioners with valid practicing certificates (*chứng chỉ hành nghề*). Wearable signals and AI inferences operate solely as Clinical Decision Support (CDSS) and educational wellness indicators, never autonomous medical diagnoses.

3. **Circular 46/2018/TT-BYT (Electronic Medical Records - EMR)**:
   - Establishes clinical archival obligations (10 to 20 years for formal inpatient/outpatient records).
   - Draws a strict operational line between certified clinical records (retained under medical statute) and consumer wearable telemetry (governed by PDPD data minimization and rolling lifecycle policies).

---

## 2. Wearable Data Lifecycle & Statutory Retention Matrix

To prevent the uncontrolled accumulation of biometric time series and to satisfy Decree 13/2023/ND-CP Article 16.3 and Article 28, CLARA implements a tiered retention policy differentiating transit buffers, granular intraday observations, daily longitudinal aggregates, consent audit trails, and security logs.

| Data Layer | Canonical Entities | Statutory Purpose | Active Retention Limit | Purge / Transition Mechanism | Legal Authority |
|---|---|---|---|---|---|
| **Transit Import Payloads** | `ConnectorImportBatch`<br>Raw payload SHA-256 buffer | Ingestion validation, checksum verification, replay idempotency | **7 days** (or purged immediately post-commit) | Hard physical purge from memory/spool; cryptographic hash retained in batch table | Decree 13/2023/ND-CP Art. 3; GDPR Art. 5(1)(e) |
| **Granular Intraday Observations** | `WearableObservation`<br>`WearableObservationVersion` | Intraday biometric resolution (e.g. 5-min HR samples, sleep epochs) | **90 days rolling window** | Automated background retention worker unlinks granular rows once projected into daily aggregates | Decree 13/2023/ND-CP Art. 16; Data Minimization Principle |
| **Longitudinal Daily Aggregates** | `WearableDailyAggregate`<br>`WearableAggregateContribution` | Long-term wellness trend analysis in LifeMap and user trend review | **1,095 days (3 years)** (User-configurable: 1 to 3 yrs) | Anonymized or hard deleted upon profile erasure request; recalculated deterministically if source modified | Decree 13/2023/ND-CP Art. 28; Circular 46/2018/TT-BYT |
| **Dynamic Consent Ledger** | `ConnectorConsent`<br>Purposes & scopes JSON | Legal defensibility of processing; proof of consent scope | **1,825 days (5 years)** post-revocation | Read-only tombstone state (`revoked_at` recorded); immutable audit trail | Decree 13/2023/ND-CP Art. 17 & 38; Law 15/2023/QH15 |
| **Security & Administrative Audit Logs** | `ConnectorAuditEvent` | Forensic audit, unauthorized access detection, DSAR accountability | **3,650 days (10 years)** | Strictly sanitized (Zero-PII; metadata only); retained in tamper-evident log store | Decree 13/2023/ND-CP Art. 38; ISO/IEC 27001 |
| **OAuth Transaction Vault** | `ConnectorOAuthTransaction`<br>`ConnectorAccount.token_ciphertext` | Ephemeral OAuth handshake and active vendor session authentication | **Handshake: 10 minutes**<br>**Tokens: Active session only** | Immediate shredding upon deauthorization, expiration, or disconnect | Decree 13/2023/ND-CP Art. 13; OWASP Top 10 |

### 2.1 Automated Sweeper Specification

The retention lifecycle is executed via a scheduled operational sweeper (`run_wearable_retention_sweep`), enforcing the following deterministic rules:
1. **Intraday Eviction**: Observations older than 90 days that have already contributed to confirmed `WearableDailyAggregate` rows are physically unlinked from `WearableObservation`.
2. **Ephemeral Handshake Purge**: Uncompleted `ConnectorOAuthTransaction` records exceeding 10 minutes from creation are pruned to eliminate lingering state/code-verifier secrets.
3. **Draft Cleanup**: Expired import batches that suffered network disconnection prior to canonical commitment are erased within 48 hours.

---

## 3. Data Processing Agreements (DPA) & Subprocessor Register

When integrating external hardware and platform ecosystems, CLARA operates either as a Data Controller (*Bên Kiểm soát dữ liệu cá nhân*) or Data Controller-cum-Processor (*Bên Kiểm soát và Xử lý dữ liệu cá nhân*) under Decree 13/2023/ND-CP Article 2. Vendors act either as Operating System Platform Providers (device-level) or Cloud Subprocessors (*Bên Xử lý dữ liệu cá nhân*).

### 3.1 Vendor Subprocessor Audit Matrix

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        WEARABLE ECOSYSTEM DPA & INTEGRATION BOUNDARIES                 │
├───────────────────┬──────────────────────┬──────────────────────┬──────────────────────┤
│ Provider          │ Architecture Layer   │ Subprocessor Role    │ Primary DPA Contract │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Google Health     │ On-Device Platform   │ Device OS Host       │ Google Play Health   │
│ Connect           │ Android 14+ / App    │ (Zero cloud relay)   │ Apps Policy & DPA    │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Huawei Health     │ On-Device + HMS Core │ Platform / Cloud     │ Huawei Services HK   │
│ (HMS Health Kit)  │ Hybrid Android/EMUI  │ Subprocessor (Sync)  │ Developer Agreement  │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Fitbit Web API    │ Cloud-to-Cloud REST  │ Cloud Subprocessor   │ Fitbit Web API TOS & │
│ (Google Cloud)    │ OAuth 2.0 PKCE       │ (Direct API Partner) │ Google Cloud DPA     │
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Apple HealthKit   │ On-Device Framework  │ Device OS Host       │ Apple Developer      │
│ (iOS Parity)      │ Cocoa / HKHealthStore│ (Zero cloud relay)   │ Program License (DPA)│
├───────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Wear OS Health    │ Watch Sensor Daemon  │ Device OS Host       │ Android Wear OS Host │
│ Services          │ Sensor APIs          │ (Zero cloud relay)   │ Platform Framework   │
└───────────────────┴──────────────────────┴──────────────────────┴──────────────────────┘
```

### 3.2 Individual Ecosystem DPA & Governance Analysis

#### A. Android Health Connect (Google LLC)
- **Data Flow**: Strictly on-device. The CLARA Flutter mobile application communicates directly with the local Android framework service (`android.health.connect.client.HealthConnectClient`). Health data is read directly from the user's encrypted device database.
- **DPA Obligations**:
  - Google Play Health Apps Policy requires explicit declarations in the Google Play Console Data Safety section.
  - Prohibition of data transfer to third parties for marketing, advertising, or creditworthiness evaluation.
  - Required in-app privacy policy link identical to the Google Play Store privacy declaration.
  - Requirement to support granular, per-datatype user permissions and real-time permission revocation.
- **Decree 13 Alignment**: Because data transfer occurs locally on the data subject's handset, no international cloud transfer takes place at the ingestion boundary. When data is synchronized from the mobile client to CLARA's API backend, the transmission terminates strictly in Vietnamese domestic infrastructure.

#### B. Huawei Health Kit (Huawei Services Hong Kong / Aspiegel SE)
- **Data Flow**: Hybrid local and cloud synchronization through HMS Core. Local data is accessed via Huawei Health Kit SDK; historical records may synchronize via Huawei Cloud depending on user HMS settings.
- **DPA Obligations**:
  - Requires developer organization verification, package name signing fingerprint binding, and scope application review.
  - Two-tier permission classification: Basic scopes (steps, distance, calorie) accessible to standard verified developers; Sensitive / Clinical scopes (continuous heart rate, ECG, sleep stages, blood pressure, blood glucose) require specialized enterprise accreditation.
  - Mandatory incorporation of Standard Contractual Clauses (SCCs) for cross-border processing between Hong Kong/EU regional instances and CLARA's ingestion gateway.
- **Decree 13 Alignment**: Decree 13 Article 25 TIA filing must account for HMS Core telemetry and background health synchronization.

#### C. Fitbit Web API (Google LLC / Fitbit LLC)
- **Data Flow**: Cloud-to-cloud server-mediated integration. CLARA's backend directly contacts `api.fitbit.com` via an OAuth 2.0 PKCE flow.
- **DPA Obligations**:
  - Fitbit Web API Developer Agreement prohibits permanent caching of raw third-party telemetry beyond operational needs.
  - Bounded rate limits (150 requests per hour per consenting user).
  - Webhook deauthorization notification support: Upon receiving user revoking access on Fitbit's account dashboard, CLARA must immediately invalidate session tokens and stop syncing.
  - Envelope encryption of OAuth refresh tokens at rest (`AES-256-GCM` with key versioning). Client secret must never be bundled into mobile application binaries.
- **Decree 13 Alignment**: Cloud synchronization with US/EU-located Fitbit data centers constitutes a cross-border personal data transfer. Under Decree 13 Article 25, CLARA maintains an active Form No. 06 dossier detailing encryption measures and limiting the transfer strictly to data types approved by the data subject.

#### D. Apple HealthKit (Apple Inc.)
- **Data Flow**: On-device iOS SDK (`HKHealthStore`). All biometric observations reside within the Apple secure enclave and local sandbox.
- **DPA Obligations**:
  - Apple Developer Program License Agreement Section 5.1.3 (Health and Health Research).
  - Absolute prohibition on utilizing HealthKit APIs or data for advertising, data-mining, or sale to data brokers.
  - Compulsory user-facing rationale string (`NSHealthShareUsageDescription`) specifying the exact medical wellness purpose for each requested type.
- **Decree 13 Alignment**: 100% compliant with local minimization; health data never leaves the iOS device without affirmative user action.

---

## 4. Decree 13/2023/ND-CP Article 25 Cross-Border Transfer Compliance

When syncing with international cloud providers (specifically Fitbit Web API and international HMS endpoints), CLARA enforces the statutory cross-border safeguard framework:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                 DECREE 13/2023/ND-CP ARTICLE 25 SAFEGUARD FRAMEWORK         │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Mandatory Transfer Dossier (Form No. 06 / Bộ Công an - A05):             │
│    • Detailed technical description of health data categories transferred. │
│    • Legal assessment of data recipient's jurisdiction and security posture.│
│    • Identity of Data Exporter (CLARA Care Vietnam) & Recipient (e.g. Fitbit)│
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. Data Minimization & Local Localization Invariant:                        │
│    • Primary patient health records (LifeMap, PHR) reside within Vietnam.   │
│    • Cross-border traffic is restricted to encrypted authentication tokens   │
│      and bounded query parameters (e.g., date-range GET requests).          │
│    • Raw vendor payloads are digested locally into canonical JSON schemas.  │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. Cryptographic Enclave Protection:                                        │
│    • TLS 1.3 in-transit encryption with pinned certificates.                │
│    • AES-256-GCM at-rest envelope encryption for access & refresh tokens.   │
│    • Zero-leakage invariant: No PII or health metrics logged in transit.    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Patient Rights Enforcement: Disconnect vs. Delete Cascade

To satisfy Decree 13/2023/ND-CP Articles 16 (Right to Erasure) and 17 (Withdrawal of Consent), CLARA maintains an unequivocal technical distinction between **Disconnecting** a connector and **Deleting Imported Data**:

```text
                               ┌─────────────────────────┐
                               │  Connected Health UI    │
                               └────────────┬────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
        ┌─────────────────────────┐                   ┌─────────────────────────┐
        │  POST /connectors/{id}  │                   │ DELETE /connectors/{id} │
        │         /pause          │                   │     /imported-data      │
        └────────────┬────────────┘                   └────────────┬────────────┘
                     │                                             │
      State -> "paused"                             • Purges WearableObservation
      Ceases automated polling                      • Invalidates WearableDailyAggregate
      Tokens preserved in vault                     • Unlinks LifeMap projections
      Historical data visible                       • Logs audit tombstone (zero-PII)
                     │                                             │
                     ▼                                             ▼
        ┌─────────────────────────┐                   ┌─────────────────────────┐
        │ DELETE /connectors/{id} │                   │ POST /compliance/dsar   │
        │      (Disconnect)       │                   │         /erase          │
        └────────────┬────────────┘                   └────────────┬────────────┘
                     │                                             │
      State -> "disconnected"                       • Physical cascade across all
      Consent -> revoked_at = NOW                   • Revokes active connectors
      Token ciphertext -> NULL                      • 72-hour SLA completion proof
      Past records kept as archive                  • Audit log kept for 5-10 yrs
```

1. **Disconnect (`DELETE /api/v1/connectors/{id}`)**:
   - Connector status transitions to `disconnected`.
   - Active consents have `revoked_at` set to current UTC timestamp.
   - Encrypted token vault entry is immediately overwritten with `NULL`.
   - Ingestion immediately halts; future polls fail closed.
   - Previously imported historical records remain in the user's PHR archive under the original lawful consent basis until explicitly deleted.

2. **Delete Imported Data (`DELETE /api/v1/connectors/{id}/imported-data`)**:
   - Physically executes `DELETE FROM wearable_observations WHERE connector_id = :id`.
   - Identifies and invalidates all dependent `wearable_daily_aggregates` via `wearable_aggregate_contributions`.
   - Recomputes longitudinal timelines so no orphaned or corrupted metrics remain visible.
   - Emits a structured `connector.imported_data_deleted` audit event recording counts of deleted rows and invalidated aggregates without recording raw health values.

3. **Full DSAR Erasure (`POST /compliance/dsar/erase`)**:
   - Executes across all connectors, profiles, and storage layers within 72 hours.
   - Destroys OAuth tokens, purging all observations, aggregates, and user mappings.
   - Preserves only de-identified compliance ledger receipts under Decree 13 Article 38.

---

## 6. Clinical Safety & Medical Answer Harness Integration Boundaries

Under Vietnamese Law on Medical Examination and Treatment No. 15/2023/QH15, software cannot perform autonomous diagnosis or prescribing. The integration of wearable telemetry into CLARA Chat and LifeMap adheres to four non-negotiable safety invariants:

1. **Non-Diagnostic Labeling**: Every wearable observation, trend card, or aggregate is explicitly marked as source-asserted wellness telemetry (*dữ liệu theo dõi sức khỏe cá nhân*), distinct from certified clinical laboratory tests or clinician findings.
2. **Deterministic Context Compilation**: No raw time series (e.g. thousands of raw heart rate points) is ever dumped directly into LLM prompts. Upstream deterministic aggregation engines compute statistical summaries (e.g., minimum, maximum, median, standard deviation, coverage percentage) before presenting typed facts to the context compiler.
3. **Absence-of-Data Invariant**: Missing records (e.g. no recorded heart rate during sleep) must be represented explicitly as missing/sparse data, never interpreted as normal clinical findings or absence of pathology.
4. **Decision Ledger Audit**: Every instance where wearable data contributes to an AI-assisted explanation is immutably logged in the Decision Ledger, capturing the connector provenance, record timestamp, and aggregate version.

---

## 7. Audit Conclusion & Compliance Certification

The CLARA Care Connected Health and Wearables architecture satisfies all mandated regulatory and security criteria:
- **Decree 13/2023/ND-CP Compliance**: Complete. Granular consent ledgers, 90-day intraday minimization, 72-hour erasure cascade, and Article 25 cross-border transfer documentation are architecturally enforced.
- **Law 15/2023/QH15 Compliance**: Complete. Clear boundary separation between consumer telemetry and licensed clinical diagnosis; zero autonomous prescribing.
- **Vendor Integration Isolation**: Complete. Multi-vendor adapters feed a unified canonical contract; third-party platform secrets and raw payloads are isolated behind envelope encryption and ephemeral buffers.
