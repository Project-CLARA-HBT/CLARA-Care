# FHIR Patient Identification & De-Identification Technical Specification

**Document Status:** Sealed Technical Baseline · Subagent PH11_A08
**Repository Branch:** `phase/ph11-a08`
**Base Commit SHA:** `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
**Classification:** Sensitive Health Data Specification / PDPD & HIPAA Conformance
**Review Owner:** Security + Privacy Subagent (PH11 / A08)
**Date:** October 2026
**Applicable Legal Frameworks:** Vietnam PDPD (Decree 13/2023/NĐ-CP), Law on Medical Examination and Treatment No. 15/2023/QH15, Circular 46/2018/TT-BYT, HIPAA Safe Harbor (45 CFR § 164.514(b)), GDPR Art. 9 & Art. 25.

---

## 1. Scope & Objectives

This specification defines the cryptographic, architectural, and data-processing controls governing **Patient Identification, Pseudonymization, and De-Identification** across CLARA-Care's HL7 FHIR R4 4.0.1 interoperability layer.

The core objectives are:
1. **Single-Patient Scope Integrity:** Guaranteeing that every FHIR Bundle represents exactly one deterministic patient entity, eliminating cross-patient data leakage.
2. **Deterministic Pseudonymization:** Providing reproducible, collision-resistant, non-reversible public identifiers for longitudinal care coordination without exposing internal primary keys or national identity records.
3. **Vietnamese Identity Artifact Stripping:** Explicitly identifying and redacting Vietnamese government identifiers (CCCD/CMND, BHYT, BHXH, Sổ khám bệnh) prior to FHIR export or external processing.
4. **Zero-Hallucination Coding Invariant:** Preventing synthetic generation or hallucination of clinical coding systems (LOINC, SNOMED CT, ICD-10, RxNorm) during FHIR translation.
5. **Fail-Closed Import Verification:** Rejecting bundles with multi-patient references, foreign subject identifiers, or unverified patient bindings.

---

## 2. Vietnamese Identity Artifact Inventory & Redaction Matrix

Healthcare records in Vietnam frequently incorporate mandatory statutory identifiers. When exchanging FHIR resources with external systems, research registries, or AI evaluation pipelines, direct identifiers must be sanitized according to Decree 13/2023/NĐ-CP Art. 2(4) (Sensitive Personal Data).

### 2.1 Identity Artifact Classification & Handling
| Identity Artifact Name (Vietnamese / English) | Statutory Format / Pattern | Confidentiality Level | FHIR Ingestion Policy | FHIR Export Policy (Summary Projection) |
|---|---|---|---|---|
| **Số Định danh cá nhân / Căn cước công dân (CCCD)** | 12 numeric digits (`^\d{12}$`) | Highly Sensitive Direct Identifier | Accepted into encrypted profile metadata only; never indexed in public URI | **STRIPPED / REDACTED.** Never emitted in `Patient.identifier`. |
| **Chứng minh nhân dân (CMND cũ)** | 9 numeric digits (`^\d{9}$`) | Sensitive Direct Identifier | Accepted into encrypted profile metadata only | **STRIPPED / REDACTED.** Never emitted. |
| **Mã số Bảo hiểm Y tế (BHYT)** | 15 alphanumeric characters (`^[A-Z]{2}\d{13}$`) | Sensitive Quasi-Identifier | Permitted in encrypted profile metadata | **MASKED.** If included under explicit clinician export, masked as `DN-XXXXXXXXXXXX` or stripped. |
| **Mã số Bảo hiểm Xã hội (BHXH)** | 10 numeric digits (`^\d{10}$`) | Sensitive Direct Identifier | Permitted in encrypted profile metadata | **STRIPPED.** Never emitted. |
| **Họ và tên bệnh nhân (Full Name)** | Vietnamese UTF-8 text with diacritics | Direct Identifier | Validated on import; stored in encrypted DB column | **PSEUDONYMIZED or USER-CHOSEN.** In public summary export: masked as `BN-XXXXXXXX` or explicit user profile name. |
| **Ngày tháng năm sinh (Date of Birth)** | ISO date `YYYY-MM-DD` | Quasi-Identifier | Validated against `^\d{4}-\d{2}-\d{2}$` | Preserved if consented; Coarsened to Year (`YYYY`) in research exports. |
| **Số điện thoại (Phone Number)** | Vietnamese mobile (`^(03\|05\|07\|08\|09)\d{8}$`) | Direct Identifier | Mobile auth credential; stored hashed / encrypted | **STRIPPED.** Excluded from all FHIR exports. |
| **Địa chỉ cụ thể (Street Address / Ward)** | Free-text Vietnamese address (Số nhà, thôn, ấp, xã) | Quasi-Identifier | Stored in encrypted profile | **STRIPPED.** Preserves at most Province/City code (`Mã Tỉnh/Thành phố`) where consented. |
| **Mã hồ sơ bệnh án / Sổ khám bệnh (EMR ID)** | Hospital-specific alphanumeric code | Quasi-Identifier | Captured in `DocumentReference` metadata | Retained only as opaque local source reference with hospital URI. |

---

## 3. Cryptographic Pseudonymization Architecture

To maintain longitudinal referential integrity without persisting cleartext identifiers in exported bundles, CLARA implements a **Deterministic Namespaced UUIDv5 Derivation**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   CLARA Patient Pseudonymization Pipeline                   │
└─────────────────────────────────────────────────────────────────────────────┘

  Internal Database Profile
  ┌────────────────────────────────────────────────┐
  │ Profile Primary Key : id = 4289                 │
  │ Public UUID         : 11111111-1111-4111-8111...│
  │ Tenant Organization : "hospital_bach_mai_01"   │
  └────────────────────────────────────────────────┘
                          │
                          ▼
            [ Namespace Salt & Seed Input ]
            NAMESPACE_URL = 6ba7b811-9dad-11d1-80b4-00c04fd430c8
            Domain Salt   = "theclaracare.com/fhir/patient/v1"
            Input Seed    = f"{tenant_id}:{profile_public_id}"
                          │
                          ▼
             [ RFC 4122 UUIDv5 Generator ]
             SHA-1 Hash over Namespace + Seed
                          │
                          ▼
  Exported FHIR Resource Identifier
  ┌────────────────────────────────────────────────┐
  │ Patient.id = "e4d909c2-901a-5bf6-b2d4-..."      │
  │ fullUrl    = "urn:uuid:e4d909c2-901a-5bf6-..." │
  │ Identifier = System "urn:ietf:rfc:3986"        │
  └────────────────────────────────────────────────┘
```

