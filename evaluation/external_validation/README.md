# External validation protocol

This directory prepares, but does not fabricate, a lawfully accessed,
subject-disjoint real-EHR cohort. Full-MIMIC independent validation remains
**NOT RUN**. A user-supplied MIMIC-IV Demo-on-FHIR 2.1.0 archive has been run
as source-derived, non-headline evidence with `independent_curator=false` and
no annotation oracle.

Only a real data steward may create a headline-eligible external manifest. The preparer
must run outside this repository's git tree and emit deidentified derived task
records only. Synthetic governance perturbations are a separate challenge set;
they must never be merged into real-EHR clinical ground truth.

Required pre-run evidence: dataset/version and access authority; inclusion and
exclusion query; source checksums when permitted; salted subject tokens;
development-subject hash; test-subject hash; disjointness proof; domain and
missingness counts; independent curator identity/attestation; and a frozen
cohort manifest. The final cohort must be `partition: sealed_holdout` and
cannot be relabelled from development data. Validation requires salted
development and test token files, hashes each, rejects overlap, and checks the
frozen subject count.

The curator-owned preparer accepts only already deidentified structured JSONL;
it requires the development token file, rejects synthetic-oracle fields, and
freezes a sealed manifest. It never downloads MIMIC or reads credentialed raw
tables:

```bash
python3 -m evaluation.external_validation.prepare_cohort \
  --input-jsonl /secure/derived/selected.jsonl \
  --development-subjects /secure/development-subject-tokens.txt \
  --output-dir /secure/evidence/cohort \
  --dataset mimic_iv --dataset-version 4.0 \
  --lawful-attestation 'Steward attestation' \
  --curator-attestation 'Independent curator attestation' \
  --freeze-id external-freeze-1
```

For MIMIC Demo on FHIR, `prepare_mimic_demo_fhir.py` hashes patient/slot/value
identifiers, freezes a 20/80 subject split, and emits medication,
diagnosis/problem, and lab tasks. Its timestamp-derived targets are not
clinician labels and `headline_eligible` remains false.

For eICU Demo common-offset records, the developer-prepared source-derived
protocol is deliberately non-headline and compares events only within the same
ICU unit stay and source slot. It freezes a subject-disjoint 20/80 development/
evaluation split before task selection, leaves knowledge time unavailable, and
uses the source valid-offset resolver as a strong parity reference. It neither
compares offsets across stays nor treats the latest offset as clinical truth:

```bash
python3 -m evaluation.external_validation.prepare_common_offset_tasks \
  --records datasets/normalized/eicu_crd_demo_2_0_1/records.jsonl \
  --normalization-manifest datasets/normalized/eicu_crd_demo_2_0_1/normalization_manifest.json \
  --source-manifest datasets/manifests/eicu_crd_demo_2_0_1.json \
  --output datasets/normalized/eicu_crd_demo_2_0_1/source-derived-v1 \
  --freeze-id eicu-demo-offset-v1 \
  --dataset-id eicu_crd_demo_2_0_1 --dataset-version 2.0.1
```

The production-primitive execution is separately frozen in
`protocols/eicu-demo-source-offset-v1.json`. It encodes source offsets as an
abstract relative coordinate only; it does not invent an ICU admission date or
source knowledge time. The run must start from a clean tracked worktree:

```bash
services/api/.venv/bin/python -m evaluation.external_validation.run_common_offset_glhs \
  --tasks datasets/normalized/eicu_crd_demo_2_0_1/source-derived-v1/tasks.jsonl \
  --cohort-manifest datasets/normalized/eicu_crd_demo_2_0_1/source-derived-v1/cohort_manifest.json \
  --protocol evaluation/external_validation/protocols/eicu-demo-source-offset-v1.json \
  --output artifacts/evidence-program/eicu-demo-source-offset-glhs-v1

services/api/.venv/bin/python -m evaluation.external_validation.validate_common_offset_glhs \
  --output artifacts/evidence-program/eicu-demo-source-offset-glhs-v1 \
  --tasks datasets/normalized/eicu_crd_demo_2_0_1/source-derived-v1/tasks.jsonl \
  --cohort-manifest datasets/normalized/eicu_crd_demo_2_0_1/source-derived-v1/cohort_manifest.json \
  --protocol evaluation/external_validation/protocols/eicu-demo-source-offset-v1.json
```

This invokes `record_evidence`, `propose_assertion`, `apply_transition`, and
`reconstruct_state` from the production API code on an isolated SQLite scratch
database. It is an in-process engineering execution, not an HTTP/PostgreSQL or
clinical-validation claim. The strong valid-offset condition is a mandatory
parity reference; missing or invalid outputs are failures.
