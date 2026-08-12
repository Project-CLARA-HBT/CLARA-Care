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
| D. Assurance | complete locally | Solver-v4 fake-provider execution completes four deterministic-construction/dual-review calls plus 360 solver cells and resumes with zero calls. Focused 104 tests, migration round trip, property/adversarial/leakage gates, Ruff, mypy, docs, artifact validation, full API (1,357 passed, one skipped), and full ML (1,500 passed, two skipped) all exit 0. Isolated deployed-boundary execution remains external. |
| E. Phase-A freeze | complete | Current replacement freeze `17dd4b8c558c2ec0cb8c2572728093d9aa3ce914` is `COMPLETE` and `VALID`, freezes 47 transitive inputs, preserves the initial zero-call proof, and records 1,990 historical Phase-B calls before replacement. It supersedes solver-v4 freeze `ac599d35d240dba83aa08ca3111575ccf23d25dd`. |
| F. Initial Phase-B synthetic benchmark | complete | The replacement canonical probe accepted both declared requested→reported mappings in one attempt each with no fallback. The bounded benchmark completed 360/360 solver cells over two controlled synthetic source fixtures, 18 adversarial variants, two models, and nine conditions; four construction requests were rejected by deterministic invariants, for 364 benchmark requests total. Resume used an injected no-call transport and made zero requests. Artifacts validate and pass secret scanning. |
| G. Corrective evaluation iteration | complete | Freeze `af5b2150` aligned oracle/packet semantics and ran an eight-subject/44-case mechanism cohort. A zero-call correction at `c57f6300` fixed repeated-case subject clustering, used strict THSS as the pre-registered reference, limited primary inference to five registered comparators, applied Holm over ten model×comparator tests, and counted missing outputs as errors. |
| H. Exploratory solver-v4 iteration | complete | Deterministic construction plus bounded dual-model review removed fragile model-authored DSL projections. Solver v4 made independent-axis, exact-status, and decisive-time rules explicit. The sealed 792-cell exploratory rerun reached 94.57% all-axes exact and 98.86% timeliness, but no Holm-adjusted superiority. The n=8 design cannot mathematically achieve Holm-adjusted p<0.05 for ten two-sided sign tests. See [`commitloop-phase-b-v4-results.md`](commitloop-phase-b-v4-results.md). |
| I. Prospective solver-v5 mechanism cohort | complete | Anchor-only construction review eliminated future-context false rejection; an ordered decision procedure made decisive-time handling explicit. A pre-registered 64-subject, 1,152-cell one-shot run completed with zero errors/retries and 64/64 accepted constructions. Strict THSS reached 63/64 for Claude and 64/64 for Gemini, with six Holm-significant primary comparisons. The planned 51-non-tie power target was not met, so the result is significant synthetic mechanism evidence but not fully powered confirmation. See [`commitloop-confirmatory-v5-results.md`](commitloop-confirmatory-v5-results.md). |

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
| 2026-08-11 | Treat the first Phase-B result as a benchmark-contract failure requiring a new Phase-A freeze. | Runtime reconciliation uses decisive event time and a domain grace window, while the evaluation oracle used only cutoff; solver packets also hid due/grace and contradiction relation. Correcting these general contract defects is not post-hoc relabeling: the prior artifact remains immutable and the replacement run will bind to a new SHA/probe. |
| 2026-08-11 | Require mechanism coverage before interpreting condition deltas. | A two-event case makes full history, RAG, LWW, BTSA, and GLHS information-equivalent. The declared controlled cohort adds balanced temporal classes, late knowledge, multi-event history, retrieval-depth pressure, and opaque single-event perturbations without embedding labels in packets. |
| 2026-08-11 | Correct paired inference before interpreting the corrective run. | Statistics v1 overwrote repeated subject/model/condition rows and used the wrong reference. Statistics v2 reduces cases to subject means, compares strict THSS only with the five pre-registered primary comparators, counts absent cells as errors, and applies Holm across all ten primary tests. |
| 2026-08-11 | Make code own construction projections and models review only. | The router did not reliably enforce nested predicate `const` schemas. Retrying or weakening the DSL validator would be unsafe. Deterministic extraction now owns candidate, predicate, and note; both declared model families provide bounded non-clinical review. |
| 2026-08-11 | Treat solver-v4 results as exploratory and stop tuning the eight-subject cohort for significance. | Solver v4 follows disclosed post-hoc error slicing. With eight subjects and ten Holm-controlled two-sided sign tests, the minimum attainable adjusted p-value is 0.078125. A valid superiority test requires a larger prospectively frozen independent cohort, not further reuse of this test set. |
| 2026-08-11 | Restrict construction review to the anchor event and execute lifecycle/decisive-time/timeliness as an ordered solver-v5 procedure. | Construction projections are anchor-owned; supplying later events to a reviewer caused false future-leakage rejection. The remaining solver-v4 errors came from using cutoff instead of the selected decisive event or letting contradiction/status competition collapse independent axes. |
| 2026-08-11 | Freeze the 64-subject mechanism cohort and analysis before the solver-v5 probe, then run it once. | The pre-execution seal binds eight balanced strata, 1,152 cells, the ten-test Holm family, missing-output error policy, and a 51-non-tie power target. Same-cohort retuning is prohibited after the two-call probe. |

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
| Corrective evaluator regression | 57 evaluator tests passed; targeted Ruff passed; focused mypy reports no issues in 35 source files. The controlled cohort local grid has 8 source cases, 36 opaque variants, 44 total cases, four supported timeliness classes, and explicit Naive-RAG/LWW mechanism-pressure assertions. |
| Solver-v4 Phase-A gates | 104 focused tests passed with three framework warnings; migration 1, property 9, and adversarial/leakage 8 passed; Ruff and mypy (48 files) passed; local 364-call injected grid was `COMPLETE/VALID` and resumed with zero calls; full API 1,357 passed/1 skipped and full ML 1,500 passed/2 skipped. |
| Solver-v4 freeze/probe/smoke | Freeze `ac599d35d240dba83aa08ca3111575ccf23d25dd` is `COMPLETE/VALID` with 47 inputs and 1,182 historical calls disclosed. Canonical probe used two one-attempt calls. Dual-review smoke was `ACCEPTED` in exactly two requests/two attempts. |
| Solver-v4 Phase-B | `COMPLETE/VALID`: 792 attempted solver cells, 791 valid outputs, one fail-closed malformed Gemini long-context output, four accepted and four rejected construction reviews, 804 benchmark requests, zero-call injected resume, and artifact secret scan pass. Overall lifecycle/evidence/timeliness/escalation/all-axes exact were 777/765/783/788/749 of 792. |
| Solver-v5 Phase-A gates | Clean SHA `17dd4b8c558c2ec0cb8c2572728093d9aa3ce914`: 104 focused tests, migration round trip, 9 property tests, 8 adversarial/leakage tests, Ruff, mypy (48 files), docs, artifact validation, full API 1,357 passed/1 skipped, and full ML 1,500 passed/2 skipped all exit 0. Local 364-call fake grid resumed with zero calls. |
| Solver-v5 freeze/probe/cohort seal | Replacement freeze `COMPLETE/VALID`, 47 inputs, 1,990 prior calls disclosed. The exact-model probe used two one-attempt calls. The 64-subject cohort and pre-registered analysis were sealed before the probe; a 1,280-call injected dry run validated and resumed with zero calls. |
| Solver-v5 prospective Phase-B | `COMPLETE/VALID`: 64 source cases, no variants, 1,152/1,152 solver outputs, 64/64 accepted construction reviews, zero errors/retries, 1,280 benchmark requests, secret/checksum validation pass, and zero-call resume. Strict THSS was 63/64 Claude and 64/64 Gemini; six primary comparisons were Holm-significant, while every significant comparison remained below the planned 51 non-tied pairs. |
| Solver-v5 batch-5 router run | `VALID`, descriptive synthetic software evaluation only: 384 independent subjects, 3,456 cells, batch size 5, 3,236 parsed outputs and 220 fail-closed malformed outputs. Primary subject-level strict-THSS vs full-history contrast: 70 wins, 73 losses, 241 ties; exact two-sided sign p=0.8672499071; 95% bootstrap CI [-0.0677083, 0.0520833]. Zero-call reproduction matched all derived files. See [`commitloop-v5-batch5-router-results.md`](commitloop-v5-batch5-router-results.md). |

