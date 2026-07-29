# LifeMap FHIR R4 interoperability boundary

Status: implemented behind default-off flags; FHIR R4 base validation passes;
IPS conformance and terminology licensing are not approved.

## Contract

CLARA keeps its typed LifeMap model as the source of truth and exposes a
purpose-bound projection. It is not a general FHIR server. The export is a
FHIR R4 `collection` Bundle tagged `clara-r4-summary-not-ips`.

- `GET /api/v1/lifemap/v2/fhir/conformance` describes the exact boundary.
- `GET /api/v1/lifemap/v2/export/fhir-r4` requires profile authorization,
  medical consent, an allowed purpose, and an explicit minimum-necessary
  include set.
- `POST /api/v1/lifemap/v2/import/fhir-r4` accepts at most 1 MB and 500
  entries. It creates untrusted Universal Capture drafts. Import never confirms
  health truth, executes a task, or creates a medication order.
- `GET /api/v1/lifemap/v2/export/ips` fails closed until the IPS, licensing,
  terminology, and external validation gates are approved.

`LIFEMAP_FHIR_EXPORT_ENABLED` and `LIFEMAP_FHIR_IMPORT_ENABLED` default to
`false` and are independent.

## Pinned toolchain

The machine-readable lock is
`docs/interoperability/fhir-toolchain.lock.json`.

| Component | Pin |
| --- | --- |
| FHIR base | R4 `4.0.1`, `hl7.fhir.r4.core#4.0.1` |
| Validator CLI | `6.9.12` |
| Validator SHA-256 | `0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6` |
| IPS candidate | `hl7.fhir.uv.ips#2.0.1` |
| CLARA mapping | `clara-lifemap-fhir-r4-v1` |

The IPS package is a candidate only. CLARA must not add an IPS profile,
document label, or conformance statement until the generated document Bundle
passes the pinned package and the named clinical, interoperability, privacy,
and legal approvers sign the release record.

## Mapping

| CLARA source | FHIR R4 projection |
| --- | --- |
| profile identity/demographics | `Patient` |
| confirmed measurement | `Observation` |
| allergy | `AllergyIntolerance` |
| condition | `Condition` |
| confirmed medication course | `MedicationStatement` |
| episode and user goal | `CarePlan`, `Goal` |
| accepted/completed user task | `Task` |
| confirmed guided answer | `QuestionnaireResponse` |
| source-document metadata | `DocumentReference` |
| transformation lineage | `Provenance` |
| export authorization projection | `Consent` |
| export action projection | `AuditEvent` |

`MedicationRequest` is not emitted because a self-reported medication or
LifeMap task is not a clinician order. Original Vietnamese or English text is
retained next to any source code. CLARA does not invent SNOMED CT, LOINC,
ICD-10, or RxNorm codes. Numeric quantities are emitted as `Quantity` only
when the source supplies a UCUM code; otherwise they remain text.

## Import and security policy

The parser rejects excess size, excess entry count or nesting, multiple or
missing patients, patient mismatch, duplicate/invalid `fullUrl`, dangling or
external references, versioned references, unsupported resource types,
unknown top-level resource elements, `modifierExtension`, `contained`,
`implicitRules`, incomplete codings, non-UCUM quantities, unsafe narrative,
and overlong strings. Provenance, Consent, AuditEvent, and Composition do not
become health candidates. Every accepted clinical candidate retains its source
resource type/id and enters review as `untrusted_external_draft`.

Trusted-source ingestion is intentionally unsupported. A future trusted-source
policy needs separate identity assurance, contract, profile matching,
terminology, provenance, revocation, and clinical-safety approval.

## Validation

Download the exact validator artifact in the lock file, verify its checksum,
then run:

```bash
FHIR_VALIDATOR_JAR=/path/to/validator_cli.jar \
  scripts/validation/validate-lifemap-fhir.sh
```

The script fails on checksum mismatch or any validator error. Base-R4 warnings
are retained as evidence; warnings must not be hidden by changing severity.
IPS validation is a separate future gate and must include
`-ig hl7.fhir.uv.ips#2.0.1`.

## Upgrade procedure

1. Open a change record with the new FHIR/IG/validator versions and upstream
   release notes.
2. Complete license and terminology review before downloading or distributing
   new packages in production.
3. Update the lock, constants, mapping version, and golden fixtures together.
4. Run unit, security, semantic round-trip, base validator, and candidate IPS
   validator suites.
5. Review every new error and warning; do not suppress unknown modifier
   semantics or terminology failures.
6. Deploy with both flags off, canary the export, compare resource counts and
   redaction, then obtain the required sign-offs.
7. Keep the previous validator/package cache and mapping available for
   rollback and for interpreting already exported Bundles.

## Licensing and terminology gate

FHIR and IPS publication terms, the HL7/FHIR marks, SNOMED CT jurisdictional
licensing, RxNorm/NLM terms, LOINC terms, and UCUM usage must be reviewed for
the intended deployment and distribution model. Repository implementation and
base validation are not legal approval.
