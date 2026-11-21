# GLHS Journal Revision — PostgreSQL TOCTOU Evidence Status

## Correction to the R4 comparator results

E16 evaluated five validators on 500 synthetic schedules in SQLite. Both the signed token and full GLHS accepted all 100 valid proposals and rejected all 400 invalid proposals. The harness assigned a reconstruction score from the arm name before evaluating the schedules. The published 100 and 50 scores should be withdrawn as evidence of byte recovery. An equal-retention comparison subsequently read actual bytes from 1,233 public dialogue snapshots across three retention stages. GLHS and a signed receipt with content-addressed storage tied on 3,699 reads. [E16 audit](comparator_recheck/RESULTS.md) · [Measured byte recovery](byte_reconstruction/RESULTS.md)

For E17, the sealed clean-control rows record 100/100 admissions by C0, C1 and C4, and 0/100 by C3. The archived prose's assertion of 100% clean liveness for all four arms is incorrect. The runner explicitly passed the observed projection to C4 on clean cases and omitted it from the corresponding C3 call. It recorded no C3 rejection reasons in these rows. These data cannot support an equally informed comparison of clean liveness. The historical R4 manuscript and its seal retain the original release. [Clean-control audit](comparator_recheck/clean_controls.json)

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

## External descriptive study of medication projection identity

We selected the first two encounters in source-file order for each person with repeat encounters in the UCI Diabetes 130-US Hospitals dataset. Of 101,766 encounters from 71,518 people, 16,773 people contributed one pair each. The other 54,745 people had a single encounter. A further 13,475 encounters occurred beyond the two selected records in file order. The study used the 23 recorded medication-status fields. File order supplied a reproducible selection rule and conveyed no assumption about clinical chronology. [Dataset (Clore, Cios, DeShazo and Strack)](https://doi.org/10.24432/C5230J)

For 5,603 pairs (33.4%), distinct encounter records yielded identical medication projections. For another 2,418 pairs (14.4%), the drug-presence indicators agreed but at least one recorded medication status differed. The remaining 8,752 pairs (52.2%) differed on presence. The production GLHS projection digest agreed with direct comparison of all source fields on 16,773/16,773 pairs. A content digest alone therefore could not distinguish the encounter instances for the first 5,603 pairs. This observation concerns one projection and sampling rule. The source contains no GLHS dispatch records, consent transitions, or observed write decisions from which to estimate a governance failure rate. [Protocol](../../evaluation/external_validation/protocols/uci296-projection-identity-v1.md) · [Aggregate result](results/uci296-projection-identity-v1.json)