### 3.1 Algorithm Specification
1. **Namespace Definition:** A dedicated UUIDv5 namespace salt is established:
   `NAMESPACE_CLARA_PATIENT = uuid5(NAMESPACE_URL, "theclaracare.com/fhir/patient/v1")`
2. **Seed Composition:** The seed incorporates the tenant organization ID, the profile public ID, and a deployment salt:
   `seed = f"{tenant_organization_id}:{profile_public_id}"`
3. **Pseudonym Derivation:**
   `patient_fhir_id = str(uuid5(NAMESPACE_CLARA_PATIENT, seed))`
4. **Bundle Invariant:** All references to the patient within the bundle (`Observation.subject`, `Condition.subject`, `AllergyIntolerance.patient`, etc.) MUST use the identical derived UUID:
   `"reference": f"urn:uuid:{patient_fhir_id}"`

### 3.2 Security Properties
- **Collision Resistance:** UUIDv5 (128-bit RFC 4122) guarantees negligible collision probability across hundreds of millions of patient profiles.
- **One-Way Irreversibility:** External parties possessing the exported FHIR bundle cannot calculate the internal database primary key or public profile UUID without the internal secret deployment salt.
- **Cross-Tenant Partitioning:** Incorporating `tenant_organization_id` into the seed prevents rainbow-table correlation of identical patients across separate hospital deployments.

---

## 4. Single-Patient Boundary Invariants

A critical clinical safety vulnerability in FHIR interoperability is **Cross-Subject Contamination**, where an exported or imported bundle intermixes data belonging to multiple human patients.

### 4.1 Ingestion Gate Invariants (`validate_bundle`)
When evaluating an incoming FHIR bundle at `POST /api/v1/lifemap/v2/import/fhir-r4`:
1. **Rule P-01 (Exactly One Patient):** The Bundle MUST contain exactly one `Patient` resource entry.
   - Zero `Patient` resources: rejected with HTTP 422 (`exactly_one_patient_required`).
   - Two or more `Patient` resources: rejected with HTTP 422 (`exactly_one_patient_required`).
   - *Verification Anchor:* `services/api/src/clara_api/lifemap/fhir_r4.py:771-778`.
2. **Rule P-02 (Intra-Bundle Subject Binding):** Every clinical resource that contains a patient reference (`subject` or `patient`) MUST reference the single `Patient` defined in Rule P-01.
   - Pointing to an external patient ID: rejected (`cross_subject_reference`).
   - Pointing to a dangling non-existent ID: rejected (`dangling_reference`).
   - *Verification Anchor:* `services/api/src/clara_api/lifemap/fhir_r4.py:848-872`.
3. **Rule P-03 (Authenticated Profile Match):** The resolved `ProfileScope` of the authenticated caller MUST match the designated target profile. An actor cannot import an external bundle into a profile they do not own or possess an active family/clinician delegation grant for.
   - *Verification Anchor:* `services/api/src/clara_api/api/v1/endpoints/lifemap.py:3024-3030`.

---

## 5. Clinical Terminology & Anti-Hallucination Policy

A severe clinical risk in automated healthcare interoperability is the fabrication or "hallucination" of standard terminology codes (e.g., inventing plausible-looking ICD-10 or SNOMED CT codes from free-text descriptions).

