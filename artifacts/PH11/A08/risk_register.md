# Security and Privacy Risk Register — CLARA-Care (PH11 / A08)

**Document Status:** Sealed Audit Baseline · Subagent A08
**Repository Branch:** `phase/ph11-a08`
**Frozen Base Commit SHA:** `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
**Audit Scope Lane:** `docs/security/`, `docs/compliance/`, `scripts/ops/`, `services/api/`, `evaluation/fhir_conformance/`
**Date:** October 2026
**Subject:** FHIR R4 Interoperability Production Profiles, Official HL7 Validator Conformance, Patient Identification/De-Identification, and Security Boundaries.

---

## 1. Executive Summary

As part of Phase PH11 (Subagent A08: Security + Privacy), an exhaustive security, privacy, and regulatory audit was conducted on CLARA-Care's HL7 FHIR Release 4 (R4 4.0.1) interoperability architecture.

The review evaluated nine specific risk vectors:
1. **Official Validator Conformance Alignment:** Conformance of CLARA summary exports and imports against the official HL7 Java Validator CLI (v6.9.12, pinned SHA-256 `0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6`).
2. **Denial of Service & Bounded Execution:** Payload size, entry counts, AST nesting depth, and string buffer limits.
3. **Dangerous FHIR Constructs:** Strict fail-closed rejection of `modifierExtension`, `contained` sub-resources, and `implicitRules`.
4. **Reference Sandboxing & Anti-SSRF:** Complete intra-bundle reference resolution and prohibition of external URIs (`http(s)://`, `//`, `_history/`).
5. **Single-Patient Boundary & Cross-Subject Isolation:** Enforcement of exactly one `Patient` resource per bundle and intra-bundle subject binding.
6. **Patient De-Identification & Vietnamese Artifact Stripping:** Deterministic UUIDv5 pseudonymization and redacting statutory national IDs (CCCD, BHYT, BHXH, Sổ khám bệnh).
7. **Quarantine Staging & Non-Auto-Confirmation:** Ensuring imported resources remain untrusted drafts (`untrusted_external_draft`) and never auto-commit to clinical truth or execute prescriptions.
8. **Safe Narrative & Anti-XSS Sanitization:** XHTML narrative element and attribute allowlisting.
9. **Regulatory Harmonization:** Decree 13/2023/NĐ-CP (PDPD), Circular 46/2018/TT-BYT (EMR), Circular 54/2017/TT-BYT, and Law 15/2023/QH15.

All core security boundaries were verified via automated operational auditing (`scripts/ops/audit_fhir_validator_conformance.py`), contract tests, and gate suites with zero critical regressions.

---

## 2. Risk Matrix & Severity Definitions

| Severity | Definition | Operational Action Required |
|:---|:---|:---|
| **CRITICAL** | Direct PHI exposure, cross-patient data pollution, autonomous medical prescription/dosage injection, or SSRF vulnerability. | Immediate architectural block; release gate halted. |
| **HIGH** | Insecure interoperability boundary, unbounded memory/CPU parsing DoS, missing feature flag gating, or unredacted statutory identifiers. | Mandatory mitigation prior to production deployment. |
| **MEDIUM** | Inconsistent temporal parsing, lack of localized terminology binding, or fail-open auxiliary validation behavior. | Prioritize in hardening sprint with compensating controls. |
| **LOW / INFO** | Informational terminology mapping discrepancies, documentation gaps, or candidate profile notices. | Tracked in operational backlog. |

---

## 3. Comprehensive FHIR R4 Risk Inventory

