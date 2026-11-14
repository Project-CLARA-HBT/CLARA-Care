# Paired Shadow-Certification (PSC): prospective research method

**Status:** a proposed research architecture and restricted reference model, not a validated discovery, independent external certificate, a new named cryptographic primitive, or a demonstration that the algorithm outperforms baselines.

## A. Motivating correction from TwinCert-F1 V3

TwinCert-F1 V3 was designed around a digital-twin compatibility gate and paired, non-inferiority certification in heterogeneous FL IDS. The internal reviewer report found five benchmark configurations labeled `INCONCLUSIVE_fallback`, variable Macro-F1 across non-IID regimes, and insufficient ablations for the proposed contributions. **Do not cite TwinCert as a validated SOTA result.** The transferable design principle is pre-deployment paired admission with explicit abstain/fallback and a real same-budget comparator. PSC applies this principle to stateful AI write authorization, a different problem; PSC must not claim conceptual originality merely because it uses twins or certificates.

## B. The narrow possible research contribution

A machine-generated health-state write is authorized only if its **actual dispatched projection** and its **current commit-time dependencies and governance** are both demonstrably valid. The proposed additional capability is **selective recovery of valid work after unrelated state changes**, subject to the exact same atomic commit safety check and a sound dependency-completeness oracle. Static signed capability tokens and read-set OCC can already express much of this mechanism; these are formidable baselines, not deficient baselines.

## C. Two independent shadows

**Shadow A (historical-disclosure verifier)**: reconstructs the immutable governed projection and the actual serialized inference request. Check H_proj against dispatch bytes; actor, purpose, task, tenant, reference epoch, expiry and lineage must match; the evidence claimed by the proposal must be a subset of the evidence supplied to inference. This does **not** prove neural semantic attention or clinician correctness.

**Shadow B (current-state counterfactual)**: reconstructs commit-time state and authorization. Re-evaluates consent and policy against current epochs, derives the conservative required dependency closure D_required(o), compares all required versioned facts, and tests whether applying the proposal would violate a formal invariant in an isolated shadow. This counterfactual is **not** a substitute for final checks under actual PostgreSQL locks or serializable transaction.

**Certificate gate**: verify authenticated binding/nonce, A and B, and ensure all predicates are checked in the same transaction that writes or rejects. For an unrelated version change, issue conditional selective recovery only when independence is witnessed and neither governance nor required dependencies changed. No silent clinical content rewrite. On unknown dependency, policy ambiguity, consent revocation or evidence gap => defer/reject (fail-closed).

## D. Exact claim model

Let P be an AI proposal, D the dispatched disclosure, R the required dependency closure, G_t the current governance tuple, S_t the current state, and H a collision-resistant digest. Let C be a bound proposal certificate.

- Supply(P,D,C): verify exact dispatch binding, evidence containment, nonce binding, and proposal lineage.
- Govern(G_t,P): verify actor/purpose/task/tenant/current consent and authorization; unknown means no admit.
- Fresh(R,S_t,C): for each e in R compare currently persisted version/digest, with mandatory governance epochs separately checked.
- Safe(S_t,P): independent deterministic domain invariants, not a physician-level clinical assessment.
- AtomicCommit(S_t,P): locks or SSI transaction rechecks all above, then writes one durable state transition with idempotent outbox.

**Admission predicate:**

`admit(P) = Supply(P,D,C) AND Govern(G_t,P) AND Fresh(R,S_t,C) AND Safe(S_t,P) AND AtomicCommit(S_t,P)`

A certificate computed outside the transaction is only an advisory candidate. Authorization MUST be repeated inside the transaction; another writer may otherwise race the gate.

**Conditional soundness obligation (not an achieved theorem):** if the oracle includes *every* policy/data dependency, the binding is authenticated, the atomic transaction/retry model is correct, and each deterministic invariant is correctly specified, a committed proposal must satisfy the stated predicates at its serialization point. General security, neural reasoning, clinical outcomes, privacy, and zero side effects are not implied.

## E. Utility mechanism and honest best-outcome potential

