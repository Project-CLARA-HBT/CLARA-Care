# Research novelty dossier — GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing from Minimal Agent Events

**Target:** 08 DIMVA 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

A *privacy-constrained sequence detector* distinguishing benign retry bursts from deliberate multi-step policy/receipt boundary reconnaissance; generalization measured on unseen attack families and tooling changes.

## 2. Gap against strongest published systems

AgentDojo and ToolEmu provide realistic agent safety attacks; IDS literature warns models can memorize environments. Novelty demands detector evaluation on independently generated multi-stage traces with constrained PHI metadata and rigorous cross-family holdout, rather than training on rejection reason codes that trivially reveal labels.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
Can a detector identify attack campaigns from PHI-minimized events at bounded benign false alarms, without using attack-specific reason-code leakage?
**Unit / primary endpoint:** independent study unit / campaign-level AUCPR. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
How does cross-family/cross-tenant holdout change precision-recall and time-to-detect relative to rule-based, IsolationForest, boosted-tree and sequence models?
**Unit / primary endpoint:** independent study unit / campaign-level AUCPR. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
How do adaptive attacker retries and privacy budgets affect detection and diagnostic reconstruction?
**Unit / primary endpoint:** independent study unit / campaign-level AUCPR. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

Derive minimal log schema independent of raw patient data; split by attack family and synthetic tenant; keep rejection codes masked in leak-safe primary test, then disclose effect of allowing them in an ablation.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | static threshold on failures per window | strong operational baseline | NOT_RUN on new study |
| B1 | temporal rule sequence / finite-state signature | strong interpretable baseline | NOT_RUN on new study |
| B2 | Isolation Forest on privacy-minimized counts | unsupervised comparator | NOT_RUN on new study |
| B3 | gradient-boosted trees with controlled features | supervised comparator | NOT_RUN on new study |
| B4 | sequence model with time-aware features | candidate; only if holdout gain | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents | NeurIPS 2024 Datasets & Benchmarks | Stateful tool-agent attack/defense benchmark, not a direct authorization system | https://proceedings.nips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html |
| ToolEmu: Identifying the Risks of LM Agents with an LM-Emulated Sandbox | ICLR 2024 | Risk-oriented emulation and judge validation; do not equate simulated tool outcomes with persisted transactions | https://proceedings.iclr.cc/paper_files/paper/2024/file/7274ed909a312d4d869cc328ad1c5f04-Paper-Conference.pdf |
| InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents | Findings of ACL 2024 | External tool injection attacks; semantic threat families not equivalent to write admission | https://aclanthology.org/2024.findings-acl.624/ |
| Outside the Closed World: On Using Machine Learning for Network Intrusion Detection | IEEE Symposium on Security and Privacy 2010 | Warns against test-train environmental leakage and unrealistic anomaly-detection labels | https://doi.org/10.1109/SP.2010.25 |
| tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains | ICLR 2025 | Final database-state / policy-following evaluation; historical repo warns tasks outdated | https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Multi-stage synthetic sessions plus benign retries, outages, latency spikes; attacker cannot read privileged logs; frozen family-holdout groups with no shared templates across train/test.

**Independent oracle:** Campaign intent and authorized action adjudicated from simulator ground truth, never from detector score or gateway final reason code.

**Experimental measurements:** campaign-level AUCPR; false alarms per 1000 benign sessions; time-to-detect; unseen-family recall; bytes of retained sensitive metadata; adaptive evasion success.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

If rule thresholds perform as well as sequence models on family-held-out traces, do not claim ML necessity; if detector depends on post-hoc failure labels, invalidate primary experiment.

**Feasibility risk:** Security venue will require demonstrated attack novelty and realism. Explicit avoid simplistic generated labels.

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

