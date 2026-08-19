# R3 Workstream A Report — Baseline and Evidence-Registry Reconciliation

Date: 2026-08-19
Branch: `codex/commitloop-phase-a`
Spec: `MASTER_SPEC_REVIEWER_R3_2026-08-19.md` §1.7, §2.11 (REG-01..REG-03), Workstream A (A-001..A-006).
Scope: research/docs only. No production code changes. No sealed artifact modified
(`artifacts/**`, `research/glhs_journal/protocol_v2/**` read-only).

## 1. A-001 — Baseline

| Item | Value |
| --- | --- |
| `git rev-parse HEAD` | `0a6c5940b164d5f262d1f82a9a7ad9a443275602` — **MATCHES expected** |
| Tracked dirty files | 0 (no modified tracked files) |
| Untracked files | 5286 (user docs / datasets / untracked artifacts; none staged) |
| `python3` | Python 3.14.3 |
| `services/api/.venv/bin/python` | Python 3.11.15 |
| `node` | v24.13.1 |
| Alembic versions (`ls \| sort \| tail -3`) | `20260818_0056_governance_policy_epochs.py`, `20260818_0057_commitment_effective_time.py`, `__pycache__` |

Migration head: newest revision is `20260818_0057_commitment_effective_time.py` (tracked).
`20260818_0056_governance_policy_epochs.py` is present on disk but currently **untracked** in git.

## 2. A-002 — Registry / seal snapshot (recorded, not modified)

| File | sha256 (recorded) |
| --- | --- |
| `research/publication_registry.yaml` | `a2a0f0947849f50984b719b4eb15dae81920d319fa90cdb2e4ed2fe4498a6ef0` |
| `research/FINAL_TOP_TIER_EVIDENCE_STATUS.md` | `c8b496bc784166bc1eb21d88b3509a0b3db4bdbb3876e18a3d418435712b8d3b` |
| `research/glhs_journal/CURRENT_EVIDENCE_STATUS.json` | `6aa8d9e45b7dd9d4d80c524c85d664dfd4e3154d869ffdce19dceab36d12f770` |
| `research/claim_ledger.csv` | `b7bd52c7f03bbb55c1a5715813d0dc78de6534f32a74cd98b78a31e0dfac3b36` |

All four are tracked files; none were modified by this workstream. `publication_registry.yaml` was
updated later (A-004/A-006) as its own documented change.

## 3. A-005 (CRITICAL) — GLHS 5-vs-12 schedule TOCTOU discrepancy

### 3.1 Hash verification vs `protocol_v2/artifact-sha256.json`

| File | Declared sha256 | Recomputed | Result |
| --- | --- | --- | --- |
| `postgres_toctou_protocol_v2.json` | `c10836f3e25c29cd83ade06cf104f67d97484397ec037809a36482685830798d` | same | **PASS** |
| `statistics_plan_v2.json` | `46a7e270f067769a3c43dc643dd448a2a25bdfffe74597c2d3b399b073af4fa7` | same | **PASS** |
| `run_v2_raw.json` | `ae8932f69b87e825b3ec942a453aa97b60156581c90a694f9ccdfc79b19c3d8d` | same | **PASS** |
| `analysis_v2.json` | `39efc4c7632e305eaea6b7ea12c339752266a901ad931fda806e58f207d95990` | same | **PASS** |

All 4/4 **PASS**. No failing hash.
Not sealed (no entry in the manifest): `postgres_toctou_protocol_v2_1.json`
(`0b36ec3af7d1e9c43c92d6d825922d2f7364772dfdd2decf42126e0d6fe425c4`, untracked). `README.md`
(`e7f431efb6948d846d65cfe3848bd3d71a9d5e7f5c8a87d174e7a4445a6a0a54`) is the run book, not part of
the byte seal.

v1 seal (`artifacts/glhs-postgres-toctou/GLHS-POSTGRES-TOCTOU-FINAL-20260817-01/artifact-sha256.json`)
also re-verified: `result.json`, `analysis/analysis.json`, `tables/schedule_matrix.csv` — **3/3 PASS**.

### 3.2 `run_v2_raw.json` structure vs protocol v2

