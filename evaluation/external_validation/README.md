# External validation protocol

This directory prepares, but does not fabricate, a lawfully accessed,
subject-disjoint real-EHR cohort. Full-MIMIC independent validation remains
**NOT RUN**. A user-supplied MIMIC-IV Demo-on-FHIR 2.1.0 archive has been run
as source-derived, non-headline evidence with `independent_curator=false` and
no annotation oracle.

Only a real data steward may create the source-derived manifest. The preparer
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
