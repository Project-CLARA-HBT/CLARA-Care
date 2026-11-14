# ACNS 2027 · Novelty contract and independent scope register

> **Task:** `ACNS-scope` · **Phase:** `P01` · **Venue:** `acns` · **Status:** signed register
>
> **Source SHA (base):** `7ebdbbf0740e87ffebe3538d6893a53eaccf2216`
> **Dependencies honored:** `SH-claim_overlap` (PASS, publication overlap firewall + `reuses_archive: []` for acns) and `SH-literature_hardening` (PASS, 24-source validity ledger).
>
> **Version:** `clara.venue2027.acns.novelty-contract.v1`

## 0. Title and target reader

- **Title (working):** *SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems*
- **Target reader:** A security researcher or reviewer at ACNS who must decide which assurance claims a published tool-using AI agent system is actually entitled to make — for example, a program-committee member evaluating whether "the provider acknowledged receipt, therefore the model executed the tool" is a justified inference, or a practitioner designing remote-attestation evidence flows for LLM agent deployments who needs to know which evidence types bound which claims. Secondary readers: authors of agent-safety benchmarks (AgentDojo/ToolEmu lineage) who must scope what their observability categories do and do not prove.

## 1. Contribution class: this is a SoK, not a new mechanism

**Declaration:** This study declares itself a **Systematization of Knowledge (SoK)**. Its contribution is a **systematic evidence-boundary taxonomy plus a coverage matrix** over a pre-registered 2019–2026 corpus: an evidence-to-claim lattice spanning assembly, egress, transport acknowledgment, provider-attested receipt, execution trace, and semantic consumption, populated by extraction from published systems and validated by independent dual human coding with mechanized counterexample witnesses.

**This contract does NOT claim a new mechanism.** No new cryptographic primitive, no new authorization protocol, no new detector, and no new attestation scheme is proposed or evaluated. Where the blueprint's RQ2 constructs *counterexample witnesses*, those witnesses are small executable demonstrations that map the **boundaries of existing evidence semantics** — they are instruments of the taxonomy's falsification, not a defense mechanism. The candidate mechanism field from the task manifest ("define observation/trust axes, mechanically enumerate implication candidates, construct counterexamples, publish extraction rules and an adjudicated selection ledger") is the **review methodology**, not a deployable system artifact.

Falsification rule for the contribution class itself: if the taxonomy merely restates RFC 9334 (RATS) or existing provenance literature (W3C PROV) without new cases and insights, or fails independent coder agreement, the SoK contribution is withdrawn rather than repackaged as a mechanism paper.

## 2. Claim-to-prior-work falsification matrix

Each row states a claim this study could be tempted to make, the strongest prior work that would falsify its novelty, and the scope guard that keeps the claim inside the SoK boundary. Prior-work identifiers use real registry IDs from `research/venue2027/_shared/literature_validity_ledger.csv` (`research/publication_registry.yaml` contains no ACNS-specific entry; the ACNS study claim lives in `research/venue2027/_shared/study_claims.json` and `publication_overlap_registry.yaml`, study key `acns`, with `reuses_archive: []`).

