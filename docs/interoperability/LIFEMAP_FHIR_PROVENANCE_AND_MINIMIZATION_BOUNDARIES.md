# LifeMap FHIR Provenance & Minimization Boundaries

- **Phase ID**: PH12 (LifeMap longitudinal intelligence)
- **Agent ID**: A09
- **Role**: Docs + research evidence
- **Applicable Interoperability Profiles**:
  - HL7 FHIR Release 4 (R4)
  - SMART App Launch Framework (v1 & v2)
  - HL7 FHIR Provenance & AuditEvent Profiles
- **Baseline Commit**: `36e5b95fac7e65712f0779de253d8ed18dc693d7`
- **Status**: **VERIFIED & AUDITED**

---

## 1. Overview & Regulatory Interoperability Context

Under the Vietnam Law on Medical Examination and Treatment No. 15/2023/QH15 and Circular 46/2018/TT-BYT on Electronic Medical Records, healthcare providers and health information systems must maintain clear data boundaries and clinical accountability when exchanging longitudinal patient data.

When exchanging longitudinal data via FHIR R4 interfaces:
1. Patient self-reported information must never masquerade as verified physician clinical orders.
2. Third-party FHIR resources imported from external hospital sandboxes or clinics must be isolated in a non-authoritative draft capture queue until validated.
3. Every export or read interaction must be accounted for in privacy-preserving FHIR `AuditEvent` and `Provenance` resources without leaking internal reasoning traces (Zero-CoT) or extraneous protected health information (PHI).

---

## 2. Resource Mapping & Prescribing Boundary Invariant

### 2.1 Medication Mapping Boundary

To uphold Law 15/2023/QH15 Articles 32 & 53 (prohibition of non-physician prescribing):

| Clinical Source | LifeMap Truth State | Outbound FHIR R4 Resource | Permitted Scopes | Autonomous Action |
|---|---|---|---|---|
| Licensed Physician Order | `confirmed` | `MedicationRequest` (Status: `active` / `completed`) | `user/MedicationRequest.read`, `system/MedicationRequest.rs` | Prescribing physician holds sole clinical liability. |
| Patient Self-Reported Med | `user_reported` | `MedicationStatement` (Status: `recorded`) | `patient/MedicationStatement.rs`, `user/MedicationStatement.read` | Informational only. Cannot initiate pharmacy dispensing. |
| AI / OCR Extraction Draft | `draft` | **Suppressed from standard FHIR export** | Internal draft review only | Blocked from external export until confirmed. |

Under no circumstances may a patient assertion or AI extraction generate a `MedicationRequest`. If an untrusted caller attempts to issue a `MedicationRequest` without physician credentials, the gateway rejects the request with HTTP 403 (`forbidden_prescribing_intent`).

---

## 3. SMART-on-FHIR Scopes to ProfileScope Mapping

Incoming SMART-on-FHIR OAuth2 access tokens are translated directly into the internal `ProfileScope` model:

```text
SMART-on-FHIR Token Scopes                     LifeMap ProfileScope
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│ patient/MedicationStatement.rs  │ ────────> │ allowed_data_classes:           │
│ patient/Observation.rs          │           │   {"medications", "observations"}│
│ launch/patient                  │           │ allowed_actions: {"view"}       │
│ fhirUser                        │           │ purpose: "clinician_handoff"    │
└─────────────────────────────────┘           └─────────────────────────────────┘
```

### Granular Scope Translation Invariants:
1. **Context Isolation**:
   - `patient/*`: Confined strictly to the authorized patient profile associated with the OAuth launch context.
   - `user/*`: Bound to the clinician user; requires a matching `FamilyAccessGrant` or hospital provider link to access the patient profile.
   - `system/*`: Restricted to backend microservices with mutual TLS (mTLS) and IP whitelisting.
2. **Permission Gating**:
   - Permission `r` (read) maps to `ProfileScope.allowed_actions = {"view"}`.
   - Permission `c` (create) or `u` (update) on clinical resources requires doctor role verification.
   - Administrative scopes are barred from clinical data classes (`platform_root_cannot_read_phi`).

---

## 4. Untrusted Third-Party FHIR Import Isolation

When external hospital EHRs, diagnostic centers, or third-party health apps push FHIR bundles into LifeMap:

1. **Draft Capture Queue**: Incoming resources (`Condition`, `Observation`, `AllergyIntolerance`, `MedicationStatement`) are ingested strictly as `draft` truth state records via `import_fhir_r4_as_capture_drafts` (`services/api/src/clara_api/api/v1/endpoints/lifemap.py`).
2. **No Immediate Timeline Mutation**: Draft imports do not automatically alter the patient's active timeline projections or trigger diagnostic AI alerts.
3. **Mandatory Human Verification**: The patient or attending physician must review the imported draft items in the LifeMap review queue and explicitly promote them to `user_reported` or `confirmed`.
4. **Source Provenance Retention**: The originating FHIR `Bundle.id`, source institution, and import timestamp are preserved in `LifeMapEventRevision.source_reference_id`.

---

## 5. AuditEvent & Provenance Data Minimization

Under Decree 13/2023/ND-CP Article 9, compliance audit logs must be minimized to avoid creating duplicate secondary repositories of sensitive medical data.

When LifeMap emits FHIR `AuditEvent` and `Provenance` resources:

1. **Pseudonymization**: The patient subject is identified solely by their opaque UUID (`Patient/<profile_public_id>`). Internal database primary keys (`id`) and Citizen Identity Card numbers (CCCD) are never included.
2. **Zero-CoT Sanitization**: AI reasoning prompts, search query text, and intermediate retrieval scores are excluded from audit payload details.
3. **Action Categorization**: Actions are recorded using standard FHIR audit action codes (`C` = Create, `R` = Read, `U` = Update, `D` = Delete, `E` = Execute).
4. **Purpose of Use Encoding**: The `purposeOfUse` coding reflects the exact statutory purpose (e.g., `TREAT` = Treatment, `HPAYMT` = Healthcare Payment, `CLINTRL` = Clinical Research with separate consent).

---

## 6. Summary of Interoperability Invariants

- **INV-INTEROP-01**: FHIR `MedicationRequest` is strictly reserved for licensed physician orders; consumer assertions emit exclusively as `MedicationStatement`.
- **INV-INTEROP-02**: Inbound external FHIR bundles enter strictly as `draft` capture queues; zero autonomous promotion to active clinical truth.
- **INV-INTEROP-03**: FHIR `AuditEvent` records preserve access history without storing plaintext clinical queries or PII.
- **INV-INTEROP-04**: Revoked consent cascades immediately to disable external FHIR endpoints for the revoked resource category.
