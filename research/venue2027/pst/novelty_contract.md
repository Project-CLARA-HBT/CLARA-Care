# Novelty Contract — ReceiptMin (`pst` venue, Phase P01, task PST-scope)

- **Contract:** `design_scope()->NoveltyRegister` — signed scope register, design-level only.
- **Version:** 1.0.0 (2026-11-15, worktree base SHA `7ebdbbf0740e87ffebe3538d6893a53eaccf2216`).
- **Purpose:** freeze the independent contribution, the claim-to-prior-work falsification matrix, the three research questions, and the non-overlap boundaries for the study *ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization* **before any run**.
- **Allowed input:** design constants and decision rules only. This contract contains **no measured results and no empirical numbers**; every quantitative outcome is deferred to P02+ and must derive mechanically from `artifacts/venue2027/pst/<run_id>/manifest.json`.
- **Failure semantics:** if any falsification condition below fires, dependent tasks must treat the corresponding claim as rejected and report the negative result; the study-level decision is then re-evaluated (GO → re-scope or NO-GO). Missing dependency evidence blocks rather than guesses.
- **Dependencies:** `SH-claim_overlap` PASS, `SH-literature_hardening` PASS (see `research/venue2027/proof/`). Registry: `research/venue2027/_shared/publication_overlap_registry.yaml`. Ledger: `research/venue2027/_shared/literature_validity_ledger.csv`.

## Title and target reader

**Title:** ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization.

**Target reader:** privacy-engineering and security researchers in the PETS/PoPETs community who study disclosure minimization, transparent logging, and metadata leakage; secondarily, healthcare-security auditors and AI-governance engineers who must decide how much audit detail an AI health-assistant may retain, and for how long, while preserving legitimate forensic accountability. The reader is assumed to know hash chains, HMAC-bound capabilities, and encrypted append-only logs, but not to accept any claim about their reconstructability limits without measurement.

## Scope (one paragraph)

This study measures the trade-off surface — a *reconstruction-versus-linkability frontier* — between legitimate post hoc forensic reconstruction of AI health-action audit events and attacker-side identity linkage/attribute inference, when audit artifacts are minimized to purpose-bound receipts that preserve event commitments and consent/policy-epoch proofs while dropping patient detail. The candidate artifact (B4: purpose-bound minimized receipt plus retention map) is evaluated against full plaintext retention (B0), hash-only digests (B1), an encrypted full log with role-gated decryption and managed deletion (B2), and RFC 9162-style Merkle transparency with authorized material retrieval (B3), on synthetic longitudinal workflows with an ex-ante frozen forensic query set, a compromised read-only audit-reader threat model including auxiliary-data joins, and a trusted offline complete ledger as the independent oracle. The unit of analysis is the independent synthetic case history (never per-event pseudo-replication); the dataset is `synthetic-pst-2027` with no real patient records; development and confirmatory splits follow the freeze protocol.

## Distinct contribution and primary endpoint

**Primary endpoint (study-level):** forensic reconstructability score — the fraction of the ex-ante frozen legitimate forensic query set (authorization, provenance, and commit-eligibility questions) answerable exactly from retained audit artifacts at each retention stage, scored against the independent oracle ledger and reported jointly with attacker linkability/attribute-inference bounds under a compromised read-only audit reader. The score is one coordinate of the formally defined *reconstruction-versus-linkability frontier* that this study contributes as its distinct measurable object.

This endpoint is a **reconstructability measure**: it quantifies how much decision-relevant forensic content survives purpose-bound audit minimization, jointly with the privacy cost of what remains. It is not a disclosure rate (PoPETs), not a crash-consistency or forbidden-commit rate (DSN/COMPSAC), not a replay acceptance rate (IFIP SEC), not an evidence-coverage matrix (ACNS), not a conformance-divergence rate (SACMAT), not a detection AUC (DIMVA), and not an unsafe-clinical-action rate (AIME). No other 2027 CLARA study measures this endpoint, and the published literature (matrix below) defines no equivalent measurable frontier for retained audit receipts.

