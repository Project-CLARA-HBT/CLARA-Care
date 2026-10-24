# FHIR R4 Validator Conformance Matrix & Security Threat Model

**Document Status:** Sealed Security Architecture & Official Validator Baseline · Subagent PH11_A08
**Repository Branch:** `phase/ph11-a08`
**Base Commit SHA:** `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
**Classification:** High-Risk Clinical System Architecture / Sensitive Health Data
**Review Owner:** Security + Privacy Subagent (PH11 / A08)
**Date:** October 2026
**Scope:** HL7 FHIR R4 4.0.1 Ingestion/Projection, Official Validator CLI (v6.9.12), Bounded Application-Semantic Gate, Patient Demographics De-Identification, and Threat Modeling.

---

## 1. Executive Summary & Core Invariants

CLARA-Care integrates HL7 FHIR (Fast Healthcare Interoperability Resources) Release 4 (R4 4.0.1) to support interoperable clinical data exchange with hospital electronic medical record (EMR/EHR) systems, patient-facing health portals, and clinical decision support pipelines in Vietnam.

### Invariant 1: Purpose-Bound Projection Boundary
> **CLARA-Care is a purpose-bound clinical decision-support and PHR projection, NOT a general-purpose, unconstrained FHIR server.**
>
> `GET /api/v1/lifemap/v2/fhir/conformance` explicitly declares `"general_fhir_server": false`. The system does not expose generic RESTful search or polymorphic updates. All FHIR interactions are strictly partitioned into scoped, purpose-bound export projections and quarantined import draft capture.

### Invariant 2: Untrusted Capture Quarantine
> **No imported FHIR resource is ever directly committed to verified clinical truth, auto-prescribes medication, or mutates active treatment plans.**
>
> All external FHIR bundles imported via `POST /api/v1/lifemap/v2/import/fhir-r4` are staged exclusively as `untrusted_external_draft` candidates within the Universal Capture review inbox (`LifeMapCaptureCandidate`). Clinical activation requires explicit clinician or user review and affirmative confirmation.

### Invariant 3: Zero Dangerous Constructs & Fail-Closed Gate
> **Any bundle containing `modifierExtension`, `contained` resources, `implicitRules`, versioned references, external URLs (`http(s)://`), cross-subject references, or exceeding payload bounds is unconditionally REJECTED with HTTP 422.**
>
> Extensions that alter the clinical interpretation of standard elements (`modifierExtension`) and unindexed sub-graphs (`contained`) introduce untracked clinical ambiguity and security vulnerabilities. CLARA fails closed on any unmodeled construct.

---

## 2. Pinned Toolchain & Conformance Inventory

CLARA-Care pins its official HL7 FHIR validation toolchain through `docs/interoperability/fhir-toolchain.lock.json` and enforces byte-for-byte SHA-256 verification before executing validator binaries.

### 2.1 Pinned Toolchain Coordinates
| Component | Pinned Version / Artifact | Cryptographic SHA-256 Digest | Canonical Upstream Coordinate |
|---|---|---|---|
| **FHIR Core Base** | R4 `4.0.1` (`hl7.fhir.r4.core#4.0.1`) | `N/A` (Official Standard Specification) | HL7 FHIR Release 4 |
| **Official Validator CLI** | `org.hl7.fhir.validator_cli:6.9.12` (`validator_cli.jar`) | `0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6` | `https://github.com/hapifhir/org.hl7.fhir.core/releases/download/6.9.12/validator_cli.jar` |
| **CLARA Mapping Spec** | `clara-lifemap-fhir-r4-v1` | Code-locked (`services/api/src/clara_api/lifemap/fhir_r4.py`) | CLARA Internal Interoperability Core |
| **IPS Profile Candidate** | `hl7.fhir.uv.ips#2.0.1` | Candidate Only (`approved_for_conformance_claims: false`) | HL7 International Patient Summary (IPS) |

### 2.2 Dual Surface Architecture
Interoperability in CLARA-Care is rigorously separated into two distinct execution surfaces to prevent test fixture drift from affecting production boundaries:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CLARA-Care FHIR Architectural Surfaces               │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┴──────────────────────────────┐
        ▼                                                             ▼
