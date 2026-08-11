# CommitLoop / GLHS ExecPlan

## Scope

CommitLoop is an additive, evaluation-first layer for reconciling a
future-oriented clinical commitment against later, provenance-linked evidence.
The existing GLHS ledger and its profile state counter remain canonical.

## Phase A constraints

- No request to the evaluation router or either evaluation model.
- No production runtime/provider changes and no End_User model selection.
- Model outputs remain reviewable proposals; deterministic code owns predicate
  validation, gold construction, reconciliation, and commit decisions.
- Real-EHR and clinical-adjudication work is **BLOCKED_EXTERNAL / NOT RUN**.

## Checkpoints

| Checkpoint | Status | Evidence / next action |
| --- | --- | --- |
| A. Baseline audit | complete | Existing GLHS migrations end at `20260810_0053`; no CommitLoop namespace exists. Starting SHA `81c024d74ea9201b31e22b5c02b1b6f852c0ce9e` is already dirty from the preceding GLHS program and must not be treated as a Phase-A freeze. |
| B. Commitment domain + DSL | complete | Migration `20260810_0054`, four frozen domain policies, closed/bounded predicate evaluator, GST-coupled proposal/write gateway, bitemporal reconstruction/reconciliation, commitment THSS, and consent/profile-scoped human API routes are implemented. Focused policy/gateway/migration and DSL/reconciliation suites pass, including the full migration-chain upgrade → downgrade → upgrade round trip. |
| C. Offline evaluator | complete | Explicit STU3/R4 ingestion (including STU3 `ProcedureRequest` without provenance relabeling), source-grounded construction, deterministic oracle, leakage-checked distinct packets, exact-model injected client with bounded valid request shape/decoding budget and no fallback, candidate-slot precision/recall/F1 and temporal-window scoring, product-state scoring, subject-clustered paired statistics, manifests, checkpoints, per-cell outputs and SHA-256 sealing are implemented. Stable offline and freeze/probe-gated Phase-B CLIs/Make targets are present; Phase-B paths are tested only with injected transports before freeze. |
| D. Assurance | in progress | The two-subject/two-model/nine-condition fake-provider grid now materializes two source cases plus 18 opaque adversarial variants, completes 10 typed construction/review calls plus 360 solver cells, resumes with zero calls, and passes strengthened sealed-artifact validation. Solver calls execute the frozen system prompt and prediction schema. The BTSA packet executes its independent mechanism-mapped arbitration adapter. The API boundary covers auth, active/revoked consent and append-only re-acceptance, cookie CSRF, cross-owner isolation, stale version rejection, decision reconstruction, and real THSS snapshot compilation. Full API and ML service suites exit 0; isolated deployed-boundary execution remains external. |
| E. Phase-A freeze | complete | Replacement freeze `20543ed6cef6d9d1f2189bbb77a1266fcf21ae8d` is `COMPLETE` and `VALID`, with 18 frozen inputs. It preserves the initial zero-call proof and records the three post-initial-freeze probe/diagnostic calls. It supersedes `154ee41064c936c1c599c26a70a8460840cce304`, whose historical v1 seal remains evidence at its original SHA but is not compatible with the stricter v2 reported-model validator. |
| F. Phase-B synthetic benchmark | complete | The replacement canonical probe accepted both declared requested→reported mappings in one attempt each with no fallback. The bounded benchmark completed 360/360 solver cells over two controlled synthetic source fixtures, 18 adversarial variants, two models, and nine conditions; four construction requests were rejected by deterministic invariants, for 364 benchmark requests total. Resume used an injected no-call transport and made zero requests. Artifacts validate and pass secret scanning. |

