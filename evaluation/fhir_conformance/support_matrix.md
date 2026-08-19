# FHIR application conformance — supported surface inventory (H-001)

Freeze: `FHIR-CONFORMANCE-V1-20260819` (see `seal/seal.json`).
This inventory answers **H-001: exactly which R4/STU3 resource types and
Bundle forms the product claims supported**. Every claim below is cited to
code or docs; nothing is inferred from intent.

## 1. Claim surfaces

There are **two distinct FHIR surfaces** in this repository. They must not be
conflated:

| Surface | Location | Version | Bundle forms |
| --- | --- | --- | --- |
| **A — LifeMap FHIR R4 projection/import (product API)** | `services/api/src/clara_api/lifemap/fhir_r4.py`, endpoints in `services/api/src/clara_api/api/v1/endpoints/lifemap.py`, docs `docs/interoperability/lifemap-fhir-r4.md` | **R4 4.0.1 only** | export `collection`; import `collection` / `document` |
| **B — GLHS CommitLoop FHIR bench ingestion** | `evaluation/commitloop/fhir_ingest.py`, `fixtures.py` | **STU3 + R4** | `collection` / `transaction` |

Surface A is the production product boundary; it is R4-only and makes no STU3
claim. Surface B is the offline evaluation/GLHS pipeline and is the only place
STU3 is claimed. `GET /api/v1/lifemap/v2/fhir/conformance` states
`general_fhir_server: false` — the product is a purpose-bound projection, not a
FHIR server.

## 2. Surface A — LifeMap FHIR R4 (production API)

Pins (shared with `scripts/validation/validate-lifemap-fhir.sh` via
`docs/interoperability/fhir-toolchain.lock.json`):

- FHIR base: R4 `4.0.1` (`hl7.fhir.r4.core#4.0.1`)
- Validator CLI: `6.9.12`, SHA-256
  `0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6`
- Mapping version: `clara-lifemap-fhir-r4-v1`

### 2.1 Resource types — accepted on import (`SUPPORTED_RESOURCE_TYPES`, `fhir_r4.py:32`)

| # | Resource type | Import accepted | Export emitted |
| --- | --- | --- | --- |
| 1 | `Patient` | yes | yes (exactly one) |
| 2 | `Observation` | yes | yes |
| 3 | `AllergyIntolerance` | yes | yes |
| 4 | `Condition` | yes | yes |
| 5 | `MedicationStatement` | yes | yes |
| 6 | `MedicationRequest` | yes | **no** (never emitted; not a clinician order) |
| 7 | `CarePlan` | yes | yes |
| 8 | `Goal` | yes | yes |
| 9 | `Task` | yes | yes |
| 10 | `QuestionnaireResponse` | yes | yes |
| 11 | `DocumentReference` | yes | yes |
| 12 | `Provenance` | yes (parsed) | yes |
| 13 | `Consent` | yes (parsed) | yes |
| 14 | `AuditEvent` | yes (parsed) | yes |
| 15 | `Composition` | yes (document form only) | **no** |

Notes:

- `Provenance`, `Consent`, `AuditEvent`, `Composition` are accepted by the
  structural gate but **never become health candidates** on import
  (`import_candidates`, `fhir_r4.py:1008`). This is deliberate
  (`docs/interoperability/lifemap-fhir-r4.md`).
- `MedicationRequest` is accepted on import but never exported.

### 2.2 Bundle forms

- Export: `type: collection` only.
- Import: `type: collection` or `type: document`. A `document` bundle must have
  `timestamp`, a full `identifier`, and a `Composition` as the first entry
  (`fhir_r4.py:893-903`). `transaction`, `batch`, `history`, `searchset`,
  `message`, and `subscription-notification` forms are rejected.

### 2.3 Application-semantic contract (import gate, `validate_bundle`)

Rejections enforced by the app (independent of HL7 structural validity):

- exactly one `Patient` per bundle (`exactly_one_patient_required`);
- every reference must resolve inside the bundle (`dangling_reference`) — this
  is what stops cross-subject and external references, including
  `http(s)://`, `//`, and `/_history/` forms (`external_reference_forbidden`);
