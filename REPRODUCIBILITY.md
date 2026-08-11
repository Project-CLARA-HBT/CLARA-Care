# GLHS evidence program reproducibility index

## Current status

The current revision is not a clean final headline freeze. A non-headline MIMIC
Demo run exists at
`artifacts/evidence-program/2026-08-09-mimic-demo-no-annotation-v1/`: 31
development and 69 evaluation subjects are token-disjoint; 6,741 source-derived
tasks span medication, diagnosis/problem, and lab state. It has no independent
curator, clinical annotations, provider-model utility, deployed adversarial
run, PostgreSQL full-stack run, or clean source revision. Therefore no headline
clinical, privacy, utility, or superiority conclusion may be generated.

Existing Q2/Q3 outputs are developer-authored structural evidence only; see
[evaluation/glhs_q3/README.md](evaluation/glhs_q3/README.md) and
[claim-to-evidence matrix](docs/reports/glhs-q3-claim-to-evidence-matrix-2026-08-08.md).
The Demo run is sealed separately as
`sealed_nonheadline_not_claim_eligible`; its `artifact-sha256.json` hashes all
derived outputs without weakening the headline seal.

## Frozen-run contract

For each final run, create `artifacts/evidence-program/<run-id>/`. It must
contain environment, cohort/split/domain/annotation/adjudication/oracle/
comparator/model manifests; raw case and per-run outputs; domain/utility/
adversarial/human/fullstack/statistical/error CSVs; report; figures/tables; and
an artifact SHA-256 manifest.

Before execution, freeze and hash cohort/split, annotation guide/oracle,
policies, comparator, task/prompt/model/retrieval settings, endpoints, and
statistics plan. `evaluation.evidence_program.validate_statistics_plan` checks
the subject-clustered uncertainty and bounded-claim protocol, while
`evaluation.evidence_program.freeze.verify_freeze` rejects
an incomplete or non-independent freeze.

## Commands

Dataset foundation (metadata first; no command implies a dataset is clinically
validated):

```bash
python scripts/data/list_sources.py
python scripts/data/inspect.py --dataset <id>
python scripts/data/verify.py --dataset <id> --output /tmp/<id>-verification.json
python scripts/data/fetch.py --dataset <id> --accept-license
python scripts/data/normalize.py --dataset <id>
python scripts/data/freeze_manifest.py --dataset <id>
python scripts/data/verify_manifest.py --dataset <id>
```

`inspect` reports only presence and size. `verify` computes local SHA-256 and
archive integrity but does not claim canonical authenticity when the provider
does not supply a pinned checksum. `normalize` writes patient-level records only
under gitignored local paths. `freeze_manifest` refuses a dirty tracked
worktree, unresolved canonical source or existing manifest; it never imports
raw records into git. `verify_manifest` fails if the manifest self-hash,
registry hash, source commit, or current local source inventory has changed.

Current local MIMIC-IV Demo on FHIR adapter output contains 927,109 common
records for 100 deidentified source subjects and explicitly preserves missing
knowledge time for every record. It is a non-headline adapter/structural source,
not an independent clinical oracle. Its tracked manifest payload SHA-256 is
`e5257d01f07024cfc965f0f263484c49fac2c5728539de3d030db8b0eadec738`;
canonical checksum status remains `NOT_PROVIDED`.

Structural regression only:

```bash
services/api/.venv/bin/python -m pytest -q evaluation/glhs_q3/test_run.py
python3 -m evaluation.glhs_q3.run --output artifacts/glhs-q3/<structural-run-id>
```

MIMIC Demo source-derived run (requires the user-supplied Demo-on-FHIR archive
to be extracted locally and a secret salt outside git):

```bash
python3 -m evaluation.external_validation.prepare_mimic_demo_fhir \
  --fhir-root /secure/mimic-demo-fhir/fhir \
  --output artifacts/evidence-program/<run-id>/fhir-source-derived \
  --token-salt-file /secure/token-salt.bin \
  --lawful-access-attestation 'Demo access attestation' --freeze-id <freeze-id>
python3 -m evaluation.domain_portability.run_source_derived \
  --records artifacts/evidence-program/<run-id>/fhir-source-derived/records.jsonl \
  --output artifacts/evidence-program/<run-id>/domain-source-derived
python3 -m evaluation.evidence_program.report_demo_run --run-dir artifacts/evidence-program/<run-id>
python3 -m evaluation.evidence_program.seal_nonheadline --run-dir artifacts/evidence-program/<run-id>
```

Protocol validation (does not run a clinical evaluation):

```bash
python3 -m evaluation.external_validation.validate_manifest --manifest /secure/cohort.json --development-subjects /secure/dev-tokens.txt --test-subjects /secure/test-tokens.txt
python3 -m evaluation.independent_adjudication.validate_manifest --manifest /secure/annotation.json
python3 -m evaluation.downstream_utility.validate_manifest --tasks /secure/tasks.json --models /secure/models.json --freeze /secure/freeze.json
python3 -m evaluation.evidence_program.seal --run-dir artifacts/evidence-program/<run-id> --freeze /secure/freeze.json
python3 -m evaluation.evidence_program.status --output /tmp/evidence-readiness.json
```

## Paper mapping

| Paper evidence | Source version | Commands/manifests | Outputs |
| --- | --- | --- | --- |
| Structural GLHS mechanics | exact clean git SHA/tag required | Q3 command above | `artifacts/glhs-q3/<id>/` |
| Temporal comparator | comparator version + source mapping | comparator tests + frozen manifest | comparator manifest |
| MIMIC Demo source-derived mechanics | dirty SHA `76eb5c2f...`; non-headline only | Demo commands above | `artifacts/evidence-program/2026-08-09-mimic-demo-no-annotation-v1/` |
| External/adjudicated evidence | exact clean SHA/tag required | curator-owned frozen protocol | `artifacts/evidence-program/<id>/` |
| Tables/figures | same artifact SHA manifest | report generator only | frozen generated files |

Never place licensed EHR data, salts, credentials, patient text, or reviewer
identities in git. Reported numbers must be derived from frozen raw artifacts,
not copied manually.