- Run ID `GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01` — **matches** protocol. PASS.
- Schema `glhs-postgres-governance-toctou-final-v2` — **matches** protocol. PASS.
- Schedule count **12** (`TOCTOU-V2-01..12`) — **matches** the 12-schedule protocol. PASS.
- Executed source revision `67e528b61512aabc201b344e54f9e3e724490e41` — git commit `67e528b6` exists
  (`git cat-file -t 67e528b6` → `commit`). `git show 67e528b6 --stat` lists
  `evaluation/glhs_postgres_toctou/executor_v2.py` + `tests/test_executor_v2.py` — i.e. the v2
  **executor code**, not the JSON protocol files (those are sealed working-tree files). PARTIAL.

### 3.3 Honest finding — claim-eligibility UNRESOLVED (no failing hash)

`run_v2_raw.json` top-level `status` = **`EXECUTED_V2_OBSERVATION_MISMATCH`**; validation block =
`VALIDATED_V2_OBSERVATIONS_NOT_EXECUTED` (`database_executed=false`, `result_emitted=false`).
Classification audit: 10/12 match; **TOCTOU-V2-05** and **TOCTOU-V2-09** expected
`indeterminate_ordering` but observed `rejected_*` (conservative direction, but mismatch). The
frozen protocol's `result_rule` states a mismatch run is **not claim-eligible**.

Conclusion: the v2 12-schedule artifact **exists and is fully byte-verified**, and is the
manuscript-cited canonical artifact; it may **not** be cited as claim-eligible until a re-run yields
`EXECUTED_V2_FROZEN_OBSERVATIONS` or the mismatches are reconciled and resealed (Workstream D-001/
D-004). Documented in `research/glhs_journal/CANONICAL_TOCTOU_EVIDENCE.md` (v1 = historical,
v2 = canonical manuscript-cited evidence, both byte-verified, no overwriting).

## 4. A-004 — Registry reconciliation from verified artifacts

| Registry study | Old status/run | New status | headline_run_id | Verified artifact bound |
| --- | --- | --- | --- | --- |
| `govred-rivf-2026` (02) | `NOT_RUN`/`protocol_implementation` | `sealed_claim_eligible_executable_primary_schedules` | `2026-08-17-rivf-final-003` | `research/govred_rivf/results/final-003-analysis-v2.json` sha `098d4c3b...` (verified), 450 cases, 4 arms, run_id `2026-08-17-rivf-final-003`, source `5b2c0dbf`; manifest `artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json` sha `f5b20de1...` (verified, 450 cases) |
| `assurance-soict-2026` (03) | `NOT_RUN`/`development_mutation_infrastructure_only` | `sealed_w8_45mutant_complete` | `govmut-soict-2026-final-v2` | `research/assurance_soict/seal/govmut-soict-2026-final_analysis-v2` sha `e3ab1832...` (verified) + `_run-v2` sha `c59768dc...` (verified), freeze `govmut-soict-2026-final-v2`, 45 mutants / 720 executions / 4 strategies; claim mapping `seal/claim_to_evidence.csv` sha `451bcb60...` |
| `glhs-journal` (01) | `existing_glhs_runs_background_only` | `revision_evidence_sealed_partial` | `GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01` | v2 12-schedule protocol_v2 artifacts (4/4 sha PASS) + pointer `research/glhs_journal/CANONICAL_TOCTOU_EVIDENCE.md`; v1 `GLHS-POSTGRES-TOCTOU-FINAL-20260817-01` retained as historical |

CareGuard (06) and FMC (05-era presentation) intentionally remain NOT_RUN/not-applicable — no
sealed benchmark exists for either (CareGuard external source is PAUSED_BY_OPERATOR).

### 4.1 A-004 path-verification notes (spec claims vs disk reality)

- Spec A-004 cites `artifacts/commitloop/local-phase-a-v6/metrics.json` as the "384-subject" run.
  **Disk reality:** that run is 2 subjects / 20 cases / 360 cells (`run_manifest.json`
  `subject_count=2`, `execution_mode=phase_a_fake`), status COMPLETE — it is **not** a 384-subject
  claim-eligible artifact.
