# R3 Follow-up Validation Report

- Audit date: 2026-08-19
- Audited HEAD: `f3a00573e594ee4923bf8e29b3afe283c41ea962`
- Branch: `codex/commitloop-phase-a`
- Decision: **BLOCKED**; true R3 `DONE` is not supportable.
- Scope: read-only validation of HEAD and the R3 follow-up inputs. This report is
  the only intended change from this validation.

## Repository Scope

The inspected commit range was `0a6c5940..f3a00573`:

- `c011582a` `docs(research): R3 baseline audit and evidence registry reconciliation`
- `8ef508b7` `docs(careguard): freeze statistics plan, mapping review protocol, RxMap feasibility disposition`
- `3263d011` `feat(govred): three-state primary, Not Run capability audit, repetition/holdout protocols`
- `02593485` `docs(research): add R3 release gate audit`
- `00c5a31b` `feat(glhs): concurrency repetition manifest and malformed-output offline audit`
- `f3a00573` `docs(research): synchronize R3 claims and release evidence package`

The latest commit's new executable scope was inspected in
`evaluation/glhs_postgres_toctou/` and its tests, plus the GLHS repetition and
malformed-audit freeze inputs. The R3 GovRed, FHIR, GLHS ablation, and GovMut
follow-up files in the range/worktree were also inspected. The latest commit's
`research/release_r3/` package was checked as a generated evidence package; its
`BUILD_INFO.json` records `source_commit` as `00c5a31b`, not the audited HEAD
`f3a00573`. The worktree was already dirty with unrelated tracked and untracked
changes; those changes were not reverted or modified.

## Targeted Validation

Commands below were run with the existing API virtual environment. No freeze,
benchmark runner, database runner, or seal command was invoked.

| Area | Command/result | Status |
| --- | --- | --- |
| GLHS lineage | `PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m pytest services/api/tests/test_glhs_inference_context_binding.py services/api/tests/test_commitloop_gateway.py services/api/tests/test_glhs_mandatory_thss_binding.py services/api/tests/test_glhs_gateway.py services/api/tests/test_glhs_policy_epoch.py services/api/tests/test_glhs_foundation_migration.py -q` -> `75 passed, 1 skipped` | PASS (tests) |
| GLHS repetition helpers | `PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m pytest evaluation/glhs_postgres_toctou/tests/test_commit_order.py evaluation/glhs_postgres_toctou/tests/test_jitter.py evaluation/glhs_postgres_toctou/tests/test_repeat_manifest.py evaluation/glhs_postgres_toctou/tests/test_executor_v3.py -q` -> `35 passed` | PASS (tests) |
| GLHS ablation | `PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m pytest evaluation/glhs_binding_only_ablation/tests/test_ablation.py -q` -> `23 passed` | PASS (tests) |
| FHIR | `PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m pytest evaluation/fhir_conformance/tests -q` -> `33 passed` | PASS (tests) |
| GovMut | Targeted W8/W9/fair-budget/freeze/runner suite -> first run `31 passed, 1 failed`; isolated W9 rerun -> `1 passed`; sequential full rerun -> `32 passed` | PASS (final rerun); initial failure recorded |
| D malformed audit | `PYTHONPATH=.:services/api/src services/api/.venv/bin/python -m pytest research/glhs_journal/malformed_audit_v1/test_taxonomy_parser.py -q` -> `6 passed` | PASS (tests) |
| Targeted ruff | `services/api/.venv/bin/ruff check evaluation/glhs_postgres_toctou evaluation/glhs_binding_only_ablation evaluation/fhir_conformance research/glhs_journal/malformed_audit_v1 services/api/tests/test_glhs_inference_context_binding.py services/api/tests/test_commitloop_gateway.py services/api/tests/test_glhs_mandatory_thss_binding.py services/api/tests/test_glhs_gateway.py` -> `All checks passed!` | PASS |
| GovMut ruff | The combined ruff invocation that included all requested workstreams and GovMut files -> 26 errors: 21 `ISC004` classifier errors, plus unused-variable/import and string-literal errors in budget/renderer/test files. A direct `ruff check evaluation/property_assurance` rerun reported the 21 classifier errors. | FAIL |

The initial GovMut failure was
`test_w9_freeze_input_matches_sealed_methods_hypothesis_and_limits`; the same
test passed when rerun alone, and the complete targeted suite passed on the
sequential rerun. It is retained here as an observed transient result, not
treated as a release blocker by itself.

## Evidence Status

Passing tests do not create a release seal. The following evidence gates remain
open at this HEAD:

- **GLHS lineage / Gate B:** the current binding implementation, migration, and
  tests are working-tree candidates, not an immutable code/freeze/test identity;
  no sealed PostgreSQL regression evidence covers the required lineage,
  restart/reload, and concurrency cases.
- **GLHS ablation / Gate C:** the 320 logical schedules and arm-diff tests pass,
  but there is no isolated PostgreSQL 640-execution result, paired analysis, or
  seal. The available SQLite smoke path is explicitly non-final.
- **GLHS repetition / Gate D:** `FREEZE.md` remains
  `NOT EXECUTED - PENDING`; `repeat_raw.jsonl` and schedule-level `analysis.json`
  are absent. The required 50 repetitions for each of 12 logical schedules
  therefore do not exist.
- **D malformed audit / Gate D:** the offline audit verifies 49/49 files and
  reports 0 malformed cells in the available 360-cell, two-subject artifact.
  It is descriptive only and is not the missing immutable 384-subject raw
  v5-batch5 output; it cannot reproduce or promote the reported approximately
  220-malformed decomposition.
- **FHIR / Gate H:** the available run records structural `MISMATCH` for
  `neg-invalid-temporal` and `neg-version-mismatch`. The required
  `evaluation/fhir_conformance/seal/artifact-sha256.json`, `analysis.json`, and
  `seal.json` are absent. The test suite passing does not close those evidence
  gaps.
- **GovMut / Gate F:** W8 remains the preserved sealed result, but the W9 human
  review artifact and promoted W9 freeze are absent. No W9 execution/seal or
  equal-wall-clock budget-normalized comparison exists. The targeted GovMut
  lint failure also remains unresolved.
- **GovRed / Gate E:** the 50-repeat protocol is explicitly pending with no
  result emitted, and the 39-schedule holdout is not independently human-authored
  or executed.
- **CareGuard / Gate G:** the authorized current DAV identity/source frame,
  blinded mapping review, and CareGuard execution/seal remain absent.
- **Release reconciliation / Gate I:** the f3a package demotes the GLHS v2
  claim correctly, but its generated `BUILD_INFO.json` is bound to the prior
  `00c5a31b` source commit rather than audited HEAD `f3a00573`. The package also
  records `MISSING_TRACKED_PDF_SOURCES` and `MISSING_PDF_BUILD_TOOLS`.
  Uncommitted worktree edits cannot be treated as a release identity.

## True-DONE Rule

True `DONE` requires every required gate to be `DONE`, all required evidence to
be sealed and hash-verified, manual gates to be completed by their owners, and
no stale claim to contradict the canonical registry. The test passes above are
useful validation signals, but they do not satisfy those conditions. Exact
blockers are the missing PostgreSQL runs/seals, the missing 384-subject raw
artifact, FHIR mismatches and absent seal files, open human gates, GovMut lint
errors, and the package source/PDF preflight mismatch at the audited HEAD.