| # | Candidate claim | Falsifying prior work (registry id) | What the prior work already establishes | Scope guard / what remains distinct |
|---|---|---|---|---|
| F1 | "We introduce the first attestation evidence taxonomy for remote attestation" | `rats9334` (IETF RFC 9334, RATS Architecture) | Defines the normative attester/evidence/verifier/relying-party boundary and evidence-concept taxonomy for remote attestation | ACNS does **not** claim to invent attestation evidence concepts. The lattice *extends* observation/trust axes to tool-using AI systems (tool dispatch, provider receipt, execution trace, semantic consumption), classes that RFC 9334 does not enumerate; claims are phrased as coverage of published AI systems against an extended lattice, with RFC 9334 as baseline B0 |
| F2 | "We are the first to model provenance/lineage of AI actions" | `fhir5` (HL7 FHIR R5 Provenance/AuditEvent) and W3C PROV (baseline B1 in the blueprint) | Standardized retrospective lineage and audit-event models; provenance of records is long established | ACNS claims no provenance novelty. PROV/FHIR-style lineage is the *retrospective* baseline arm; the SoK's distinct object is the **claim-evidence implication lattice** (which assurance inferences are valid), not lineage recording |
| F3 | "We are the first to empirically expose agent attack surfaces / observability gaps" | `agentdojo24` (AgentDojo, NeurIPS 2024 D&B) and `toolemu24` (ToolEmu, ICLR 2024) | Stateful tool-agent attack/defense benchmarking and LM-emulated risk analysis with judge validation; AgentDojo/ToolEmu observability categories are baseline B2 | ACNS performs **no attack campaign and no benchmark run** as primary evidence. The SoK *codes and systematizes* the evidence categories such benchmarks implicitly assume, and tests reviewer agreement on them; benchmark-category overlap is disclosed as baseline B2, not claimed as a new empirical result |
| F4 | "Our counterexample witnesses are a novel enforcement/verification mechanism" | `rats9334` (evidence/verifier separation) and `ct9162` (RFC 9162, Certificate Transparency: verifiable logs ≠ confidentiality ≠ execution proof) | Both standards already separate evidence, verification, and the guarantee actually delivered | Witnesses are declared **instruments of falsification for implication pairs** (boundary-mapping artifacts), explicitly not deployable enforcement; the paper will not evaluate them as a defense or report detection/prevention rates |
| F5 | "We resolve AI-assurance claims clinically / improve clinical safety" | `who21` (WHO AI health governance guidance) and `cse2026` / `medhelm2026` (clinical LLM evaluation baselines) | Governance guidance and physician-consensus evaluation frameworks already bound clinical AI claims | ACNS corpus coding is **clinical-domain-agnostic**; no clinical endpoint, no patient data, no clinical-effectiveness claim appears in this study. Health framing appears only as motivating context for why overstated attestation claims matter |
| F6 | "The evidence-boundary matrix is itself a new evaluation benchmark" | `agentdojo24`, `toolemu24`, `tauben25` (tau-bench) | Benchmarks with held-out task suites and database-state evaluation already exist for tool agents | The coverage matrix is a **coding instrument over the literature corpus**, not a runnable benchmark; no leaderboard, no held-out task split, no model-under-test. Benchmark construction would be a separate, future, separately-frozen study |
| F7 | "Independently double-coded systematic review is our methodological invention" | Established PRISMA-style systematic-review practice (protocol-level prior art; `X01`–`X10` task lineage) | Double coding, adjudication, and PRISMA-style screening are standard review methodology | The methodological claim is limited to **pre-registration and publication of extraction rules, disagreement resolution, and counterexample reproduction for AI-attestation claims** — an application, not an invented method |

**Falsification condition (study-level, from blueprint):** if inter-rater Cohen kappa on the corpus shows the taxonomy does not achieve the pre-registered agreement threshold, or the populated matrix adds no cases beyond RFC 9334/PROV categories (no new cases and insights), the SoK contribution is **not** claimed. Any κ value reported later must come from executed coder sessions recorded under `artifacts/venue2027/acns/<run_id>/manifest.json`; none are asserted here.

## 3. Research questions, endpoints, baselines, oracles, tests, falsification

Exactly three RQs, verbatim in scope from the blueprint and the `ACNS-scope` manifest entry. Each RQ names its primary endpoint, the strongest competing baseline from the blueprint baseline table, an independent oracle, the statistical test, and the falsification condition.

### RQ1 — Evidence strength mapping

- **RQ:** Which attestation claims are actually supported by which observable evidence and trusted parties in published agent systems?
- **Primary endpoint:** distribution of extracted corpus claims across the evidence-strength lattice (evidence source × observer × supported level), reported as **coverage of the evidence-strength lattice** with the ambiguous-claim fraction as supporting measure. Unit = one extracted claim from the reviewed corpus (never per-event pseudo-replication).
- **Strongest competing baseline (blueprint table):** **B0 — RFC 9334/RATS attestation evidence framework** (normative taxonomy baseline): the strongest competing explanation is that the published corpus's claim/evidence structure is already fully described by RFC 9334 categories, making the extended lattice redundant. W3C PROV (B1) is the retrospective-lineage comparator arm.
- **Independent oracle:** two independent human coders applying the frozen extraction manual (`ACNS-X05`), with third-party adjudication (`ACNS-X06`); no internal LLM agent is represented as an independent reviewer.
- **Statistical test:** inter-rater **Cohen's κ** (two-rater nominal agreement on lattice level), with exact Clopper–Pearson 95% CIs on category proportions; ambiguous-claim fraction reported with binomial CI.
- **Falsification condition:** if the corpus's claims map entirely onto B0 categories with no residual cases requiring the extended axes (no new cases and insights), **or** coder agreement on the extended lattice falls below the pre-registered κ threshold in `ACNS-rq_registry`/`ACNS-freeze`, RQ1's contribution collapses into "RFC 9334 suffices" and the SoK claim is withdrawn for this arm.

### RQ2 — Invalid implication pairs and counterexample witnesses