- The only 384-subject data located is `artifacts/commitloop/confirmatory-cohort-v3/`:
  `cohort/cohort_manifest.json` (384 bundle hashes, status `GENERATED_NOT_FROZEN`) and
  `offline_dry_run/statistical_results.json` (`subject_count: 384`) which is explicitly
  `DESCRIPTIVE_SYNTHETIC_ONLY` ("fake_transport_validation_not_clinical_evidence").
- The 64-subject positive result is verified at `artifacts/commitloop/confirmatory-cohort-v2/`:
  `benchmark/run_manifest.json` (64 subjects, COMPLETE) + `result_audit.json`
  (`status=COMPLETE_VALID`, `metrics_sha256=ad3cbc6b...`, implementation `17dd4b8c`).
- **Consequence:** the "384-subject sealed null result" artifact is **not located in a
  claim-eligible/sealed form** on this branch; D-006 ("locate immutable 384-subject raw outputs and
  verify seal/hash") remains OPEN. No run ID was invented; the registry records only verified IDs.

## 5. A-006 — Duplicate-publication fields

Added to every manuscript in `research/publication_registry.yaml`:
`parent_study_id`, `evidence_freeze_ids`, `publication_relationship`, `overlap_status`.

| Pair | parent_study_id | freeze evidence | overlap_status |
| --- | --- | --- | --- |
| 02 `govred-rivf-2026` / 08 `bigdata-healthcare-2026` | `govred-final-003` | `2026-08-17-rivf-final-003` | `same-frozen-evidence; second-venue-requires-material-extension` |
| 03 `assurance-soict-2026` / 11 `bigdata-ml-2026` | `govmut-w8-45mutant` | `govmut-soict-2026-final-v2` | `same-frozen-evidence; second-venue-requires-material-extension` |

08 and 11 were added as `held_extension_only` entries (per GRD-06/GMT-07 routing rules). Other
manuscripts: `careguard-vn` standalone, `glhs-journal` primary, `fmc-2026`
presentation-only derivative of `glhs-journal`. Registry `updated_at` set to `2026-08-19`.

## 6. A-003 — Machine-readable baseline audit

Written to `research/R3_BASELINE_AUDIT.json` (`schema_version: clara-r3-baseline-audit.v1`,
`baseline_commit: 0a6c5940...`), mapping all 13 blocker ids to `repo_path`, `status`
(DONE / PARTIAL / MISSING / MANUAL-GATE), `evidence_path`, `notes`:

DONE: `registry_stale` (this workstream), `duplicate_publication` (this workstream).
PARTIAL: `toctou_discrepancy` (bytes verified, claim-eligibility unresolved), `govred_states`,
`govred_notrun`, `govmut_renderer`, `fhir_matrix`.
MISSING: `glhs_lineage`, `glhs_ablation`, `malformed_audit`, `govred_holdout`,
`govmut_survivors`, `govmut_budget`.
MANUAL-GATE: `careguard_gate` (authorized DAV/API acquisition + signature fields).

## 7. Remaining manual gates / open items

- `toctou_discrepancy`: v2 run must be re-executed to `EXECUTED_V2_FROZEN_OBSERVATIONS` or the
  TOCTOU-V2-05/-09 mismatches reconciled against a frozen revision and resealed before any
  claim-eligible citation (D-001/D-004).
- `careguard_gate` (MANUAL): authorized/current Vietnam identity frame (DAV export/API) before any
  CareGuard benchmark (G-001..G-005).
- `fhir_matrix` (PARTIAL→MANUAL): administrative support letter/signatures/milestone date (H-009).
- `govred_holdout` / `govmut_budget` / `govmut_survivors` / `malformed_audit` / `glhs_lineage` /
  `glhs_ablation`: require new frozen runs (E/D/C/B workstreams); no run IDs exist yet and none were
  invented.
- 384-subject raw outputs: not located in sealed claim-eligible form on this branch (D-006 open).

## 8. Commit scope

Committed files (only): `research/publication_registry.yaml`,
`research/glhs_journal/CANONICAL_TOCTOU_EVIDENCE.md`, `research/R3_BASELINE_AUDIT.json`,
`research/R3_WORKSTREAM_A_REPORT.md`. User's untracked docs (`CLARA_*`, `MASTER_SPEC*`, `*.docx`,
`datasets/`, etc.) were not staged.