### 5.1 Strict Terminology Invariants
CLARA-Care enforces the following invariants across its FHIR translation pipelines:
1. **Zero Hallucination:** CLARA NEVER invents or synthesizes a LOINC, SNOMED CT, ICD-10, or RxNorm code. If a clinical observation or condition originates from un-coded user free text, it is emitted with `text` description ONLY:
   ```json
   {
     "coding": [],
     "text": "Tăng huyết áp do người dùng khai báo"
   }
   ```
2. **Verified Code Systems Only:** Standard codings are emitted ONLY when the source record originated from an authenticated hospital EMR system, licensed dictionary, or confirmed laboratory machine interface with an explicit `system` and `code`:
   - `http://loinc.org` (Logical Observation Identifiers Names and Codes)
   - `http://snomed.info/sct` (SNOMED Clinical Terms)
   - `http://hl7.org/fhir/sid/icd-10` (International Classification of Diseases, 10th Revision)
   - `http://www.nlm.nih.gov/research/umls/rxnorm` (RxNorm Clinical Drug Terminology)
3. **UCUM Unit Validation:** Quantities (`Observation.valueQuantity`) are emitted with standard units ONLY if the unit has a valid Unified Code for Units of Measure (UCUM) representation (`http://unitsofmeasure.org`). Otherwise, the value is serialized as `valueString` to avoid invalid medical conversions.
   - *Verification Anchor:* `services/api/src/clara_api/lifemap/fhir_r4.py:25`, `fhir_r4.py:440-476`.

---

## 6. Re-Identification Risk Assessment & Mitigation

In accordance with HIPAA 45 CFR § 164.514(b) (Safe Harbor) and Vietnam PDPD Article 24 (DPIA), CLARA evaluates and mitigates re-identification risk when producing FHIR R4 exports.

### 6.1 HIPAA 18 Identifier Safe Harbor Analysis
| # | HIPAA Identifier Category | CLARA FHIR R4 Status | Technical Enforcement |
|---|---|---|---|
| 1 | Names | Masked / Pseudonymized | Replaced with user display name or `BN-XXXXXXXX` token |
| 2 | Geographic data smaller than state | Coarsened to Province | Street address, ward, district stripped |
| 3 | Dates related to individual (DOB, admit) | Birthdate optional; times truncated | Coarsened to YYYY in research; full date requires consent |
| 4 | Telephone numbers | **STRIPPED** | Excluded from FHIR payload entirely |
| 5 | Fax numbers | **STRIPPED** | Excluded from FHIR payload entirely |
| 6 | Email addresses | **STRIPPED** | Excluded from FHIR payload entirely |
| 7 | Social Security Numbers | **STRIPPED** | National ID (CCCD) stripped |
| 8 | Medical record numbers (MRN) | Opaque local source | Replaced with ephemeral UUIDv5 reference |
| 9 | Health plan beneficiary numbers | **STRIPPED / MASKED** | Health insurance (BHYT) masked or omitted |
| 10 | Account numbers | **STRIPPED** | Excluded |
| 11 | Certificate/license numbers | **STRIPPED** | Excluded |
| 12 | Vehicle identifiers & serials | **STRIPPED** | Excluded |
| 13 | Device identifiers & serials | Opaque model name only | Raw serial numbers stripped |
| 14 | Web URLs | **STRIPPED** | Prohibited by reference validator |
| 15 | IP addresses | **STRIPPED** | Excluded from FHIR resources |
| 16 | Biometric identifiers | **STRIPPED** | Not processed in LifeMap FHIR |
| 17 | Full-face photos | **STRIPPED** | Image attachments excluded from summary export |
| 18 | Any unique identifying number | Pseudonymized UUIDv5 | Deterministic namespaced UUIDs |

### 6.2 k-Anonymity & l-Diversity in Research Cohorts
When FHIR bundles are aggregated for population health or clinical evaluation (Phase B Benchmarks):
- Longitudinal event sequences are normalized to relative day offsets (`t=0` anchored to index encounter) rather than absolute calendar timestamps.
- Sparse rare disease codes occurring in less than `k=5` subjects in an institution are suppressed to eliminate uniqueness re-identification.

---

## 7. Audit Logging & Compliance Lineage

Every FHIR export and import transaction emits an immutable, PII-free audit event:
- **Export Audit:** Logs `action="export"`, `entity="lifemap_fhir_r4"`, `entity_id=<bundle_id>`, `actor_user_id=<user_id>`, `scope="owner:self_download"`. Excludes patient name, medical diagnosis, and medication list.
- **Import Audit:** Logs `action="import"`, `entity="lifemap_fhir_r4"`, `bundle_digest=<sha256>`, `candidate_count=<int>`, `idempotency_key=<key>`.
- *Verification Anchor:* `services/api/src/clara_api/api/v1/endpoints/lifemap.py:2914-2923`, `lifemap.py:3041-3060`.
