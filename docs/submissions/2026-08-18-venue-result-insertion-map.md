# Venue result insertion map — sealed evidence as of 2026-08-18

Use these statements only within the named claim boundary. This file supersedes the earlier pre-final-run map.

## GovRed-Health — RIVF / IEEE BigData Healthcare

Sealed run: `2026-08-17-rivf-final-003`, frozen source `5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb`.

Primary stale/unauthorized-commit acceptance over 210 executable mandatory-primary schedules per arm:

| Arm | Failures / n | Rate | Wilson 95% CI |
| --- | ---: | ---: | --- |
| UNBOUND | 120/210 | 0.571 | 0.504–0.636 |
| STATE_VERSION_ONLY | 90/210 | 0.429 | 0.364–0.496 |
| SNAPSHOT_BOUND_STATE_ONLY | 90/210 | 0.429 | 0.364–0.496 |
| GLHS_STRICT | 30/210 | 0.143 | 0.102–0.197 |

Exact paired McNemar GLHS_STRICT vs UNBOUND: `b=90`, `c=0`, `p=1.6155871338926322e-27`.

Secondary evidence: prohibited disclosure 0/270 in every arm; audit reconstruction complete 60/270 Strict and 120/270 Snapshot-State; `NOT_RUN=180` per arm excluded from denominators. All 30 Strict primary residuals were `concurrent_stale_state_write` schedules with indeterminate ordering; serial authorization-drift families produced zero invalid Strict commits.

Permitted interpretation: **GLHS-Strict reduced stale/unauthorized-commit acceptance relative to Unbound in the executable frozen primary schedules.** Do not claim production cybersecurity effectiveness, universal concurrency safety, or general privacy proof.

## GovMut-Health — SOICT / IEEE BigData ML

Sealed freeze: `govmut-soict-2026-final-v2`, source `ab877e04`.

- 45 reviewed non-equivalent mutants.
- 16 frozen method/seed slots per mutant; 720 total executions.
- 0 infrastructure errors.
- Unmutated baseline preflight: 16/16 PASS, 0 false kills.

| Strategy | Killed / 45 | Mutation score | Exact paired p vs M3 |
| --- | ---: | ---: | ---: |
| M0 regression | 16 | 0.356 | 0.125 |
| M1 stateless property | 4 | 0.089 | 3.05e-05 |
| M2 state machine | 6 | 0.133 | 1.22e-04 |
| M3 combined | 20 | 0.444 | reference |

M3 subsumed M0: 16 both, 4 M3-only, 0 M0-only. The four-mutant gain over M0 was not significant. M3 significantly exceeded M1 and M2. M0 also exceeded M1 (`p=0.00183`) and M2 (`p=0.0213`). Seed-level terminal outcomes were 161 KILLED and 559 SURVIVED, but the scientific unit is the mutant, not the execution.

Permitted interpretation: **the combined strategy produced the highest observed mutation score and complements regression testing; it does not establish formal verification or a universal hierarchy of testing methods.**

## GLHS — FMC / AMIA HSS / AMIA Amplify

Model-context cohort:

- 64 prospectively frozen controlled synthetic subjects.
- 1,152 model-condition solver cells.
- Strict THSS: Claude 63/64 all-axes exact; Gemini 64/64.
- Aggregate all-axes exact: 1,027/1,152 = 89.15%.
- Six of ten preregistered contrasts Holm-significant; significant contrasts had only 9–21 discordant subjects, below the planned informative-pair target.

Governance TOCTOU evidence:

- Run `GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01`, 12 frozen PostgreSQL schedules.
- Persisted governance writers included consent revoke, role change, and policy-epoch advance.
- 0 forbidden commits observed; 0 indeterminate ordering; 0 deadlock-as-safety.
- Invalid post-change attempts were rejected; temporally valid controls could commit.

Bounded formal assurance:

- Depth-5 exhaustive exploration: 21,361 unique states, 90,432 transitions, 0 violations of 11 invariants.
- This is bounded finite-state checking, not universal proof.

Permitted interpretation: **GLHS provides tested software continuity from governed disclosure to persistent write admission under the frozen synthetic/system conditions.** Do not claim clinical efficacy or correctness for arbitrary unbounded interleavings.

## CLARA-Care FHIR App

Verified processing evidence suitable for the application:

- SyntheticMass: 1,307,771 FHIR Bundles processed.
- MIMIC-IV Demo FHIR: 927,109 records for 100 subjects.
- eICU Demo: 540,237 normalized records for 1,841 subjects and 2,520 ICU stays.

These counts support ingestion/provenance and adapter-execution claims only. They do not establish clinical correctness or FHIR server conformance.

## CareGuard-VN

Do not fill an external-results section yet. Final evidence status is `PAUSED_BY_OPERATOR`; no final DAV crawl or sealed CareGuard external benchmark was run in the evidence-upgrade program.