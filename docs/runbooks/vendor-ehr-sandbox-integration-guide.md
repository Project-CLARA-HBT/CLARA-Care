# Vendor EHR Sandbox Integration Guide & Operational Runbook

Status: Operational Runbook | Classification: Production Operations & Interoperability
Applies to: CLARA Care FHIR R4 Interoperability Projection Layer (PH11)
Governing Specifications: HL7 FHIR R4 (v4.0.1), SMART on FHIR (v2.0.0), Circular 46/2018/TT-BYT, Circular 54/2017/TT-BYT

---

## 1. Executive Summary & Purpose

This operational runbook governs the integration, security verification, and maintenance of connections between CLARA Care and external vendor Electronic Health Record (EHR) sandbox environments.

CLARA Care operates as a Vietnamese, safety-first Medical AI Assistant—**a clinical assistant, not a doctor replacement**. In accordance with core architectural invariants:
- **Projection-Only Model:** CLARA maintains its typed LifeMap and Personal Health Record (PHR) models as the authoritative internal source of truth. It is not an open general-purpose FHIR server. Export is provided as a purpose-bound FHIR R4 collection Bundle (`clara-r4-summary-not-ips`).
- **Untrusted External Draft Ingestion:** Inbound FHIR R4 resources imported from EHR sandboxes or hospital portals are strictly bounded (maximum 1 MB and 500 entries) and quarantined as `untrusted_external_draft` records. Import never confirms health truth, never executes a clinical task, and never creates an active medication order.
- **Zero-Mock Policy:** Vendor sandbox integrations must use explicitly designated synthetic sandbox credentials and test patient cohorts. No mock data may ever be promoted to production clinical databases.
- **Fail-Closed Feature Flags:** Inbound and outbound FHIR interoperability are governed by independent, default-off feature flags: `LIFEMAP_FHIR_EXPORT_ENABLED=false` and `LIFEMAP_FHIR_IMPORT_ENABLED=false`.

---

## 2. Supported Vendor EHR Sandbox Targets

| Vendor / Platform | API Standard | Profile / Specification | Target Sandboxes | Primary Use Case |
|---|---|---|---|---|
| **Epic Systems** | FHIR R4 / SMART on FHIR | USCDI v1/v2, Epic open.epic R4 | open.epic public sandbox, Epic App Market test harnesses | Inpatient / outpatient summary exchange, lab and observation retrieval |
| **Oracle Health (Cerner)** | FHIR R4 / SMART on FHIR | Millennium FHIR R4, US Core | Cerner code Developer Sandbox (`fhir-ehr-code.cerner.com`) | Longitudinal patient history, allergy and medication reconciliation |
| **SMART Health IT** | SMART on FHIR v2 | Open Reference FHIR R4 | `launch.smarthealthit.org/v/r4/fhir` | Protocol validation, token lifecycle and refresh testing |
| **HAPI FHIR / Medplum** | FHIR R4 (4.0.1) | Base FHIR R4 Core | Local / Staging HAPI FHIR test instance | Deterministic conformance validation and regression testbed |
| **Vietnamese Hospital HIS/LIS** | RESTful / FHIR R4 Adaptation | Circular 46/2018/TT-BYT, Circular 54/2017/TT-BYT | VNPT-HIS Sandbox, Viettel Solutions HIS Staging, FPT.eHospital | Vietnamese clinical documentation, DAV drug registration, ICD-10 bilingual records |

---

## 3. Architecture & Boundary Invariants

### 3.1 Boundary Endpoints

1. **Conformance Statement:**
   - Endpoint: `GET /api/v1/lifemap/v2/fhir/conformance`
   - Role: Describes the exact FHIR projection boundary, capability status, and explicit non-general-server status (`general_fhir_server: false`).
2. **Export Projection:**
   - Endpoint: `GET /api/v1/lifemap/v2/export/fhir-r4`
   - Gating: Requires active medical consent, verified profile authorization, allowed clinical purpose, and explicit minimum-necessary include parameters.
