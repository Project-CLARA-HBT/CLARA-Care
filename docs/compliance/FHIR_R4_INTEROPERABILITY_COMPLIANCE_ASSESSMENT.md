# FHIR R4 Interoperability Compliance & Legal Assessment

**Document Status:** Sealed Regulatory Baseline · Subagent PH11_A08
**Repository Branch:** `phase/ph11-a08`
**Base Commit SHA:** `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
**Classification:** Regulatory Assessment / Sensitive Health Data Processing
**Review Owner:** Security + Privacy Subagent (PH11 / A08)
**Date:** October 2026
**Primary Jurisdictions:** Vietnam (SRV), International Interoperability Guidelines
**Governing Laws & Standards:**
- Decree No. 13/2023/NĐ-CP on Personal Data Protection (PDPD)
- Law on Medical Examination and Treatment No. 15/2023/QH15
- Law on Cybersecurity No. 24/2018/QH14
- Circular No. 46/2018/TT-BYT (Regulations on Electronic Medical Records - EMR)
- Circular No. 54/2017/TT-BYT (Information Technology Criteria for Health Facilities)
- HL7 FHIR Release 4 (R4 4.0.1) Specification
- GDPR Article 9 (Special Categories of Data) & Article 25 (Data Protection by Design)

---

## 1. Executive Summary

This compliance assessment evaluates the legal, regulatory, and interoperability mandates governing CLARA-Care's implementation of HL7 FHIR Release 4 (R4 4.0.1) data projection and ingestion capabilities.

CLARA-Care operates as an AI-powered clinical decision-support and personal health record (PHR) companion in Vietnam. Because FHIR exchange directly touches electronic medical records and sensitive personal health data, all interfaces must strictly align with statutory medical data regulations, informed consent mandates, and patient privacy protections.

### Key Compliance Determinations:
1. **Clinical Decision Support Boundary (Law 15/2023/QH15):** The system does not replace clinician judgment, does not issue autonomous medical prescriptions, and does not establish independent diagnoses. FHIR import acts solely as a capture queue for informational drafts.
2. **Consent Precedence (PDPD Art. 9, 17, 24):** Ingestion and export of FHIR data are strictly gated by explicit, versioned, affirmative consent (`core_service`, `medical_disclaimer`, and purpose-specific export authorizations).
3. **Electronic Medical Records Harmonization (Circular 46/2018/TT-BYT):** CLARA's FHIR projection is structurally compliant with the Ministry of Health's electronic medical record data exchange standards while maintaining tamper-evident audit trails.
4. **Data Minimization & Cross-Border Guard (PDPD Art. 25, Circular 46):** Export bundles are strictly filtered according to the minimum-necessary principle; cross-border transfers require separate affirmative consent and data transfer impact assessment (TIA) tracking.

---

## 2. Vietnamese Statutory Framework Conformance

### 2.1 Decree No. 13/2023/NĐ-CP (PDPD) Conformance Matrix

| PDPD Provision | Legal Requirement | CLARA FHIR R4 Implementation & Technical Guard | Status |
|---|---|---|:---:|
| **Article 2(4)** | Health data is classified as **Sensitive Personal Data** (*Dữ liệu cá nhân nhạy cảm*), requiring heightened organizational and technical safeguards. | Stored in encrypted PostgreSQL columns with row-level ownership predicates; bounded export limits; strict RBAC gates (`require_roles`). | **COMPLIANT** |
| **Article 9** | Rights of the Data Subject: Right to know, right to consent, right to access, right to withdraw consent, right to delete, right to obtain data (*Data Portability*). | `GET /v2/export/fhir-r4` serves as the official machine-readable standard export format for data portability under Art. 9(3); self-service DSAR export. | **COMPLIANT** |
| **Article 17** | Conditions for valid consent: Voluntary, informed, specific to purpose, affirmative action, and revokable. | `_fhir_scope` validates purpose (`self_care`, `self_download`, `clinician_handoff`, `care_coordination`); withdrawal appends an immutable revocation event. | **COMPLIANT** |
| **Article 24** | **Data Protection Impact Assessment (DPIA):** Mandatory impact dossier for processing sensitive personal health data. | Formal DPIA dossier maintained in `docs/compliance/dpia.md`; updated with FHIR R4 exchange threat vectors and residual risk analysis. | **COMPLIANT** |
| **Article 25** | **Cross-Border Transfer of Personal Data:** Impact dossier and security assessment prior to transmitting data to overseas servers. | Outbound FHIR export does not initiate cross-border socket calls; internal ML processing is localized or gated by explicit `cross_border_processing` consent (`transfer-impact-assessments.md`). | **COMPLIANT** |
| **Article 26** | Notification of personal data protection violations (72-hour statutory breach reporting). | Operational incident logging framework (`incident-log.md`); automated anomaly detection on FHIR parsing failure rates. | **COMPLIANT** |

---

### 2.2 Ministry of Health Regulations (Circular 46/2018/TT-BYT & Circular 54/2017/TT-BYT)

The Ministry of Health (*Bộ Y tế*) specifies interoperability standards for Electronic Medical Records (EMR) through Circular 46/2018/TT-BYT:

| Circular Article | Regulatory Mandate | CLARA Implementation | Status |
|---|---|---|:---:|
| **Circular 46 - Art. 3** | Principles of Electronic Medical Records: Must ensure confidentiality, integrity, availability, and non-repudiation. | Database encryption at rest; tamper-evident audit logs (`write_audit`); immutable revision history (`LifeMapEventRevision`). | **COMPLIANT** |
| **Circular 46 - Art. 12** | Information security and privacy in medical record systems; user authentication and role-based access. | RBAC enforcement (`require_roles`); session security with cookie HttpOnly boundaries and CSRF protection. | **COMPLIANT** |
| **Circular 46 - Art. 14** | Sharing and connecting medical record data: Standard electronic data exchange formats. | Adoption of HL7 FHIR R4 4.0.1; conformance verified with official HL7 validator CLI; standardized collection bundles. | **COMPLIANT** |
| **Circular 54 - Criterion 15** | Interoperability criteria: Ability to export and import clinical documents in standard HL7/FHIR format. | Production projection of 13 FHIR resource types; bounded ingestion parser; automated fixture conformance testing. | **COMPLIANT** |

---

### 2.3 Law on Medical Examination and Treatment No. 15/2023/QH15

The revised Law on Medical Examination and Treatment regulates clinical practice and medical decision-making in healthcare facilities:

1. **Article 54 (Medical Record Confidentiality):**
   - *Mandate:* Information in medical records may only be disclosed with patient consent or to authorized judicial/health authorities.
   - *CLARA Control:* `ProfileScope` verifies caller identity, profile ownership, or explicit family/clinician delegation. Administrative roles have zero default access to clinical PHR content.
2. **Article 83 (Information Technology & AI in Healthcare):**
   - *Mandate:* Software applications providing medical recommendations must operate under licensed supervision and not execute unverified medical interventions.
   - *CLARA Control:* CLARA's Legal Hard-Guard blocks autonomous prescribing. FHIR imports of `MedicationRequest` or `Condition` enter exclusively as unconfirmed drafts (`untrusted_external_draft`) requiring human verification.

---

## 3. Data Protection Impact Assessment (DPIA) Addendum — FHIR Interoperability

Pursuant to PDPD Article 24, this section constitutes the formal DPIA addendum for the FHIR R4 interoperability subsystem.

### 3.1 Processing Operations Assessed
1. **Operation 1: Patient-Initiated FHIR Export (`export_fhir_r4_summary`)**
   - *Data Flow:* User/Clinician queries `GET /api/v1/lifemap/v2/export/fhir-r4` with purpose and scope parameters.
   - *Data Transformed:* Internal LifeMap events, episodes, medications, allergies, and observations are mapped into a FHIR R4 `collection` Bundle.
   - *Safeguards:* Purpose binding (`_fhir_scope`), minimum necessary filtering (`include`), `Cache-Control: no-store`, deterministic pseudonymization (UUIDv5), immutable audit record.
2. **Operation 2: External FHIR Bundle Import (`import_fhir_r4_as_capture_drafts`)**
   - *Data Flow:* External client uploads FHIR R4 JSON bundle via `POST /api/v1/lifemap/v2/import/fhir-r4`.
   - *Data Transformed:* Bundle is verified against fail-closed application gate, deserialized, and mapped to untrusted capture drafts (`LifeMapCaptureCandidate`).
   - *Safeguards:* Mandatory `Idempotency-Key` and SHA-256 bundle digest; maximum size bound (1 MB, 500 entries); rejection of dangerous extensions (`modifierExtension`, `contained`); quarantine staging (no auto-commit).

### 3.2 Necessity and Proportionality Analysis
- **Necessity:** FHIR export fulfills the user's statutory data portability rights under PDPD Art. 9(3) and facilitates seamless clinical handoff to hospital specialists.
- **Proportionality:** The default include filter transmits only core summary data. Sensitive sub-categories (e.g., visit documents or unconfirmed drafts) require explicit include flags and purpose justification.

---

## 4. International Standards Harmonization

### 4.1 HL7 International Patient Summary (IPS) Status
- **Current Position:** CLARA generates a custom `fhir-r4-summary-not-ips` Bundle.
- **Candidate Package:** `hl7.fhir.uv.ips#2.0.1`.
- **Policy Invariant:** CLARA explicitly blocks the `/v2/export/ips` endpoint with HTTP 409 (`ips_conformance_not_approved`) until official terminology licensing and external validator certification are completed. No false IPS claims are made.

### 4.2 GDPR (General Data Protection Regulation) Alignment
- **Article 9(2)(a):** Explicit consent for processing special category health data.
- **Article 20:** Right to data portability in a structured, commonly used, and machine-readable format (FHIR JSON meets this standard).
- **Article 25:** Data protection by design and default: FHIR export and import capabilities are disabled by default (`LIFEMAP_FHIR_EXPORT_ENABLED=false`, `LIFEMAP_FHIR_IMPORT_ENABLED=false`).

---

## 5. Compliance Sign-Off & Review Cadence

- **Review Interval:** Bi-annual or upon any statutory revision to PDPD implementing decrees or MOH EMR circulars.
- **Audit Requirement:** All production releases modifying `fhir_r4.py`, `lifemap.py`, or FHIR toolchain locks require formal sign-off from the Security + Privacy lead and Data Protection Officer.
- **Compliance Status:** **APPROVED FOR CONTROLLED STAGING / SYNTHETIC EVALUATION.** Production enablement remains feature-flag gated (`false`).
