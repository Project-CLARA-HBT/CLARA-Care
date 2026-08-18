# 2026 CLARA-Care conference research-content status

**Status date:** 2026-08-18  
**Scope:** scientific/research-content completeness only. Submission logistics, mentor letters, form fields, file-size limits, and simultaneous-submission policy are intentionally outside this status.

## Research-content readiness

| Manuscript | Status | Evidence now available |
| --- | --- | --- |
| **RIVF 2026 — GovRed-Health** | **READY WITH LIMITATIONS** | Sealed run `2026-08-17-rivf-final-003`: 270 executed schedules/arm; primary denominator 210/arm; stale/unauthorized-commit acceptance 0.571 Unbound, 0.429 State-Version-Only, 0.429 Snapshot-Bound-State-Only, 0.143 GLHS-Strict; GLHS-Strict vs Unbound exact McNemar `b=90,c=0,p=1.62e-27`; prohibited disclosure 0/270 every arm. |
| **SOICT 2026 — GovMut-Health** | **READY** | Freeze `govmut-soict-2026-final-v2`: 45 reviewed mutants × 16 frozen method/seed slots = 720 executions, 0 infrastructure errors. Mutation scores M0/M1/M2/M3 = 0.356/0.089/0.133/0.444. M3 > M1 (`p=3.05e-05`) and M3 > M2 (`p=1.22e-04`); M3 vs M0 not significant (`p=0.125`). All 16 unmutated preflight checks passed. |
| **FMC 2026 — GLHS abstract VI/EN** | **READY** | Frozen 64-subject synthetic two-model cohort; PostgreSQL governance-TOCTOU v2 with 12 schedules and 0 forbidden commits; bounded formal exploration 21,361 states / 90,432 transitions / 0 invariant violations at depth 5. |
| **IEEE BigData Healthcare 2026 — GovRed-Health** | **READY WITH LIMITATIONS** | Same sealed GovRed study, with explicit NOT_RUN exclusions and concurrency/audit limitations. |
| **IEEE BigData ML 2026 — GovMut-Health** | **READY** | Same sealed 45-mutant GovMut study; mutant is the scientific unit, seeds/executions are not independent N. |
| **AMIA HSS 2026 — GLHS** | **READY** | 64-subject synthetic model cohort + 12-schedule governance-TOCTOU matrix + bounded formal assurance. |
| **AMIA Amplify 2027 — CLARA-Care System Demo** | **READY** | Working governed read/write prototype plus TOCTOU and bounded-formal evidence; no clinical-deployment claim needed for the research content. |
| **AMIA/HL7 FHIR App 2026 — CLARA-Care** | **READY** | Verified local processing: 1,307,771 SyntheticMass FHIR Bundles; 927,109 MIMIC-IV Demo FHIR records for 100 subjects; eICU Demo normalization 540,237 records for 1,841 subjects / 2,520 ICU stays; coupled to governed disclosure/writeback evidence. |
| **CareGuard-VN** | **NOT RESULT-COMPLETE** | Final evidence program records `PAUSED_BY_OPERATOR`; no DAV crawl or final external CareGuard source acquisition/benchmark was run. Keep as methods/protocol draft until external evaluation is executed and sealed. |

## Claim boundaries that remain mandatory

- **GovRed:** `NOT_RUN=180` per arm are protocol exclusions and never count as successes. All 30 GLHS-Strict primary residuals are `concurrent_stale_state_write` with indeterminate ordering; therefore do not claim universal concurrency safety.
- **GovMut:** the experimental unit is one reviewed mutant. The 720 method/seed executions are execution mechanics, not `N=720` independent samples.
- **GLHS model cohort:** 64 subjects are controlled synthetic software/mechanism evidence, not clinical efficacy. Six of ten preregistered contrasts were Holm-significant, but significant contrasts had only 9–21 discordant subjects and the planned informative-pair target was not met.
- **Formal assurance:** 21,361 states / 90,432 transitions with zero violations is bounded finite-state checking, not an unbounded proof.
- **FHIR ingestion counts:** demonstrate ingestion/provenance/adapter execution, not clinical correctness.
- No manuscript should claim superiority to MemTX/MemTxn/CommitGuard as systems because no faithful same-task direct execution exists.

## Repository evidence used

- `research/FINAL_TOP_TIER_EVIDENCE_STATUS.md`
- `research/govred_rivf/results/final-003-analysis-v2.json`
- `research/govred_rivf/MANUSCRIPT_RESULTS.md`
- `research/assurance_soict/results/final-analysis.json`
- `research/glhs_journal/protocol_v2/analysis_v2.json`
- `research/evidence_upgrade/formal/FORMAL_ASSURE_REPORT.md`
- `docs/architecture/commitloop-confirmatory-v5-results.md`
- `docs/architecture/glhs-evidence-hardening-status.md`

The manuscript sources synchronized on 2026-08-18 are stored under `docs/submissions/manuscripts/2026-08-18/`.