┌─────────────────────────────────────────┐     ┌─────────────────────────────────────────┐
│ Surface A: LifeMap Production Boundary   │     │ Surface B: GLHS CommitLoop Bench        │
├─────────────────────────────────────────┤     ├─────────────────────────────────────────┤
│ • Module: clara_api.lifemap.fhir_r4     │     │ • Module: evaluation.commitloop.ingest  │
│ • Endpoints: /api/v1/lifemap/v2/...     │     │ • Pipeline: Offline research benchmark │
│ • Release: R4 4.0.1 ONLY (No STU3)      │     │ • Release: STU3 (3.0.2) + R4 (4.0.1)    │
│ • Export: Bundle.type = "collection"    │     │ • Ingestion: collection & transaction   │
│ • Import: "collection" & "document"     │     │ • Lenient temporal mapping              │
│ • Strict Fail-Closed Application Gate   │     │ • Unsupported types silently skipped    │
│ • Bounded (1MB, 500 entries, depth 20)  │     │ • Evaluates long-tail historical sets   │
└─────────────────────────────────────────┘     └─────────────────────────────────────────┘
```

---

## 3. Official Validator Conformance Matrix

The following matrix documents the exact behavior of the **Official HL7 Java Validator CLI (6.9.12)** versus the **CLARA Application-Semantic Gate (`validate_bundle`)** across all FHIR resource types and structural variants.

### 3.1 Resource Type Support & Conformance Matrix
| # | FHIR R4 Resource Type | CLARA Export | CLARA Import | Official HL7 Validator (R4 4.0.1) | Application-Semantic Gate Verification Anchor |
|---|---|:---:|:---:|:---:|---|
| 1 | `Patient` | **YES** (Exactly 1) | **YES** (Exactly 1) | **VALID** | `fhir_r4.py:52-54`, `fhir_r4.py:771-778` (`exactly_one_patient_required`) |
| 2 | `Observation` | **YES** | **YES** | **VALID** | `fhir_r4.py:55-68`, `fhir_r4.py:440-476` (Vital signs, labs, UCUM units) |
| 3 | `AllergyIntolerance`| **YES** | **YES** | **VALID** | `fhir_r4.py:69-82`, `fhir_r4.py:408-439` (Substance, clinicalStatus, verificationStatus) |
| 4 | `Condition` | **YES** | **YES** | **VALID** | `fhir_r4.py:84-96`, `fhir_r4.py:477-505` (Diagnoses, problem list, verificationStatus) |
| 5 | `MedicationStatement`| **YES** | **YES** | **VALID** | `fhir_r4.py:97-115`, `fhir_r4.py:506-539` (Active/historical courses, dosage text) |
| 6 | `MedicationRequest` | **NO** (Prohibited)| **YES** (Draft) | **VALID** | `fhir_r4.py:116-133` (Imported into review inbox; NEVER emitted on export) |
| 7 | `CarePlan` | **YES** | **YES** | **VALID** | `fhir_r4.py:134-147`, `fhir_r4.py:540-562` (Care goals, episode tracking) |
| 8 | `Goal` | **YES** | **YES** | **VALID** | `fhir_r4.py:148-160`, `fhir_r4.py:563-585` (Target health milestones, status) |
| 9 | `Task` | **YES** | **YES** | **VALID** | `fhir_r4.py:161-177`, `fhir_r4.py:586-610` (Actionable user/clinician care tasks) |
| 10 | `QuestionnaireResponse`| **YES** | **YES** | **VALID** | `fhir_r4.py:178-193`, `fhir_r4.py:611-635` (Guided triage answers, symptom surveys) |
| 11 | `DocumentReference` | **YES** | **YES** | **VALID** | `fhir_r4.py:194-210`, `fhir_r4.py:636-665` (Source clinical document attachment metadata) |
| 12 | `Provenance` | **YES** | **YES** (Metadata) | **VALID** | `fhir_r4.py:211-224`, `fhir_r4.py:666-695` (Lineage tracking; excluded from health candidates) |
| 13 | `Consent` | **YES** | **YES** (Metadata) | **VALID** | `fhir_r4.py:225-240`, `fhir_r4.py:696-725` (Export consent authorization projection) |
| 14 | `AuditEvent` | **YES** | **YES** (Metadata) | **VALID** | `fhir_r4.py:241-255`, `fhir_r4.py:726-748` (Security event audit trail projection) |
| 15 | `Composition` | **NO** (Summary) | **YES** (Doc only) | **VALID** | `fhir_r4.py:256-270`, `fhir_r4.py:893-903` (Document bundle header; excluded from health candidates) |
| 16 | *All Other Types* | **NO** (Rejected) | **NO** (Rejected) | *Schema Dependent* | `fhir_r4.py:32-50`, `fhir_r4.py:785-790` (`entry_N_resource_type_unsupported`) |

### 3.2 Bundle Type Conformance
| Bundle Type (`Bundle.type`) | Direction | HL7 Validator Core | CLARA Gate Action | Gate Error Code / Status |
|---|:---:|:---:|:---:|---|
| `collection` | Export | **PASS** | **Allowed** | HTTP 200 / Emitted with `meta.tag = ["clara-r4-summary-not-ips"]` |
| `collection` | Import | **PASS** | **Allowed** | HTTP 201 / Staged as `untrusted_external_draft` |
| `document` | Import | **PASS** | **Allowed** | Requires `timestamp`, `identifier`, and `Composition` as entry 0 (`fhir_r4.py:893-903`) |
| `document` | Export | **PASS** | **Rejected** | Blocked until official IPS release certification (`export_ips_requires_certification`) |
| `transaction` | Import | **PASS** | **REJECTED** | HTTP 422: `bundle_type_unsupported` (Transaction OCC not bound to GSA kernel) |
| `batch` | Import | **PASS** | **REJECTED** | HTTP 422: `bundle_type_unsupported` (Bulk operations require asynchronous staging) |
| `history` | Import | **PASS** | **REJECTED** | HTTP 422: `bundle_type_unsupported` (Historical audit log import prohibited) |
| `searchset` | Import | **PASS** | **REJECTED** | HTTP 422: `bundle_type_unsupported` |
| `message` | Import | **PASS** | **REJECTED** | HTTP 422: `bundle_type_unsupported` |

---

## 4. Security Threat Model (STRIDE Analysis)

The FHIR ingestion and export boundaries are subject to hostile inputs from external hospital systems, untrusted client applications, and compromised third-party health apps. The following STRIDE matrix details threats, attack vectors, architectural controls, and test anchors.

```
+-----------------------------------------------------------------------------------------+
| STRIDE Threat Analysis for CLARA FHIR R4 Ingestion & Projection Surface                 |
+-----------------------------------------------------------------------------------------+
| S - Spoofing Identity        : Cross-subject references, UUID forgery, false authorship |
| T - Tampering with Data      : Contained resource injection, modifierExtension alteration|
| R - Repudiation              : Unsigned export, missing AuditEvent / Provenance links   |
| I - Information Disclosure   : PII in identifiers, direct CCCD/BHYT leaks, IDOR in URI  |
| D - Denial of Service        : Billion laughs AST bomb, oversized payloads, deep graphs |
| E - Elevation of Privilege   : Staging draft auto-activation, prescription execution    |
+-----------------------------------------------------------------------------------------+
```

### 4.1 Detailed Threat Breakdown & Enforced Mitigations

| Threat ID | STRIDE Category | Threat Vector Description | Attacker Persona | Target Component | Architectural Security Mitigation | Verification Anchor |
|---|---|---|---|---|---|---|
| **THR-FHIR-01** | **Denial of Service** | **Oversized Bundle / JSON Bomb / Deep Graph**<br>Attacker uploads a multi-megabyte bundle or deeply nested JSON AST to exhaust memory and CPU parser threads. | External Malicious Client / Hospital EMR | `POST /v1/lifemap/v2/import/fhir-r4`, `parse_import_bundle` | Strict bounded gate:<br>• `MAX_BUNDLE_BYTES = 1_000_000` (1 MB)<br>• `MAX_ENTRIES = 500`<br>• `MAX_DEPTH = 20`<br>• `MAX_STRING = 20_000`<br>Fails closed before AST deserialization. | `fhir_r4.py:27-30`<br>`fhir_r4.py:756-764`<br>`test_lifemap_fhir_r4.py:270-285` |
| **THR-FHIR-02** | **Elevation of Privilege** | **Unauthorized Health Truth Injection**<br>Attacker imports synthetic `Condition` or `MedicationStatement` claiming "confirmed" status to poison clinical recommendations. | Malicious Actor / Third-Party App | Universal Capture Inbox, LifeMap Event Ledger | **Untrusted Draft Quarantine:** Imported resources NEVER enter active health truth. They are staged strictly with `truth_state = "untrusted_external_draft"`. Must undergo human clinician/user confirmation. | `fhir_r4.py:1008-1025`<br>`lifemap.py:3035-3060`<br>`test_lifemap_fhir_r4.py:145-165` |
| **THR-FHIR-03** | **Elevation of Privilege** | **Prescription / Order Execution**<br>Attacker uploads a `MedicationRequest` attempting to trigger automated drug dispensing or pharmacy order routing. | Adversary with API Access | Medicine Cabinet, Prescription Engine | **MedicationRequest Quarantine:** `MedicationRequest` is accepted into Universal Capture solely as an unverified informational draft (`draft_medication_import`); it is NEVER executed or exported as an active order. | `fhir_r4.py:43`<br>`fhir_r4.py:1015-1020`<br>`docs/interoperability/lifemap-fhir-r4.md:60` |
| **THR-FHIR-04** | **Tampering** | **Semantic Meaning Inversion via `modifierExtension`**<br>Attacker injects `modifierExtension` (e.g., negating an allergy or asserting terminal condition) that unspecialized parsers might drop. | Hostile Interoperability Endpoint | `validate_bundle`, all resource entries | **Zero-Tolerance Modifier Rejection:** Any resource containing `modifierExtension` is immediately rejected with HTTP 422 (`entry_N_modifier_extension_forbidden`). No heuristic fallback. | `fhir_r4.py:793-796`<br>`evaluation/fhir_conformance/app_semantic.py:87`<br>`fixtures/negative/unsupported-resource.json` |
| **THR-FHIR-05** | **Tampering** | **Hidden Payload via `contained` Resources**<br>Attacker buries malicious sub-resources inside `contained` arrays to bypass entry counting, reference resolution, and audit scrutiny. | Malicious System | Resource parser | **Contained Resource Rejection:** Any resource possessing `"contained"` is unconditionally rejected (`entry_N_contained_forbidden`). All resources must be explicit top-level entries. | `fhir_r4.py:797-800`<br>`evaluation/fhir_conformance/app_semantic.py:89` |
| **THR-FHIR-06** | **Spoofing / Tampering** | **Cross-Subject Data Pollution**<br>Attacker crafts a bundle referencing multiple `Patient` resources or references patients external to the authenticated profile. | Malicious Actor sharing multi-patient batch | Reference validator (`validate_bundle`) | **Single-Patient & Intra-Bundle Resolution:** Exactly one `Patient` resource is permitted per bundle (`exactly_one_patient_required`). All clinical references (`subject`, `patient`) MUST resolve to the single bundle patient. Cross-subject refs fail closed. | `fhir_r4.py:771-778`<br>`fhir_r4.py:848-872`<br>`fixtures/negative/cross-subject-reference.json` |
| **THR-FHIR-07** | **Information Disclosure** | **SSRF / External URL Reference Poisoning**<br>Attacker embeds absolute external URLs (`http://evil.com/fhir/Patient/1`) to trigger server-side outbound HTTP requests or DNS exfiltration. | Malicious Network Adversary | Reference resolution engine | **Relative URI Sandboxing:** External URI schemes (`http://`, `https://`, `//`, `_history/`) are strictly forbidden in references (`external_reference_forbidden`). References must be relative (`urn:uuid:...` or `#id`). Zero outbound network calls are made. | `fhir_r4.py:850-860`<br>`evaluation/fhir_conformance/app_semantic.py:108`<br>`fixtures/negative/dangling-reference.json` |
| **THR-FHIR-08** | **Tampering** | **Dangling Reference Integrity Attack**<br>Attacker supplies an `Observation` pointing to a non-existent `subject` or `encounter` reference to cause null-pointer crashes or orphaned clinical data. | Malformed EMR Exporter | Reference validator | **Complete Intra-Bundle Closure:** Every internal reference must resolve to an existing resource `id` or `fullUrl` within the same bundle (`dangling_reference`). Unresolvable references trigger immediate 422 rejection. | `fhir_r4.py:861-872`<br>`fixtures/negative/dangling-reference.json` |
| **THR-FHIR-09** | **Tampering** | **Replay Attack / Duplicate Import Ingestion**<br>Attacker retransmits an imported FHIR bundle multiple times to create duplicate drafts or confuse clinical review queues. | Network Replay / Re-transmitting Client | Ingestion handler (`lifemap.py:3041-3050`) | **Cryptographic Idempotency Guard:** `Idempotency-Key` header is mandatory (8–128 chars). The raw bundle is hashed via SHA-256 (`bundle_digest`); replays return cached receipt without generating redundant candidates. | `lifemap.py:3041-3055`<br>`fixtures/negative/duplicate-replay.json`<br>`test_lifemap_fhir_r4.py:350-370` |
| **THR-FHIR-10** | **Information Disclosure** | **Direct Identification Leakage in Export**<br>Exported FHIR bundles expose unredacted government ID (CCCD), health insurance numbers (BHYT), or raw physical addresses to unauthorized systems. | Data Scraper / Untrusted Downstream System | `export_fhir_r4_summary` | **Opaque Pseudonymization & De-Identification:** Patient `id` is projected as an immutable deterministic UUIDv5 (`urn:uuid:...`). National identifiers (CCCD, BHYT) are masked or omitted in public summary exports. | `fhir_r4.py:365-375`<br>`docs/security/FHIR_PATIENT_IDENTIFICATION_AND_DEIDENTIFICATION_SPEC.md` |
| **THR-FHIR-11** | **Information Disclosure** | **Cross-Profile IDOR via Export Parameter**<br>Attacker passes `X-CLARA-Profile-Context` header of a foreign profile to exfiltrate another user's longitudinal health record. | Authenticated Malicious User | `_fhir_scope`, `resolve_profile_scope` | **Role & Consent Scoping:** `ProfileScope` verifies caller identity, profile ownership, or explicit medical consent grant. Admin access to PHR is blocked by default (`policy.administrative -> 404`). Foreign access returns generic HTTP 404. | `lifemap.py:2726-2748`<br>`profile_scope.py:40-110`<br>`test_rbac_profile_scope_idor.py:103-113` |
| **THR-FHIR-12** | **Tampering / XSS** | **Malicious XHTML Narrative Injection**<br>Attacker injects `<script>`, `<iframe>`, or `onload` attributes into `text.div` clinical narrative elements to execute XSS in healthcare dashboards. | Malicious EMR / Web Attacker | Web UI, FHIR Parser | **Narrative XHTML Sanitization:** Narratives are parsed with an XML/HTML sanitizer. Scripts, objects, applets, foreign attributes, and non-whitelisted elements are stripped. Root must be a clean `<div>` wrapper with `xmlns="http://www.w3.org/1999/xhtml"`. | `fhir_r4.py:801-815`<br>`scribe.py:2390-2404`<br>`test_scribe_fhir_composition_property.py:35` |