3. **Draft Ingestion:**
   - Endpoint: `POST /api/v1/lifemap/v2/import/fhir-r4`
   - Constraints: Maximum payload 1 MB, maximum 500 entries. Quarantined into Universal Capture drafts with `import_trust: untrusted_external_draft`.
4. **Candidate IPS Export Gate:**
   - Endpoint: `GET /api/v1/lifemap/v2/export/ips`
   - Gating: Hard fail-closed until international patient summary licensing, terminology, and external clinical validations are officially approved.

### 3.2 Clinical Safety & RBAC Invariants

- **Single-Patient Isolation:** Inbound Bundles must contain exactly one `Patient` resource matching the authenticated profile ID. Cross-patient references, multiple patients, or foreign tenant IDs trigger immediate `400 Bad Request` or `403 Forbidden`.
- **Prescription Order Immunity:** `MedicationRequest` resources from EHR sandboxes are never mapped to executable doctor orders within CLARA Care. Self-reported or imported medications are represented as unconfirmed drafts or `MedicationStatement` with zero execution authority.
- **Narrative XSS Quarantine:** All `.text.div` XHTML narrative blocks are inspected using regex pattern matching (`_UNSAFE_NARRATIVE`) to reject `<script>`, `<iframe>`, `javascript:`, or inline event handlers.
- **Reference Integrity:** External URIs (`http://`, `https://`, `//`) and versioned history URLs (`/_history/`) are forbidden inside reference fields to eliminate Server-Side Request Forgery (SSRF).
- **Prohibited Extensions:** `modifierExtension` elements and `contained` resources are strictly rejected to prevent semantic obfuscation.

---

## 4. Vendor Sandbox Setup & Credential Management

### 4.1 SMART on FHIR Backend Services (System-to-System)

For automated synchronization between CLARA Care's backend connectors and vendor EHR sandboxes:

1. **Key Pair Generation:**
   Generate an asymmetric RS384 or ES384 key pair strictly within the secure secrets management infrastructure (HashiCorp Vault or AWS KMS). Never store private keys in source control:
   ```bash
   # Generate ES384 private key (staging sandbox use only)
   openssl ecparam -name secp384r1 -genkey -noout -out sandbox_ehr_private.pem
   openssl ec -in sandbox_ehr_private.pem -pubout -out sandbox_ehr_public.pem
   ```
2. **JWKS Publication:**
   Publish the public key to CLARA's audited JWKS endpoint (`https://auth.theclaracare.com/.well-known/jwks.json`) with an assigned `kid` (key identifier).
3. **Vendor Registration:**
   Register the application in the vendor developer portal (e.g., Epic open.epic or Cerner code Console) providing:
   - Client Type: Confidential Backend Service
   - Token Endpoint Auth Method: `private_key_jwt`
   - JWKS URI: `https://auth.theclaracare.com/.well-known/jwks.json`
   - Allowed Token Algorithms: `RS384`, `ES384`
4. **Scope Authorization:**
   Request strictly minimum-necessary read scopes:
   ```text
   system/Patient.read system/Observation.read system/Condition.read system/AllergyIntolerance.read system/MedicationStatement.read system/DocumentReference.read
   ```
   *Warning:* Never request wildcard write scopes (`system/*.write`).

### 4.2 Standalone Patient Launch (Patient-Mediated)

For patient-directed import where the user authenticates directly against their hospital portal:

1. **App Registration:**
   - Redirect URI: `https://app.theclaracare.com/api/v1/auth/callback/ehr`
   - Launch Mode: Standalone Launch
   - PKCE Enforcement: Required (`S256` code challenge)
2. **Patient Scopes:**
   ```text
   launch/patient openid fhirUser offline_access patient/Patient.read patient/Observation.read patient/Condition.read patient/AllergyIntolerance.read patient/MedicationStatement.read
   ```
3. **Session & Token Isolation:**
   Access tokens and refresh tokens received from the EHR authorization server must be encrypted at rest using AES-256-GCM. Tokens are scoped strictly to the authenticated CLARA user profile ID.

---

## 5. Ingestion Pipeline & Quarantine Workflow