The distinct contribution is therefore **measurement under minimization**, not mechanism invention: a formally defined frontier, an adversarial attacker model with auxiliary joins, an independent oracle ledger, and the first quantitative evidence comparing purpose-bound minimized receipts with strong encryption- and transparency-based retention baselines under equal budget.

## Claim-to-prior-work falsification matrix

Each row states a claim this study makes, the closest real prior work (ledger id from `literature_validity_ledger.csv` or registry id from `publication_registry.yaml`), what that prior work actually guarantees, and the test by which prior work would refute the claim. Ledger entries are currently `UNVERIFIED`/not reproduced; `PST-prior` must verify primary sources before any baseline-fidelity or comparative claim is asserted.

| # | Claim by this study | Prior work (id) | What the prior work actually guarantees | Falsification test — the claim fails if |
|---|---|---|---|---|
| CL-1 | Append-only integrity evidence alone bounds neither attribute inference nor linkage for retained audit reads. | `ct9162` (RFC 9162 Certificate Transparency) | Tamper-evident Merkle append-only logging; explicitly integrity, not confidentiality or minimization. | A plain RFC 9162-style Merkle log arm (B3) with authorized material retrieval matches B4 on forensic answerability *and* on all attacker-exposure bounds at equal budget, i.e. the frontier separation over integrity-only prior art is not measurable. |
| CL-2 | Cryptographic commitment identifiers (HMAC digests) leave audit-metadata linkage unbounded by themselves. | `macaroons14` (Macaroons, NDSS 2014) | Caveat-bound HMAC capabilities for decentralized authorization; scoped authentication, not audit-content minimization or reconstructability control. | Hash-only digest receipts (B1) statistically match B4 on attacker advantage including auxiliary joins while matching RQ1 answerability, i.e. purpose-bound receipt structure adds no measurable value over HMAC identifiers. |
| CL-3 | Standard clinical audit/interoperability schemas define no quantitative reconstruction-versus-linkability endpoint. | `fhir5` (HL7 FHIR R5 AuditEvent/Provenance) | Interoperability structure for audit and provenance resources; conformance is not a privacy or forensic-sufficiency guarantee. | A FHIR-conformant retention profile is shown to already specify measurable reconstructability bounds equivalent to the study endpoint, invalidating the endpoint-novelty claim. |
| CL-4 | Purpose-bound audit minimization is not machine unlearning and is not evaluated by unlearning axes. | `muse` (MUSE, machine unlearning evaluation) | Distinguishes unlearning, future-disclosure prevention, and utility for *models and derived content*, not for retained ledger receipts. | MUSE-style evaluation dimensions are shown to already capture retained-audit reconstruction equivalence, collapsing the measurement-framework claim to a re-application of existing axes. |
| CL-5 | Attestation evidence-level vocabulary does not quantify post hoc forensic reconstruction. | `rats9334` (IETF RATS architecture) | Strict evidence/attester/verifier role separation; prevents equating a digest with hardware attestation. | RATS evidence roles already supply an equivalent reconstruction-vs-linkability frontier metric for audit retention, making the proposed metric redundant. |
| CL-6 | ABAC purpose/attribute vocabularies carry no quantitative audit-retention frontier. | `nistabac` (NIST SP 800-162) | Formal attribute-based authorization vocabulary and considerations; no measurable retained-read endpoints. | NIST ABAC guidance is shown to define measurable retained-read endpoints equivalent to the study endpoint. |
| CL-7 | Authorization-engine consistency does not imply audit-retention reconstructability properties. | `zanzibar19` (Zanzibar, USENIX ATC 2019) | Consistent global authorization with permission re-evaluation; no post-retention audit metadata exposure bounds. | Consistency-aware authorization is shown to provide documented post-retention audit exposure bounds matching B4, removing the gap this study measures. |
| CL-8 | Normative governance guidance is not empirical evidence of a frontier. | `who21` (WHO ethics and governance of AI for health) | Normative principles on purpose limitation and governance; no benchmark or measurable endpoint. | WHO guidance is shown to prescribe a measurable audit-minimization endpoint, contradicting the declared empirical gap. |
| CL-9 | A well-managed encrypted full log (B2) is the strongest competing explanation of any observed frontier: encryption plus retention policy may already dominate minimized receipts. | `glhs-journal` lineage (parent program background) plus standard encryption practice | Parent GLHS results are background only; encryption with key-gated deletion is established practice, not evidence about reconstructability frontiers. | B2 dominates B4 simultaneously on privacy (RQ2 bounds) and reconstruction (RQ1 answerability) at comparable cost (RQ3) — the study-level falsification rule below fires and the superiority claim is rejected. |
| CL-10 | The evidence base of this study is new, not rebranded archive results. | frozen GLHS E15–E22 experiments and the accepted HEALTHINF paper (parent program) | Historical background results from a different data surface and question. | Any outcome row, figure, or denominators of this study is derived from E15–E22 or HEALTHINF results — archive reuse as new evidence, which invalidates the study. |

