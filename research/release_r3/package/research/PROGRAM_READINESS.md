# Research-program evidence register

Status at 2026-08-19: **GovRed final-003 and GovMut W8 are claim-eligible; CareGuard and GLHS revision remain gated**. This register
is a cross-study handoff map. The study-specific readiness documents and claim
ledgers remain authoritative; this file neither replaces them nor authorizes an
execution, external contact, or submission.

| Study | Primary claim / current state | Evidence still required | Authority or controlled action required |
| --- | --- | --- | --- |
| GovRed-Health / RIVF | Final-003 executable primary schedules — `sealed_claim_eligible` | Fresh holdout, repetition/auditability execution, and RIVF dual-model protocol QA remain open; 180 protocol-excluded cases per arm remain outside denominators. | Operator-owned isolated follow-up execution; never use `clara-app` or production resources. |
| GovMut-Health / SOICT | W8 comparative mutation score — `sealed_claim_eligible` | Budget-fair equal-wall-clock comparison, survivor classification, and any W9 extension remain separate gates; W8 raw scores are not budget-normalized. | New freeze and independently reviewed extension inputs before any second-venue claim. |
| CareGuard-VN | `RESULT-INCOMPLETE` — no benchmark result | Current Vietnam identity frame with reuse terms, authorized frozen RxNorm release, complete four-role source set, locked split, and oracle-identity execution. | Official source access or published reuse/export authority; absence from DDInter remains unknown, never a negative label. |
| GLHS revision | Byte-verified v2 TOCTOU artifact — `claim-eligibility unresolved` | Reconcile two frozen v2 observation mismatches, plus clinical adjudication and false-stale/scaling gates. | Isolated PostgreSQL rerun/reseal and qualified independent external reviewers; development observations remain non-final. |
| FMC 2026 | Permission to present related under-review work — `NOT_RUN` | A compatible organizer reply that addresses under-review work and duplicate archival publication, retained with source/hash. | Organizer response. Until then all materials are preparation-only and must not be submitted. |

## Global claim rule

A protocol, hash gate, development trace, discovery receipt, or source subset is
not a primary result. A primary claim can change only after its corresponding
study ledger records claim-eligible evidence and the required controlled action
or external authority above has occurred.

## Authoritative pointers

- `research/claim_ledger.csv`
- `research/govred_rivf/READINESS.md`
- `research/assurance_soict/READINESS.md`
- `research/careguard_vn/READINESS.md`
- `research/glhs_journal/REVISION_READINESS.md`
- `research/fmc2026/POLICY_CLEARANCE.md`
