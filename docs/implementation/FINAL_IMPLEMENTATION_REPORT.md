# CLARA master implementation report

Status date: 2026-07-31. This report is evidence-first: it distinguishes
implemented code from planned, blocked and unmeasured work. It does not claim
clinical validation, a human evaluation, production deployment, or a benchmark
result that was not actually run.

Reconciliation checkpoint: this document was updated after the recent V4,
LifeMap, Research, Scribe, Council, CareGuard, deployment and i18n commits,
including `8bd27232` through `b7327001`. Per the current user direction, this
documentation-only checkpoint did **not** run format, lint, type checks,
tests, builds, evaluation or deployment. Earlier execution records below are
historical evidence only; they do not validate commits made after those runs.

## Executive summary

This implementation pass strengthened CLARA's safety and evidence boundaries:

- added a typed, checksum-locked CLARA-Eval VN foundation and judge artifacts;
- added a typed Vietnamese/English catalog for the authenticated web shell;
- routed safety, LifeMap, Scribe and Council bounded LLM calls through typed
  model task contracts with a rollback switch;
- set the governed runtime configuration to DeepSeek V4 Pro and Flash task
  profiles, with deployment-time guards for an explicit Pro default, distinct
  Flash profile and task-routing switch;
- added an auditable Vietnamese clinical language pre-processing layer;
- added a structured wording renderer with an independent fidelity verifier and
  deterministic Vietnamese fallback;
- made Today start with the four consumer care tasks instead of requiring a
  person to navigate technical module names;
- removed Scribe's automatic code assignment (including fallback `R69`) and
  fabricated end-user “AI confidence” percentage;
- added consent- and version-bound Scribe clinician edits, a verifier gate for
  synchronous Research results, a governed V4 LifeMap ask path, and a Council
  client boundary which withholds reasoning traces.
- removed the remaining production runtime model/provider configuration seam
  from Research and Control Tower: those paths now reuse the registry-built
  task client and ignore historical `llm_runtime`/`llm_*` JSON keys;
- strengthened a strict CareGuard rollout so a full DrugBank release is
  authoritative only when its mounted manifest, SQLite index and dictionary
  counts match; and
- expanded catalog-backed Vietnamese/English wording across login/onboarding,
  Research, Community, Scribe, administrative RAG, and the corresponding
  Unified/Redesign mobile journeys (chat, profile/PHR, evidence, connected
  health, community, Settings and More);
- added a generated web/mobile consumer-terminology contract, localized the
  Council setup/review/result journey and the guided medicine-entry flow, and
  extended the Unified mobile LifeMap flow through capture, replay, review,
  question and baseline steps;
- preserved the requested UI locale when the normal clinical-answer path
  builds its independently verified structured explanation;
- excluded records explicitly marked retracted by external Research sources
  before they reach the RAG evidence set; and
- added a read-only comparison of immutable LifeMap revisions. It does not
  mutate truth-state, provenance, confirmation state or revision history.
- localized the fixed mobile CareGuard DDI result chrome and the web
  medication-consent gate. These presentation changes do not rewrite clinical
  alerts, change DDI risk, alter DrugBank data or relax consent gating.

The repository already contained significant LifeMap, CareGuard, Council,
Research and mobile work. The work above integrates with those safety
boundaries without weakening RBAC, consent, CSRF, emergency handling, FIDES,
no-PII telemetry or LifeMap confirmation/provenance rules.

## Current and target architecture

Current request flow remains Web/Mobile → API → ML. Deterministic policy owns
authorization, consent, state transition, audit, emergency fast-path, final
DrugBank DDI authority and confirmed LifeMap writes. The new target selection
boundary is `clara_ml.llm.model_registry`: a bounded task resolves to the
configured DeepSeek V4 Pro or Flash profile, a versioned prompt/output contract
and a safe fallback. `DEEPSEEK_MODEL` is guarded to the Pro profile; Flash is
for contract-approved bounded work. No end-user request selects a provider or
model. These are repository/runtime-config changes only: no production
environment or provider availability was verified in this checkpoint.