| Risk ID | Category | Title | Severity | Likelihood | Impact | Status | Mitigating Architectural Control |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **SEC-FHIR-01** | Boundary / DoS | Oversized Bundle & AST Nesting Attack | **HIGH** | Medium | High | **Mitigated** | Bounded gate: 1 MB payload, 500 entries, depth 20, string 20k (`fhir_r4.py:27-30`). |
| **SEC-FHIR-02** | Clinical / Safety | Semantic Meaning Inversion via `modifierExtension` | **CRITICAL**| Low | Critical | **Mitigated** | Strict fail-closed rejection of `modifierExtension` with HTTP 422 (`fhir_r4.py:938`). |
| **SEC-FHIR-03** | Injection / Bypass | Hidden Sub-Payload via `contained` Resources | **HIGH** | Medium | High | **Mitigated** | Rejection of any resource with `contained` key (`fhir_r4.py:938`). |
| **SEC-FHIR-04** | Security / SSRF | Outbound Socket SSRF via External Reference URI | **CRITICAL**| Medium | Severe | **Mitigated** | Rejection of `http(s)://`, `//`, `_history/` references; zero outbound calls (`fhir_r4.py:957`). |
| **SEC-FHIR-05** | Integrity / Safety | Cross-Patient Contamination in Multi-Patient Bundle | **CRITICAL**| Medium | Critical | **Mitigated** | Single-patient invariant (`exactly_one_patient_required`); relative closure (`fhir_r4.py:771`). |
| **SEC-FHIR-06** | Privacy / PDPD | Statutory National ID (CCCD/BHYT) Leakage on Export | **HIGH** | Low | High | **Mitigated** | Stripping of CCCD/CMND; deterministic UUIDv5 pseudonymization (`fhir_r4.py:365`). |
| **SEC-FHIR-07** | Clinical / Legal | Autonomous Health Truth or Prescription Injection | **CRITICAL**| Low | Critical | **Mitigated** | Staged solely as `untrusted_external_draft`; `MedicationRequest` quarantined (`fhir_r4.py:1008`). |
| **SEC-FHIR-08** | Web / XSS | Malicious XHTML Narrative Injection (`Resource.text.div`) | **MEDIUM** | Medium | Medium | **Mitigated** | XML/HTML sanitization stripping scripts, applets, and event handlers (`fhir_r4.py:953`). |
| **SEC-FHIR-09** | Integrity / Concurrency | Ingestion Duplicate Replay & Desynchronization | **MEDIUM** | High | Medium | **Mitigated** | Mandatory `Idempotency-Key` + SHA-256 raw bundle digest check (`lifemap.py:3041`). |
| **SEC-FHIR-GAP-01** | Semantic / Temporal | Lenient Temporal Format Verification in Semantic Gate | **MEDIUM** | High | Low | **Accepted** | Documented gap (FHIR-02); verified by secondary official HL7 validator pass. |
| **SEC-FHIR-GAP-02** | Regulatory / IPS | Uncertified IPS Profile Export Claims | **MEDIUM** | Low | Medium | **Mitigated** | `GET /v2/export/ips` unconditionally returns HTTP 409 (`lifemap.py:2999`). |

---

## 4. Detailed Risk Assessments & Verified Anchors

### 4.1 SEC-FHIR-02: Semantic Meaning Inversion via `modifierExtension`
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/fhir_r4.py:938-939`
  - `evaluation/fhir_conformance/app_semantic.py:87`
  - `evaluation/fhir_conformance/fixtures/negative/unsupported-resource.json`
- **Mechanism & Attack Vector:**
  FHIR specifies that if a resource contains a `modifierExtension`, the reading system cannot ignore it because it may negate or fundamentally alter the meaning of the resource (e.g., changing an allergy to "not allergic" or specifying that a condition is ruled out). An attacker injecting a `modifierExtension` into an imported bundle could deceive clinical systems if unhandled.
- **Architectural Mitigation:**
  CLARA enforces a zero-tolerance policy. Any entry containing `"modifierExtension"` is immediately rejected with HTTP 422 (`entry_N_unsafe_modifier_or_contained`). No fallback heuristic is permitted.
- **Residual Risk:** Negligible. Verified in positive/negative test suites.

---

### 4.2 SEC-FHIR-04: Outbound Socket SSRF via External Reference URI
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/fhir_r4.py:955-962`
  - `services/api/src/clara_api/lifemap/fhir_r4.py:850-860`
  - `evaluation/fhir_conformance/fixtures/negative/dangling-reference.json`
- **Mechanism & Attack Vector:**
  External EMR systems often output absolute URLs in `Reference.reference` (e.g., `https://hospital.vn/fhir/Patient/100`). An attacker could supply internal loopback URLs (`http://127.0.0.1:8000/internal`, `http://169.254.169.254/latest/meta-data`) to trigger Server-Side Request Forgery or cloud metadata exfiltration during reference parsing.
- **Architectural Mitigation:**
  CLARA's parser inspects every `.reference` and `.url` property. Any string beginning with `http://`, `https://`, `//`, or containing `/_history/` is rejected with HTTP 422 (`external_reference_forbidden`). The FHIR engine performs zero outbound network socket operations.