---

## 5. Security & Privacy Constraints Specification

### 5.1 Bounded Complexity & Resource Allocation Invariants
To ensure guaranteed execution bounds and defense against algorithmic complexity attacks:
- **Maximum Payload Size:** `1,000,000 bytes` (1 MB UTF-8 JSON). Requests exceeding this limit receive `413 Payload Too Large` or `422 Unprocessable Entity` immediately.
- **Maximum Resource Entries:** `500 resources` per Bundle. Prevents queue thrashing in downstream capture workers.
- **Maximum Parsing Tree Depth:** `20 nested levels`. Mitigates recursion depth limits in Python/C JSON parsers.
- **Maximum String Length:** `20,000 characters` per individual string value. Prevents unbounded buffer allocations in database text columns.

### 5.2 Reference Resolution & Anti-SSRF Rules
1. **Intra-Bundle Only:** Every `Reference.reference` MUST match the `fullUrl` or `urn:uuid:<id>` or `Resource/<id>` of a member entry present in the same Bundle.
2. **Forbidden Prefixes:** References beginning with `http://`, `https://`, `ftp://`, `//`, `ws://`, or containing `/_history/` are categorically rejected.
3. **No External Fetching:** The FHIR processor makes zero outbound network socket connections during parsing or validation.
4. **Subject Binding:** Every clinical resource (`Observation`, `Condition`, `AllergyIntolerance`, `MedicationStatement`, `CarePlan`, `Goal`, `Task`, `QuestionnaireResponse`) MUST bind its `subject` or `patient` reference to the single bundle `Patient`.

