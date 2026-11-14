# Research novelty dossier — Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage

**Target:** 03 IFIP SEC 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

Study a *multi-principal interleaving* in which a valid consent-purpose receipt is delegated, refreshed and consumed across policy-epoch changes and concurrent replay. Define a consumed-once invariant and a tested provenance binding for delegated proposal chains.

## 2. Gap against strongest published systems

Macaroons and Zanzibar already solve substantial parts of contextual authorization and consistency. A credible new claim must show a specific multi-hop lineage/replay counterexample against strong correctly configured caveat-token and versioned authorization baselines, not just signature checking.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
Under which delegation and epoch interleavings do signed context-bound capability baselines admit an invalid replay or reject valid operations?
**Unit / primary endpoint:** independent study unit / invalid replay admissions. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
Is the proposed consume-once transition linearizable under two or more real PostgreSQL sessions and revoked scope?
**Unit / primary endpoint:** independent study unit / invalid replay admissions. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
What are token size, verification latency and legitimate operation rejection costs relative to well-configured Macaroons and Zanzibar-like policies?
**Unit / primary endpoint:** independent study unit / invalid replay admissions. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

Receipts are typed commitments: HMAC over actor, patient, tenant, purpose, task, consent/policy epoch, dispatch digest, nonce and parent reference. Verify the full delegation ancestry and atomically consume the nonce, not just signature equality.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | bearer signed receipt | weak control | NOT_RUN on new study |
| B1 | Macaroon HMAC caveats: actor, purpose, task, expiry, nonce | strong token baseline, correct semantics | NOT_RUN on new study |
| B2 | Zanzibar/OpenFGA with consistency token and fresh policy evaluation | strong relationship consistency baseline | NOT_RUN on new study |
| B3 | Cedar/OPA policy decision with replay nonce registry | strong security-engineering comparator | NOT_RUN on new study |
| B4 | proposed delegated lineage transition verifier | candidate | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud | NDSS 2014 | Strong caveat-bound HMAC capability; prevents overstating novelty of scoped tokens | https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/ |
| Zanzibar: Google’s Consistent, Global Authorization System | USENIX ATC 2019 | Consistency-aware authorization; tests novelty beyond permission re-evaluation | https://www.usenix.org/conference/atc19/presentation/pang |
| Cedar policy language and authorization reference implementation | Open source reference policy engine | Executable ABAC/PBAC comparator with expressivity and schema limits documented | https://github.com/cedar-policy/cedar |
| OpenFGA: Zanzibar-inspired fine-grained authorization | Open source reference policy engine | Executable ReBAC/ABAC control with policy/consent model mapping limits | https://github.com/openfga/openfga |
| Remote ATtestation procedureS (RATS) Architecture | IETF RFC 9334 | Strict evidence / attester / verifier boundary; prevents calling a SHA-256 hash hardware attestation | https://www.rfc-editor.org/rfc/rfc9334.html |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Distinct 900 adversarial interleavings in isolated synthetic accounts across delegation/revocation/retry/tenant switches; clean controls matched per threat family.

**Independent oracle:** Independent allow/deny oracle based on frozen principal graph and commit-time consent epoch, not candidate verifier output.

**Experimental measurements:** invalid replay admissions; valid control acceptance; duplicate consumption race; token bytes; p95 verify latency; authorization DB round trips.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

If a properly scoped Macaroon plus consistent authorization check is decision-equivalent on all attacks, state equivalence and do not claim stronger security.

**Feasibility risk:** Potentially weak novelty relative to existing capability systems; reject manuscript if B1/B2 already meet every invariant.

## 9. Reviewer objections to anticipate

- Strong prior work may already implement the mechanism; require a distinguishing observation from the strongest baseline.
- Benchmark and baseline adaptations may alter threat model or semantics; validate equivalence using official examples and an independent oracle.
- Synthetic-data efficacy may not transfer to clinical settings or adversarial deployments; report domain shift and a negative generalization test.
- Checksums and passing unit tests do not prove the comparative claim or its statistical power.
- Existing GLHS/HEALTHINF/RIVF/SOICT evidence may overlap; independently define contribution, results and publication relationship.

# Cross-study integrity rules

- **Status:** prospective research; source code and publication package are not experimental evidence.
- **Clinical separation:** Synthetic data is not clinical validation; no real patients, live medical actions, or unverifiable provider output.
- **Source of truth:** Git SHA, immutable protocol freeze and raw JSONL must be consistent; checksums do not prove backend truthfulness or design novelty.
- **Real baselines:** Literature references are not executable baselines by themselves. Original external code/adapter must run, or status is NOT_RUN_EXTERNAL (not a weak substitute).
- **Priority:** a strong negative result or equivalence with prior art is more publishable than false superiority.
- **Paper integrity:** Verify corresponding author status, policies on generative AI, author anonymity, copyright and fees before submission. Do not send overlapping contributions to multiple venues at the same time.

