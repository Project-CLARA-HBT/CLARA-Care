# Research novelty dossier — ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization

**Target:** 09 PST 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

A formally defined *reconstruction-versus-linkability frontier* for AI health action receipts, separating proof of an event commitment from recovery of sensitive content under post-retention access privileges.

## 2. Gap against strongest published systems

Hash chains, transparency logs, HMAC identifiers and encryption already exist; a useful contribution requires new quantitative evidence about audit decision reconstructability versus attacker attribute/linkage inference for longitudinal health workflows.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
What fraction of legitimate forensic questions remain answerable under hash-only, encrypted, and selective retention receipts?
**Unit / primary endpoint:** independent study unit / forensic query answerability. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
Can linkage and attribute exposure be bounded under compromised read-only audit access, including auxiliary-data joins?
**Unit / primary endpoint:** independent study unit / forensic query answerability. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
What retention, key deletion and proof-generation costs emerge across audit volumes and retention epochs?
**Unit / primary endpoint:** independent study unit / forensic query answerability. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

Define forensic query set ex ante; preserve commitment and consent/policy epoch proofs while removing patient detail; test attacker with auxiliary linkage metadata and a realistic audit-reader privilege.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | full plaintext append-only log | utility upper bound / privacy lower bound | NOT_RUN on new study |
| B1 | hash-only log or content digests | storage/privacy baseline, weak audit utility | NOT_RUN on new study |
| B2 | encrypted log with role-gated decryption and deletion | strong confidentiality comparator | NOT_RUN on new study |
| B3 | RFC 9162-like Merkle append-only integrity + authorized material retrieval | strong integrity baseline | NOT_RUN on new study |
| B4 | proposed purpose-bound minimized receipt and retention map | candidate | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| Certificate Transparency Version 2.0 | IETF RFC 9162 | Merkle append-only transparency model, integrity != confidentiality | https://www.rfc-editor.org/rfc/rfc9162.html |
| Remote ATtestation procedureS (RATS) Architecture | IETF RFC 9334 | Strict evidence / attester / verifier boundary; prevents calling a SHA-256 hash hardware attestation | https://www.rfc-editor.org/rfc/rfc9334.html |
| Zanzibar: Google’s Consistent, Global Authorization System | USENIX ATC 2019 | Consistency-aware authorization; tests novelty beyond permission re-evaluation | https://www.usenix.org/conference/atc19/presentation/pang |
| Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud | NDSS 2014 | Strong caveat-bound HMAC capability; prevents overstating novelty of scoped tokens | https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/ |
| Ethics and Governance of Artificial Intelligence for Health | World Health Organization | Ethics, purpose and clinical claims boundary | https://www.who.int/publications/i/item/9789240029200 |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Synthetic records/events with explicit correlation surfaces, varying log sizes, user identifiers, retention windows, backups; externality of key deletion declared in threat model.

**Independent oracle:** Trusted offline complete ledger retained only for evaluation; blinded authorized forensic queries and attacker inference tests.

**Experimental measurements:** forensic query answerability; record-level linkability risk; attribute inference risk; retained bytes; proof generation latency; authorized investigation recovery.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

If encrypted full logs with a well-managed retention policy dominate minimized receipts on privacy and reconstruction, reject novelty superiority claim.

**Feasibility risk:** Avoid claiming content deletion from immutable historical disclosures or from unverified cloud backups.

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

