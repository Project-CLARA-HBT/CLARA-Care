# CLARA-Eval VN

CLARA-Eval VN is CLARA's evidence boundary for Vietnamese clinical language,
patient communication, Research RAG, CareGuard/DrugBank, Scribe/ASR, LifeMap,
Council, wording and model routing. It does not convert synthetic fixtures
into clinical benchmark results.

## Suites

| Suite | Purpose | Gate behaviour |
| --- | --- | --- |
| `smoke` | PR integrity, privacy and artifact contract | Passes when fixtures/manifests validate. Product metrics remain `not_measured`. |
| `nightly` | Live-capable evidence collection | Emits evidence artifacts even when approved live input is unavailable. |
| `release` | Locked release evidence | Fails closed if approved locked/live evidence was not executed. |
| `judge_demo` | Human-readable judge package | Creates the report package without claiming unmeasured results. |

## Commands

```bash
make eval-smoke
make eval-nightly
make eval-release       # intentionally non-zero without locked live evidence
make eval-judge-report
```

`make eval-judge-report` writes `artifacts/judge-report/`: `index.html`,
`summary.md`, `metrics.json`, `ablations.csv`, `critical-errors.csv`,
`model-manifest.json`, `dataset-manifest.json` and `examples/` (plus
machine-readable supporting artifacts).

## Evidence policy

All checked-in fixtures are synthetic safety fixtures, checksum-locked and
prohibited from containing PHI or secrets. A metric with unavailable data,
model trace, retrieval snapshot, licensed DrugBank index, or clinician review
must be `not_measured`, with a reason and exact follow-up command. An empty
critical-error count is never reported as proof that there were zero errors.

The release suite requires an approved locked dataset reference, immutable
retrieval snapshot, runtime model/prompt resolution, and approved live
execution evidence. Configure its values out of band; do not commit datasets,
tokens, patient content, or provider keys.

The checked-in task-contract manifest also records whether each task is
assigned the governed `pro` or `flash` DeepSeek V4 profile. Judge artifacts
capture that configuration but label it `configured_not_executed` until a
credentialed live trace is supplied; they never turn a configured model into a
measured quality or latency result.

## Data and model cards

- Dataset card: `evaluation/clara_eval/datasets/README.md`,
  `evaluation/clara_eval/datasets/manifest.json` and
  [`docs/ml-governance/clara-eval-vn-dataset-card.md`](../ml-governance/clara-eval-vn-dataset-card.md).
- Model/runtime card: `docs/ml-governance/clara-eval-vn-model-card.md`.
- Operational response: `docs/runbooks/clara-eval-vn.md`.
