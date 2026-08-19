# GovMut-Health SOICT assurance readiness

Status: **W8 SEALED AND ANALYZED — govmut-soict-2026-final-v2**.

The W8 freeze contains 45 real, noncosmetic, semantically distinct executable mutants and 720 controlled executions across M0-M3, with zero infrastructure exclusions. The locked contribution is a health-AI governance fault taxonomy, executable mutant corpus, and comparative adequacy evidence—not novel PBT, state-machine, or mutation testing. Earlier in-process and one-mutant runs remain development diagnostics and are not merged into the W8 denominators.

An independent toy governed-store contract now covers subject, actor, purpose,
state, policy, consent, expiry, digest, and idempotent replay without importing
GLHS/CLARA code. It is an external-validity substrate only, not a second
clinical implementation, mutation result, or generalization claim.

Remaining extension gates: a budget-fair equal-wall-clock comparison, prespecified survivor classification, and any W9 follow-up. These are not prerequisites for the sealed W8 mutation scores and must not be backfilled with development diagnostics.

`development_suite_matrix.json` now binds M0 regression, M1 stateless
property, M2 state-machine, and M3 combined targets in one machine-readable
development-only contract. It prevents a partial combined suite from being
silently compared with another method, but does not freeze targets, execute a
mutant, or establish a mutation score.

The overlay primitive now creates a copied, anchored, one-change source file
and rejects cosmetic or non-unique anchors. The 45 anchored variants were bound
into the W8 frozen corpus and executed against the complete M0-M3 matrix. The
separate W8 seal, not the earlier development ledger, is the source for the
mutation-score denominator and adequacy comparison.

All artifacts in `artifacts/assurance/2026-08-16-dev-001/` are retained for
audit but invalid as mutant executions. Their raw output exposed an isolation
defect: pytest imported the workspace source rather than the staged overlay.
They must not be used for a gap signal, score, or comparison. The runner now
uses a staged working directory and absolute test targets, with a regression
test for that contract, and records the repository revision for later runs.
Corrected development runs use a new run ID and remain
non-headline until a corpus and final protocol are frozen.

Corrected development run `2026-08-16-dev-003` executed M08-A against the
current combined suite using the staged source tree. It was killed by the
existing tampered assertion-value regression (1 failed, 20 passed); retained
raw output identifies the staged import path. This is one development mutant
outcome, not a mutation score or comparative-adequacy result.

Corrected development run `2026-08-16-dev-004` executed M02-A under the same
staged-import probe. It was killed by the state-machine policy-mutation rule
(1 failed, 20 passed), and the raw output retains Hypothesis's minimized trace.
This is likewise one development mutant outcome, not a score or method
comparison.

Corrected development run `2026-08-16-dev-005` executed M03-A under the same
staged-import probe. It survived the current combined suite (21 passed), which
is a local development coverage-gap signal for consent-version revalidation.
It is not evidence of deployed behavior, a score, or a method comparison.

After adding a consent-mutation state-machine rule, the distinct run
`2026-08-16-dev-006` killed M03-A (1 failed, 20 passed) with a retained,
minimized trace. The M03 runs use different target hashes and are not a before/
after adequacy comparison; both remain development evidence only.

Combined M3 execution of M04-A in `2026-08-17-dev-007` reached the explicit
120-second runner timeout after 20 test completions. It is retained as an
`INFRASTRUCTURE_ERROR_NOT_KILLED` artifact and excluded from every prospective
mutation-score denominator. Its timeout must be diagnosed before a final suite
time limit can be frozen.

M04-A survived an older M0 target file, then the distinct updated M0 run
`2026-08-17-dev-009` killed it with a foreign-profile assertion regression
(1 failed, 13 passed). The target hash changed with the new test, so these are
sequential development diagnostics, not comparative adequacy evidence.

M05-A likewise survived an older M0 target file, then updated M0 run
`2026-08-17-dev-011` killed it using a foreign-actor THSS snapshot-binding
regression (1 failed, 14 passed). Its run records the repository revision,
staged import path, target hash, and raw output; the changed target hash still
rules out any comparative adequacy interpretation.

M07-A also survived an older M0 target file, then updated M0 run
`2026-08-17-dev-013` killed it with a clock-based expired-snapshot regression
(1 failed, 15 passed) that preserves snapshot-ledger immutability. It is one
development diagnostic with a changed target hash, not comparative evidence.

Current staged M0 run `2026-08-17-dev-014` killed M08-A with the existing
tampered assertion-value regression (1 failed, 15 passed). It is a single
development mutation datum with no mutation-score denominator or comparison.

Current staged M0 run `2026-08-17-dev-015` killed M09-A using the mandatory
THSS-binding regression (1 failed). This is direct binding conformance only,
not an API/PostgreSQL end-to-end outcome or a comparative score.

Current staged M0 run `2026-08-17-dev-016` killed M06-A with a direct
snapshot-purpose mismatch regression (1 failed). It retains the staged import
path, repository revision, target hash, and raw output. This is one development
diagnostic for the purpose coordinate only; it provides neither a mutation-score
denominator nor a method comparison.

