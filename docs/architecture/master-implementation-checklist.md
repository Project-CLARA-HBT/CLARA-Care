# Master implementation checklist (PR-01 to PR-15)

This is a delivery ledger, not proof that a checkpoint is done. The latest
documentation reconciliation deliberately ran no test, build, evaluation or
deployment under the current user direction; recent code checkpoints are
recorded as implementation evidence, not release evidence.

| PR | Scope | State | Evidence gate |
| --- | --- | --- | --- |
| 01 | Audit, ADRs, baseline | implemented | source inventory, ADRs and an explicit static NO-GO baseline |
| 02 | i18n foundation | partial | typed vi/en catalog now covers the authenticated shell, auth/onboarding, Today, consumer chat, consent (including the Medicines medical-consent gate), LifeMap review, guided and manual Cabinet entry, Living Evidence, Research/source hub, Community, Scribe Enterprise consent/transcript, note/sign/export, grounding, coding/addendum and process panels, Council setup/review/result and administrative RAG web flows. A generated consumer-terminology contract spans web/mobile. Unified/Redesign mobile coverage now includes onboarding, chat, LifeMap capture/replay/review/questions/baselines, Medicines/cabinet, fixed CareGuard DDI result chrome, redesigned Scribe consent/transcript/session chrome, and Family access-log labels rendered from additive stable API codes with legacy fallbacks, visits, profile/PHR, living evidence, connected health, community, Settings and More. These presentation checkpoints through `01ae02a4` have no fresh test/build/eval/deploy evidence; broader domain migration, scanner coverage and a fully shared generated catalog remain. |
| 03 | Personal task-first UX | implemented primary journey | Today exposes the four plain-language consumer tasks; technical evidence pages are hidden from personal navigation but retain compatible deep links |
| 04 | Model registry/contracts | implemented for bounded safety tasks | typed contracts, DeepSeek-only V4 Pro/Flash resolution, governed default-off Encoder-SLM shadow configuration, deployment environment guard and explicit routing/model rollback configuration. `04aa0095` corrects the mobile static Settings disclosure to describe task-selected Pro/Flash rather than inaccurately claiming Pro for all tasks; per-response disclosure remains API-sourced. The ASR payload/provider route is now registry-owned (`whisper-1` default plus allowlist), so no audio workflow falsely claims V4 Flash or sends audio to a V4 text model. Client generation now enforces each task contract's temperature/token ceiling; the intentional long Research ceiling is versioned at 12,288 tokens. Production runtime remains unverified |
| 05 | Vietnamese clinical NLP | implemented v1 | expanded deterministic language cues; no evaluated/bundled encoder SLM |
| 06 | Hybrid task/risk router | partial | semantic closed-schema primary with deterministic safety fallback; governed V4 paths serve safe chat intents and read-only LifeMap asks, while a default-off, redacted Encoder-SLM shadow adapter remains unevaluated and cannot alter deterministic safety/authorization decisions |
| 07 | Structured renderer/verifier | implemented deterministic baseline | closed semantic input, independent fidelity verifier, Vietnamese fallback and `medical_answer_v2` integration; normal and emergency paths preserve requested UI locale; human usability metric remains unmeasured |
| 08 | CareGuard VN normalization | partial/pre-existing | strict operation now requires a mounted signed release whose SQLite index, manifest/checksums and DDI plus dictionary inventories agree; no LLM substitutes for an unavailable release. The latest mobile DDI localization changes fixed presentation chrome only and preserve API-provided alert text, risk and DrugBank authority. Licensed full benchmark/index material remains unavailable in this checkout. |
| 09 | Scribe safety refactor | implemented safety correction in code | no automatic R69/code assignment or uncalibrated confidence display; clinician mutations require consent and a compatible version. Latest Enterprise and redesigned-mobile Scribe localization (`b6f6c034`, `b68b0899`, `39e04607`, `b9822d54`, `3ffba4e8`, `8c75a628`, `8f5ad61f`, `6a866b15`) is presentation-only and does not change those safety semantics; fresh tests are deferred/not run |
| 10 | Council hybrid shadow | partial | structured intake and ablation path; the fixed-weight shadow is explicitly `rule_shadow`, never a neural model or probability, and reasoning traces plus uncalibrated intake confidence are withheld from client/stream output. Setup/review/result localization exists; provisioned LLM/specialist evaluation remains external |
| 11 | Research verifier | partial | claim/citation tracing exists and synchronous result release now passes the verifier gate; explicitly retracted external records are filtered before final evidence selection. Reviewed RAG gold set and fresh regression evidence are unavailable |
| 12 | LifeMap VN features | partial | revision/provenance/review exist, read-only asks have a governed V4 route, and immutable revision comparison is read-only; approved NL-query/visit-summary evaluation remains |
| 13 | CLARA-Eval VN | implemented foundation | nine tracks, manifests, suite configs, judge artifacts, active-eval integration and opt-in approved live execution; no reviewed clinical live manifest is installed |
| 14 | Security/ops hardening | partial | release gate fails closed on missing locked evidence. Compose variants explicitly receive governed Scribe, ASR, Encoder-SLM-shadow and CareGuard-wording controls; deployment validation rejects missing DeepSeek V4 Pro/Flash, DeepSeek-only, task-routing or strict-DrugBank prerequisites. Family Circle now uses localized generic mutation/load errors rather than raw errors. Docker/image build, provider availability and production operational proof remain unverified. |
| 15 | Mobile parity | partial | Unified mobile/locale/consent paths exist; catalog-backed onboarding, chat, LifeMap capture/replay/review/questions/baselines, Medicines/cabinet, fixed CareGuard DDI result chrome, visits, Family/visit detail and access-log rendering from compatible stable codes, profile/PHR, living evidence, connected health, community, Settings and More flows were added. A focused Family API contract test was added in `01ae02a4` but not run. A generated consumer-terminology contract exists; device E2E and broader parity remain. |

## Required exit evidence

- Format, lint and type check relevant code.
- Unit plus API/contract/invariant tests when boundaries change.
- Eval smoke and explicit `not measured` detail for unavailable metrics.
- Web/service build where tooling is available.
- i18n and no-secret/no-PII-log review.
- Rollback and feature-flag state for risky behavior.
- A current run of the above gates after each affected checkpoint; historical
  pass results must not be used as proof for later commits.