- **Residual Risk:** Negligible. Verified by automated auditor and fixture tests.

---

### 4.3 SEC-FHIR-05: Cross-Patient Contamination in Multi-Patient Bundle
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/fhir_r4.py:771-778`
  - `services/api/src/clara_api/lifemap/fhir_r4.py:848-872`
  - `evaluation/fhir_conformance/fixtures/negative/multiple-patient.json`
  - `evaluation/fhir_conformance/fixtures/negative/cross-subject-reference.json`
- **Mechanism & Attack Vector:**
  Batch exports from clinic databases often mix multiple patients in a single transaction. If imported into a user's personal health profile, another person's laboratory results, medications, or diagnoses would pollute the user's LifeMap, presenting a direct risk to clinical safety.
- **Architectural Mitigation:**
  1. The validator enforces `len(patients) == 1` (`exactly_one_patient_required`).
  2. Every clinical resource (`Observation`, `Condition`, `MedicationStatement`, etc.) MUST explicitly bind its subject reference to the single bundle patient. Cross-subject references fail closed with HTTP 422.
- **Residual Risk:** Negligible.

---

### 4.4 SEC-FHIR-07: Autonomous Health Truth or Prescription Injection
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `services/api/src/clara_api/lifemap/fhir_r4.py:1008-1025`
  - `services/api/src/clara_api/api/v1/endpoints/lifemap.py:3035-3060`
  - `docs/interoperability/lifemap-fhir-r4.md:17-19`
- **Mechanism & Attack Vector:**
  If an imported FHIR resource could automatically transition to "confirmed" truth state, an attacker or compromised integration partner could inject false prescriptions, alter allergies, or fabricate medical emergencies without patient or clinician knowledge.
- **Architectural Mitigation:**
  Imported candidates are staged solely into `LifeMapCaptureCandidate` as `untrusted_external_draft`. They never bypass the Universal Capture review inbox. `MedicationRequest` resources are quarantined as informational drafts and cannot trigger drug dispensing or active prescription state.
- **Residual Risk:** Negligible.

---

### 4.5 SEC-FHIR-GAP-01: Lenient Temporal Format Verification in Semantic Gate
- **Severity:** **MEDIUM** (Accepted Operational Gap)
- **Affected Anchors:**
  - `evaluation/fhir_conformance/support_matrix.md:83-87`
  - `evaluation/fhir_conformance/fixtures/negative/invalid-temporal.json`
- **Finding Description:**
  The pure Python application-semantic gate (`validate_bundle`) validates that date/time strings conform to general string bounds, but does not strictly reject semantically invalid calendar values (such as month 13 or leap-day anomalies in non-leap years). The official HL7 Java validator correctly flags these as schema errors.
- **Compensating Controls:**
  The staging queue treats all incoming dates as draft values; downstream clinical parsing validates dates before active timeline projection.
- **Remediation Plan:**
  Integrate strict ISO 8601 calendar regex and calendar math into `fhir_r4.py` in Phase PH24.

---

## 5. Security & Privacy Release Checklist

- [x] Official HL7 Java Validator CLI pinned to v6.9.12 with SHA-256 verified in `docs/interoperability/fhir-toolchain.lock.json`.
- [x] Payload size (1 MB), entry count (500), depth (20), and string length (20,000) bounds enforced in `fhir_r4.py`.
- [x] Fail-closed rejection of `modifierExtension`, `contained`, and `implicitRules` verified by automated auditor.
- [x] Single-patient boundary and anti-SSRF relative reference resolution verified by positive/negative fixture suites.
- [x] Export endpoints gate behind `lifemap_fhir_export_enabled` and require affirmative medical disclaimer consent.
- [x] Export responses emit `Cache-Control: no-store` and `X-CLARA-Conformance: fhir-r4-summary-not-ips`.
- [x] Import endpoint requires `Idempotency-Key` and checks SHA-256 `bundle_digest` replay cache.
- [x] Imported resources staged exclusively as `untrusted_external_draft` in Universal Capture.
- [x] Uncertified IPS export endpoint fails closed with HTTP 409 (`ips_conformance_not_approved`).
- [x] Zero real patient data or unredacted secrets present in test fixtures or manifests.
