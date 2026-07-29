# Master implementation checklist (PR-01 to PR-15)

This is a delivery ledger, not proof that a checkpoint is done.

| PR | Scope | State | Evidence gate |
| --- | --- | --- | --- |
| 01 | Audit, ADRs, baseline | implemented | source inventory, ADRs and an explicit static NO-GO baseline |
| 02 | i18n foundation | partial | typed vi/en catalog, parity and shell literal checks; domain migration remains |
| 03 | Personal task-first UX | implemented primary journey | Today exposes the four plain-language consumer tasks; technical evidence pages are hidden from personal navigation but retain compatible deep links |
| 04 | Model registry/contracts | implemented for bounded safety tasks | typed contracts, DeepSeek-only resolution and explicit rollback config |
| 05 | Vietnamese clinical NLP | implemented v1 | deterministic language cues and regression tests; no bundled encoder SLM |
| 06 | Hybrid task/risk router | partial/pre-existing | semantic closed-schema primary with deterministic safety fallback; no evaluated SLM shadow |
| 07 | Structured renderer/verifier | implemented deterministic baseline | closed semantic input, independent fidelity verifier, Vietnamese fallback and `medical_answer_v2` integration; human usability metric remains unmeasured |
| 08 | CareGuard VN normalization | partial/pre-existing | DrugBank readiness/fail-closed behavior exists; licensed full benchmark unavailable |
| 09 | Scribe safety refactor | implemented UI correction | no automatic R69/code assignment or uncalibrated confidence display |
| 10 | Council hybrid shadow | partial/pre-existing | structured intake and ablation path; heuristic remains correctly labeled |
| 11 | Research verifier | partial/pre-existing | claim/citation tracing exists; reviewed RAG gold set unavailable |
| 12 | LifeMap VN features | partial/pre-existing | revision/provenance/review exist; approved NL-query evaluation remains |
| 13 | CLARA-Eval VN | implemented foundation | nine tracks, manifests, suite configs, artifacts and active-eval integration |
| 14 | Security/ops hardening | partial | release gate fails closed on missing locked evidence; external operational proof remains |
| 15 | Mobile parity | partial/pre-existing | unified mobile/locale/consent paths exist; shared catalog and device E2E remain |

## Required exit evidence

- Format, lint and type check relevant code.
- Unit plus API/contract/invariant tests when boundaries change.
- Eval smoke and explicit `not measured` detail for unavailable metrics.
- Web/service build where tooling is available.
- i18n and no-secret/no-PII-log review.
- Rollback and feature-flag state for risky behavior.