## Research questions

Exactly three research questions are frozen for this study; estimands, margins, and denominators are frozen by `PST-rq_registry` in `rq_and_estimands.yaml` before any run.

### RQ1 — Forensic sufficiency under purpose-bound minimized receipts

What fraction of legitimate forensic questions (authorization, provenance, commit-eligibility) remain answerable from purpose-bound minimized receipts across retention stages, compared with hash-only, encrypted, and full-retention audit arms?

- **Primary endpoint:** forensic query answerability per independent synthetic case history — the fraction of the ex-ante frozen query set answered exactly, by arm (B0–B4) and retention stage, scored against the independent oracle ledger.
- **Strongest competing baseline:** B2 — encrypted full log with role-gated decryption and managed retention. It trivially maximizes authorized answerability, so ReceiptMin must show answerability not distinguishably worse than B2 while strictly reducing retained sensitive content and RQ2 exposure; otherwise the minimization adds only risk.
- **Independent oracle:** trusted offline complete ledger (full plaintext event store) held by the evaluation role only, implementing the same frozen query set; the candidate implementation never imports oracle code, oracle labels are frozen before arms run, and oracle disagreement counts are reported, never repaired post hoc (per `AGENTS/EXECUTION_CONTRACT.md`).
- **Statistical test:** two-sided paired permutation test on per-history answerability (case-family clustered), pre-registered α = 0.05 with Holm correction across the three RQ families; effect sizes reported with case-bootstrap confidence intervals. Denominators are independent histories, never per-event pseudo-replication.
- **Falsification condition:** B4 answerability is distinguishably below B2 beyond the frozen non-inferiority margin, or B1 hash-only receipts are statistically indistinguishable from B4 on both answerability and every RQ2 exposure bound — in either case the claim of a separated reconstruction-versus-linkability frontier is rejected.

### RQ2 — Metadata exposure under compromised read-only audit access

Can record-level identity linkage and attribute-inference exposure be bounded when an audit reader combines minimized receipts with auxiliary linkage data?

