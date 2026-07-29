# CLARA-Eval VN datasets

`manifest.json` is the source of truth for the fixture identity, checksum,
provenance and measurement status of all nine evaluation tracks. The checked-in
JSONL files are deliberately tiny synthetic safety fixtures. They exercise
contracts such as emergency fast-path, DrugBank fail-closed behavior and
LifeMap state isolation; they are not clinical benchmarks and must never be
used to claim accuracy, recall, cost, latency or usability results.

Validate before any runner or report:

```bash
python -m evaluation.clara_eval.datasets.validate \
  --manifest evaluation/clara_eval/datasets/manifest.json \
  --repository-root .
```

Every unavailable metric records `not_measured`, an honest reason and the
exact suite command needed once the consented/licensed/reviewed dataset and
environment exist. Sensitive raw patient data, secrets and unreviewed medical
claims are forbidden from this directory.
