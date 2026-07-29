# CLARA master implementation report

Status date: 2026-07-30. This report is evidence-first: it distinguishes
implemented code from planned, blocked and unmeasured work. It does not claim
clinical validation, a human evaluation, production deployment, or a benchmark
result that was not actually run.

## Executive summary

This implementation pass strengthened CLARA's safety and evidence boundaries:

- added a typed, checksum-locked CLARA-Eval VN foundation and judge artifacts;
- added a typed Vietnamese/English catalog for the authenticated web shell;
- routed safety, LifeMap, Scribe and Council bounded LLM calls through typed
  model task contracts with a rollback switch;
- added an auditable Vietnamese clinical language pre-processing layer;
- removed Scribe's automatic code assignment (including fallback `R69`) and
  fabricated end-user “AI confidence” percentage.

The repository already contained significant LifeMap, CareGuard, Council,
Research and mobile work. The work above integrates with those safety
boundaries without weakening RBAC, consent, CSRF, emergency handling, FIDES,
no-PII telemetry or LifeMap confirmation/provenance rules.

## Current and target architecture

Current request flow remains Web/Mobile → API → ML. Deterministic policy owns
authorization, consent, state transition, audit, emergency fast-path, final
DrugBank DDI authority and confirmed LifeMap writes. The new target selection
boundary is `clara_ml.llm.model_registry`: a bounded task resolves to the
configured DeepSeek client, a versioned prompt/output contract and a safe
fallback. No end-user request selects a provider or model.

The Vietnamese language layer is deterministic pre-processing only. It retains
source text and exposes normalized language cues to model contracts; it is not
represented as a neural model. Semantic LLM classification remains bounded to
closed JSON and is followed by deterministic safety policy.

## PR/checkpoint summary

| PR | Status | Evidence / limitation |
| --- | --- | --- |
| PR-01 Audit/ADRs | implemented | Architecture inventory, ADRs and master ledger: `919b8ba7`; static active-eval baseline is NO-GO (`442c85e5`). |
| PR-02 i18n | partial | Typed vi/en catalog, parity tests and shell/Today literal scanners; `/today` now reacts to locale with locale date formatting. Domain-page migration remains incremental. |
| PR-03 task-first UX | implemented primary journey | Today now begins with four consumer tasks (ask, medicine check, save visit information, prepare visit). Research/evidence remain deep-link-compatible but no longer crowd personal navigation. Dense legacy surfaces remain. |
| PR-04 registry/contracts | implemented for bounded safety tasks | Safety triage, LifeMap capture/visit, Scribe, Council shadow, RAG reranking/NLI and default RAG synthesis use registry task contracts. Research-agent construction remains migration work. |
| PR-05 Vietnamese clinical layer | implemented v1 | `1f16c7c6` adds normalization, typo handling, negation, experiencer, temporality, units and medication aliases. No encoder SLM is bundled. |
| PR-06 hybrid router | partial | Closed-schema semantic safety router has deterministic emergency/legal fallback. `clara_ml.model_router` now supplies a typed metadata-only shadow route which only raises risk; an evaluated encoder/SLM classifier is not installed. |
| PR-07 renderer | implemented deterministic baseline | Structured input, audience templates, independent fidelity verifier and deterministic Vietnamese fallback are integrated into `medical_answer_v2`. A reviewed human-usability score remains unmeasured. |
| PR-08 CareGuard | partial/pre-existing | DrugBank SQLite readiness/fail-closed path exists. Licensed full-DrugBank benchmark data is unavailable in this checkout. |
| PR-09 Scribe | implemented UI safety correction | `eaa749c0` removes automatic code/R69 and uncalibrated percentage. Existing grounding/ASR tests remain. |
| PR-10 Council | partial | Structured intake, specialist/shadow and ablation paths exist; fixed-weight heuristic does not drive deterministic triage and the consumer UI no longer presents it as neural or as a percentage. |
| PR-11 Research verifier | partial/pre-existing | Claim/citation tracing and research-quality harness exist; reviewed RAG gold set is absent. |
| PR-12 LifeMap | partial/pre-existing | Revision/provenance/capture review and Vietnamese locale support exist; broader NL-query/visit-summary evaluation needs approved cases. |
| PR-13 CLARA-Eval VN | implemented foundation | `0b103426`: nine tracks, suite configs, manifests, smoke/nightly/release/judge artifacts and CI integration. Product quality metrics remain `not_measured` until approved data/execution exists. |
| PR-14 security/ops | partial | Release gate now fails closed on missing locked evidence; restore/security certification evidence remains an external operational task. |
| PR-15 mobile parity | partial/pre-existing | Unified mobile, locale wiring and consent paths exist; a shared web/mobile catalog and device E2E execution require Flutter tooling/device availability. |

## Features and safety invariants preserved

- RBAC/profile isolation, consent and cookie CSRF remain API-owned.
- Emergency fast-path remains deterministic and does not wait for model output.
- FIDES/claim verification and DrugBank authority are unchanged.
- Registry task contracts retain DeepSeek-only behavior and a controlled rollback:
  `MODEL_REGISTRY_ENABLED`, `MODEL_REGISTRY_FORCE_ROLLBACK` and
  `MODEL_REGISTRY_ROLLBACK_MODEL`.
