# Runbook: CLARA-Eval VN

## PR / local smoke

1. Run `make eval-smoke`.
2. Inspect `artifacts/clara-eval-vn/smoke/metrics.json` and confirm only
   manifest integrity is measured unless approved evidence was executed.
3. Run `make eval-judge-report` to build the reviewer package.
4. Do not add artifacts, patient content, tokens or licensed DrugBank material
   to git; `artifacts/` is ignored.

## Release gate

`make eval-release` must return non-zero until the locked dataset, retrieval
snapshot, runtime model/prompt resolution and approved live evaluator are
available. This is expected fail-closed behaviour, not a test to bypass.

The GitHub `Release` workflow is manual-only. It resolves an immutable target
SHA and proposed semantic version, runs the locked gate against that SHA, and
only creates/pushes the tag after the gate succeeds. Do not create a `v*`
release tag by hand to bypass this sequence: an unvalidated tag is not a
release attestation and must be deleted only through the incident/change
process if it was created accidentally.

To continue after the external dependencies are provisioned, run:

```bash
CLARA_EVAL_LOCKED_DATASET_REF='approved immutable reference' \
CLARA_EVAL_API_BASE_URL='https://approved-api.example' \
CLARA_EVAL_ML_BASE_URL='https://approved-ml.example' \
make eval-release
```

The current foundation runner will still label unavailable execution data
`not_measured`; connect only an approved evaluator before changing this gate.

## Incident and rollback

If an evaluator detects a critical error, preserve sanitized metadata and
artifact hashes, disable the related feature flag, select the previous approved
model/prompt configuration, and follow `docs/runbooks/lifemap-ml-governance.md`.
Never paste prompts, patient text, drug lists, authorization headers or model
keys into issues or workflow logs.