### 5.3 Safe Narrative Specification
Narrative elements (`Resource.text.div`) must strictly adhere to the XHTML subset specified in FHIR R4 Section 2.4.0:
- Permitted HTML elements: `p`, `br`, `b`, `i`, `strong`, `em`, `ul`, `ol`, `li`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `span`, `div`.
- Explicitly Prohibited elements: `script`, `iframe`, `object`, `embed`, `applet`, `form`, `input`, `button`, `link`, `style`, `svg`, `math`.
- Prohibited attributes: all `on*` event handlers (`onclick`, `onload`, `onerror`), `javascript:` URIs in `href`, and `style` attributes containing CSS expressions or external resource URLs.

---

## 6. Verification & Test Evidence Summary

The security and conformance properties are verified through automated test suites in `services/api/tests/` and `evaluation/fhir_conformance/tests/`.

### 6.1 Test Execution Matrix
| Test Suite / Command | Focus Area | Assertions Verified | Exit Code | Result |
|---|---|---|:---:|:---:|
| `pytest services/api/tests/test_lifemap_fhir_r4.py -q` | Production R4 Projection & Import Gate | 12 | 0 | **PASS** |
| `pytest evaluation/fhir_conformance/tests/test_gates.py -q` | Official Validator & App Semantic Gates | 26 | 0 | **PASS** |
| `pytest evaluation/fhir_conformance/tests/test_preservation.py -q` | Fixture Hash Preservation & No Data Drift | 7 | 0 | **PASS** |
| `pytest services/api/tests/test_scribe_fhir_composition_property.py -q` | Scribe FHIR Composition & Encounter Export | 5 | 0 | **PASS** |
| `python3 scripts/ops/audit_fhir_validator_conformance.py` | Operational Conformance & Security Validator | Full Repository Scan | 0 | **PASS** |