- **Primary endpoint:** attacker advantage over a declared prior — re-identification and attribute-inference advantage, plus linkability precision — measured per independent synthetic subject under a compromised read-only audit-reader privilege with auxiliary-data joins.
- **Strongest competing baseline:** B1 — hash-only content digests, the minimal prior-art minimization; if B1 already achieves the same attacker-advantage bound including auxiliary joins, purpose-bound receipt structure is not measurably better. Cross-checked against B2 under the same reader privilege without decryption keys.
- **Independent oracle:** blinded attacker-evaluation harness operated by the evaluation role, with ground-truth subject and attribute labels taken from the trusted offline complete ledger; the harness never imports candidate code, and the attacker model (privilege, auxiliary tables, join strategy) is frozen ex ante.
- **Statistical test:** one-sided exact permutation test of attacker advantage against the declared prior, subject-level clustered, pre-registered α = 0.05 with Holm correction across RQ families; linkability precision reported with case-bootstrap confidence intervals.
- **Falsification condition:** the auxiliary-join attacker's advantage against B4 exceeds the pre-registered exposure bound, or is statistically indistinguishable from the advantage achievable against B1/B2 under the same privilege — then the claim that purpose-bound minimization bounds metadata exposure is rejected.

### RQ3 — Operating costs across audit volumes and retention epochs

What retention, key-deletion, and proof-generation costs emerge across audit volumes and retention epochs for purpose-bound minimized receipts relative to strong baselines?

- **Primary endpoint:** retained bytes, proof-generation latency, and authorized investigation recovery time, per independent audit-volume and retention-epoch condition (case-clustered), for B4 versus each baseline.
- **Strongest competing baseline:** B3 — RFC 9162-style Merkle append-only integrity with authorized material retrieval, the simplest semantics achieving integrity plus authorized recovery; cross-checked against B2 storage and deletion costs.
- **Independent oracle:** the trusted offline complete ledger provides ground-truth recovery answers and reference timings; cost instrumentation is validated against fixed reference workloads frozen before any run, and all timing distributions are reported, not only aggregates.
- **Statistical test:** paired case-clustered bootstrap (pre-registered 10,000 resamples) on per-condition cost ratios of B4 versus each baseline, reporting median ratios and 95% confidence intervals; any equivalence claim requires the interval to lie inside a frozen equivalence margin.
- **Falsification condition:** B3 and B2 jointly dominate B4 on all three cost axes while matching RQ1 answerability and RQ2 bounds — then the operating-cost motivation for purpose-bound minimization is rejected.

## Baseline arms

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | full plaintext append-only log | utility upper bound / privacy lower bound |
| B1 | hash-only log or content digests | minimal prior-art minimization; weak audit utility |
| B2 | encrypted log with role-gated decryption and deletion | strongest confidentiality comparator; dominant competing explanation |
| B3 | RFC 9162-like Merkle append-only integrity + authorized material retrieval | strongest integrity baseline |
| B4 | proposed purpose-bound minimized receipt and retention map | candidate (evaluation instrument, see access-control boundary) |

All arms run at equal data, permission, and compute budget. A baseline implemented as `NOT_RUN_EXTERNAL` is a transparent status that blocks comparative claims against that arm; it is never replaced by an unnamed custom surrogate.

## Non-overlap with the PoPETs 2027 study

The PoPETs 2027 study (*Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts*, registry endpoint `revoked-context re-disclosure rate`) and this study share the CLARA repository and background governance code, but are independent on every required distinction (anti-salami test in `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`):

1. **Time direction:** PoPETs prevents *future-context disclosure* — prohibited attributes reaching outbound dispatches after consent revocation. PST measures *post hoc audit-event reconstruction and retention* — what a forensic reader can reconstruct from already-committed audit artifacts.
2. **Data surface:** PoPETs evaluates cached AI context, prompts, cache keys, and outbound dispatch pipelines. PST evaluates retained audit receipts, retention maps, and audit-reader access — different artifacts, different dataset (`synthetic-popets-2027` vs `synthetic-pst-2027`), separate task contracts.
3. **Threat model:** PoPETs adversary exploits the dispatch/caching pipeline with correct source-boundary authorization. PST adversary is a compromised read-only audit reader combining receipts with auxiliary linkage tables.
4. **Primary endpoint:** `revoked-context re-disclosure rate` (PoPETs) vs `forensic reconstructability score` (PST) — disjoint quantities; neither study's outcome can serve as the other's evidence.
5. **Shared context, explicitly secondary:** both studies may reuse repository consent/epoch vocabulary as shared context, but no measurement, figure, or outcome row is shared, and the PoPETs cache-invalidator is never a PST baseline.