The Vietnamese language layer is deterministic pre-processing only. It retains
source text and exposes normalized language cues to model contracts; it is not
represented as a neural model. Semantic LLM classification remains bounded to
closed JSON and is followed by deterministic safety policy.

## PR/checkpoint summary

| PR | Status | Evidence / limitation |
| --- | --- | --- |
| PR-01 Audit/ADRs | implemented | Architecture inventory, ADRs and master ledger: `919b8ba7`; static active-eval baseline is NO-GO (`442c85e5`). |
| PR-02 i18n | partial | Typed vi/en catalog now covers the authenticated shell, auth/onboarding, Today, consumer chat, consent (including the Medicines medical-consent gate), LifeMap review, Medicines (including guided entry), Living Evidence, Research/source hub, Community, Scribe, Council setup/review/result and administrative RAG web flows. `fca5fba9` adds a generated web/mobile consumer-terminology contract. Unified/Redesign mobile catalog work now also covers onboarding, chat, LifeMap capture/replay/review/questions/baselines, Medicines/cabinet, CareGuard DDI result chrome, visits, family, profile/PHR, living evidence, connected health, community, Settings and More. Locale-aware dates/numbers were added where these surfaces own them. Static strings and other web/mobile domain surfaces remain; no fresh verification was run for these localization commits. |
| PR-03 task-first UX | implemented primary journey | Today now begins with four consumer tasks (ask, medicine check, save visit information, prepare visit). Research/evidence remain deep-link-compatible but no longer crowd personal navigation. Dense legacy surfaces remain. |
| PR-04 registry/contracts | implemented for bounded tasks | Safety triage, LifeMap capture/visit/ask, Scribe, Council shadow, RAG reranking/NLI, RAG synthesis and Research planning/reasoning use registry task contracts. `8bd27232` removes the explicit Research/RAG runtime override seam and ignores historical Control Tower/provider JSON keys, so request payloads and queued jobs cannot select a provider, endpoint, model or key. `59e63b90` makes the optional external Encoder-SLM shadow adapter resolve exclusively through its closed, shadow-only registry contract. The governed configuration routes V4 Pro to safety/reasoning and V4 Flash to bounded extraction/reranking/planning; deployment validation requires the distinct profiles, DeepSeek-only mode and task routing. `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED=false` restores the legacy single configured DeepSeek model, while explicit rollback selects a known prior model. Runtime deployment remains unverified. |
| PR-05 Vietnamese clinical layer | implemented v1 | `1f16c7c6` adds normalization, typo handling, negation, experiencer, temporality, units and medication aliases; `70cc2877` expands the deterministic fallback clinical-language layer. The hybrid-router shadow contract carries only categorical/count language signals (never source text). No evaluated encoder SLM is bundled. |
| PR-06 hybrid router | partial | Closed-schema semantic safety router has deterministic emergency/legal fallback. Safe chat intents and LifeMap ask requests have governed V4 task paths, but deterministic emergency/legal policy remains authoritative. `clara_ml.model_router` supplies a typed metadata-only shadow route; the external Encoder-SLM is still default-off and cannot alter a deterministic emergency/legal outcome, authorization, consent, DrugBank or confirmed LifeMap write. An evaluated encoder/SLM classifier is not installed. |
| PR-07 renderer | implemented deterministic baseline | Structured input, audience templates, independent fidelity verifier and deterministic Vietnamese fallback are integrated into `medical_answer_v2`. `fba3e639` preserves the selected UI locale in the normal response path as well as the emergency path. A reviewed human-usability score remains unmeasured. |
| PR-08 CareGuard | partial/pre-existing | DrugBank SQLite readiness/fail-closed path exists. `d12d15e0` requires source release/hash, canonical manifest digest, per-shard checksums and matching DDI **and** dictionary table counts before a strict full release is authoritative; deterministic Vietnamese alias matches expose DrugBank/RxCUI traceability without guessing. The deployment environment guard rejects a strict rollout without a real mounted artifact directory, SQLite, manifest integrity or required paths. Feature-flagged `CAREGUARD_WORDING_RENDERER_ENABLED` adds an optional consumer explanation only after final deterministic facts, through the fidelity verifier; it neither reads raw medication names nor changes DrugBank/risk/alerts/recommendation. `d6a9371c` localizes fixed mobile DDI chrome only; API-provided clinical alerts remain authoritative text. Licensed full-DrugBank benchmark data is unavailable in this checkout. |
| PR-09 Scribe | implemented safety correction in code | `eaa749c0` removes automatic code/R69 and uncalibrated percentage. `0c6b268d` additionally requires consent for clinician-edit mutations and applies version-aware edit conflict handling. The new endpoint and client tests were added but not run in this checkpoint. |
| PR-10 Council | partial | Structured intake, specialist/shadow and ablation paths exist; fixed-weight heuristic does not drive deterministic triage and the consumer UI no longer presents it as neural or as a percentage. `ee156724` removes reasoning-trace fields from ML streaming/client presentation; `d153d79b` suppresses uncalibrated intake confidence; `89b1aade` and `8fdfac33` localize the setup, review and result journey. These changes do not establish a clinical specialist evaluation. |
| PR-11 Research verifier | partial/pre-existing | Claim/citation tracing and research-quality harness exist. `9ce7d6d3` makes synchronous Research responses pass the verifier gate before release. `9f71e9fd` filters explicitly retracted external records before final RAG evidence selection. A reviewed RAG gold set and current regression execution are absent. |
| PR-12 LifeMap | partial/pre-existing | Revision/provenance/capture review and Vietnamese locale support exist. `6294386d` adds a governed V4 LifeMap ask path that is read-only and retains the existing confirmation/truth-state boundary. `47162ccc` adds a read-only comparison between immutable revision snapshots, without modifying source revisions or truth-state. Broader NL-query/visit-summary evaluation needs approved cases. |
| PR-13 CLARA-Eval VN | implemented foundation | `0b103426`: nine tracks, suite configs, manifests, smoke/nightly/release/judge artifacts and CI integration. `59722a20` adds metric-specific evidence gaps and exact measurement commands for all six judge headlines. Product quality metrics remain `not_measured` until approved data/execution exists. |
| PR-14 security/ops | partial | Release gate now fails closed on missing locked evidence. Security checkpoints upgrade Axios and its HTTP/form transitive closure, Next 15.5.22, Mermaid 10.9.6, DOMPurify 3.4.12, UUID 14.0.1 and Playwright 1.62.0. `012e0b5b` wires Scribe stage flags, ASR controls, Encoder-SLM shadow controls and CareGuard wording controls into both application compose variants instead of relying on `--env-file` substitution alone; its environment guard also rejects an unprovisioned strict DrugBank mount. The existing guard rejects a deployment environment that lacks governed V4 Pro/Flash configuration, DeepSeek-only mode or enabled task routing. CI now requires web Vitest and production-artifact Playwright E2E gates when web/CI changes; the local production-dependency audit historical record decreased from 11 (7 high, 4 moderate) to 3 high, all in the Next/PostCSS/Sharp chain without a compatible audit-proposed fix. Restore/security certification evidence, current scan results and the remaining dependency remediation remain external/ongoing work. |
| PR-15 mobile parity | partial/incremental | Unified mobile, locale wiring and consent paths exist. In addition to the shell/Profile hub locale checkpoints, catalog work covers onboarding, chat, LifeMap planning/capture/replay/review/questions/baselines, Medicines hub/cabinet, fixed CareGuard DDI result chrome, Visits, Family/visit detail, PHR, living evidence, connected health, community, Settings and More. `fca5fba9` provides a generated shared consumer-terminology contract rather than claiming a fully shared UI catalog. Device E2E execution and fresh verification of these commits remain outstanding. |