- Eval manifests and reports do not copy secret values, PHI, prompts or patient
  text; their fixture policy rejects PHI/secrets.
- Scribe no longer assigns diagnosis/procedure codes from regex text and no
  longer renders an uncalibrated confidence percentage.
- The renderer emits consumer wording only from released severity/action/
  warning/uncertainty fields; its independent verifier rejects missing
  warnings, softened uncertainty, added dose text and unapproved prescribing
  language before a response is released.

## Tests and evaluation evidence

Executed in this workspace:

| Check | Result |
| --- | --- |
| Web lint + TypeScript | pass for i18n and Scribe checkpoints |
| Web full unit/property suite | pass: 74 files, 635 tests |
| Eval formatting/Ruff/mypy | pass: 12 files; mypy clean |
| Eval unit suite | pass: 8 tests |
| Eval manifest validator | pass: 9 required tracks, checksums/counts validated |
| Eval smoke and judge runner | pass via `python -m evaluation.clara_eval.run ...` |
| Eval release suite | expected non-zero (2): no approved locked/live evidence; diagnostics written |
| Model registry focused suite | pass: 39 tests (registry, Council shadow, capture triage, main API) |
| Vietnamese language/router focused suite | pass: 14 tests |
| LifeMap intelligence/invariant suite | pass: 9 tests (read-only ask, exact revision citations, profile scope and truth-state-preserving summaries) |
| CareGuard normalization/DrugBank focused suite | pass: 42 tests |
| Current web production build | pass: Next production build completed after current UI/router checkpoints |
| Renderer contract/fidelity + emergency response integration | pass: 18 focused tests; Ruff and mypy clean for renderer and `medical_answer_v2` |
| Task-first Today/navigation | pass: focused lint, TypeScript and 11 navigation/i18n/static surface tests |
| Static active-eval | executed, NO-GO; it recorded zero runtime measurements and no latency samples |

`make` itself is unavailable in this workspace (`make: command not found`), so
`make eval-judge-report` could not be invoked literally here. The exact Python
command behind that target was executed successfully. CI runners invoke the
same target/runner. The API full suite has no confirmed terminal result: its
first execution detached before a summary and a background log rerun was
stopped by the environment before it wrote output. Do not infer its status from
focused tests; run the direct command below before release.

## Evaluation results, critical errors and cost/latency

`artifacts/judge-report/` is generated on demand and is ignored by git. The
report emits one genuine measurement: checked-in fixture manifest integrity.
All clinical quality, human usability, DrugBank recall, ASR WER, RAG quality,
Council ablation, model latency and cost metrics are explicitly `not_measured`
with a reason and a command. This repository contains no approved reviewed
corpus, immutable retrieval snapshot, licensed full DrugBank benchmark, live
provider trace, cost ledger or human-study result to compute them.

The static active-eval baseline is NO-GO, not a release approval: its DDI,
fallback and refusal runtime counts were zero and latency samples were absent.
There are no measured before/after clinical or cost/latency improvements.

## Data migrations and rollback

No database migration was added in these checkpoints. Roll back a checkpoint
by deploying its prior commit after preserving the current database and audit
trail; do not rewrite history. For model incidents, disable the affected
feature flag, set the explicit known prior model in
`MODEL_REGISTRY_ROLLBACK_MODEL`, enable `MODEL_REGISTRY_FORCE_ROLLBACK`, restart
ML, then run `make eval-smoke`. Disable the force flag after recovery.

## External blockers and remaining work

1. Approved locked clinical datasets, clinician review and immutable retrieval
   snapshots are unavailable. Run `make eval-nightly` after provisioning them;
   then run `make eval-release` for a release decision.
2. Licensed full DrugBank benchmark/index material is unavailable in this
   checkout. Provision it only server-side, then run `make eval-release`.
3. No live provider cost/latency trace is installed. Collect sanitized,
   aggregate routing telemetry and run `make eval-nightly`.
4. Full web/domain-page i18n and common mobile terminology are not yet fully
   catalog-backed. Continue catalog migration surface by surface with parity
   tests; do not label it complete before the scanner scope covers them.
5. RAG synthesis and research-agent direct model-client constructors remain to
   be migrated to the model registry; add a task contract and regression tests
   before each move. Reranking and NLI verification are already registry-bound.
6. Server deploy remains blocked by the previously observed low remote disk
   capacity; do not rebuild remotely until capacity is restored.
7. GitHub reported 130 dependency advisories on the default branch at push time
   (1 critical, 51 high, 63 moderate, 15 low). They were not remediated in this
   safety/evaluation checkpoint and require a separately reviewed dependency
   upgrade pass with service and web regression evidence.

## Exact local, CI and evaluation commands

```bash
# quality and service tests (standard developer/CI image)
make lint && make type-check && make test && make docs-check
cd apps/web && npm run lint && npx tsc --noEmit && npm run test && npm run build

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
