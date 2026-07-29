# Master implementation checklist (PR-01 to PR-15)

This is a delivery ledger, not proof that a checkpoint is done.

| PR | Scope | State | Evidence gate |
| --- | --- | --- | --- |
| 01 | Audit, ADRs, baseline | in progress | source inventory, ADRs, command record |
| 02 | i18n foundation | planned | typed catalogs, parity and hard-code checks |
| 03 | Personal task-first UX | planned | journeys, a11y and visual checks |
| 04 | Model registry/contracts | planned | typed contracts and rollback config |
| 05 | Vietnamese clinical NLP | planned | language-slice evaluation and safety tests |
| 06 | Hybrid task/risk router | planned | shadow comparison and under-routing gate |
| 07 | Structured renderer/verifier | planned | fidelity tests and deterministic fallback |
| 08 | CareGuard VN normalization | planned | DrugBank integrity and benchmark evidence |
| 09 | Scribe safety refactor | planned | grounding/no-auto-code/retention evidence |
| 10 | Council hybrid shadow | planned | ablation and safety comparison |
| 11 | Research verifier | planned | claim/citation matrix and RAG evaluation |
| 12 | LifeMap VN features | in progress | invariant and source-review evidence |
| 13 | CLARA-Eval VN | in progress | suites, manifests, artifacts, active-eval |
| 14 | Security/ops hardening | planned | release/restore/security gate evidence |
| 15 | Mobile parity | in progress | contract, locale, consent, a11y evidence |

## Required exit evidence

- Format, lint and type check relevant code.
- Unit plus API/contract/invariant tests when boundaries change.
- Eval smoke and explicit `not measured` detail for unavailable metrics.
- Web/service build where tooling is available.
- i18n and no-secret/no-PII-log review.
- Rollback and feature-flag state for risky behavior.