## Features and safety invariants preserved

- RBAC/profile isolation, consent and cookie CSRF remain API-owned.
- Emergency fast-path remains deterministic and does not wait for model output.
- FIDES/claim verification and DrugBank authority are unchanged.
- The optional CareGuard wording projection is OFF by default, is derived only
  from final risk/readiness/provenance categories, and cannot make a required
  DrugBank source failure look like an all-clear.
- Registry task contracts retain DeepSeek-only behavior and a controlled rollback:
  `MODEL_REGISTRY_ENABLED`, `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED`,
  `MODEL_REGISTRY_FORCE_ROLLBACK` and `MODEL_REGISTRY_ROLLBACK_MODEL`.
- V4 task selection never changes deterministic emergency, authorization,
  consent, DrugBank, confirmed LifeMap-write or final safety-policy decisions.
- Research/RAG and Control Tower configuration cannot reintroduce an
  end-user- or job-selected LLM provider, endpoint, model or API key; their
  historical runtime keys are ignored and omitted on write.
- Strict CareGuard operation requires a verified mounted DrugBank release with
  matching DDI and dictionary inventory. It never substitutes a curated rule
  set or LLM conclusion when that release is unavailable.
- Council reasoning is not released through the consumer client/streaming view;
  only the permitted conclusion structure remains available.
