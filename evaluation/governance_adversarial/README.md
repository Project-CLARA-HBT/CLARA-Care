# Governance adversarial evaluation

Status: **NOT RUN** until executed against an isolated real API/database/cache
deployment. Unit fixtures or direct gateway calls are not a boundary test.

The frozen attack manifest must cover cross-subject retrieval, revoked-consent
cache/index reuse, role and purpose mismatch, stale THSS replay, concurrent
stale write, GST-bypass prompt, prompt injection in patient evidence,
unrelated-disclosure request, and derived-cache persistence after revocation.
Emit exact attack counts for unauthorized disclosure, bypass, stale commit,
wrong-subject exposure, revocation failure, policy decision, and audit traces.

`run.py` can collect transport observations from an operator-authorized
deployment. It requires `--allow-network`, a frozen attack manifest, and an
optional `CLARA_EVIDENCE_BOUNDARY_TOKEN`; it writes response hashes only and
marks every observation `operator_label_required`. Do not convert those
observations to attack outcomes without the separate operator/adjudicator
classification CSV validated below.

```bash
python3 -m evaluation.governance_adversarial.run --manifest /secure/attacks.json --base-url http://127.0.0.1:8000 --output artifacts/evidence-program/<run-id>/transport.json --allow-network
python3 -m evaluation.governance_adversarial.validate_results --results /secure/adversarial.csv --manifest /secure/adversarial_manifest.json
```
