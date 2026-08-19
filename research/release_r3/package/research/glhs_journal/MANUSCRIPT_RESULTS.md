# GLHS Journal Revision — PostgreSQL TOCTOU Evidence Status

## Canonical guarantee

On the evaluated snapshot-bound path, a proposal derived from THSS retains the exact disclosure binding through GST admission; universal provenance-sensitive retention across every internal review/adaptation path has not yet been established.

## Canonical run identity

- Run ID: `GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01`
- Frozen source revision: `67e528b61512aabc201b344e54f9e3e724490e41`
- Backend: fresh isolated PostgreSQL, random per-run schema, non-default `glhs_final` database
- Unit of analysis: one frozen logical schedule; retries and repeated API calls are not additional N
- Classification: ordering established only when observable; genuinely overlapping races are `INDETERMINATE`
- Evidence root: `research/glhs_journal/protocol_v2/`
- Seal: four declared SHA-256 entries pass; the raw run status is `EXECUTED_V2_OBSERVATION_MISMATCH`, so this artifact is byte-verified but not currently claim-eligible.

## Final schedule matrix

| Schedule set | Outcome summary | Forbidden commit | Ordering |
| --- | --- | --- | --- | --- |
| v2, 12 frozen schedules | 10 rejected; 1 committed control before revoke; 1 committed concurrent proposal; 0 observed indeterminate outcomes | 0 | 2 expected/observed classification mismatches |

## Summary

- Schedules executed: 12 (all protocol identifiers present)
- Rejected by governance/state revalidation: 10
- Committed transitions: 2 (one control and one concurrent proposal)
- Forbidden commit observed: 0
- Observed indeterminate outcomes: 0
- Classification mismatches: `TOCTOU-V2-05` and `TOCTOU-V2-09`; both were expected to be `indeterminate_ordering` but observed rejection.

The frozen protocol states that any expected/observed classification mismatch is not
claim-eligible. The mismatch is conservative in direction, but it remains a mismatch;
no universal concurrency or provenance-retention guarantee is claimed.

## Historical v1 record

The five-schedule run `GLHS-POSTGRES-TOCTOU-FINAL-20260817-01` (source
`2074f87550c5ee32302bde47bc0b9e6be6af36b5`) remains immutable historical evidence:
four rejected schedules, one committed transition with indeterminate ordering, and
zero forbidden commits. It is not overwritten by v2.

## Context-utility evidence balance

- The verified positive cohort contains 64 synthetic subjects (`confirmatory-cohort-v2`, `COMPLETE_VALID`). Its subject-level positive result is retained as historical evidence and is not a clinical-effectiveness claim.
- The 384-subject strict-versus-full-authorized-history record is `DESCRIPTIVE_SYNTHETIC_ONLY`, with 384 ties and effect 0.0. Its cohort is `GENERATED_NOT_FROZEN`; it is not a sealed null result and must not be cited as one.
- These positive and null-context records remain separate evidence classes. Neither changes the TOCTOU claim-eligibility mismatch above.

## Dual-model protocol QA

- `gemini-3.6-flash-high` + `claude-sonnet-4-6`, frozen protocol packet
- Pre-reconciliation agreement: 1.0; Cohen's kappa 1.0; unresolved 0
- This is a dual-model blinded protocol-review surrogate; it is not human/clinician/expert adjudication and not clinical-effectiveness evidence.
- No frozen subject/output adjudication packets existed, so no separate output-adjudication run was eligible.

## Claim boundary

The byte-verified v2 artifact supports only a descriptive account of the observed
12-schedule run pending reconciliation of its two frozen classification mismatches.
The historical v1 matrix demonstrates governance/state revalidation rejecting stale
or no-longer-authorized persistent proposals in observed serial schedules, with one
concurrent-writer schedule honestly left INDETERMINATE. Neither run claims clinical
benefit or a universal production guarantee.