- only the 15 resource types above (`entry_N_resource_type_unsupported`);
- no unknown top-level elements, no `modifierExtension` / `contained` /
  `implicitRules`, complete codings, UCUM-only quantities, bounded size
  (1 MB / 500 entries / depth 20 / string 20 000), safe narrative.

**Gap recorded (FHIR-02, invalid temporal fields):** the import gate does not
parse or reject invalid temporal values. See
`fixtures/negative/invalid-temporal.json` — HL7 flags it, the CLARA gate
accepts it. This is preserved as evidence, not hidden.

**Replay protection** is endpoint-level via `Idempotency-Key` + digest
(`lifemap.py` import handler, `_begin`/`replay_command`); the pure
`parse_import_bundle` gate is idempotent by design and does not dedupe.

## 3. Surface B — GLHS CommitLoop bench (STU3 + R4)

Pins are code-level in `evaluation/commitloop/fhir_ingest.py`
(`SUPPORTED_FHIR_VERSIONS = {"STU3", "R4"}`). There is **no external
validator pin** for this surface; the HL7 validator is applied to its fixtures
in this package with the same pinned JAR, `-version 3.0.2` for STU3.

| # | Resource type | R4 | STU3 |
| --- | --- | --- | --- |
| 1 | `Patient` | yes (exactly one) | yes (exactly one) |
| 2 | `AllergyIntolerance` | yes | yes |
| 3 | `CarePlan` | yes | yes |
| 4 | `Condition` | yes | yes |
| 5 | `MedicationRequest` | yes | yes |
| 6 | `Observation` | yes | yes |
| 7 | `Procedure` | yes | yes |
| 8 | `ProcedureRequest` | no | yes |
| 9 | `ServiceRequest` | yes | no |

Bundle forms: `collection` / `transaction` (`fhir_ingest.py:110-113`).

Bench application contract: one `Patient` required
(`bundle_must_contain_one_patient`); references must be `Patient/<id>`,
`<id>`, or absent (`cross_subject_reference` otherwise); unsupported resource
types are **silently skipped** (not rejected); temporal mapping is lenient —
`authoredOn`, `issued`, `effectiveDateTime`, `performedDateTime`,
`recordedDate`, `onsetDateTime`, `scheduledDateTime`, and `effectivePeriod` /
`performedPeriod` / `occurrencePeriod` / `scheduledPeriod` / `period` are
accepted, other fields (e.g. STU3 `ProcedureRequest.occurrenceDateTime`) are
not reconstructed.

## 4. Fixture coverage per claimed path (H-003/H-004)

| Claimed path | Positive fixture | Negative fixtures touching it |
| --- | --- | --- |
| A R4 collection export/import (Patient-only golden) | `positive/r4/lifemap-summary-r4.json` (repo fixture) | missing-patient, multiple-patient, wrong-patient-reference, cross-subject-reference, dangling-reference, unsupported-resource, invalid-temporal, provenance-loss, duplicate-replay |
| A R4 collection full export surface (13 emitted types) | `positive/r4/lifemap-full-export-r4.json` (synthetic, mapper-shaped) | — |
| A R4 document import form | `positive/r4/lifemap-document-r4.json` (synthetic) | — |
| A bundle-form scope (transaction rejected by A) | `positive/r4/bench-r4-transaction.json` (bench-accepted, A-rejected by design) | — |
| B R4 bench types incl. `ServiceRequest` | `positive/r4/bench-r4-collection.json` | version-mismatch-stu3-r4 |
| B STU3 bench types incl. `ProcedureRequest` | `positive/stu3/bench-stu3-collection.json` | version-mismatch-stu3-r4 |

Synthetic fixtures are minimal, deterministic, and clearly labelled
`synthetic` in the fixture manifest (`fixtures/manifest.json`); the two
`lifemap-*` R4 fixtures mirror the production mapper's exact output shape.
No real patient data is present anywhere in this package.
