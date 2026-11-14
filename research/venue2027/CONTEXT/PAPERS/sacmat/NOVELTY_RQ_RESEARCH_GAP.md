# Research novelty dossier — PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines

**Target:** 07 SACMAT 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

A *history-sensitive conformance property* for delegated consent and purpose-bound access with trace-level metamorphic test generation and independent oracle adjudication across Cedar, OpenFGA and OPA encodings.

## 2. Gap against strongest published systems

MC/DC XACML policy testing and XACBench cover static policy structures; what must be demonstrated as new is systematic conformance testing of policy *histories* with revocation/redelegation and replay, including portability failures attributable to mismatched semantics.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
Which distinct trace-level policy errors are undetected by static rule/decision coverage but exposed by temporal metamorphic tests?
**Unit / primary endpoint:** independent study unit / mutation score at fixed oracle budget. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
How many executable mutants representing revocation, delegation, purpose and temporal precedence are killed by comparable budgets for random, MC/DC-inspired and PolicyTrace generation?
**Unit / primary endpoint:** independent study unit / mutation score at fixed oracle budget. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
Across Cedar, OpenFGA and OPA, which semantics are faithfully expressible, and where do adapters necessarily diverge?
**Unit / primary endpoint:** independent study unit / mutation score at fixed oracle budget. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

Define a portable three/four-valued decision oracle (PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE) and a partial mapping to each PDP; test revocation-before-replay, delegation expiration, explicit-deny precedence and temporal reorderings.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | uniform random authorization requests | weak reference | NOT_RUN on new study |
| B1 | MC/DC-inspired XACML policy testing (Xu et al. SACMAT 2018) | strong coverage baseline | NOT_RUN on new study |
| B2 | XACBench policy profile–driven synthetic tests | strong benchmark baseline | NOT_RUN on new study |
| B3 | property-based history generator without temporal metamorphs | strong stateful testing baseline | NOT_RUN on new study |
| B4 | PolicyTrace temporal generator plus oracle | candidate | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| Automated Coverage-Based Testing of XACML Policies | ACM SACMAT 2018 | MC/DC and mutation-adequacy baseline; must not compare naive only | https://doi.org/10.1145/3205977.3205979 |
| XACBench: a XACML policy benchmark | Soft Computing | Policy generation and evaluation benchmark; explicit scope difference from longitudinal traces | https://doi.org/10.1007/s00500-020-04925-5 |
| Cedar policy language and authorization reference implementation | Open source reference policy engine | Executable ABAC/PBAC comparator with expressivity and schema limits documented | https://github.com/cedar-policy/cedar |
| OpenFGA: Zanzibar-inspired fine-grained authorization | Open source reference policy engine | Executable ReBAC/ABAC control with policy/consent model mapping limits | https://github.com/openfga/openfga |
| Guide to Attribute Based Access Control (ABAC) Definition and Considerations | NIST SP 800-162 updated 2019 | Formal authorization vocabulary and policy attributes | https://doi.org/10.6028/NIST.SP.800-162 |
| Zanzibar: Google’s Consistent, Global Authorization System | USENIX ATC 2019 | Consistency-aware authorization; tests novelty beyond permission re-evaluation | https://www.usenix.org/conference/atc19/presentation/pang |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Versioned synthetic policy and principal graphs + 50 independently designed mutants; reserve fresh holdout mutant families; source/seed freeze prior to scoring.

**Independent oracle:** Executable declarative reference semantics and independent human review of semantically non-equivalent mutants.

**Experimental measurements:** mutation score at fixed oracle budget; trace witness detection coverage; policy-engine disagreement; invalid/indeterminate parity; generation runtime; minimal failure trace length.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

If trace generator does not outperform stateful and MC/DC-guided baselines at equal oracle-call budget, do not claim novel fault detection; publish portability limits transparently.

**Feasibility risk:** SACMAT Dataset/Tool track is likely better than a main claim. Need actual external engine execution rather than merely naming them.

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

