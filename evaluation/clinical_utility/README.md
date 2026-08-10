# THSS downstream utility protocol

Status: **NOT RUN**. No provider/model outputs are fabricated. The frozen task
manifest must use identical instances across `full_authorized`, `naive_rag`,
`btsa_or_tpr`, `glhs_no_thss`, `thss_default`, and `thss_strict`; it must lock
prompt, output schema, decoding, retrieval, context budget, scoring and seeds.
At least two genuinely distinct model families are required for a headline
utility conclusion. Record correctness, critical omission, unsupported
assertion, conflict handling, evidence fidelity, authorized disclosure, token
counts, latency, cost, and errors in raw per-run output.

The runner must reject a release unless the global freeze and two model families
are present; an empty or synthetic score is not a fallback.

Before a headline artifact seal, validate the raw complete grid:

```bash
python3 -m evaluation.clinical_utility.validate_output \
  --output artifacts/evidence-program/<run-id>/thss_utility.csv \
  --tasks /secure/tasks.json --models /secure/models.json --freeze /secure/freeze.json
```