```
[External EHR Sandbox]
         |
         | (Encrypted TLS 1.3 POST /api/v1/lifemap/v2/import/fhir-r4)
         v
+-------------------------------------------------------------+
| 1. Ingress & Resource Boundary Filter                       |
|    - Payload size <= 1,048,576 bytes (1 MB)                 |
|    - Entry count <= 500 entries                             |
|    - Single Patient validation (patient_identity_mismatch)  |
+-------------------------------------------------------------+
         |
         v
+-------------------------------------------------------------+
| 2. Security & Anti-Injection Sanitization                   |
|    - Strip / reject unsafe XHTML narrative (XSS prevention) |
|    - Reject modifierExtension & contained resources         |
|    - Reject external / versioned URI references (SSRF)      |
|    - Validate critical codings (system + code required)     |
+-------------------------------------------------------------+
         |
         v
+-------------------------------------------------------------+
| 3. Candidate Isolation & Provenance Attachment              |
|    - Mark import_trust = 'untrusted_external_draft'         |
|    - Attach Provenance: vendor_id, bundle_id, timestamp     |
|    - Exclude Provenance/Consent/Composition from clinicals  |
+-------------------------------------------------------------+
         |
         v
+-------------------------------------------------------------+
| 4. Quarantine Storage in Universal Capture Table            |
|    - Status: PENDING_USER_VERIFICATION                      |
|    - Emits: lifemap.fhir_import_drafts_created (no PII)     |
+-------------------------------------------------------------+
```

---

## 6. Vietnamese EMR & HIS Conformance (Circular 46 & Circular 54)

### 6.1 Regulatory Context

Under Circular 46/2018/TT-BYT and Circular 54/2017/TT-BYT issued by the Ministry of Health (MOH) Vietnam:
- Electronic medical records must maintain immutable audit logs, digital signatures, and verifiable timestamps.
- Terminology must bind to official Vietnamese national catalogs:
  - ICD-10 Vietnamese clinical diagnostic codes (MOH Decision 4469/QD-BYT).
  - National Drug Administration of Vietnam (DAV) drug registration numbers (`so_dang_ky`).
  - Circular 43/2013/TT-BYT laboratory and technical procedure nomenclature.

### 6.2 Bilingual Mapping Rules

When importing from or exporting to Vietnamese hospital systems:
1. **Preserve Original Narrative:** Always store Vietnamese textual descriptions alongside standardized codes. Never discard original doctor notes.
2. **No Invented Codings:** If a vendor EHR entry contains an unrecognized local drug code or hospital-specific lab code, retain it as text with system URI `https://theclaracare.com/fhir/source-kind`. Do not invent SNOMED CT, LOINC, or RxNorm codes.
3. **UCUM Quantities:** Vital signs and laboratory numeric measurements are converted to FHIR `Quantity` only when the unit strictly adheres to the Unified Code for Units of Measure (`http://unitsofmeasure.org`). Otherwise, the value is preserved as a descriptive string.

---

## 7. Dual-Read & Parity Verification Runbook

Before enabling any EHR sandbox connector in pre-production or staging:

### Step 1: Pre-Flight Verification
Verify that the FHIR toolchain lock file is intact:
```bash
# Check toolchain pin and validator SHA-256
grep -E "version|sha256" docs/interoperability/fhir-toolchain.lock.json
```

### Step 2: Conformance Endpoint Inspection
Query the local or staging conformance endpoint:
```bash
curl -s http://localhost:8000/api/v1/lifemap/v2/fhir/conformance | jq .
```
Verify expected keys:
- `fhir_version`: `"4.0.1"`
- `conformance`: `"fhir-r4-summary-not-ips"`
- `general_fhir_server`: `false`

### Step 3: Synthetic Dual-Read Ingestion Test
Send a synthetic FHIR R4 Bundle containing Patient, Blood Pressure Observation, and MedicationStatement:
```bash
curl -X POST http://localhost:8000/api/v1/lifemap/v2/import/fhir-r4 \
  -H "Authorization: Bearer ${TEST_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/fhir/synthetic_patient_bundle.json
```
Verify response:
- HTTP Status: `201 Created`
- Created drafts count matches input clinical resources
- Every draft has status `untrusted_external_draft`
- Zero automatic updates committed to active patient health profile