- **RQ:** Which claimed implication pairs are invalid under explicit adversarial and provider models, and can small executable witnesses demonstrate this?
- **Primary endpoint:** **counterexample reproduction rate** over the mechanically enumerated implication-pair candidate set — the fraction of classified-invalid implications for which the witness executes deterministically and reproduces the failure under the stated adversarial/provider model. Unit = one implication pair.
- **Strongest competing baseline (blueprint table):** **B2 — AgentDojo/ToolEmu evidence and attack observability categories** (empirical study taxonomy): the strongest competing explanation is that existing benchmark observability categories already separate these evidence levels and imply the same invalidity boundaries, making the witness program redundant. (B0/RFC 9334 is again consulted for whether the boundary is already normative.)
- **Independent oracle:** each witness's expected verdict is fixed **before** execution in the case's `truth.json` produced by the independent coders/adjudication path — the oracle never imports the witness code; disagreement is resolved by adjudication, never by repairing the oracle to match the candidate.
- **Statistical test:** exact **binomial (Clopper–Pearson) CI** on the reproduction rate against the pre-registered minimum coverage threshold; per-family McNemar paired comparison against B2-derived expected classifications for cases where both assign a verdict.
- **Falsification condition:** if witnesses fail to reproduce their designated counterexamples (reproduction below threshold), or every enumerated invalid implication is already implied invalid by B0/B2 category semantics alone (taxonomy restatement), RQ2's added value is falsified and the negative result is reported as such.

### RQ3 — Taxonomic reliability

- **RQ:** How consistently can independent reviewers classify claims and reproduce counterexamples across a pre-registered corpus?
- **Primary endpoint:** **inter-rater Cohen's κ** on claim classification across the frozen corpus, with disagreement resolution rate and retained-ambiguous fraction as supporting measures. Unit = one (claim, rater-pair) classification.
- **Strongest competing baseline (blueprint table):** **B3 — two independent human-coded new taxonomy** (candidate SoK arm): the strongest competing explanation is that any reasonable two-rater coding of the same corpus — without this study's lattice, extraction rules, or witness gallery — would reach the same agreement and coverage, so the specific taxonomy contributes nothing beyond generic careful human coding. B1 (W3C PROV audit events) serves as the structured-vocabulary comparator for classification support.
- **Independent oracle:** the adjudicated third-coder decision stream (`ACNS-X06`), sealed before analysis; coders never see candidate tooling outputs, and the adjudication ledger is published.
- **Statistical test:** Cohen's κ with bootstrap CI over claims; disagreement resolution rate with exact binomial CI; κ comparison between the study taxonomy and a B3-style generic coding via paired bootstrap on the shared claim set.
- **Falsification condition:** if κ for the study taxonomy does not exceed the generic B3-style coding by the pre-registered margin (or is not superior on disagreement resolution), the "systematic taxonomy" contribution fails its own reliability test and no SoK claim is made.

## 4. Scope (one paragraph) — the truly distinct contribution

The truly distinct ACNS 2027 contribution is the **systematic evidence-boundary taxonomy and coverage matrix**: a pre-registered, reproducibly extracted, independently double-coded evidence-to-claim lattice for attestation in tool-using AI systems, covering six evidence classes (assembly, egress, transport acknowledgment, provider-attested receipt, execution trace, semantic consumption), together with the observation/trust axes and the mechanized counterexample-witness gallery that mark exactly where each claim-evidence implication fails absent explicit trust assumptions. Nothing else in this paper is claimed as new: the attestation vocabulary descends from RFC 9334, the lineage model from provenance standards, the empirical observability framing from agent-safety benchmarks, and the review method from established systematic-review practice; each is used as a baseline, cited candidly, and never rebranded. No new mechanism, protocol, detector, or benchmark is proposed; the study's falsifiable outputs are the populated matrix, the agreement statistics over it, and the reproduced witnesses — and the study commits in advance to reporting their failure as a negative result if they do not clear the pre-registered thresholds.

## 5. Non-overlap declaration

### 5.1 Refusal of frozen E15–E22 archive as new evidence

This study **refuses** to use the frozen GLHS R4 E15–E22 experiment results as new evidence, new baselines, or primary data. Per the blueprint ("Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments"), the anti-salami gate (item 5: "Same simulation, frozen E15–E22 data … cannot count as nine independent results"), and `SH-claim_overlap` (ACNS declares `reuses_archive: []`), the ACNS SoK:

- reuses **no** E15–E22 outcome, schedule, figure, or frozen manifest as an ACNS result;
- cites GLHS/HEALTHINF, where relevant, as **prior work disclosed in the related-work section**, never as independently generated ACNS evidence;
- notes additionally (from `CONTEXT/SOURCE_AUDIT_2026_11_14.md`) that historical E15–E19 runs attested `sqlite:///:memory:` and E20 provider receipts were `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE` — these historical-frozen rows are **unreproduced mixed-version evidence** and are excluded from any ACNS claim under the execution contract's "no claim derived from unreproduced, mixed-version or historical-frozen evidence" rule.