## Decisions

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-08-10 | Reuse GLHS profile state versions and evidence IDs. | Avoid a parallel canonical patient store and preserve existing GST/provenance boundaries. |
| 2026-08-10 | Keep CommitLoop evaluation-only until offline gates pass. | Router output cannot approve architecture, code, predicates, gold, or Phase-A completion. |
| 2026-08-10 | Preserve lifecycle, evidence and timeliness as independent axes. | A commitment can remain open while conflicted or overdue; no single status silently collapses those facts. |
| 2026-08-10 | Freeze four distinct domain policies in deterministic code. | Medication, allergy, condition and observation commitments require different actions, authorities, grace windows, conflict handling and abstention rules. |
| 2026-08-10 | Treat injected transports as the only valid Phase-A provider path. | The complete 36-cell grid, checkpoint resume, scoring and artifact seal can be tested without a router credential or external request. |
| 2026-08-11 | Make typed generation/review advisory and deterministic acceptance authoritative. | Both model families can be simulated in Phase A, but only source-equality, DSL and anchor-note validators accept construction inputs; no model creates gold or clinical truth. |
| 2026-08-11 | Gate any Phase-B probe on a sealed Phase-A freeze. | The probe command validates the sealed run directory before constructing clients, refuses missing/incomplete or nonzero-call freezes, and enforces the exact two declared models. |
| 2026-08-11 | Require timezone-aware API bitemporal values. | Snapshot and transition boundaries reject naïve timestamps and normalize offset timestamps to UTC before reconstruction. |
| 2026-08-11 | Bind Phase-A evidence and every Phase-B probe to the live frozen repository. | Validation evidence must name the tested SHA and record each required gate's exact command, zero exit code, result summary, and timezone-aware completion time. Before any transport call, the probe rejects a dirty worktree, a changed HEAD, or any frozen-input inventory/hash drift. |
| 2026-08-11 | Reject secret-bearing validation evidence before artifact creation. | Exact command/result evidence is scanned in memory before `implementation_freeze.json` is written, so an accidental authorization value cannot be left behind in a failed freeze directory. |
| 2026-08-11 | Rebaseline ML runtime tests to the deployment-owned DeepSeek-only contract. | Request provider/model/endpoint overrides remain ignored and absent from responses; generation outages fail closed with one 503 path, while retrieval/cache tests use explicit retrieval-only mode or injected offline clients instead of restoring implicit local synthesis. |
| 2026-08-11 | Keep Phase-B probe and benchmark outputs outside the sealed Phase-A artifact tree. | Adding a post-freeze file beneath the Phase-A run would invalidate its exact inventory. The probe records exact-model capability/base-URL hashes, and the benchmark binds its manifest to both the freeze SHA and probe SHA-256 before any provider request. |
| 2026-08-11 | Materialize adversarial edits against fulfillment evidence, not the anchor request. | Cancellation, supersession, conflict, partial completion, late ingestion, duplication, missing prerequisites, fuzzy time, and post-cutoff evidence now create opaque solver cases and separate deterministic gold. Variant labels are joined only after inference; a valid-time-only ablation cannot expose evidence unknown at cutoff. |
| 2026-08-11 | Make escalation a frozen solver output instead of an unmeasured placeholder. | Prediction schema/prompt v2 and the deterministic oracle now require `ESCALATE` for conflicting or insufficient evidence, or an unresolved overdue commitment. Scoring and artifact validation enforce explicit overall and adversarial denominators. |
| 2026-08-11 | Treat `[REDACTED]` as the only accepted nonblank key placeholder and require a token boundary for `sk-` detection. | This preserves fail-closed credential scanning without corrupting ordinary `risk-...` paths; a marker with appended material remains a finding. The authorized history remediation changes only five assignment values. |
| 2026-08-11 | Freeze the router's observed namespace-stripped reported-model IDs as a closed requested→reported mapping. | The canonical post-freeze probe rejected both short IDs before benchmark start. Two diagnostic requests confirmed valid JSON and the exact IDs `gemini-3.6-flash-high` and `claude-sonnet-4-6`; arbitrary aliases, requested-ID echoes, and fallbacks remain rejected. Replacement-freeze provenance retains all three diagnostic calls. |
| 2026-08-11 | Treat the Phase-B run as synthetic software evidence only. | The run contains two controlled R4 fixtures and deterministic adversarial derivatives, not the available Synthea archive, real EHR data, or clinician-adjudicated cases. Zero timeliness and all-axes exact accuracy prevent a primary-endpoint winner claim. |

## Validation evidence