- Scribe clinician changes are consent-gated and version-aware; they do not
  restore automatic coding or uncalibrated confidence.
- Eval manifests and reports do not copy secret values, PHI, prompts or patient
  text; their fixture policy rejects PHI/secrets.
- Scribe no longer assigns diagnosis/procedure codes from regex text and no
  longer renders an uncalibrated confidence percentage.
- The renderer emits consumer wording only from released severity/action/
  warning/uncertainty fields; its independent verifier rejects missing
  warnings, softened uncertainty, added dose text and unapproved prescribing
  language before a response is released.

## Tests and evaluation evidence

The table below records historical executions in this workspace. It is not a
current green status. Per current user direction, no format/lint/type check,
unit/integration/contract/migration/safety test, eval smoke, build, secret/PII
review, E2E run or deployment was run after the following newer commits:
`716e062d`, `6294386d`, `9ce7d6d3`, `0c6b268d`, `ee156724`, `81d1d6b9`,
`39de7393`, `99ab3182`, `0a6cee55`, `bd9a07e0`, `b30f2608`, `d182fc31`,
`2b0bf003`, `cc60d16d`, `6cf1bc39`, `1dbe8c1f`, `6364da91`, `5f8151e0`,
`8bd27232`, `daf1e551`, `1bf5a214`, `d12d15e0`, `012e0b5b`, `511107f9`,
`4e898cab`, `33cb11ec`, `b15210a2`, `f1eb4fa2`, `26547a8f`, `a4989c14` and
`3d90e878`, `43102b4a`, `1b6c7cbd`, `85c8e5b4`, `027423b1`, `d153d79b`,
`70cc2877`, `59e63b90`, `fca5fba9`, `c872746c`, `9f71e9fd`, `c4249152`,
`59037f19`, `47162ccc`, `89b1aade`, `c0ac3777`, `3628db26`, `8fdfac33`,
`d6a5abc5`, `fba3e639`, `f24ee6f4`, `b0ac6e40`, `d6a9371c` and `b7327001`.
Tests added in those commits are therefore **not run**, rather than pass or
fail.

Historical executions:

