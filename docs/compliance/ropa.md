# Record of Processing Activities (ROPA) — CLARA-Care

**Document status:** Living record · version-controlled
**Legal basis:** Decree No. 13/2023/NĐ-CP (PDPD) Art. 24; Law on Artificial Intelligence No. 134/2025/QH15 (record-keeping duties)
**Controller:** CLARA-Care operator (Data Controller / Bên Kiểm soát dữ liệu)
**Last reviewed:** 2026-03 (notice version `2026-03-v1`)

> Bản ghi hoạt động xử lý dữ liệu cá nhân (ROPA). This document enumerates every
> processing activity CLARA-Care performs, the personal-data categories involved,
> the purpose and legal basis, recipients (including cross-border processors),
> and the retention period for each category. It is the single human-readable
> source-of-truth that the admin records manifest
> (`GET /api/v1/compliance/records`) and the retention sweep
> (`services/api/src/clara_api/compliance/retention.py`) mirror.

## 1. System positioning

CLARA-Care is **decision-support software operating on self-declared data**. It
is **not a medical device and not an EMR/EHR**. It is classified as a
**high-risk AI system in the health domain** under AI Law 134/2025 (see
`risk-management-file.md`). Nothing in this record changes that positioning.

## 2. Data categories and classification

All health-related data CLARA holds is **sensitive personal data / dữ liệu cá
nhân nhạy cảm** under PDPD Art. 2(4).

| Category | Examples (from the data model) | Classification |
|---|---|---|
| Account identity | email, full name, role, account status | personal data |
| PHR profile | full name, DOB, gender, blood type, height/weight, phone, address, emergency contact, insurance id, notes | sensitive personal data |
| PHR coded lists | allergies, conditions, medications (`allergies_json`, `conditions_json`, `medications_json`) | sensitive personal data |
| PHR observations | self-recorded clinical observations (name, value, unit, observed-on, source) | sensitive personal data |
| PHR versions / audit | version snapshots and before/after audit JSON | sensitive personal data |
| Medicine cabinet | drug name, normalized name, dosage, dosage form, quantity, RxCUI, notes | sensitive personal data |
| Clinical queries | free-text questions sent to the assistant | sensitive personal data |
| Consent ledger | typed, versioned consent grants/withdrawals (`user_consents`) | personal data (operational) |
| Session/auth tokens | authentication session material | personal data (operational) |
| Compliance events | append-only, PII-free audit events (`compliance_events`) | no PII (opaque hashed refs only) |
| DSAR log | request type, timestamps, status, opaque hashed user ref (`dsar_requests`) | no PII |

## 3. Processing activities

### 3.1 Core decision-support (clinical Q&A)

- **Purpose:** Answer the user's medical-information questions with retrieval-augmented synthesis. Decision-support only — no diagnosis, no prescription.
- **Data categories:** Clinical queries; optionally PHR/medicine-cabinet context when personalization consent is present.
- **Legal basis:** Consent (`core_service` purpose) under PDPD Art. 11/13.
- **Recipients:** Internal CLARA_ML service; offshore LLM processor (see §4) when `cross_border_processing` consent is present and gating allows.
- **Retention:** Query log — 365 days, then delete (data minimization).

### 3.2 Personalization

- **Purpose:** Tailor answers using the user's PHR, allergies, conditions, and medicine cabinet.
- **Data categories:** PHR profile, coded lists, observations, medicine cabinet.
- **Legal basis:** Consent (`personalization` purpose). When absent or withdrawn, personalization context is excluded on all subsequent requests (Req 2.3).
- **Recipients:** Internal only (unless cross-border consent also present).
- **Retention:** PHR profile and medicine cabinet — 1095 days, then anonymize.

### 3.3 Cross-border model inference

- **Purpose:** Generate the synthesized answer via the offshore LLM, and generate embeddings for retrieval.
- **Data categories:** Minimized query text / retrieval text. Direct identifiers excluded where feasible (Req 4.3).
- **Legal basis:** Explicit, separately-toggleable consent (`cross_border_processing`) under PDPD Arts. 25–27 and the AI-Law high-risk obligation.
- **Recipients:** YEScale-hosted DeepSeek LLM endpoint and YEScale embedding endpoint — both offshore (non-VN). See `transfer-impact-assessments.md`.
- **Retention:** No content is logged. Only a no-PII transfer event (processor, purpose, opaque ref) is recorded (Req 4.4).

### 3.4 Research use

- **Purpose:** Use de-identified data to improve clinical-quality evaluation.
- **Legal basis:** Consent (`research` purpose), default off.
- **Recipients:** Internal research-quality harness only.
- **Retention:** Governed by the originating category; de-identified before use.

### 3.5 Sharing

- **Purpose:** Share a PHR record with a chosen recipient (e.g. a clinician) at the user's initiative.
- **Data categories:** PHR profile and coded lists per the share scope (`phr_shares`).
- **Legal basis:** Consent (`sharing` purpose).
- **Recipients:** The recipient the user designates.
- **Retention:** For the lifetime of the share; revoked on deletion.

### 3.6 AI transparency acknowledgement

- **Purpose:** Record that the user has seen the AI Transparency Notice (Req 1.2, 1.6).
- **Data categories:** Typed consent row (`ai_transparency` purpose) with the acknowledged notice version.
- **Legal basis:** Legal obligation (AI Law transparency) + consent record.
- **Retention:** Retained in the append-only consent ledger.

### 3.7 Compliance event logging & DSAR handling

- **Purpose:** Maintain the append-only audit trail and process data-subject rights requests.
- **Data categories:** Event type, opaque hashed subject reference, processor, severity, counts/flags only — never PII (Req 6.3, 7.4).
- **Legal basis:** Legal obligation (record-keeping; data-subject rights).
- **Retention:** Compliance events and DSAR rows — 3650 days, retained for legal defensibility (no PII).

## 4. Recipients — third-party / cross-border processors

| Processor (id) | Role | Purpose | Jurisdiction | TIA reference |
|---|---|---|---|---|
| `yescale-deepseek` | Data processor (LLM inference, governed DeepSeek V4 Pro/Flash via configured gateway) | `llm_inference` | offshore (non-VN) | `transfer-impact-assessments.md#yescale-deepseek` |
| `yescale-embeddings` | Data processor (embedding generation, OpenAI-compatible endpoint `https://api.yescale.io/v1`) | `embedding_generation` | offshore (non-VN) | `transfer-impact-assessments.md#yescale-embeddings` |

These mirror the seeded `TransferRegistry`
(`services/api/src/clara_api/compliance/transfer.py`) and are summarized in the
privacy policy (Req 4.5).

## 5. Retention schedule (source-of-truth: `retention.py`)

| Category | Retention (days) | Action | Basis |
|---|---|---|---|
| `phr_profile` | 1095 | anonymize | health-record self-management; consent-based |
| `medicine_cabinet` | 1095 | anonymize | health-record self-management; consent-based |
| `query_log` | 365 | delete | service operation; data minimization |
| `session_token` | 90 | delete | authentication security |
| `compliance_event` | 3650 | retain | legal defensibility; contains no PII |
| `dsar_request` | 3650 | retain | legal defensibility; contains no PII |

Expired rows are anonymized or deleted by the scheduled retention sweep, gated
by `COMPLIANCE_RETENTION_JOB_ENABLED` (Req 7.2). With the flag off the sweep is
an inert no-op, preserving current behavior.

## 6. Data-subject rights pointers

Access, correction, deletion/anonymization, restriction, and consent withdrawal
are served through the DSAR service (`dsar.py`); see `dpia.md` §6 for the rights
matrix and the statutory 30-day response window.