| Command | Result |
| --- | --- |
| Consolidated focused GLHS/CommitLoop/comparator suite | 128 passed (including migration round trip, API contract/integration, consent revocation/CSRF/stale-write/THSS boundaries, STU3 construction, Hypothesis predicate properties, sealed/replacement-freeze and probe gates, adversarial/temporal-boundary scoring, naming, executable BTSA adapter fidelity, reported-model mapping, and redaction boundary regressions); three pre-existing Starlette/FastAPI deprecation warnings only |
| `pytest evaluation/commitloop/tests -q` | 54 passed, including materialized opaque adversarial cases, crash-safe resume/error-ledger recovery, FHIR knowledge-time normalization, strict THSS packet scoping, escalation and two-snapshot temporal-boundary metrics, frozen solver prompt/schema execution, freeze-gated Phase-B benchmark, declared reported-model mapping and fallback rejection, replacement-freeze call provenance, seal-directory isolation, zero-call rejection paths, exact redaction-marker handling, and embedded `risk-...` false-positive prevention |
| CommitLoop freeze-surface Ruff | All checks passed for evaluator, migration, API/GLHS commitment modules, endpoint tests, property tests, and naming tests |
| CommitLoop freeze-surface mypy | Success: no issues found in 41 source files |
| `python -m evaluation.commitloop.cli local-fixture --output artifacts/commitloop/local-phase-a-v7 --max-requests 500` followed by the same command | First run 370 injected calls (10 construction/review + 360 solver); resumed run 0 calls; two subjects, two source cases, 18 opaque variants; both complete; explicit `execution_mode=phase_a_fake` |
| `python -m evaluation.commitloop.cli validate --run-dir artifacts/commitloop/local-phase-a-v7` | `VALID`; complete SHA-256 inventory after the latest resume, structured-error, FHIR known-time, strict-THSS, escalation-schema, and temporal-boundary scoring changes |
| Strengthened validator regression (`test_local_e2e.py`, `test_statistics.py`) | 5 passed: complete-grid tamper, resume, generation-budget, sealing and paired-statistics checks |
| Phase-A freeze/probe regression (`test_freeze.py`, `test_provider_probe.py`) | 12 passed: clean-worktree and tested-SHA binding, structured complete evidence, all required gates, pre-write evidence-secret rejection, tracked-secret rejection, live repository/input drift rejection before transport, sealed fixture freeze, exact-model probe, and tamper rejection |
| Commitments API contract/integration | 9 passed: anonymous 401; active/missing/revoked consent and append-only re-acceptance; cookie CSRF; owner proposal/transition/read; stale version 409; cross-owner 404; strict THSS snapshot; timezone and domain validation |
| Consent/auth regression plus Commitments boundary | 58 passed; Ruff and targeted mypy pass; three pre-existing framework deprecation warnings |
| `pytest -q services/api/tests` | 1,357 passed, 1 skipped, 51 warnings; full API service suite exited 0 after explicitly classifying FastAPI documentation routes and updating the stale Control Tower test to lock DeepSeek-only/no-runtime-provider-selection behavior |
| `PYTHONPATH=services/ml/src:. services/ml/.venv/bin/python -m pytest -q --tb=no services/ml/tests` | Exit 0: 1,500 passed and 2 skipped out of 1,502 collected; six FastAPI deprecation warnings. Council/CareGuard/NLP contracts, RAG injected-client behavior, cache/retrieval-only wiring, routed-chat fail-closed behavior, and stale provider/fallback expectations were repaired or rebaselined without enabling production fallback. No external provider call was made. |
| `make eval-commitloop-local` + `eval-commitloop-validate` | Complete 370-call injected-transport grid; validator reports `VALID`; `router_calls_before_freeze=0` |
| Updated local construction metrics | Candidate-slot F1 `1.0` (8/8 slots) and temporal-window accuracy `1.0` (2/2) on the deterministic fixture; synthetic software evidence only |
| Fake-solver variant metrics | Lifecycle accuracy `108/360 = 0.30`, evidence accuracy `324/360 = 0.90`, timeliness accuracy `360/360 = 1.00`, escalation accuracy `180/360 = 0.50`, and all-axes exact `72/360 = 0.20`. Adversarial-only escalation is `144/324 = 0.4444`; known-time and valid-time two-snapshot boundary pairs are each `0/36`, combined transition-pair accuracy `0/72`. These intentionally negative fake-transport results prove denominators/variant gold paths only; they are not model-quality evidence. Longer longitudinal replay remains `NOT_MEASURED`. |
| `make eval-commitloop-secret-scan` | Passed for CommitLoop/GLHS implementation scope |
| Full tracked-repository secret scan | Passed after the authorized five-value history redaction and scanner boundary regression tests; no untracked user archive is modified or included in the freeze |
| `pytest evaluation/property_assurance/test_naming_migration.py -q` | 2 passed; canonical naming/compatibility aliases remain regression-locked |
| Protocol/property/API-contract tests plus `make docs-check` | Property+naming rerun 4 passed; documentation links valid |
| `git diff --check` | Passed; no whitespace-error findings |
| Replacement Phase-A freeze | `implementation_freeze.v2` at `20543ed6cef6d9d1f2189bbb77a1266fcf21ae8d`: `COMPLETE`, `VALID`, 18 frozen inputs, initial router-call count 0, three disclosed Phase-B diagnostic calls before replacement, full tracked-repository/artifact secret scan passed |
| Replacement canonical probe | Two calls, one attempt per declared model, JSON contract and usage fields available, non-streaming responses, no retries/fallback; reported IDs exactly match the frozen closed mapping; probe SHA-256 `125cbdf9f1e8e52cd19120c9e59700e6dbec040afff6e913f6d10b4d1a1cbca8` |
| Phase-B benchmark and resume | `COMPLETE` and `VALID`: 2 subjects, 2 controlled synthetic source cases, 18 adversarial variants, 2 models × 9 conditions × 20 cases = 360/360 solver outputs, zero solver/provider errors, 360 solver plus 4 rejected-construction requests = 364 requests; injected no-call resume made 0 requests |
| Phase-B primary metrics | Lifecycle `231/360 = 0.6417`; evidence `215/360 = 0.5972`; timeliness `0/360`; escalation `169/360 = 0.4694`; all-axes exact `0/360`. Every arm has zero exact accuracy, so no condition wins the primary endpoint; paired exact deltas are zero. |
| Phase-B adversarial/operational metrics | Adversarial escalation `134/324 = 0.4136`; false alerts `7/72 = 0.0972`; missed conflicts `32/36 = 0.8889`; missed loops `36/144 = 0.25`; known-time, valid-time, and combined two-snapshot transition accuracy are all zero. No retries; latency p50/p95/p99 `2881.99/5987.62/7372.60 ms`. Provider-reported usage fields: 371,823 prompt, 26,455 completion, and 649,592 total tokens. |

