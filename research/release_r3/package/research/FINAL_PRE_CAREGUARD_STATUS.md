# CLARA-Care Final Program Status (Pre-CareGuard)

Machine-generated status from immutable artifacts (W0-T08 `render_status.py`); hand-edited claims do not override machine state. RIVF and GLHS sections below are rendered from artifact state; SOICT/FMC/CareGuard sections are carried forward verbatim (outside W0 scope).

Machine status: `clara-w0-machine-status.v1` — top-level SEALED. RIVF dual-model protocol QA NOT_RUN_pending_router_key (recorded, not claimed); GLHS dual-model protocol QA complete (kappa 1.0, unresolved 0).

## RIVF / GovRed — COMPLETE + ANALYZED + SEALED

- Run ID: `2026-08-17-rivf-final-003`
- Frozen git SHA: `5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb`
- Source SHA consistency: reconciliation == manifest.code_revision == analysis-v2.source_sha == sealed_run_inventory (5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb)
- Frozen stats plan: `artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_statistics_plan.json` (sha256 `db5da691f648dc8d6c9db4a673580ed81913e8076c3a5df0052f3c414768cdbc`, hash matches reconciliation: True)
- Final N: 270 executed logical cases per arm (4 arms); 180 NOT_RUN per arm (protocol exclusions, no denominator)
- Primary: stale/unauthorized-commit acceptance —
- UNBOUND: 0.571 (95% CI 0.504-0.636)
- STATE_VERSION_ONLY: 0.429 (95% CI 0.364-0.496)
- SNAPSHOT_BOUND_STATE_ONLY: 0.429 (95% CI 0.364-0.496)
- GLHS_STRICT: 0.143 (95% CI 0.102-0.197)
- Paired McNemar GLHS_STRICT vs UNBOUND: exact two-sided p = 1.6155871338926322e-27 (log10 -26.79; b=90, c=0); manuscript may state p<0.0001
- Prohibited disclosure: 0/270 every arm
- Artifact seal: `artifacts/govred/2026-08-17-rivf-final-003/artifact-sha256.json` (resolved=True, 6 entries) + `research/govred_rivf/results/analysis.json`
- Claim eligibility: SEALED_CLAIM_ELIGIBLE_executable_primary_schedules; RIVF dual-model protocol QA `NOT_RUN_pending_router_key` (recorded, not claimed)
- Raw rows reconciled: True

## GLHS — V1 HISTORICAL / V2 CLAIM-ELIGIBILITY UNRESOLVED

- Historical v1 run ID: `GLHS-POSTGRES-TOCTOU-FINAL-20260817-01`, source `2074f87550c5ee32302bde47bc0b9e6be6af36b5`, 5 frozen schedules; 4 rejected, 1 committed with indeterminate ordering, forbidden commit observed 0.
- Canonical v2 run ID: `GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01`, source `67e528b61512aabc201b344e54f9e3e724490e41`, 12 byte-verified schedules; 10 rejected, 2 committed, forbidden commit observed 0.
- V2 classification mismatches at `TOCTOU-V2-05` and `TOCTOU-V2-09` leave the run **not claim-eligible** under its frozen result rule; no universal concurrency guarantee is claimed.
- Dual-model protocol QA: agreement 1.0, kappa 1.0, unresolved 0 (protocol packet; no frozen subject/output packets existed).
- V1 seal remains immutable; v2 seal is `research/glhs_journal/protocol_v2/artifact-sha256.json` (4/4 hashes pass).

## SOICT / GovMut — COMPLETE + ANALYZED + SEALED

- Freeze: `govmut-soict-2026-final-v2`, source `ab877e04`, hypothesis 6.163.0, seeds [17,23,41,97,271]
- Dual-model review: 45/45 NON_EQUIVALENT, review artifact SHA `e9a19c4f71b26aee876ff216aa58c56314c6eb9d57b27087caa0f1e266381ba6`
- M0-M3 matrix: complete (45 included mutants x 4 methods x 5 seeds = 720 executions), 0 infrastructure exclusions
- Status: `SEALED_W8_45MUTANT_COMPLETE`; scores M0 0.356, M1 0.089, M2 0.133, M3 0.444; raw and not budget-normalized

## FMC — SUBMISSION-READY (content package)

- English/Vietnamese abstracts, GLHS disclosure, presentation outline, venue format validation, submission checklist complete; author metadata and portal confirmation pending.

## CareGuard-VN — RESULT-INCOMPLETE (refreshed 2026-08-19 by Workstream G R3)

Supporting source roles acquired under controlled manifests only: DDInter 2.0
positive reference (222,383 rows), RxNorm 2026-08-03 prescribable terminology
(6,183,895 RRF rows), and a five-record DailyMed regulatory-confirmation
subset. These are distinct source roles, not a benchmark or negative set.
Statistics plan is frozen (precision target: positive-reference N = 203 at
p=0.05, 385 at p=0.10, planning target 385); mapping-review protocol, RxMap
feasibility disposition (`ASSET_GATED`), and negative-reference decision
(specificity `UNSUPPORTED`) are recorded under `research/careguard_vn/`.

No DAV crawl or CareGuard benchmark run was performed. The Vietnam identity
frame (CG-01 external MANUAL gate) is NOT acquired, so the four-role source set
cannot validate and no final-test execution or performance result exists. See
`research/careguard_vn/READINESS.md` for the full CG-01..CG-07 gate checklist.