The intervention is *not* an extra gate that simply rejects more writes. It is a **dependency-complete selective rescue** for independent concurrent changes, with a well-specified abstention option. It can potentially outperform profile-global invalidation on legitimate completion while retaining the safety of equivalent strong validators. It may *lose* to plain PostgreSQL SERIALIZABLE or signed capabilities due to overchecking and crypto CPU cost. Include both; a negative result is valid.

We optimize the safety/utility/cost frontier, not test accuracy in isolation:

- Hard safety: paired invalid-admission risk difference and an exact one-sided upper confidence bound with a preregistered minimum independent N.
- Useful work: valid eligible task completion / false-stale denial for clean-control cases.
- Operational cost: latency p50/p95/p99, throughput, retries, bytes and verification CPU.
- Selectivity: certified / abstained / rejected rates; a method cannot win by rejecting all requests.
- Generalization: unseen attacker families, new sites/domains, widened policy semantics, higher contention, dependency graph misspecification.

## F. Double certification (guarded statistical decision)

1. Safety **non-inferiority** to the strongest comparator, on independently oracle-labeled invalid proposals. Set margin epsilon_s and confidence level before holdout. Use paired risk differences/cluster bootstrap or exact discordant-pair intervals. Never use p>0.05 as proof of equivalence.
2. Utility **superiority** on legitimate proposals, in a separate locked holdout; compare paired valid completion, coverage or false-stale burden; predefine minimum practically interesting delta_u and account for latency.
3. Coverage floor, fairness and missingness: a verifier that abstains on everyone is disqualified. Fail-close behavior is evaluated separately from utility.
4. **Certification outcome** is one of CERTIFIED, INCONCLUSIVE or REJECTED. An inconclusive trial cannot be relabeled as successful; no adaptive tuning on final holdout.

## G. How to get strong numbers legitimately

- Method must have a genuine mechanism advantage: selective dependency independence, not an artificial weak baseline.
- Pre-pilot on development-only cases; debug correctness, verify oracle disagreement, tune all algorithms on matched budget; **freeze** final tasks, baseline candidates, thresholds and all primary estimands.
- Run all arms per same independent unit, randomized/counterbalanced arm order; isolate DB schemas and avoid cross-arm contamination.
- Report primary endpoint with valid CI and exact independent unit. All planned test strata, including failures and timeouts, appear in tables.
- Include strong negative tests (signed token, always-revalidate, PG SERIALIZABLE, policy engines), ablations, unknown-dependency stress and out-of-domain holdout.
- Do not claim universal zero unsafe actions from zero observed failures. The one-sided Clopper--Pearson upper bound after zero failures among N independent units is `1 - alpha^(1/N)`; at alpha=.05, for N=600 it is about 0.498%. Assumptions about independent units still matter.
- No untrue physician adjudication or hardware attest claims; if clinicians, providers or original external baselines cannot run, explicitly mark NOT_RUN and narrow the claim.

## H. Threat model and negative baselines

| Candidate attack/failure | Independent expected predicate | Strong comparator that could invalidate novelty |
|---|---|---|
| Same-tenant cross-purpose reuse | historical binding false | Macaroons with purpose caveat |
| Permission/consent revoked between inference and commit | current governance false | in-transaction ABAC/serialized policy check |
| Allergy dependency read omitted | required closure false | complete read-set OCC + PostgreSQL SERIALIZABLE |
| Independent medication record changed | valid rebase possible | fine-grained OCC or SSI retry |
| Provider fallback changes serialized projection | historical binding false | end-to-end dispatch receipt attestation |
| Duplicate effects after recovery | durable effect mismatches | transactional outbox + idempotency |
| Log hash survives but identifying metadata leaks | privacy attacker succeeds | minimal logging + Merkle proof |

## I. Product boundary

The reference package is pure stdlib Python to demonstrate **contract-level behavior only**. It does not connect to CLARA DB, run an LLM, emulate policy engines, provide clinical validation or certify live transactions. Its passing tests are engineering smoke tests, not reported experimental safety. Production integration must use the file-by-file plans and independent proof obligations.