Development run `2026-08-17-dev-017` executed the newly anchored M01-C
commitment stale-state mutant against the complete development M0 target set.
It survived (27 passed) with staged-import proof and retained raw output. This
is a local regression-coverage gap for that enforcement site only, not an
equivalence finding, mutation score, or comparison with M1–M3.

Development run `2026-08-17-dev-018` executed the same M01-C mutant against
the M1 stateless-property target and it survived. This is another local
development coverage-gap signal; it neither supplies M2/M3 outcomes nor a
method comparison.

Development run `2026-08-17-dev-023` executed newly anchored M05-B against
the complete development M0 target set. It was killed by the explicit current
actor-role THSS-binding regression (1 failed, 26 passed). This confirms only
one staged direct-gateway development diagnostic, not a mutation score or
comparison with the property/state-machine methods.

Development run `2026-08-17-dev-024` executed the same M05-B mutant against
M1 and it survived (7 passed). This local property-suite coverage gap is not a
comparison: M2 and M3 have not been run for this mutant and the matrix remains
development-only.

Development run `2026-08-17-dev-025` attempted M05-B under M2 but reached the
explicit 120-second runner timeout. Its `INFRASTRUCTURE_ERROR_NOT_KILLED`
artifact is excluded from every prospective denominator and supplies no M2
adequacy result. The state-machine timeout must be diagnosed before a final
method limit can be frozen.

The timeout diagnosis found a reference-model defect: its boolean governance
flag could not distinguish proposals made before a second consent mutation.
The development state machine now tracks a governance epoch and its unmutated
baseline passes without reducing examples or steps. A distinct M05-B M2 run
`2026-08-17-dev-027` then survived (1 passed), but has a different target hash
from the timeout and still supplies no method comparison or score.

With that repaired M2 target included, `2026-08-17-dev-028` ran M05-B under
M3 and killed it through the explicit direct THSS actor-role regression (1
failed, 34 passed). This is a diagnostic only: prior M0/M1 runs do not share
the repaired combined target set, and no corpus/protocol freeze exists.

Fresh post-repair M0 and M1 reruns (`2026-08-17-dev-029` and `-030`) preserve
the observed kill/survive pattern for this one mutant. They complete a
development diagnostic group with the separately retained M2/M3 artifacts,
but there is no frozen corpus, seed/limit protocol, or comparative inference.

Development runs `2026-08-17-dev-031` through `-034` executed the distinct
M02-D base-proposal policy-version overlay under the then-current development
M0–M3 matrix and survived all four suites with staged-source import proofs.
Those artifacts predate the addition of the direct base-proposal stale-policy
regression to M0/M3, so they are not comparable to any later execution. This
is a narrow local coverage-gap diagnostic only: the matrix and corpus are not
frozen, non-equivalence has not been established, and it contributes to no
mutation-score denominator or method-comparison inference.

After adding the direct base-proposal stale-policy regression to M0, development
run `2026-08-17-dev-035` killed M02-D through that expanded staged M0 target
set. This is a post-matrix-change diagnostic only: its target hashes differ from
the earlier M1–M3 artifacts, so it cannot be used for a method comparison.

The development runner now resolves a named method only through the checked
`development_suite_matrix.json`, or records explicit manual targets; mixing the
two fails closed. Run `2026-08-17-dev-039` re-executed M02-D through that M0
matrix selector, with the same source/catalog/test-target hashes as dev-035 and
a staged-source import proof. It was killed again by the direct stale-policy
regression. This is a runner-reproducibility diagnostic, not an additional
mutant, independent replicate, mutation-score datum, or method comparison.

Generated-method matrix runs now require an explicit Hypothesis seed and retain
it in the raw execution artifact; manual-target runs continue to record whether
a seed was supplied. Development run `2026-08-17-dev-040` executed M02-D under
M1 with seed `20260817` and survived. It verifies this reproducibility control
only: the final ordered seed list, Hypothesis-version/limit freeze,
non-equivalence review, corpus freeze, and M0–M3 execution remain open, so it
is not an additional replicate, score datum, or method-comparison result.

The paired M2 and M3 development runs `2026-08-17-dev-041` and `-042` complete
the current M02-D vector with the same explicit generated-method seed. M2
survived and M3 was killed; together with the matrix-selected M0 and seeded M1
diagnostics, this is one current-target development vector for one mutant. It
does not make retries or generated examples independent units, and it remains
outside every mutation-score denominator and method-comparison inference until
the corpus, final seed list, limits, non-equivalence review, and analysis plan
are independently frozen.

`evaluation/property_assurance/final_freeze.py` supplied the pre-execution
integrity gate for W8. The resulting final manifest, reviewed non-equivalence
list, corpus execution, scores, and comparisons are sealed under
`research/assurance_soict/seal/`; this gate remains required for any future W9
extension.

## W8 sealed result (2026-08-18)

The claim-eligible freeze is `govmut-soict-2026-final-v2`: M0 0.356 (16/45),
M1 0.089 (4/45), M2 0.133 (6/45), and M3 0.444 (20/45). The scores use
`detected_any_seed`; seeds are deterministic streams, not independent subjects.
M3 is the M0+M1+M2 union/superset, and the raw ranking is not
budget-normalized. The second venue remains extension-only under the shared
W8 evidence freeze.
