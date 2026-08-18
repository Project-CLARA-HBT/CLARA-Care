# Synchronized manuscript research-content status

Generated from the user-provided VN/US LaTeX manuscript packs on 2026-08-18 and checked against sealed evidence on `codex/commitloop-phase-a`.

## READY

- SOICT 2026 — GovMut-Health
- FMC 2026 — GLHS Vietnamese and English abstracts
- IEEE BigData ML 2026 — GovMut-Health
- AMIA HSS 2026 — GLHS
- AMIA Amplify 2027 — CLARA-Care System Demonstration
- AMIA/HL7 FHIR App 2026 — CLARA-Care

## READY WITH LIMITATIONS

- RIVF 2026 — GovRed-Health
- IEEE BigData Healthcare 2026 — GovRed-Health

The GovRed result is sealed and publishable as controlled synthetic software robustness evidence, but `NOT_RUN=180` per arm are excluded protocol rows and all 30 Strict primary residual failures are concurrent-stale-state schedules with indeterminate ordering. Do not promote the result to universal concurrency or production-security validation.

## NOT RESULT-COMPLETE

- CareGuard-VN: final external benchmark remains paused/not executed.

## Source synchronization performed

The corresponding local LaTeX pack was updated to remove pre-run PENDING markers and insert the sealed results:

- GovRed: 270 executed schedules/arm; primary n=210/arm; failure rates 0.571/0.429/0.429/0.143; Strict vs Unbound exact McNemar `p=1.62e-27`; prohibited disclosure 0/270 each arm.
- GovMut: 45 mutants; 720 method/seed executions; 0 infrastructure errors; M0/M1/M2/M3 mutation scores 0.356/0.089/0.133/0.444; M3 significant vs M1/M2 but not M0.
- GLHS: 64-subject controlled synthetic model cohort; 12-schedule PostgreSQL governance-TOCTOU matrix with 0 forbidden commits; bounded exploration 21,361 states / 90,432 transitions / 0 invariant violations.
- FHIR application: SyntheticMass 1,307,771 FHIR Bundles; MIMIC-IV Demo FHIR 927,109 records/100 subjects; eICU Demo 540,237 normalized records/1,841 subjects/2,520 ICU stays.

All LaTeX manuscript files marked READY above passed `pdflatex -draftmode -interaction=nonstopmode -halt-on-error` after synchronization.