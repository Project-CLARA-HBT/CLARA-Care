# Research novelty dossier — Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts

**Target:** 02 PoPETs 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

Define *future dispatch noninterference* under consent revocation for every derivation path (prompt segment, cached summary, embedding pointer, retry payload, and fallback transport). Provide a dependency-closure invalidation algorithm and leakage audit that explicitly excludes information already delivered to any external provider.

## 2. Gap against strongest published systems

Existing access control and cache invalidation can block future reads, and machine unlearning targets a different threat. A research gap exists only if persistent indirect derived context, retry queues, and fallback paths cause measurable post-revocation leakage that strong per-use reauthorization baselines miss.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
Can any post-revocation model dispatch contain disallowed attributes through transitive caches or retries, even when direct record access is denied?
**Unit / primary endpoint:** independent study unit / future unauthorized disclosure rate. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
Does origin- and purpose-labeled dependency closure match a full always-recompute authorized view on disclosure traces?
**Unit / primary endpoint:** independent study unit / future unauthorized disclosure rate. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
What are cache hit, bytes transferred, re-computation, false invalidation and authorized utility costs at increasing lineage density?
**Unit / primary endpoint:** independent study unit / future unauthorized disclosure rate. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

For grant g, purpose p, and dispatch d after revocation time t_r, require forbidden_label(g,p) ∩ lineage(d)=∅ under a declared observation model. Label derived artifacts at creation; invalidate reverse edges on revocation; reauthorize at every dispatch.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | TTL-only cache | weak lower bound | NOT_RUN on new study |
| B1 | coarse cache purge on consent change | strong simple safety baseline | NOT_RUN on new study |
| B2 | always-recompute authorized projection per dispatch | privacy reference upper bound, cost comparator | NOT_RUN on new study |
| B3 | Zanzibar-like consistency-token authorization + derived-cache tagging | strong architecture baseline if adapter truly supports derivations | NOT_RUN on new study |
| B4 | proposed transitive provenance-label invalidation | candidate | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| Zanzibar: Google’s Consistent, Global Authorization System | USENIX ATC 2019 | Consistency-aware authorization; tests novelty beyond permission re-evaluation | https://www.usenix.org/conference/atc19/presentation/pang |
| MUSE: Machine Unlearning Six-Way Evaluation for Language Models | Research evaluation work | Strong distinction between unlearning, future disclosure prevention and utility | https://research.google/pubs/muse-machine-unlearning-six-way-evaluation-for-language-models/ |
| Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud | NDSS 2014 | Strong caveat-bound HMAC capability; prevents overstating novelty of scoped tokens | https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/ |
| Remote ATtestation procedureS (RATS) Architecture | IETF RFC 9334 | Strict evidence / attester / verifier boundary; prevents calling a SHA-256 hash hardware attestation | https://www.rfc-editor.org/rfc/rfc9334.html |
| Certificate Transparency Version 2.0 | IETF RFC 9162 | Merkle append-only transparency model, integrity != confidentiality | https://www.rfc-editor.org/rfc/rfc9162.html |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Synthetic 1200 unique subjects with 3-6 longitudinal contexts each; factorial lineage fanout, delayed cache writes, retries, and policy changes; source-disjoint holdout; label N by subject not number of dispatches.

**Independent oracle:** Independent recomputation of all live-purpose permission clauses from source snapshots; byte-level dispatch interceptor and sealed cancellation log.

**Experimental measurements:** future unauthorized disclosure rate; attribute-exposure byte count; conditional cache hit rate; false invalidation rate; latency and rebuild cost; replay-path coverage.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

If complete per-dispatch authorization + recompute matches the candidate with negligible overhead and zero leakage, narrow novelty to an engineering performance trade-off; never assert erasure of prior external disclosures.

**Feasibility risk:** Inability to retract already delivered content must be stated prominently. Post-revocation future leakage only; no claim of cryptographic retroactive erasure.

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

