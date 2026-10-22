# Consent Ledger Retention & DSAR Impact Specification (PH05)

## Statutory Mandates (PDPD Vietnam & Decree 13/2023/ND-CP)

Under Decree 13/2023/ND-CP on Personal Data Protection (PDPD), data subjects possess statutory rights to:
1. **Access and Portability (DSAR Export):** Receive a complete, structured export of all processed personal data and consent history.
2. **Withdrawal of Consent:** Revoke previously granted consent without penalty or retrospective invalidation.
3. **Erasure (Right to be Forgotten):** Request deletion of personal data subject to statutory medical retention laws.

## Retention vs Erasure Reconciled Invariants

| Data Category | Live Storage Table | DSAR Export Scope | Retention Period Post-Erasure | Legal Basis for Post-Erasure Retention |
|---|---|---|---|---|
| Active Health Dossier | `phr_records`, `lifemap_events` | Full machine JSON | Erased within 72 hours | N/A (Erased upon request) |
| Medication Cabinet | `medicine_cabinets`, `cabinet_items` | Full machine JSON | Erased within 72 hours | N/A (Erased upon request) |
| Clinical Scribe Audio | Temporary spool | Excluded (ephemeral) | 0 hours (Evicted immediately) | Data minimization |
| Consent Ledger | `user_consents` | Complete timestamped audit trail | **Retained 5 years (Redacted)** | Statutory compliance proof (PDPD Art. 17 & Medical Law) |
| Compliance Audit Log | `compliance_events` | Hashed references only | **Retained 5 years (No-PII)** | Regulatory audit defense |

## DSAR Export Pipeline Contract

When a user initiates `POST /compliance/dsar/export`, the pipeline executes:
1. `UserConsent` table query: Retrieves all historical rows for `user_id`, including `accepted_at` and `revoked_at`.
2. Purpose reconciliation: Maps each record to human-readable Vietnamese and English statutory purpose labels.
3. Redaction verification: Confirms that export metadata contains zero internal cryptographic keys, database row IDs, or third-party tracking identifiers.
4. ZIP bundle emission: Emits encrypted, time-limited download URL expiring in 24 hours.