The negative/adversarial control for this contract is exactly the rejected move: presenting an overlapping published GLHS result as new ACNS evidence (`ACNS-scope` §4). This contract refuses it.

### 5.2 Distinction from IFIP SEC 2027 (mechanism paper)

| Axis | IFIP SEC 2027 | ACNS 2027 (this study) |
|---|---|---|
| Class | New **mechanism**: replay-closed authorization across purpose, delegation, and AI proposal lineage | **SoK**: taxonomy + coverage matrix; explicitly *no new mechanism* (§1) |
| Primary endpoint | Replay acceptance rate across purpose/delegation lineage (unique attack histories) | Evidence-boundary coverage matrix; κ, ambiguous-claim fraction, counterexample reproduction rate |
| Evidence | Executed adversarial schedules on the candidate mechanism vs baselines | Extracted and coded claims from a 2019–2026 publication corpus + executable witnesses |
| Evaluation object | The mechanism's admission decisions | The published literature's claim-evidence structure |
| Data | Synthetic IFIP-specific schedules (`synthetic-ifip_sec-2027`) | Literature corpus + synthetic coding fixtures (`synthetic-acns-2027`) |

Per `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md` ("IFIP/ACNS: One is replay-resistant admission, one is SoK bibliographic taxonomy; literature SoK must be independent of self-referential performance results") and `GATES/ANTI_SALAMI_REVIEW.md` ("IFIP SEC–ACNS (mechanism vs SoK)"), ACNS consumes **zero** IFIP SEC experimental inputs, shares no primary endpoint, and derives no ACNS claim from IFIP mechanism runs — including the attestation-adjacent IFIP receipt constructs, which appear only as cited related work and, where relevant, as corpus items coded like any other published system. Conversely, the SoK's coverage matrix must not be presented as evidence of the IFIP mechanism's effectiveness.

### 5.3 Distinction from DIMVA 2027 (detection paper)

DIMVA 2027 (GovernanceTrace) is a **detection** study: campaign-level probing detection PR-AUC at a fixed false-alarm budget, from minimal agent event telemetry, with held-out attacker families. ACNS is a **systematization** study with no detector, no training data, no detection metric, and no event-stream evaluation. The anti-salami gate's IFIP/DIMVA distinction (prevention vs detection) is itself orthogonal to ACNS: ACNS is neither prevention nor detection but *evidence-semantics mapping*. ACNS shares with DIMVA only the abstract motivation (governance assurance in agent systems); it uses no DIMVA telemetry, synthetic campaigns (`synthetic-dimva-2027`), detectors, PR-AUC/FPR measurements, or code. No ACNS witness is a detection mechanism, and no DIMVA result may populate the ACNS coverage matrix.

### 5.4 Cross-study firewall summary

Against all sibling 2027 studies (DSN, PoPETs, IFIP SEC, COMPSAC, AIME, SACMAT, DIMVA, PST): ACNS shares the repository and background infrastructure but has (1) a different precise RQ (what attestation evidence supports what claims — a literature question, not a system-behavior question), (2) a different primary endpoint (coverage matrix / κ / reproduction rate — not any runtime violation, disclosure, commit, detection, or reconstructability rate), (3) independently frozen inputs (pre-registered corpus + coding protocol, no frozen E15–E22 reuse), (4) a material new contribution (the extended lattice + witness gallery), and (5) candid citation of the closest related published work (§2). The 5-part distinction test of `PREVIOUS_ANTI_OVERLAP_MATRIX.md` passes.

## 6. Venue-fit risk (carried from task manifest)

ACNS 2027's CFP may not offer a SoK-specific track; submission proceeds only after verifying venue scope and completion of the original systematic method (frozen protocol, executed coding, published ledger). If ACNS 2027 does not accept SoK-format papers, this manuscript routes to a SoK-friendly alternative venue rather than being reshaped into a fake mechanism paper.

## 7. Decision

**Decision: GO** — conditional on the pre-registered gates above: the SoK contribution stands only if (a) the corpus yields cases beyond RFC 9334/PROV/B2 categories, (b) coder agreement meets the pre-registered κ threshold and beats the B3-style generic coding by the registered margin, and (c) witnesses reproduce at or above the registered rate. Failing any of these, the registered negative result is reported and the SoK claim is withdrawn. No empirical value is asserted by this contract; all thresholds and observed values enter via `ACNS-rq_registry`, `ACNS-freeze`, and `artifacts/venue2027/acns/<run_id>/manifest.json`.

Signed: ACNS-scope researcher agent · 2026-11-15 · base `7ebdbbf0740e87ffebe3538d6893a53eaccf2216`
