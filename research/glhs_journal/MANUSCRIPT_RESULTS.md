# GLHS Journal Revision — PostgreSQL TOCTOU Final Matrix Results

## Run identity

- Run ID: `GLHS-POSTGRES-TOCTOU-FINAL-20260817-01`
- Frozen source revision: `2074f87550c5ee32302bde47bc0b9e6be6af36b5`
- Backend: fresh isolated PostgreSQL, random per-run schema, non-default `glhs_final` database
- Unit of analysis: one frozen logical schedule; retries and repeated API calls are not additional N
- Classification: ordering established only when observable; genuinely overlapping races are `INDETERMINATE`

## Final schedule matrix

| Schedule | Outcome | Forbidden commit | Ordering | Latency (ms) |
| --- | --- | --- | --- | --- |
| TOCTOU-01 (consent mutation) | assertion_consent_mismatch | not observed | ordered serial | 51.3 |
| TOCTOU-02 (actor/role mutation) | proposal_snapshot_actor_role_mismatch | not observed | ordered serial | 53.8 |
| TOCTOU-03 (concurrent governance writer vs proposal writer) | transition_committed | not determinable | **INDETERMINATE** | 40.4 |
| TOCTOU-04 (policy/governance mutation) | proposal_snapshot_policy_mismatch | not observed | ordered serial | 17.4 |
| TOCTOU-05 (concurrent consent/policy writer vs proposal) | proposal_snapshot_consent_mismatch | not observed | rejected_after_or_during_race | 12.3 |

## Summary

- Schedules executed: 5 (all frozen schedules)
- Rejected by governance/state revalidation: 4
- Committed transition: 1 (TOCTOU-03, ordering not determinable)
- Forbidden commit observed: 0
- INDETERMINATE ordering: 1 (TOCTOU-03)

## Dual-model protocol QA

- `gemini-3.6-flash-high` + `claude-sonnet-4-6`, frozen protocol packet
- Pre-reconciliation agreement: 1.0; Cohen's kappa 1.0; unresolved 0
- This is a dual-model blinded protocol-review surrogate; it is not human/clinician/expert adjudication and not clinical-effectiveness evidence.
- No frozen subject/output adjudication packets existed, so no separate output-adjudication run was eligible.

## Claim boundary

The final PostgreSQL matrix demonstrates governance/state revalidation rejecting stale or no-longer-authorized persistent proposals in the observed serial schedules, with one concurrent-writer schedule honestly left INDETERMINATE. It does not claim ordering guarantees for races whose interleaving cannot be established, and does not claim clinical benefit.
