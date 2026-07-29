# CLARA production-readiness implementation plan

Status: active implementation plan. Last audited: 2026-07-30.

## Evidence-based baseline

| Area | Current evidence | Assessment | Next checkpoint |
| --- | --- | --- | --- |
| Safety kernel | API RBAC, consent, CSRF, audit and LifeMap command boundaries exist; ML has emergency and FIDES guards. | Distributed safety kernel; invariants exist but are not one shared boundary. | PR-04/06/14 |
| Vietnamese UX | Default UI language is Vietnamese and guided flows exist, but locale storage is not a translation system. | Partial. | PR-02/03 |
| Task-first UX | Today, onboarding, medicine add, PHR hub and LifeMap episode flows have focused routes. | Partial; dense legacy surfaces remain. | PR-03/12/15 |
| Model use | DeepSeek runtime, deterministic safety guards, RAG and evaluators exist. | Direct provider-specific paths remain. | PR-04–07 |
| CareGuard | DrugBank ingestion/readiness, DDI safety tests and fail-closed behavior exist. | VN normalization/renderer benchmark remains. | PR-08 |
| Scribe | Consent, grounding and safety tests exist. | Production wording/coding calibration remains. | PR-09 |
| Council | Rules, structured components and ablation script exist. | Hybrid contracts require convergence. | PR-10 |
| Research | Retrieval/RAG and verifier tests exist. | Claim-level evaluation/reporting needs convergence. | PR-11 |
| LifeMap | Revision, provenance, capture review and profile scope exist. | VN query/summary journey remains incremental. | PR-12 |
| Evaluation | `active-eval.yml` and KPI/hard-negative loop exist. | Multi-track CLARA-Eval VN is being added. | PR-13 |
| Operations | Deploy/runbooks, migrations and safety tests exist. | Release manifest, restore and security gate need explicit evidence. | PR-14 |
| Mobile | Unified shell, consent and API tests exist. | Shared locale/contract parity remains. | PR-15 |

## Execution and rollback

Each checkpoint is an ordinary forward commit; no history rewrite or force push
is permitted. Risky model changes are configuration-gated and shadowed first.
Database changes require an Alembic downgrade or documented restore procedure.
The evaluator never sends fixture text, names, email, drug lists, or source
documents to aggregate telemetry.

The implementation ledger is
[`master-implementation-checklist.md`](master-implementation-checklist.md).

## Baseline command record

The repository declares `make lint`, `make type-check` and `make test`, but
this environment has no `make` executable (`make: command not found`). Those
aggregate checks are **not measured** here. Reproduce on a standard developer
or CI image with:

```bash
make lint && make type-check && make test && make docs-check
(cd apps/web && npm run lint && npm run test && npx tsc --noEmit)
```
