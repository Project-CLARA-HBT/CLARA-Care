# Contract clause ablation

This deterministic developer-authored study adds admissibility clauses one at
a time: temporal/provenance resolver, base-version write, authorization at
disclosure, provenance/audit, snapshot ID, full snapshot context/digest and
disclosed-evidence membership, then current reauthorization/policy/consent/
expiry. It localizes mechanisms; it is not external validation or clinical
evidence.

Run without network access:

```bash
PYTHONPATH=. services/api/.venv/bin/python \
  -m evaluation.contract_clause_ablation.run --output /new/output/path
```

The command refuses to overwrite an existing directory and writes raw cell
outcomes, recomputable per-variant aggregates and a SHA-256 inventory.
`experiment_manifest.json` freezes the exact case order, clause order and
runner/engine digests; `validate_frozen_contract` and `validate` fail closed on
contract or result tampering.
