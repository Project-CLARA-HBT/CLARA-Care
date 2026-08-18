# Release Schema V2 — systems / nonclinical release

Workstream: **W11 CI/release + reproducibility**. Additive release-gate schema
for the **systems / nonclinical** evidence class. It does not modify the legacy
headline human-validation gate
(`evaluation/evidence_program/release_gate.py`), which remains the record for
any future headline clinical claim.

Code: `evaluation/evidence_program/release_gate_v2.py`
Tests: `evaluation/evidence_program/test_release_gate_v2.py`
Schema version: `clara-release-schema.v2`

## Why v2 exists

The legacy `release_gate` schema (`status`, `approved_by`, and the five
`*_attested` flags) carries headline human-validation semantics. Systems /
nonclinical evidence must be releasable without fabricating or implying human
validation, and a release record must make that distinction explicit at the
schema level instead of collapsing it into a single `approved` status.

## Fields

| Field | Type | Semantics |
| --- | --- | --- |
| `schema_version` | string | Must equal `clara-release-schema.v2`; mismatches refuse. |
| `status` | string | Must equal `approved`; anything else refuses. |
| `release_id` / `run_id` | string | Release and underlying run identifiers. |
| `code_revision` / `protocol_sha256` | string | Git revision and frozen-protocol digest that produced the run. |
| `clinical_human_validation_status` | string | `NOT_AVAILABLE` unless genuine, byte-resolvable evidence is attached (below). |
| `dual_model_supportive_review_attested` | boolean | Dual-model supportive protocol review was run and is nonclinical. |
| `external_structural_validation_attested` | boolean | External structural/mechanical validation was run. |
| `real_boundary_governance_attested` | boolean | Real-boundary governance (e.g. RIVF) result exists. |
| `postgres_concurrency_attested` | boolean | Persisted-governance concurrency (e.g. GLHS v1/v2) result exists. |
| `formal_assurance_attested` | boolean | Bounded formal/exhaustive assurance was executed. |
| `approved_by` / `approved_at` | string | Reviewer identity and ISO-8601 approval time. |

All five nonclinical attestations must be truthy for approval; any false value
raises `nonclinical_release_attestation_missing`.

## `clinical_human_validation_status` — never fake human validation

- Allowed statuses: `NOT_AVAILABLE` and `AVAILABLE_WITH_GENUINE_EVIDENCE`.
- `NOT_AVAILABLE` requires no further fields and is the default for a
  systems / nonclinical release.
- Any other value raises `clinical_human_validation_invalid_status`.
- `AVAILABLE_WITH_GENUINE_EVIDENCE` is **only** accepted when the record also
  carries a `clinical_human_validation_evidence` bundle:

  ```json
  {
    "clinical_human_validation_evidence": {
      "artifact_path": "evaluation/human_review/.../signed-labels.json",
      "sha256": "<hex digest of the artifact bytes>"
    }
  }
  ```

  The validator (a) requires the bundle, (b) requires the artifact path to
  resolve under the repository root, (c) requires the file to exist, and
  (d) requires its on-disk SHA-256 to match the declared hash. A missing
  bundle, missing bytes, an out-of-repository path, or a SHA mismatch all
  refuse — so an "available" flag is never self-attested.

This is the mechanism that makes "genuine" machine-verifiable instead of a
boolean the author sets: claiming clinical human validation requires real,
byte-bound evidence, and nothing in this module fabricates one.

## Legacy semantics preserved

`evaluation/evidence_program/release_gate.py` (schema
`headline`/`REQUIRED` fields, `status == "approved"`, the
`external_cohort_attested` / `independent_adjudication_attested` /
`two_model_family_utility_attested` / `real_boundary_adversarial_attested` /
`postgres_fullstack_attested` flags, and `approved_by`/`approved_at`) is
**unchanged and remains the gate for any future headline human-validated
claim**. v2 does not replace it, does not weaken it, and never maps a
nonclinical approval onto a headline human-validation claim. A v2 record that
sets `clinical_human_validation_status` to anything other than `NOT_AVAILABLE`
without the genuine evidence bundle is refused by design.

## Validation

```bash
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m pytest -q evaluation/evidence_program/test_release_gate_v2.py
```

The tests assert, among other things, that the gate **refuses to mark clinical
human validation as available** without genuine resolvable evidence
(`test_v2_gate_refuses_to_mark_clinical_human_validation_available_without_evidence`).
