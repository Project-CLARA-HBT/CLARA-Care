# GLHS Q2 frozen structural evaluation

Run the exact protocol with:

```bash
make eval-glhs-q2
```

The runner creates **exactly 400 developer-authored structural cases over 200
subject tokens**: 100 direct-conformance, 240 compositional, and 60 ambiguity
cases. Cases `Q2-0281` through `Q2-0340` are the checksum-locked, 60-case
compositional holdout. They are not clinical data, clinical labels, or a
clinical-effectiveness benchmark.

Before each comparator executes, the command writes and hashes:

- `policy.json`
- `task_relevance_manifest.json`
- `oracle_manifest.json`
- `holdout_manifest.json`
- `mechanism_evidence.json`

The resulting artifact directory contains the required raw CSV and JSON files:
`summary.json`, `environment.json`, `cases.csv`, `outcomes.csv`, `per_run.csv`,
`conformance.csv`, `baseline_comparison.csv`, `ablation.csv`,
`thss_ablation.csv`, `error_analysis.csv`, `operational_metrics.csv`,
`cost_of_success.csv`, `scalability.csv`, the frozen
contracts, `evidence-manifest.json`, `report.md`, and publication-ready SVGs.

`glhs_full` is a transparent reference-policy conformance model in the
developer-authored cohort. Its score is deliberately marked as non-independent
and must never be reported as a clinical or final benchmark score. The required
120-case, three-seed model-backed arm is a separate, synthetic-only structural
experiment. Run it *inside the configured ML runtime* after freezing the model
provider/config snapshot:

```bash
/app/.venv/bin/python /tmp/run_model_arm.py \
  --cases /path/to/q2/cases.csv --output /path/to/model-arm \
  --code-revision "$(git rev-parse HEAD)" --transport direct
make eval-glhs-q2-model-integrate \
  MODEL_ARM_SOURCE=/path/to/model-arm MODEL_ARM_OUTPUT=/path/to/summary
```

`--transport direct` uses only the versioned task client. It rejects a configured
fallback/rollback model and records provider errors as errors; it does not route
opaque structural labels through End_User medical guardrails or substitute a
heuristic score. The integrator fails if any one of the 120 × 3 fixed runs is
absent or duplicated.

External MIMIC/Synthea cohorts may only be supplied as lawful, privacy-minimised
structural-perturbation manifests with checksums. Their outcomes are reported
separately. A sealed external holdout requires a documented freeze and curator
independence attestation before the result can be labelled eligible for final
score release.

### Prepare the full supplied Synthea STU3 archive

The archive may contain more than one million FHIR patient bundles. The
preparer scans it once without extraction and keeps only salted subject tokens,
bounded episode counts and predeclared structural oracle fields. It uses a
temporary token-only SQLite index, then removes it after emitting the checksum
locked JSONL; source identifiers, free text, codes and clinical values are
never persisted.

For the complete archive (rather than a deterministic sample), use
`--selection-modulus 1` in a persistent job shell:

```bash
python3 -m evaluation.glhs_q2.prepare_synthea_archive \
  --archive synthea_1m_fhir_3_0_May_24.tar.gz \
  --token-salt-file /secure/local/q2-token-salt.bin \
  --output /secure/local/q2-derived/synthea-stu3-full-development \
  --selection-modulus 1 \
  --lawful-access-attestation 'Local Synthea archive, non-clinical structural evaluation.'

make eval-glhs-q2-external-stream \
  MANIFEST=/secure/local/q2-derived/synthea-stu3-full-development/manifest.json \
  OUTPUT=artifacts/glhs-q2/synthea-stu3-full-development
```

This still produces a **synthetic development** structural cohort. It is not
clinical ground truth, independent validation, or a final score release.
