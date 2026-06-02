# Council Synthetic Testing Flow (Worker C)

## Scope
- Reproducible synthetic case generation for Council.
- Runnable endpoint evaluation with summary metrics and pass/fail checks.
- Manual baseline comparison scaffold (no paid external API required).

## Scripts
- Generator: `scripts/demo/generate_council_synthetic_cases.py`
- Evaluator: `scripts/demo/run_council_synthetic_eval.py`

## Quick Run
```bash
python3 scripts/demo/generate_council_synthetic_cases.py --seed 20260406 --total-cases 60

python3 scripts/demo/run_council_synthetic_eval.py \
  --cases data/demo/council-synthetic-cases-seed20260406-n60.json \
  --base-url http://127.0.0.1:8110 \
  --endpoint /v1/council/run \
  --internal-key "$ML_INTERNAL_API_KEY"
```

## Outputs
- Eval JSON summary: `data/demo/council-synthetic-eval-*.json`
  - triage distribution
  - escalation ratio
  - confidence-like proxies (`confidence_score`, `support_ratio`, `disagreement_index`, `data_quality_score`)
  - pass/fail checks and per-case results
- Eval Markdown: `data/demo/council-synthetic-eval-*.md`
- Baseline scaffold template JSON: `data/demo/council-synthetic-eval-*-baseline-template.json`
  - includes `baseline_candidate` placeholders
  - includes manual scoring fields: triage/safety/actionability/evidence quality
