# PSC formal proof obligations and operational safeguards

These obligations are **proposed proofs**; no universal theorem has been formally verified.

## O1 Supply authenticity and evidence closure
- Input: immutable canonical dispatch bytes, projection hash, receipt authenticated by trusted service key, actual principal/scope and proposal evidence references.
- Claim: if `Witness_A` accepts, declared evidence is a subset of the exact attested dispatch and all scope/lineage tokens match.
- Counterexamples: wrong actor, purpose, task, model-provider fallback, serialization mutation, stale/cross-run nonce, post-hoc citation injection.
- Failure boundary: LLM neural attention is not observable from server-side receipts; do not infer it.

## O2 Dependency closure soundness
- Required dependencies are generated from operation schemas and independently audited by a separate oracle.
- All required clinical data, consent, role, task and policy epochs must be included.
- Model fails closed for unrecognized mutation kinds, inherited or indirect relationships.
- Prove (or bounded-check) `D_required(o) subseteq D_verified(o)`; a miss is a hard failure, not a tolerable false negative.

## O3 Version locality and legitimate rescue
- Unrelated changes to keys not in the complete dependency closure may not invalidate an otherwise valid proposal.
- If policy/consent epoch or any required key changes, refuse/recompute with no implicit content patching.
- Witness pair must be recomputed inside the ultimate transaction.

## O4 Atomic recheck under actual backend
- Execute against real PG16; validate `SERIALIZABLE` retries/locks and policy writers, not a Python simulation.
- Commit and audit/outbox records must be durable together or have explicit idempotent reconciliation.
- Verify linearization against independent history exports (Jepsen/Elle) and failure-injected schedules.

## O5 Restrictive certificate semantics
- The signed receipt only proves authenticity/integrity under key/nonce trust assumptions.
- Key compromise, rollback, replay window, host trust and key rotation are explicit threat dimensions.
- A hash digest is not an RFC9334 hardware attestation result; verify real attester/evidence/verifier roles if using that term.

## O6 Selective risk certification without cherry picking
- Unit is independent clinical case / schedule / attack campaign, not jitter repeat.
- Non-inferiority margin from external risk tolerance, not chosen after final results.
- Upper bound for 0 unsafe successes among N independent units: `1 - 0.05**(1/N)` (illustrative one-sided binomial; not valid under arbitrary cluster dependence).
- Utility superiority requires simultaneous coverage and safety constraints; if violated, mark INCONCLUSIVE or REJECTED.

## O7 Independent examiner and completeness
- Threat model explicitly includes poisoned or unknown oracle, model-provider omissions, missing dispatch bytes, crash/restart, and adversarial requests.
- An independent checker must derive expected labels without importing PSC candidate code.
- Artifact revision, README, code commit, dependency lock and actual backend all match each manuscript result sentence.