### Step 4: Official HL7 Validator Execution
Run the pinned HL7 Java Validator CLI (`6.9.12`) against generated export Bundles:
```bash
FHIR_VALIDATOR_JAR=/tmp/validator_cli.jar \
  scripts/validation/validate-lifemap-fhir.sh
```
Acceptance criteria:
- Return code: `0`
- Zero schema validation errors
- Zero unauthorized IPS candidate claims

---

## 8. Incident Response & Emergency Procedures

### 8.1 Severity 1: Sandbox Malformed Ingestion Flood or SSRF Probe

**Symptoms:** Spike in 400 Bad Request responses, attempts to provide external URIs in references, or high CPU utilization during JSON parsing.

**Immediate Remediation:**
1. **Engage Ingestion Kill-Switch:**
   Set environment variable across API instances:
   ```bash
   export LIFEMAP_FHIR_IMPORT_ENABLED=false
   ```
   Or update via dynamic admin configuration.
2. **Purge Unverified Quarantined Drafts:**
   Execute database remediation query to remove unconfirmed drafts associated with the compromised vendor client:
   ```sql
   UPDATE universal_capture_drafts
   SET status = 'PURGED_SECURITY_INCIDENT', updated_at = NOW()
   WHERE input_kind = 'fhir_r4_import'
     AND status = 'untrusted_external_draft'
     AND created_at >= NOW() - INTERVAL '2 hours';
   ```
3. **Revoke Client Credentials:**
   Rotate client secret or revoke public key registration in the vendor portal.

### 8.2 Severity 2: Statutory Consent Revocation Failure

**Symptoms:** Export endpoint returns data after user has revoked medical consent in the privacy settings.

**Immediate Remediation:**
1. **Engage Export Kill-Switch:**
   ```bash
   export LIFEMAP_FHIR_EXPORT_ENABLED=false
   ```
2. **Audit Telemetry Logs:**
   Inspect audit events for `lifemap_fhir_r4` to identify any unauthorized data egress.
3. **Notify Privacy Officer:**
   Log incident ticket under Vietnam Personal Data Protection Decree (PDPD 13/2023/ND-CP) protocol.

---

## 9. Rollback Runbook

To roll back a vendor EHR integration release:

1. **Disable Feature Flags:**
   Ensure both `LIFEMAP_FHIR_EXPORT_ENABLED=false` and `LIFEMAP_FHIR_IMPORT_ENABLED=false` are set in configuration.
2. **Downgrade Database Schema (if migration applied):**
   ```bash
   (cd services/api && alembic downgrade -1)
   ```
3. **Invalidate OAuth Leases:**
   Purge cached tokens in Redis:
   ```bash
   redis-cli -u "${REDIS_URL}" KEYS "ehr:token:*" | xargs -r redis-cli -u "${REDIS_URL}" DEL
   ```
4. **Verify Conformance:**
   Confirm endpoint returns 404 or disabled status:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/lifemap/v2/export/fhir-r4
   # Expected: 404 Not Found (when flag disabled)
   ```

---

## 10. Operational Checklist

- [ ] Vendor developer sandbox credentials provisioned and stored in secret manager.
- [ ] Asymmetric private_key_jwt key pair generated and JWKS published.
- [ ] Minimum-necessary scopes verified; write scopes strictly omitted.
- [ ] Ingestion payload size limit verified (1 MB / 500 entries).
- [ ] Narrative XSS sanitization verified with active hostile test vectors.
- [ ] Single-patient matching enforced against authenticated profile ID.
- [ ] Provenance metadata correctly attached to all quarantined drafts.
- [ ] Zero mock data verified in production schemas.
- [ ] Emergency kill-switches tested and operational.
- [ ] Conformance statement validated against `docs/interoperability/lifemap-fhir-r4.md`.
