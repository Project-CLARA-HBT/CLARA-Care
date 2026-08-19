# FHIR application conformance evidence (Workstream H)

Sealed evidence for MASTER_SPEC_REVIEWER_R3_2026-08-19 Workstream H
(FHIR-01..FHIR-05, spec 3.8). Freeze id: `FHIR-CONFORMANCE-V1-20260819`.

## Contents

| Path | Purpose |
| --- | --- |
| `support_matrix.md` | H-001 supported R4/STU3 resource-type and Bundle-form inventory (product API + GLHS bench), each claim cited to code/docs |
| `validator_wrapper.py` | H-002 batch wrapper around the pinned HL7 `validator_cli` JAR (same pin/checksum as `scripts/validation/validate-lifemap-fhir.sh` via `docs/interoperability/fhir-toolchain.lock.json`) |
| `app_semantic.py` | Replays the product's real import gates (`clara_api.lifemap.fhir_r4`, `evaluation.commitloop.fhir_ingest`) — not a reimplementation |
| `preservation.py` | H-005/H-006 resource-preservation, source-reference reconstruction, subject rejection, temporal mapping, acceptance, and unsupported-behavior comparators (N/D) |
| `fixtures/` | Positive R4/STU3 + negative application-semantic fixtures (H-003/H-004), with `manifest.json` |
| `freeze.py` / `run.py` / `seal.py` | H-007 freeze (sha256 + expected outcomes + pin + git SHA), run (validator batch + gates + metrics), seal (artifact sha256 + analysis) |
| `seal/` | Machine-sealed run output, validator logs, `artifact-sha256.json`, `analysis.json`, `seal.json` |
| `tests/` | Gate, freeze, and preservation tests |

## Run

Everything below must run with the API interpreter and source path so the
product gates are importable (repo convention):

```bash
export PYTHONPATH=services/api/src:.
services/api/.venv/bin/python -m evaluation.fhir_conformance.freeze
services/api/.venv/bin/python -m evaluation.fhir_conformance.run
services/api/.venv/bin/python -m evaluation.fhir_conformance.seal
services/api/.venv/bin/python -m pytest evaluation/fhir_conformance/tests -q
```

`run.py` resolves the pinned JAR from `FHIR_VALIDATOR_JAR`, then
`~/.cache/clara-fhir-validator/validator_cli.jar`, then downloads it from the
locked URL and verifies the locked SHA-256. If the JAR is absent and cannot be
downloaded, every HL7 fixture is recorded as `execution: PENDING` — the run
never fabricates a validator result.

## Honest separation (spec 3.8)

The seal keeps two layers distinct:

- **HL7 structural** — the pinned validator's verdict on R4/STU3 base-spec
  validity.
- **CLARA application-semantic** — the product's one-patient rule, reference
  scope, supported resource surface, and Bundle-form scope. A Bundle can be
  structurally valid yet violate that contract (see
  `fixtures/negative/missing-patient.json`, `cross-subject-reference.json`,
  `unsupported-resource.json`).

Recorded gaps (see `seal/analysis.json`): the import gate does not validate
temporal values (HL7 rejects `2026-02-30`, the CLARA gate accepts it); the
bench does not reconstruct STU3 `ProcedureRequest.occurrenceDateTime`; the
product import gate flags any `http(s)://` inside narrative `div` content
(which rejects FHIR-standard XHTML `xmlns`); replay protection is endpoint
level (`Idempotency-Key`) and not measurable offline.

`artifact-sha256.json` hashes the fixture, source, test, run, analysis, and
validator-log artifacts. It intentionally excludes itself and `seal.json` to
avoid a self-referential hash; `seal.json` records the hash of the artifact
hash manifest.

## Manual admin gate (H-009 / FHIR-05)

The support letter, signatures, advisor confirmation, and the exact milestone
date are **human administrative gates**. They are never fabricated and are not
part of this machine seal. `seal/seal.json` records them as `MANUAL_GATE`.