Phase-A commands used local deterministic fixtures or injected fake transports.
Router calls before the initial freeze remain exactly zero. Three Phase-B probe/
diagnostic calls occurred after it and before the replacement freeze. After the
replacement seal, the canonical probe used two calls and the benchmark used 364,
so the disclosed lifecycle total is 369 external calls. No further router call
was made after the completed benchmark.

## Current blockers

- The primary worktree contains unrelated untracked, user-owned archives. They
  remain untouched and unstaged. Freeze and Phase-B execution ran from a clean
  detached worktree at the committed implementation SHA.
- Real-application adversarial execution, real EHR, and clinical adjudication
  remain `BLOCKED_EXTERNAL / NOT_RUN` and must not be substituted with synthetic
  success claims.
- Root `make lint` reports 635 unrelated findings in pre-existing scripts and ML
  test files. The freeze truthfully records this repository-wide debt while the
  frozen CommitLoop/GLHS Ruff surface passes.
- Root `make type-check` reports 332 mypy errors across 43 API/ML files outside
  the CommitLoop modules. The freeze records this debt; targeted CommitLoop type
  checks pass.
- The focused Commitment endpoint integration path now passes. Isolated
  deployed-boundary adversarial execution and PostgreSQL-specific execution
  remain outstanding and are not inferred from in-process SQLite validation.

The requirement-by-requirement evidence and claim limits are maintained in
[`commitloop-phase-a-audit.md`](commitloop-phase-a-audit.md).

## Rollback

The migration is additive. Disabling any future review surface must leave the
append-only ledger intact; derived evaluator packets and artifacts are
rebuildable and noncanonical.