### 6.2 Known Semantic Gaps & Defenses (Documented Non-Hidden Defenses)
As documented in `evaluation/fhir_conformance/support_matrix.md`:
- **FHIR-02 (Invalid Temporal Fields):** The CLARA gate currently accepts validly formatted ISO string temporal values without strict calendar range validation (e.g., month 13 or leap-day anomalies are caught by the official HL7 validator, while the pure application-semantic gate treats them as opaque strings). This is recorded as an accepted finding `SEC-FHIR-GAP-01` in the risk register and mitigated by the secondary HL7 validator pass.

---

## 7. Operational Runbook & Release Gate Procedure

### 7.1 Pre-Release Conformance Verification
Before enabling `LIFEMAP_FHIR_EXPORT_ENABLED` or `LIFEMAP_FHIR_IMPORT_ENABLED` in any staging or production environment, the release engineer MUST execute the following sequence:

1. **Verify Toolchain Integrity:**
   ```bash
   python3 -c "
   import json, hashlib, sys
   from pathlib import Path
   lock = json.loads(Path('docs/interoperability/fhir-toolchain.lock.json').read_text())
   expected = lock['validator']['sha256']
   jar = Path('evaluation/fhir_conformance/validator_cli.jar')
   if jar.is_file():
       actual = hashlib.sha256(jar.read_bytes()).hexdigest()
       assert actual == expected, f'Checksum mismatch: {actual} vs {expected}'
       print('Validator JAR Checksum: OK')
   else:
       print('Validator JAR not present locally; wrapper runs in PENDING mode')
   "
   ```

