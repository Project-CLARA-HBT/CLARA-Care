# Evidence program artifact contract

All final work is written to `artifacts/evidence-program/<run-id>/`. A run is
release-eligible only after an independent curator freezes every manifest and
the verifier accepts the freeze. The release report must record explicit
NOT RUN status for each unavailable workstream; absence may never become a zero
failure rate or a surrogate score.

After all required raw outputs exist, seal the run once:

```bash
python3 -m evaluation.evidence_program.seal \
  --run-dir artifacts/evidence-program/<run-id> --freeze /secure/freeze.json
```

The command fails without writing a partial seal if any headline artifact is
missing. `artifact-sha256.json` is the immutable inventory cited by tables and
figures; a changed raw file requires a new run ID and complete rerun.
The freeze manifest must also contain `artifact_bindings` for the cohort, split,
domain, annotation, adjudication, oracle, comparator, and model manifests;
`seal` recomputes and compares each binding.
The frozen statistics plan is also required in the sealed run and hash-bound
to the freeze.

The draft [statistics plan](statistics_plan.json) is a protocol artifact only;
it must be independently reviewed and changed to `status: frozen` before any
headline run.

No sensitive clinical source data, salts, credentials, free text, or reviewer
identity belongs in this repository or artifact directory when it is tracked.

`status.py` emits a metadata-only readiness audit. It keeps
`headline_claims_permitted: false` until a sealed artifact exists and never
turns missing work into a zero or a success.