| Check | Result |
| --- | --- |
| Web lint + TypeScript | pass for i18n and Scribe checkpoints |
| Web full unit/property suite | pass: 75 files, 638 tests |
| Eval formatting/Ruff/mypy | pass: 12 files; mypy clean |
| Eval unit suite | pass: 8 tests |
| Eval manifest validator | pass: 9 required tracks, checksums/counts validated |
| Eval smoke and judge runner | pass via `python -m evaluation.clara_eval.run ...` |
| Eval release suite | expected non-zero (2): no approved locked/live evidence; diagnostics written |
| Model registry focused suite | pass: 39 tests (registry, Council shadow, capture triage, main API) |
| RAG registry runtime seam | pass: 34 focused RAG/registry tests; direct provider construction is absent from `rag/pipeline.py` |
| RAG full Ruff/mypy | not clean: focused undefined-name Ruff check passed, but the existing full selected files report 60 Ruff findings and 52 mypy findings; they were not suppressed or weakened by this work. |
| Vietnamese language/router focused suite | pass: 14 tests |
| LifeMap intelligence/invariant suite | pass: 9 tests (read-only ask, exact revision citations, profile scope and truth-state-preserving summaries) |
| CareGuard normalization/DrugBank focused suite | pass: 42 tests |
| CareGuard structured wording adapter | pass: 35 focused renderer/guardrail/DrugBank tests; default flag preserves the old response, enabled flag adds only a verified consumer projection. |
| Current web production build | pass: Next production build completed after current UI/router checkpoints |
| Renderer contract/fidelity + emergency response integration | pass: 18 focused tests; Ruff and mypy clean for renderer and `medical_answer_v2` |
| Task-first Today/navigation | pass: focused lint, TypeScript and 11 navigation/i18n/static surface tests |
| Guided-flow locale bridge | pass: Prettier, targeted ESLint, TypeScript, catalog tests and 13 guided-flow tests; test switches the global locale and observes English progress/save wording. |
| Web dependency security checkpoint | pass: full web lint, TypeScript, production build and 75 test files / 639 tests after targeted Axios/Next/Mermaid/DOMPurify/UUID/Playwright updates; `npm audit --omit=dev --json` recorded 11→3 vulnerabilities (7 high/4 moderate → 3 high). |
| Web E2E first retry | fail before assertions: Playwright standalone production server exceeded the prior 120-second build startup timeout. The bounded timeout is now 300 seconds and the retry is pending; no E2E assertion is claimed as passed. |
| Mobile Unified locale navigation | pass: `flutter test test/unified_root_test.dart` (5 tests) and targeted `flutter analyze` (no issues) |
| Mobile Profile hub locale | pass: `flutter test test/unified_root_test.dart` (6 tests), `flutter test test/unified_a11y_responsive_test.dart` (12 tests), targeted `flutter analyze`, and Dart format. |
| Mobile debug APK build | environment-blocked: Snap Flutter reported missing `cap_dac_override`; no APK result is claimed |
| Static active-eval | executed after portable previous-run selector fix, NO-GO as expected; it recorded zero runtime measurements and no latency samples |

At the time of the historical run, `make` was unavailable in this workspace
(`make: command not found`), so `make eval-judge-report` was not invoked
literally. The exact Python command behind that target was recorded as having
been executed successfully then; this reconciliation does not re-run it. The
API full suite has no confirmed terminal result: its first execution detached
before a summary and a background log rerun was stopped by the environment
before it wrote output. Do not infer its status from focused tests; run the
direct command below before release.

## Evaluation results, critical errors and cost/latency

`artifacts/judge-report/` is generated on demand and is ignored by git. The
judge landing page shows exactly the six requested judge headline measures
(Vietnamese emergency recall, medication-normalization top-1, severe DrugBank
DDI recall, unsupported RAG claim rate, Scribe clinician edit-time reduction,
and router large-LLM cost reduction). The report emits one genuine measurement:
checked-in fixture manifest integrity.
All clinical quality, human usability, DrugBank recall, ASR WER, RAG quality,
Council ablation, model latency and cost metrics are explicitly `not_measured`
with a reason and a command. This repository contains no approved reviewed
corpus, immutable retrieval snapshot, licensed full DrugBank benchmark, live
provider trace, cost ledger or human-study result to compute them.

Manifest version `2026-07-30.foundation.2` records a specific evidence gap for
each headline, rather than falling back to a generic report message: noisy
Vietnamese emergency corpus, pharmacist-adjudicated Vietnamese medication
mapping, licensed full-DrugBank pairs/index, Vietnamese gold claims with an
immutable retrieval snapshot, consented clinician edit-time study, and an
aggregate routing usage ledger respectively. These entries are metadata only,
not benchmark values.

The static active-eval baseline is NO-GO, not a release approval: its DDI,
fallback and refusal runtime counts were zero and latency samples were absent.
There are no measured before/after clinical or cost/latency improvements.

## Data migrations and rollback

No database migration was added in these latest checkpoints. Roll back a checkpoint
by deploying its prior commit after preserving the current database and audit
trail; do not rewrite history. For a governed V4 task-routing incident, first
set `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED=false` to use the legacy single
configured DeepSeek model. If a model rollback is needed, set an explicit known
prior model in `MODEL_REGISTRY_ROLLBACK_MODEL`, enable
`MODEL_REGISTRY_FORCE_ROLLBACK`, restart ML, then run `make eval-smoke` when
testing resumes. Disable the force flag after recovery.