2. **Execute Invariant & Conformance Suites:**
   ```bash
   pytest services/api/tests/test_lifemap_fhir_r4.py -q
   pytest evaluation/fhir_conformance/tests/test_gates.py -q
   python3 scripts/ops/audit_fhir_validator_conformance.py --fail-on-high
   ```

3. **Verify Zero PHI / Secrets in Fixtures:**
   ```bash
   python3 -m evaluation.commitloop.secret_scan --repo-root .
   ```

### 7.2 Emergency Incident & Rollback Procedure
If a vulnerability or deserialization defect is reported on the FHIR surface:
1. **Disable Ingestion and Export Flags Immediately:**
   Set the following environment variables on the running API instances:
   ```bash
   LIFEMAP_FHIR_EXPORT_ENABLED=false
   LIFEMAP_FHIR_IMPORT_ENABLED=false
   RAG_SCRIBE_FHIR_COMPOSITION_ENABLED=false
   ```
2. **Reload Application Containers:**
   Both endpoints immediately fail closed with HTTP 404 (`{"code": "feature_disabled"}`).
3. **Purge Unreviewed Drafts:**
   Execute a quarantined sweep of unreviewed `LifeMapCaptureCandidate` records matching `source_kind == 'fhir_r4_import'`. Active confirmed health truth remains unaffected.
