# Master implementation checklist (PR-01 to PR-15)

This is a delivery ledger, not proof that a checkpoint is done. The latest
documentation reconciliation deliberately ran no test, build, evaluation or
deployment under the current user direction; recent code checkpoints are
recorded as implementation evidence, not release evidence.

| PR | Scope | State | Evidence gate |
| --- | --- | --- | --- |
| 01 | Audit, ADRs, baseline | implemented | source inventory, ADRs and an explicit static NO-GO baseline |
| 02 | i18n foundation | partial | typed vi/en catalog now covers authenticated shell/Today, consumer chat, consent, LifeMap review, Medicines and multiple Unified mobile journeys (onboarding, LifeMap, Medicines/cabinet, Visits, Family); broader domain migration and a shared generated catalog remain |
| 03 | Personal task-first UX | implemented primary journey | Today exposes the four plain-language consumer tasks; technical evidence pages are hidden from personal navigation but retain compatible deep links |
| 04 | Model registry/contracts | implemented for bounded safety tasks | typed contracts, DeepSeek-only V4 Pro/Flash resolution, deployment environment guard and explicit routing/model rollback configuration; production runtime remains unverified |
| 05 | Vietnamese clinical NLP | implemented v1 | deterministic language cues and regression tests; no bundled encoder SLM |
| 06 | Hybrid task/risk router | partial | semantic closed-schema primary with deterministic safety fallback; governed V4 paths serve safe chat intents and read-only LifeMap asks, while a default-off, redacted Encoder-SLM shadow adapter remains unevaluated |
| 07 | Structured renderer/verifier | implemented deterministic baseline | closed semantic input, independent fidelity verifier, Vietnamese fallback and `medical_answer_v2` integration; human usability metric remains unmeasured |
| 08 | CareGuard VN normalization | partial/pre-existing | DrugBank readiness/fail-closed behavior exists; licensed full benchmark unavailable |
| 09 | Scribe safety refactor | implemented safety correction in code | no automatic R69/code assignment or uncalibrated confidence display; clinician mutations now require consent and a compatible version, but new tests are deferred/not run |
| 10 | Council hybrid shadow | partial | structured intake and ablation path; the fixed-weight shadow is explicitly `rule_shadow`, never a neural model or probability, and reasoning traces are withheld from client/stream output; provisioned LLM/specialist evaluation remains external |
| 11 | Research verifier | partial | claim/citation tracing exists and synchronous result release now passes the verifier gate; reviewed RAG gold set and fresh regression evidence are unavailable |
| 12 | LifeMap VN features | partial | revision/provenance/review exist and read-only asks have a governed V4 route; approved NL-query/visit-summary evaluation remains |
| 13 | CLARA-Eval VN | implemented foundation | nine tracks, manifests, suite configs, judge artifacts, active-eval integration and opt-in approved live execution; no reviewed clinical live manifest is installed |
| 14 | Security/ops hardening | partial | release gate fails closed on missing locked evidence; deployment env guard rejects missing DeepSeek V4 Pro/Flash, DeepSeek-only or task-routing configuration; external operational proof and fresh validation remain |
| 15 | Mobile parity | partial | Unified mobile/locale/consent paths exist; localized onboarding, LifeMap, Medicines/cabinet, Visits and Family flows were added, while device E2E, generated shared terminology and broader parity remain |

## Required exit evidence

- Format, lint and type check relevant code.
- Unit plus API/contract/invariant tests when boundaries change.
- Eval smoke and explicit `not measured` detail for unavailable metrics.
- Web/service build where tooling is available.
- i18n and no-secret/no-PII-log review.
- Rollback and feature-flag state for risky behavior.
- A current run of the above gates after each affected checkpoint; historical
  pass results must not be used as proof for later commits.
