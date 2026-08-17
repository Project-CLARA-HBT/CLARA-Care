# CLARA-Care Final Program Status (Pre-CareGuard)

Status generated after final executions for RIVF and GLHS; SOICT matrix in progress.

## RIVF / GovRed — COMPLETE + ANALYZED + SEALED

- Run ID: `2026-08-17-rivf-final-003`
- Frozen git SHA: `5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb`
- Final N: 270 executed logical cases per arm (4 arms); 180 NOT_RUN per arm (protocol exclusions, no denominator)
- Primary: stale/unauthorized-commit acceptance — UNBOUND 0.571 (95% CI 0.504-0.636), STATE_VERSION_ONLY 0.429 (0.364-0.496), SNAPSHOT_BOUND_STATE_ONLY 0.429 (0.364-0.496), GLHS_STRICT 0.143 (0.102-0.197)
- Paired McNemar GLHS_STRICT vs UNBOUND: p<0.0001 (b=90, c=0)
- Prohibited disclosure: 0/270 every arm
- Artifact seal: `artifacts/govred/2026-08-17-rivf-final-003/artifact-sha256.json` (gitignored raw store) + `research/govred_rivf/results/analysis.json`
- Claim eligibility: SEALED_CLAIM_ELIGIBLE for executable primary schedules; RIVF dual-model protocol QA pending router key (recorded, not claimed)
- Manuscript readiness: `research/govred_rivf/MANUSCRIPT_RESULTS.md`, `LIMITATIONS.md`, READINESS.md updated

## GLHS — COMPLETE + ANALYZED + SEALED

- Run ID: `GLHS-POSTGRES-TOCTOU-FINAL-20260817-01`
- Frozen git SHA: `2074f87550c5ee32302bde47bc0b9e6be6af36b5`
- Final N: 5 frozen logical schedules
- Outcomes: 4 rejected (consent/actor-role/policy/consent races), 1 committed transition (TOCTOU-03) with INDETERMINATE ordering; forbidden commit observed 0
- Dual-model protocol QA: agreement 1.0, kappa 1.0, unresolved 0 (protocol packet; no frozen subject/output packets existed)
- Artifact seal: `artifacts/glhs-postgres-toctou/GLHS-POSTGRES-TOCTOU-FINAL-20260817-01/artifact-sha256.json` + `research/glhs_journal/results/analysis.json`
- Claim eligibility: SEALED_CLAIM_ELIGIBLE (final matrix); manuscript: `research/glhs_journal/MANUSCRIPT_RESULTS.md`, `LIMITATIONS.md`

## SOICT / GovMut — IN PROGRESS

- Freeze: `govmut-soict-2026-final-v2`, git SHA `ab877e04`, hypothesis 6.163.0, seeds [17,23,41,97,271]
- Dual-model review: 45/45 NON_EQUIVALENT, review artifact SHA `e9a19c4f71b26aee876ff216aa58c56314c6eb9d57b27087caa0f1e266381ba6`
- M0-M3 matrix: running (45 included mutants x 4 methods x 5 seeds = 720 executions, atomic output)
- Status: EXECUTING; no final_run.json until complete

## FMC — SUBMISSION-READY (content package)

- English/Vietnamese abstracts, GLHS disclosure, presentation outline, venue format validation, submission checklist complete; author metadata and portal confirmation pending.

## CareGuard-VN — PAUSED_BY_OPERATOR

No DAV crawl or CareGuard source acquisition performed during this phase.