The remaining seven 2027 studies are likewise endpoint-disjoint (crash consistency, replay admission, evidence taxonomy, concurrency, clinical workflow safety, policy conformance, boundary-probing detection); the full routing is recorded in `_shared/publication_overlap_registry.yaml`.

## Archive refusal — frozen GLHS E15–E22 are not new evidence

The frozen parent-program results — GLHS R4 experiments **E15–E22** and the accepted HEALTHINF paper — **are refused as new evidence** for this study. They are background context only: citable as related work, usable for nothing else. No RQ, endpoint, denominator, figure, or comparative claim of this study may be derived from, re-labeled from, or counted with E15–E22 or HEALTHINF outcomes; violating this is the negative adversarial control of `PST-overlap` and blocks the venue. The declared registry status for this study is `reuses_archive: []`, and the study's evidence comes exclusively from new `synthetic-pst-2027` runs generated after the protocol freeze.

## Access-control boundary (no new access-control mechanism)

This study **does not propose a new access-control mechanism**. ReceiptMin is a measurement framework plus an evaluation artifact: the purpose-bound minimized receipt and retention map (B4) are experimental instruments for measuring the frontier, not authorization primitives. Authorization, consent, and enforcement semantics remain the existing CLARA systems (RBAC role gating, versioned consent, purpose binding); production integration of B4 is out of scope for this venue. The contract forbids presenting the receipt format as an enforcement mechanism in any manuscript text: phrases such as "we introduce a new access-control mechanism", "we propose a new access-control mechanism", "novel access-control mechanism", or "new authorization enforcement mechanism" are prohibited claim patterns, and any such claim in a downstream draft is a scope violation to be corrected in review.

## Study-level falsification rule

If the encrypted full log with a well-managed retention policy (B2) dominates the minimized receipts (B4) on privacy (RQ2 exposure bounds) and reconstruction (RQ1 answerability) simultaneously at comparable cost (RQ3), the novelty-superiority claim of this study is rejected. The outcome must then be reported as a meaningful negative result, or the study re-scoped under a newly signed contract — never silently re-labeled as a different contribution (anti-salami rule). A routine incomplete, stale, or UNKNOWN arm outcome is never counted as a pass, and no output is selectively dropped.

## Scope controls (positive and adversarial)

- **Positive control 1:** the contract names a specific candidate mechanism (B4) against at least three strong baselines (B1, B2, B3) with declared roles and equal budget.
- **Positive control 2:** the primary endpoint is measured against an independent oracle ledger that the candidate never imports, with frozen labels.
- **Adversarial control 1:** an E15–E22 outcome re-branded as a PST result is refused (archive reuse as new evidence).
- **Adversarial control 2:** a PoPETs future-disclosure claim imported as a PST forensic-reconstruction result is refused (different endpoint, data surface, and threat model).
- **Adversarial control 3:** the contract read as proposing a new access-control or authorization enforcement mechanism is out of scope; the boundary above rejects it.

## Decision

Decision: GO

Conditions attached to the GO:

- Condition 1 — `PST-rq_registry` must freeze estimands, non-inferiority and equivalence margins, and denominators in `rq_and_estimands.yaml` before any arm runs.
- Condition 2 — `PST-prior` must verify the ledger entries used in the matrix above against primary sources before any baseline-fidelity or comparative claim; baselines marked `NOT_RUN_EXTERNAL` block comparative claims rather than being substituted.
- Condition 3 — if the study-level falsification rule fires, the result is reported as a negative outcome and the decision is re-evaluated; the falsification path is an output, not a failure to hide.
- Condition 4 — the archive refusal and the PoPETs separation in this contract are load-bearing for the GO; `PST-overlap` must re-verify both before the venue signs off.
