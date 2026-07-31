# CLARA-Eval VN live execution contract

The repository fixtures are contract fixtures, not clinical benchmarks.  The
runner will send a live request only when all of these controls are true:

1. The selected suite allows live dependencies (`nightly` or locked `release`).
2. `CLARA_EVAL_LIVE_EXECUTION_ENABLED=true` is present for that process.
3. `CLARA_EVAL_LIVE_MANIFEST` is an absolute path outside this repository.
4. The manifest follows
   [`live-execution-manifest.schema.json`](schemas/live-execution-manifest.schema.json),
   says `approved_for_live_execution: true`, and declares no PHI or secrets.
5. The endpoint base URL is HTTPS, unless an operator explicitly sets
   `CLARA_EVAL_ALLOW_INSECURE_HTTP=true` for an isolated local environment.

The evaluation manifest belongs in the access-controlled evaluation store.  Do
not commit it, copy it into an issue, or place patient content, bearer tokens,
cookies, email addresses, names, or passwords in it.  Case IDs must be opaque
slugs; the report writes only a one-way case reference.

## Manifest shape

Each record is a POST to the configured `api` (`/api/v1/*`) or `ml` (`/v1/*`)
base URL.  Its scorer supports a declared `json_path_equals` binary verdict.
The metric must be declared for the record's track.  A failed transport request
does not become a clinical failure; it remains an execution gap.  Request and
response bodies are never written to `artifacts/`.

An optional immutable retrieval snapshot provides a reference and SHA-256. It
is reported as provenance only; the runner does not fetch or infer its content.
For the locked release suite it is required, along with a `release_binding`
object containing the exact `locked_dataset_ref` and immutable 40-character
`release_ref`. The evaluator compares those values to
`CLARA_EVAL_LOCKED_DATASET_REF` and `CLARA_EVAL_RELEASE_REF` before it sends a
request. Artifacts retain only the dataset-reference SHA-256 and the release
SHA; they never write the governed dataset reference itself.

## Running an approved nightly evaluation

```bash
CLARA_EVAL_LIVE_EXECUTION_ENABLED=true \
CLARA_EVAL_LIVE_MANIFEST=/secure/eval/clara-eval-vn-approved.json \
CLARA_EVAL_API_BASE_URL=https://approved-api.example \
CLARA_EVAL_ML_BASE_URL=https://approved-ml.example \
make eval-nightly
```

Bearer credentials may be supplied only to the evaluator process using
`CLARA_EVAL_API_BEARER_TOKEN` and `CLARA_EVAL_ML_BEARER_TOKEN`.  An internal ML
evaluation endpoint may additionally use `CLARA_EVAL_ML_INTERNAL_KEY` for its
existing `X-ML-Internal-Key` guard.  None of these values is serialized or
printed.  The report's `live-execution.json` contains opaque case references,
endpoint class, path, status class, duration and verdict only.

## GitHub Actions nightly integration

`active-eval.yml` keeps live execution off unless repository variable
`CLARA_EVAL_LIVE_EXECUTION_ENABLED` is exactly `true`. When governance approves
a de-identified manifest, store its JSON only in the Actions secret
`CLARA_EVAL_LIVE_MANIFEST_JSON`; the workflow writes it with mode `0600` under
`RUNNER_TEMP`, passes that external path to the runner, and removes it on exit.
Optional endpoint credentials remain separate Actions secrets:
`CLARA_EVAL_API_BEARER_TOKEN`, `CLARA_EVAL_ML_BEARER_TOKEN`, and
`CLARA_EVAL_ML_INTERNAL_KEY`.

The release workflow uses the separate `CLARA_EVAL_RELEASE_LIVE_EXECUTION_ENABLED`
repository variable and `CLARA_EVAL_RELEASE_LIVE_MANIFEST_JSON` secret; it binds
the manifest to its resolved release SHA before a tag can be created.

Do not put the manifest in a repository variable, artifact, pull request,
issue, or workflow output. The live flag should remain false until the
manifest approval, endpoint allowlist, dataset license, de-identification and
retrieval snapshot have been reviewed.

## Release behaviour and rollback

The locked release suite remains fail-closed until every configured product
metric is observed with an approved binary scorer, no request failed, a locked
dataset reference and immutable release SHA both match, and a retrieval snapshot
is present. It does not infer missing metrics from the synthetic fixture suite.
On a critical failure: preserve only sanitized artifact hashes, disable the
affected feature flag, restore the previous model/prompt/retrieval snapshot, and
rerun the locked suite against the previous approved manifest revision.
