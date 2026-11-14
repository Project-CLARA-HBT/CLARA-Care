# CLARA-Care 2027 — Research Question Register

Working collection | 14 November 2026 | 9 independent studies | 27 research questions

For every research question, the manuscript contains an operational outcome and a matched comparator protocol. This register is a navigation aid; the detailed methods are in each manuscript.

## 01_DSN_2027 — Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations

**RQ1 — Cross-boundary recoverability**
Can the clinical row, immutable decision receipt, and outbox event be reconciled into a consistent outcome after crashes at each persistence boundary?
*Measurement:* The primary observation is the fraction of independent histories with an orphaned mutation, phantom success, or unresolved outcome after a bounded recovery interval.

**RQ2 — Replay and governance**
Does reconciliation remain idempotent when deliveries are duplicated, workers restart, and consent is revoked during execution?
*Measurement:* Report duplicate externally visible effects and causal-order violations per independent crash/revocation history.

**RQ3 — Cost of stronger accounting**
How does explicit recovery evidence affect completion latency, durable writes, and time to recovery relative to strong workflow baselines?
*Measurement:* Compare p95 and p99 operation latency, recovery time, and write amplification under matched throughput.

## 02_PoPETs_2027 — Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts

**RQ1 — Post-revocation disclosure**
Do indirect derivations, retries, and fallback requests cause prohibited post-revocation disclosure despite correct authorization at the source-record boundary?
*Measurement:* Measure the rate and volume of forbidden attributes reaching subsequent outbound dispatches, with independent provenance-based labels.

**RQ2 — Semantic completeness of invalidation**
Does transitive, purpose-labeled invalidation produce the same authorized disclosure as a full re-computation reference?
*Measurement:* Compare disclosure equivalence and false invalidation at the level of independent patient histories.

**RQ3 — Privacy–availability trade-off**
What latency, cache-hit, and legitimate-context costs arise under different lineage fanout and update rates?
*Measurement:* Report cache hits conditional on authorization, reconstructed-context completeness, bytes transferred, and p95 latency.

## 03_IFIP_SEC_2027 — Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage

**RQ1 — Cross-context replay**
Which delegation, purpose, tenant, and epoch interleavings permit misuse of a previously valid receipt under each authorization architecture?
*Measurement:* Measure invalid replay admission per unique attack history, with paired clean authorization controls.

**RQ2 — Atomic consumption**
Can two or more concurrent consumers produce a duplicate accepted effect or bypass a revocation boundary?
*Measurement:* Measure duplicate consumption and invalid concurrent admissions using persisted PostgreSQL executions.

**RQ3 — Operational cost**
How do lineage verification and atomic nonce consumption affect valid acceptance, token size, and verification latency?
*Measurement:* Report clean acceptance and p95 verification cost at matched concurrency and permission semantics.

## 04_ACNS_2027 — SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems

**RQ1 — Evidence strength**
Which AI assurance statements are justified by assembly, dispatch, acknowledgment, provider receipt, and execution evidence under explicit trust assumptions?
*Measurement:* The unit is an extracted claim from the reviewed corpus; record its evidence source, observer, and supported level.

**RQ2 — Invalid implications**
Which commonly implied transitions between evidence levels have executable counterexamples?
*Measurement:* Measure reproducible witness coverage and classify the assumptions needed to remove each counterexample.

**RQ3 — Taxonomic reliability**
Can independent reviewers apply the evidence taxonomy consistently across systems and publication styles?
*Measurement:* Report inter-rater agreement, adjudicated disagreements, and retained ambiguous cases.

## 05_COMPSAC_2027 — Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes

**RQ1 — Safety of dependency closure**
Does a schema-derived read closure prevent forbidden dependent commits under concurrent clinical and authorization updates?
*Measurement:* Count forbidden commits per independent logical schedule using an oracle defined separately from the implementation.

**RQ2 — Avoidable contention**
How much legitimate work is rejected by profile-wide versions when intervening edits do not affect required dependencies?
*Measurement:* Estimate false-stale rejection and completed legitimate throughput under matched schedule pairs.

**RQ3 — Scaling costs**
How do dependency fanout, hot-key skew, and worker count affect throughput and tail latency relative to PostgreSQL Serializable?
*Measurement:* Measure p95/p99 latency, retry amplification, and database operations at fixed workload and correctness.

## 06_AIME_2027 — Counterfactual Clinical Workflow Safety under Changing Consent and Medication Histories

**RQ1 — Distinct error mechanisms**
How frequently do changing medications, allergies, or consent cause clinical-content errors as opposed to authorization errors?
*Measurement:* Report separate blinded labels for clinical omission and impermissible evidence use per independent vignette.

**RQ2 — Value of selective regeneration**
Can selective re-generation maintain authorized task completion while reducing avoidable refusal and processing cost relative to full refresh?
*Measurement:* Compare paired correct completion, unnecessary refusal, clinician-review load, and token/latency cost.

**RQ3 — Robustness across conditions**
How consistent are these effects across update types, independent case sources, and at least two verified model families?
*Measurement:* Estimate stratified paired contrasts and reviewer agreement, with case-family clustered uncertainty.

## 07_SACMAT_2027 — PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines

**RQ1 — Temporal fault coverage**
Which authorization defects become observable only when tests preserve the order of grants, revocations, delegation, and replay?
*Measurement:* Measure distinct trace-level fault families found beyond matched static decision coverage.

**RQ2 — Mutation-testing efficiency**
Does temporal metamorphic generation detect more non-equivalent mutants than competing methods at equal oracle-call and generation budgets?
*Measurement:* Compare paired mutation scores, detection cost, and minimal witness length.

**RQ3 — Cross-engine semantics**
Which policy histories can be represented consistently across Cedar, OpenFGA, and OPA, and where do translation semantics diverge?
*Measurement:* Report supported construct coverage, decision parity, and explicit indeterminate/untranslatable cases.

## 08_DIMVA_2027 — GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing from Minimal Agent Events

**RQ1 — Detection under data minimization**
Can malicious boundary-probing campaigns be detected at a fixed low false-alarm budget without raw clinical content or label-leaking reason codes?
*Measurement:* Report campaign-level area under the precision–recall curve and recall at a preregistered false-alarm threshold.

**RQ2 — Robustness to novel campaigns**
How does generalization change when attacker families, tenants, and tooling templates are held out entirely from training?
*Measurement:* Measure unseen-family detection, time to detection, and degradation from in-distribution evaluation.

**RQ3 — Adaptation and privacy cost**
How do paced retries, benign network faults, and stronger metadata minimization affect detection performance and diagnostic value?
*Measurement:* Compare adaptive evasion rates and retained metadata bytes at equivalent false-alarm budgets.

## 09_PST_2027 — ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization

**RQ1 — Forensic sufficiency**
Which authorization, provenance, and commit questions remain answerable from minimized receipts at different retention stages?
*Measurement:* Measure query answerability and reconstruction accuracy against independent ground truth.

**RQ2 — Metadata disclosure**
How much identity linkage and attribute inference remains possible when an audit reader combines receipts with auxiliary information?
*Measurement:* Report attacker advantage over a declared prior and linkability precision across independent synthetic subjects.

**RQ3 — Operating costs**
What are the storage, lookup, proof-generation, and controlled-recovery costs of minimization and retention-epoch changes?
*Measurement:* Compare retained bytes, verification latency, and authorized investigation completion with strong encrypted and transparency-log baselines.
