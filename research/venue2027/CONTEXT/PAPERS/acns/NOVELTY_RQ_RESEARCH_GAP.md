# Research novelty dossier — SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems

**Target:** 04 ACNS 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

An evidence-to-claim lattice for assembly, egress, transport acknowledgment, provider-attested receipt, execution trace and semantic consumption, with mechanized *counterexample witnesses* showing which implications fail absent explicit trust assumptions.

## 2. Gap against strongest published systems

Existing cryptographic attestation terminology (IETF RATS) and agent safety benchmarks address related but nonidentical assurance claims. A SoK contributes only if its systematic taxonomy is reproducible, independently double-coded and resolves real disagreements, not if it rebrands provenance as new.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
Which attestation claims are actually supported by which observable evidence and trusted parties in published agent systems?
**Unit / primary endpoint:** independent study unit / inter-rater Cohen kappa. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
Which claimed implication pairs are invalid under explicit adversarial and provider models, and can small executable witnesses demonstrate this?
**Unit / primary endpoint:** independent study unit / inter-rater Cohen kappa. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
How consistently can independent reviewers classify claims and reproduce counterexamples across a pre-registered corpus?
**Unit / primary endpoint:** independent study unit / inter-rater Cohen kappa. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

Define observation/trust axes, mechanically enumerate implication candidates, construct counterexamples for false implications, and publish extraction rules and independently adjudicated study selection ledger.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | RFC 9334/RATS attestation evidence framework | normative taxonomy baseline | NOT_RUN on new study |
| B1 | W3C PROV provenance and audit events | retrospective lineage baseline | NOT_RUN on new study |
| B2 | AgentDojo/ToolEmu evidence and attack observability categories | empirical study taxonomy | NOT_RUN on new study |
| B3 | two independent human-coded new taxonomy | candidate SoK; needs actual reviewers | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| Remote ATtestation procedureS (RATS) Architecture | IETF RFC 9334 | Strict evidence / attester / verifier boundary; prevents calling a SHA-256 hash hardware attestation | https://www.rfc-editor.org/rfc/rfc9334.html |
| Certificate Transparency Version 2.0 | IETF RFC 9162 | Merkle append-only transparency model, integrity != confidentiality | https://www.rfc-editor.org/rfc/rfc9162.html |
| AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents | NeurIPS 2024 Datasets & Benchmarks | Stateful tool-agent attack/defense benchmark, not a direct authorization system | https://proceedings.nips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html |
| ToolEmu: Identifying the Risks of LM Agents with an LM-Emulated Sandbox | ICLR 2024 | Risk-oriented emulation and judge validation; do not equate simulated tool outcomes with persisted transactions | https://proceedings.iclr.cc/paper_files/paper/2024/file/7274ed909a312d4d869cc328ad1c5f04-Paper-Conference.pdf |
| InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents | Findings of ACL 2024 | External tool injection attacks; semantic threat families not equivalent to write admission | https://aclanthology.org/2024.findings-acl.624/ |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Search ACM/IEEE/USENIX/NDSS/ICLR/NeurIPS publications from pre-registered 2019-2026 window; freeze duplicate resolution, screening decisions and extraction workbook.

**Independent oracle:** Independent dual human coders; no internal LLM agents represented as independent reviewers.

**Experimental measurements:** inter-rater Cohen kappa; ambiguous claim fraction; counterexample reproduction rate; coverage of evidence-strength lattice; disagreement resolution rate.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

If taxonomy fails coder agreement or merely restates RFC 9334 / existing provenance literature without new cases and insights, do not claim SoK contribution.

**Feasibility risk:** ACNS 2027 CFP may not offer SoK-specific track; only submit after checking venue scope and completed original systematic method.

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

