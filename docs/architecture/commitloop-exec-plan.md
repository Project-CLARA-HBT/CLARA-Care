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
| E. Phase-A freeze | pending | Guarded freeze/probe commands require all named Phase-A gate categories and scan every tracked file for credential material before sealing. The authorized repository-wide remediation now passes: five assignment values in the tracked chat-history artifact are replaced by the explicit `[REDACTED]` marker, while six `risk-...` documentation paths falsely matched by the former unbounded `sk-` pattern were restored byte-for-byte. A clean committed SHA and final broad validation evidence are still required. Router use remains prohibited before this point. |

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

## Validation evidence

| Command | Result |
| --- | --- |
| Consolidated focused GLHS/CommitLoop/comparator suite | 126 passed (including migration round trip, API contract/integration, consent revocation/CSRF/stale-write/THSS boundaries, STU3 construction, Hypothesis predicate properties, sealed-freeze/probe gates, adversarial/temporal-boundary scoring, naming, executable BTSA adapter fidelity, and redaction boundary regressions); three pre-existing Starlette/FastAPI deprecation warnings only |
| `pytest evaluation/commitloop/tests -q` | 52 passed, including materialized opaque adversarial cases, crash-safe resume/error-ledger recovery, FHIR knowledge-time normalization, strict THSS packet scoping, escalation and two-snapshot temporal-boundary metrics, frozen solver prompt/schema execution, freeze-gated Phase-B benchmark, exact probe capability metadata, seal-directory isolation, zero-call rejection paths, exact redaction-marker handling, and embedded `risk-...` false-positive prevention |
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

All commands above used local deterministic fixtures or injected fake transports.
Router calls before freeze remain exactly zero.

## Current blockers

- The primary worktree contains unrelated untracked, user-owned archives. They
  remain untouched and will not be staged; the final validation and freeze must
  run from a clean detached worktree at the committed implementation SHA.
- Real-application adversarial execution, real EHR, and clinical adjudication
  remain `BLOCKED_EXTERNAL / NOT_RUN` and must not be substituted with synthetic
  success claims.
- Root `make lint` currently fails with 635 unrelated findings in pre-existing
  scripts and ML test files. CommitLoop/GLHS-targeted Ruff and mypy commands
  pass; the repository-wide lint debt must be cleared or separately waived
  before a truthful clean implementation freeze.
- Root `make type-check` currently fails with 332 mypy errors across 43 API/ML
  files outside the CommitLoop modules. Targeted CommitLoop type checks pass;
  this repository-wide debt must likewise be cleared or separately governed
  before a truthful clean implementation freeze.
- The focused Commitment endpoint integration path now passes. Isolated
  deployed-boundary adversarial execution and PostgreSQL-specific execution
  remain outstanding and are not inferred from in-process SQLite validation.

The requirement-by-requirement evidence and claim limits are maintained in
[`commitloop-phase-a-audit.md`](commitloop-phase-a-audit.md).

## Rollback

The migration is additive. Disabling any future review surface must leave the
append-only ledger intact; derived evaluator packets and artifacts are
rebuildable and noncanonical.