Phase-A commands used local deterministic fixtures or injected fake transports.
Router calls before the initial freeze remain exactly zero. Three Phase-B probe/
diagnostic calls occurred after it and before the replacement freeze. After the
replacement seal, the canonical probe used two calls and the benchmark used 364,
so the earlier disclosed lifecycle total was 369 calls. Corrective Phase B,
statistical/generation diagnostics, solver-v4 execution, the solver-v5 probe,
and prospective mechanism-cohort run bring the current disclosed lifecycle
total to 3,272 external calls. No further router call was made after the
completed solver-v5 benchmark.

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
- The historical eight-subject solver-v4 cohort is mathematically unable to produce a
  Holm-adjusted two-sided sign-test p-value below 0.05 across ten primary tests.
  Independent prospective cohort expansion and power planning are required;
  further tuning on the current cohort is not a valid route to superiority.
- The prospective 64-subject cohort produced six Holm-significant comparisons,
  but only 9 to 21 non-tied pairs per significant comparison versus the
  pre-declared target of 51. A tie-rate-adjusted independent replication is
  required for a fully powered confirmatory label; same-cohort retuning is
  prohibited.

The requirement-by-requirement evidence and claim limits are maintained in
[`commitloop-phase-a-audit.md`](commitloop-phase-a-audit.md).

## Rollback

The migration is additive. Disabling any future review surface must leave the
append-only ledger intact; derived evaluator packets and artifacts are
rebuildable and noncanonical.
