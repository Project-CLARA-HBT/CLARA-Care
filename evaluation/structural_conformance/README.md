# GLHS Q3 synthetic structural evaluation

Run the reproducible, non-clinical structural protocol:

```bash
make eval-glhs-q3
# or choose an immutable output directory explicitly
python3 -m evaluation.glhs_q3.run --output artifacts/glhs-q3/YYYY-MM-DD-v2
```

An external structural cohort is accepted only through an explicit local
`--mimic-demo-manifest` (the name is retained for CLI compatibility). The v2
manifest supports `mimic_iv_demo`, `mimic_iv_ed_demo`, `mimic_iv_fhir_demo`,
`synthea_fhir_r4`, and `synthea_fhir_stu3`. It must point to a checksum-locked, de-identified JSONL
of controlled perturbations with a cohort-specific number of distinct subject
tokens (100 for MIMIC-IV Demo/FHIR and Synthea; 40 for the smaller
MIMIC-IV-ED Demo) and explicit oracles. The runner rejects absolute or escaping paths, unknown/raw
fields, missing lawful-access attestation and checksum mismatch. It never
downloads MIMIC or accepts/loads credentialed full MIMIC resources.

## No final score from the development protocol

`glhs_full` is a reference-policy conformance model that implements the same
declared structural rules used to label the developer cases. Its 100% value on
those cases is therefore expected and **must never be described as an
independent benchmark score**. The runner marks `score_release.final_score_released`
as `false` unless a v2 external `partition: sealed_holdout` manifest supplies
checksum-locked perturbations plus a freeze ID, oracle/development-set hashes,
curator and independence attestation. Metadata can be verified by the runner;
the curator's claimed independence still requires governance review.

Use separate manifests and report separate tables for MIMIC-IV Demo,
MIMIC-IV-ED Demo, MIMIC-IV on FHIR and each Synthea FHIR release. Never combine synthetic and
MIMIC values into one headline number. The recommended sequencing is:

1. Freeze the development perturbation policy and reference oracle.
2. Have an evaluator not involved in policy implementation create and checksum
   the sealed compositional holdout (at least 25% of cases).
3. Run the holdout once after implementation is frozen; retain its complete
   manifest and output digest.
4. Describe the outcome as structural robustness/conformance only, never
   clinical effectiveness or safety.

### Prepare a lawful local Demo cohort

Download/extract the dataset only through its approved source and terms, keep a
local token salt outside the repository, then run the preparer against the
*entire declared source tables*.  Example for MIMIC-IV Demo (paths are local
examples, not URLs):

```bash
openssl rand -out /secure/local/q3-token-salt.bin 32
python3 -m evaluation.glhs_q3.prepare_external_cohort \
  --cohort mimic_iv_demo \
  --source-root /secure/local/mimic-iv-clinical-database-demo-2.2 \
  --token-salt-file /secure/local/q3-token-salt.bin \
  --output /secure/local/q3-derived/mimic-iv-demo-development \
  --partition development \
  --lawful-access-attestation 'Lawful Demo access under applicable terms.'
python3 -m evaluation.glhs_q3.run \
  --output artifacts/glhs-q3/mimic-iv-demo-development \
  --mimic-demo-manifest /secure/local/q3-derived/mimic-iv-demo-development/manifest.json
```

For a final score, a separate evaluator—not the implementation/tuning team—has
to provide `--partition sealed_holdout` plus `--freeze-json` containing the six
required freeze fields described above.  Do not generate that JSON from this
tool or relabel a development partition as sealed.

### Prepare the supplied Synthea STU3 archive

The archive `synthea_1m_fhir_3_0_May_24.tar.gz` is nested and contains STU3
FHIR bundles.  Run this in a persistent CI/job shell (the full one-pass scan
can exceed short interactive-agent command limits):

```bash
python3 -m evaluation.glhs_q3.prepare_synthea_archive \
  --archive synthea_1m_fhir_3_0_May_24.tar.gz \
  --token-salt-file /secure/local/q3-token-salt.bin \
  --output /secure/local/q3-derived/synthea-stu3-development \
  --selection-modulus 100 \
  --lawful-access-attestation 'Local Synthea archive, non-clinical structural evaluation.'
python3 -m evaluation.glhs_q3.run \
  --output artifacts/glhs-q3/synthea-stu3-development \
  --mimic-demo-manifest /secure/local/q3-derived/synthea-stu3-development/manifest.json
```

The runner scans every patient bundle without extracting the archive, but
writes only salted token/aggregate structural data.  It reports `STU3` in the
manifest and does not claim R4 conformance.

The runner creates 300 developer-authored, oracle-labelled synthetic histories
over 150 synthetic subjects (8–30 episodes per subject), with no patient text,
drug list or clinical label. It compares six explicitly modelled structural
architectures on the same case identifiers:

| ID | Meaning |
|---|---|
| `lww` | Last-write-wins current row model. |
| `naive_rag` | Recency-oriented retrieval model without governed state. |
| `temporal_provenance_resolver` | Stronger valid-time/provenance resolver baseline without consent/GST/projection governance. |
| `glhs_full` | Governed evidence/assertion/state/transition model. |
| `glhs_no_thss` | GLHS with authorization unchanged but no context minimisation. |
| `glhs_no_gst` | GLHS-shaped model that permits direct current-state mutation. |

The test matrix covers ordinary and late evidence, duplicates, conflict,
family isolation, consent revocation, stale state version, missing provenance,
temporal and Scribe ambiguity, projection rebuild, and direct-write attack.
It outputs raw cases/outcomes, denominators, Wilson intervals, paired exact
McNemar tests, subject-clustered bootstrap risk differences, Holm adjustment,
four-profile THSS privacy–utility ablation, structural operation timing at
history depths 10/50/100/250, and six SVG figures generated from `summary.json`.

## Interpretation boundary

This is a conformance/robustness protocol for the declared structural rules,
not independent validation of a deployed implementation. Its cases and oracle
outcomes are developer authored; they cannot establish clinical accuracy,
clinical safety, real-world privacy, model quality, user benefit, external
generalisation, production latency, or superiority over a clinical system.
The timing values are pure Python state-layer simulations, explicitly separated
from database, network, browser and LLM latency. MIMIC-IV Demo is not accessed
unless a lawful, explicitly supplied manifest is passed and recorded;
credentialed full MIMIC is never accessed by this runner.

Every result must be cited with its `evidence-manifest.json`, frozen
`summary.json` SHA-256, code revision and source hashes. Do not transfer the
figures or percentages into the IEEE manuscript as clinical claims.