## External blockers and remaining work

1. Approved locked clinical datasets, clinician review and immutable retrieval
   snapshots are unavailable. Run `make eval-nightly` after provisioning them;
   then run `make eval-release` for a release decision.
2. Licensed full DrugBank benchmark/index material is unavailable in this
   checkout. Provision it only server-side, then run `make eval-release`.
3. No live provider cost/latency trace is installed. Collect sanitized,
   aggregate routing telemetry and run `make eval-nightly`.
4. Full web/domain-page i18n and common mobile terminology are not yet fully
   catalog-backed. Recent auth/onboarding, chat, consent, LifeMap, Medicines,
   Research, Community, Council, Scribe/admin RAG, PHR/evidence,
   connected-health and Settings/More checkpoints make substantial progress.
   A generated consumer-terminology contract now exists, but it is not a full
   shared/generated UI catalog. Continue migration surface by surface with
   parity tests; do not label it complete before scanner scope covers them.
5. RAG synthesis, reranking, NLI verification and Research planning/reasoning
   are registry-bound, and historical provider/runtime JSON inputs are ignored.
   The refactor has not received a fresh full authorization, contract or
   regression run; execute those deferred gates before treating the boundary as
   release evidence.
6. Production deployment was not attempted in this checkpoint per user
   direction. Before deployment, set the production environment's governed
   `DEEPSEEK_MODEL`, `DEEPSEEK_PRO_MODEL`, `DEEPSEEK_FLASH_MODEL`,
   `LLM_DEEPSEEK_ONLY`, `MODEL_REGISTRY_ENABLED` and
   `MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED` values. If strict CareGuard is
   enabled, also provision the licensed artifact mount and keep SQLite/manifest
   integrity enabled. Run the runtime guard and the deferred release validation
   before a deploy. No current server capacity, artifact availability or
   provider-availability assertion is made here.
7. Docker/container execution is unverified in this checkpoint: no current
   image build, registry push, daemon availability or deployment-host access is
   asserted. Before a release, use a provisioned Docker-capable CI/deployment
   environment to build the affected images, run the runtime guard against the
   actual protected environment file, and retain the resulting image digest for
   rollback.
8. GitHub's push response was observed moving from 130 to 100 and then to 59
   dependency advisories on the default branch after this dependency refresh
   (latest observed: 1 critical, 28 high, 22 moderate, 8 low). Targeted web
   lock upgrades reduced the local
   production-dependency audit from 11 to 3, but this does not establish that
   GitHub's cross-ecosystem advisory total is resolved. The three remaining
   web findings are in the Next/PostCSS/Sharp chain; the audit metadata offers
   no compatible Next 15 fix. Assess a Next 16/React migration separately with
   service and web regression evidence rather than forcing a misleading
   downgrade.

## Exact local, CI and evaluation commands

```bash
# quality and service tests (standard developer/CI image)
make lint && make type-check && make test && make docs-check
cd apps/web && npm run lint && npx tsc --noEmit && npm run test && npm run build

# before any strict CareGuard deployment (does not print licensed artifact data)
REQUIRE_DEEPSEEK=true scripts/ops/validate_runtime_env.sh /opt/clara-care/.env

# Docker-capable local/CI environment: validate resolved compose and build/start
# only after the quality gates above. This was not run for this checkpoint.
make check-env
docker compose --env-file .env -f deploy/docker/docker-compose.app.yml config
make docker-app-up

# authorized deployment host only, after a protected environment file, licensed
# DrugBank mount and release image digests have been provisioned
REQUIRE_DEEPSEEK=true scripts/deploy/redeploy_app_stack.sh /opt/clara-care

# CLARA-Eval VN
make eval-smoke
make eval-nightly
make eval-release
make eval-judge-report

# direct fallback when make is unavailable
PYTHONPATH=services/api/src services/api/.venv/bin/pytest -q services/api/tests
python -m evaluation.clara_eval.run \
  --config evaluation/configs/judge_demo.yaml \
  --output artifacts/judge-report

# static active-eval baseline (does not substitute for live metrics)
bash scripts/demo/run_active_eval_loop.sh \
  --run-id local-static-baseline --mode static --strict false
```
