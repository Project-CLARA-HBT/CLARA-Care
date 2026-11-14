# IFIP_SEC 2027 · Novelty contract and scope register (IFIP_SEC-scope)

**Task:** `IFIP_SEC-scope` · **Phase:** `P01` · **Venue:** `ifip_sec` · **Priority:** `P0`
**Paper:** Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage
**Contract version:** `clara.venue2027.ifip_sec.novelty_contract.v1`
**Status:** Frozen *prospective* scope contract — a design commitment, not experimental evidence. No number in this file is a research result; all empirical claims must later derive mechanically from `artifacts/venue2027/ifip_sec/<run_id>/manifest.json`.
**Provenance anchors:** prior-work ids are taken verbatim from the frozen literature validity ledger (`research/venue2027/_shared/literature_validity_ledger.csv`, SHA-256 `53025fe21969b868e988dab6fcb9f666fec109b097e35924ea0cbb7fa5457827`) and the shared overlap registry (`research/venue2027/_shared/publication_overlap_registry.yaml`, SHA-256 `79f33faca3c9d30b7cfc60573b583da39f9c9587dc16d4fcddfc44eb83d7cb0a`).

## 1. Title and target reader

**Working title:** *Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage*.

**Target reader:** security engineers and researchers who design, review, or operate capability-token and policy-engine infrastructure (Macaroons-style caveat tokens, Zanzibar/OpenFGA relationship systems, Cedar/OPA decision engines) in multi-tenant, AI-mediated health platforms. The reader is assumed to already believe that scoped tokens plus consistent authorization solve "most of" replay; the paper must therefore convince this skeptical implementer that a specific multi-hop delegation/epoch/replay interleaving defeats correctly configured baselines, and quantify the price of closing it. Secondary readers: IFIP SEC reviewers of applied authorization systems, and platform architects at healthcare AI vendors who must decide whether delegated AI proposal receipts need lineage-aware admission.

## 2. Claim-to-prior-work falsification matrix

Every candidate claim below survives **only if** its required differentiator is demonstrated against the named prior work under the named falsifying test; otherwise the claim is explicitly surrendered. Prior-work identifiers are real registry ids (see provenance anchors); none may be replaced by a stub with the same name.

| # | Candidate claim (IFIP_SEC) | Closest prior work (ledger id) | What prior work already solves | Required differentiator (must be shown, not assumed) | Falsifying test |
|---|---|---|---|---|---|
| M1 | Consumed-once replay closure across delegation hops | `macaroons14` (NDSS 2014), `zanzibar19` (USENIX ATC 2019) | HMAC caveat attenuation with nonce/expiry; consistency-token permission reads | Verify the **full delegation ancestry with parent-reference binding** and atomically consume the nonce across policy-epoch changes, not just signature equality | RQ1 vs B1/B2 on the synthetic interleaving corpus; surrender if decision-equivalent |
| M2 | Purpose + consent/policy double-epoch binding | `nistabac` (NIST SP 800-162), `cedar`, `openfga`, `xacml18` | ABAC purpose attributes; policy decision points; policy conformance testing | **Consent epoch and policy epoch are independently versioned and revalidated at verify time** inside a multi-principal delegation flow | RQ1 epoch-interleaving family vs B3 nonce registry |
| M3 | AI proposal lineage binding (parent-reference chains) | `rats9334` (RFC 9334), `elle20` (OSDI 2020) | Attester/verifier evidence boundaries; black-box history checking | Decision-level **multi-hop proposal-lineage closure** at admission time; evidence taxonomy (ACNS) and detection (DIMVA) are different endpoints | RQ1 lineage-forgery and lineage-pruning families |
| M4 | Linearizable consume-once under real concurrency | `zanzibar19`, `silo13` (SOSP 2013), `elle20` | Serializable/consistent stores; anomaly inference from exported histories | Persisted **nonce-store atomicity with revoked-scope handling across 2+ real PostgreSQL sessions** — never SQLite stand-ins | RQ2 on real PostgreSQL 16; any duplicate consumption fails the claim |
| M5 | Quantified cost/Pareto profile of replay closure | `macaroons14`, `zanzibar19`, `openfga`, `cedar`, `opa` | Token-size and evaluation-cost characteristics of the baselines themselves | Cost deltas at **equal decision safety** with frozen non-inferiority margins (token bytes, p95 verify latency, DB round trips) | RQ3; surrender if B1 dominates at equal safety |
| M6 | Adversarial replay/interleaving threat corpus | `agentdojo24`, `toolemu24`, `injecagent24` | Agent attack benchmarks (prompt injection, tool misuse) | Authorization-**admission** replay families (purpose/tenant/delegation/epoch/revocation), with matched clean controls — not prompt-injection corpora | Dataset freeze + independent-oracle agreement on the corpus |

**Strongest competing explanation (must be defeated or conceded):** a *correctly configured* Macaroon (B1) with consistent authorization checks (B2) already prevents every observed replay; any apparent advantage of the candidate is an artifact of weak baselines, unequal budgets, or SQLite stand-ins. If this explanation survives testing, the manuscript reports equivalence and stops claiming stronger security.

## 3. Research questions and endpoint contracts

**Baseline arms (frozen from `VENUES/ifip_sec/RESEARCH_BLUEPRINT.md`):**

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | bearer signed receipt | weak control |
| B1 | Macaroon HMAC caveats: actor, purpose, task, expiry, nonce | strong token baseline, correct semantics |
| B2 | Zanzibar/OpenFGA with consistency token and fresh policy evaluation | strong relationship consistency baseline |
| B3 | Cedar/OPA policy decision with replay nonce registry | strong security-engineering comparator |
| B4 | proposed delegated lineage transition verifier | candidate |

All arms run on the same synthetic account fixtures, equal compute budget, and pinned upstream sources; `NOT_RUN_EXTERNAL` is a permitted transparent status but forbids comparative claims. Minimal control vectors required before any implementation: two positive (CASE-01 legitimate same-purpose accept; valid delegation within current epoch) and two adversarial (CASE-02 cross-purpose replay deny; CASE-03 cross-tenant substitution deny), per `VENUES/ifip_sec/CASE_MATRIX.md`.

### RQ1 — Cross-context replay admission

Under which delegation and epoch interleavings do signed context-bound capability baselines admit an invalid replay or reject valid operations?

- **Primary endpoint:** invalid replay admissions per unique attack history, paired with valid control acceptance — i.e. the replay acceptance rate across purpose/delegation lineage, measured on distinct interleavings in isolated synthetic accounts across delegation/revocation/retry/tenant switches.
- **Strongest competing baseline:** B1 — Macaroon HMAC caveats (actor, purpose, task, expiry, nonce), the blueprint's "strong token baseline, correct semantics"; B2 (Zanzibar/OpenFGA consistency token with fresh policy evaluation) runs as co-comparator so a token-only win cannot be blamed on missing consistency.
- **Independent oracle:** allow/deny labels derived from the frozen principal graph and commit-time consent epoch, authored from the event sequence and policy/DB ground truth — never from candidate verifier output or candidate reason codes; ambiguous labels stay `INDETERMINATE` and are never coerced.
- **Statistical test:** exact McNemar on paired discordant decisions across matched attack histories; case-family-clustered bootstrap CI on the risk difference; zero-event arms reported with one-sided Clopper–Pearson 95% upper bounds (never "zero failures proves safety").
- **Falsification condition:** if a properly scoped Macaroon plus consistent authorization check (B1 + live epoch check) is decision-equivalent on all attack families, equivalence is stated and no stronger security is claimed; any candidate invalid replay admission on a history the oracle labels `DENY` falsifies the mechanism claim outright.

### RQ2 — Atomic consume-once under real concurrency

Is the proposed consume-once transition linearizable under two or more real PostgreSQL sessions and revoked scope?

- **Primary endpoint:** duplicate consumption races and invalid concurrent admissions per independent interleaving history on persisted PostgreSQL 16 executions, including revocation committed between dispatch and consume.
- **Strongest competing baseline:** B3 — Cedar/OPA policy decision with replay nonce registry, the security-engineering comparator that also consumes nonces and could match the consume-once invariant; B2 (consistency token) runs as co-comparator for stale-read tolerance.
- **Independent oracle:** a black-box linearizability/history checker over exported execution histories (Elle-style, per `elle20`), keyed to the frozen principal graph and revocation timeline; the checker imports no candidate code and adjudicates from persisted state, not from candidate reason codes.
- **Statistical test:** one-sided Clopper–Pearson 95% upper bound on the duplicate-consumption rate over independent interleavings (zero-event rule); exact McNemar vs B3 on paired histories; clustered uncertainty at the independent-history unit, never per-event pseudo-replication.
- **Falsification condition:** any candidate duplicate consumption, lost revocation, or revocation bypass on a valid history fails the claim and is reported as a negative result; if B3's nonce registry under serializable transactions is also linearizable on all tested interleavings at equal budget, no unique atomicity advantage is claimed.

### RQ3 — Operational cost of replay closure

What are token size, verification latency and legitimate operation rejection costs relative to well-configured Macaroons and Zanzibar-like policies?

- **Primary endpoint:** token bytes, p95 verification latency, authorization DB round trips, and legitimate-operation rejection (valid control acceptance) at matched concurrency and permission semantics.
- **Strongest competing baseline:** B1 — well-configured Macaroons, the size/latency floor among semantically correct tokens; B2 — Zanzibar/OpenFGA with consistency token, the DB round-trip comparator.
- **Independent oracle:** a frozen cost-measurement protocol with external instrumentation — DB-layer round-trip counters, harness wall-clock timestamps, and wire-format byte counts — never candidate self-reported timings; hardware and settings recorded in the run manifest.
- **Statistical test:** paired differences (candidate − baseline) per matched schedule with schedule-clustered bootstrap CIs; the legitimate-rejection increase is a frozen non-inferiority margin declared before holdout; point estimates without intervals are not reported.
- **Falsification condition:** if B1 achieves equal decision safety (RQ1) at statistically indistinguishable or lower cost on all three cost metrics, no cost-justified superiority is claimed and only the Pareto frontier is reported; a candidate false-denial increase beyond the frozen margin on legitimate role changes is a failed utility gate, not a footnote.

## 4. Scope — the truly distinct endpoint

**TRULY DISTINCT ENDPOINT: replay acceptance rate across purpose, delegation and AI proposal lineage** (shared-registry phrasing: "replay acceptance rate across purpose/delegation lineage"). This venue centres on a multi-principal interleaving in which a valid consent-purpose receipt is delegated, refreshed and consumed across policy-epoch changes and concurrent replay: the study defines a consumed-once invariant and a tested provenance binding for delegated proposal chains, and measures whether each authorization architecture admits an invalid replay or rejects a valid operation under that interleaving. The competing explanation this design must defeat is that correctly configured caveat tokens with consistent authorization already close every such replay. This endpoint is distinct from GLHS R4's disclosure-to-commit continuity (which asks whether a persistent write matches the exact disclosed projection), from DSN crash journals, from COMPSAC dependency-closure contention, from PoPETs post-revocation future disclosure, from SACMAT cross-engine conformance, and from PST audit minimization; within the 2027 program it is the only study whose primary observation is admission-time replay closure across delegation lineage under epoch changes and concurrent consumption.

## 5. Non-overlap declaration

### 5.1 Refusal of the frozen GLHS R4 archive (E15–E22)

The frozen parent protocols E15–E22 (dispatch attestation integrity, five-way comparator, current-state insufficiency witness, global-vs-disclosed support separation, transport serialization resistance, provider receipt study, formal novelty model, public reproducibility audit) are **background, not new evidence** for this venue. This contract refuses to present E15–E22 results, schedules, or denominators as IFIP_SEC evidence: no figure, table, rate, or bound from the parent archive may appear as a new experimental result here. Additional recorded backend limitations (per `CONTEXT/SOURCE_AUDIT_2026_11_14.md`): historical E15–E19 executions attest `sqlite:///:memory:` as their backend and therefore cannot support the PostgreSQL-specific concurrency claims RQ2 makes, and E20 is recorded `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE`. Every IFIP_SEC claim must derive from new confirmatory runs on the `synthetic-ifip_sec-2027` dataset, with results filenames deriving mechanically from `artifacts/venue2027/ifip_sec/<run_id>/manifest.json`, after protocol freeze and without opening any holdout early.

### 5.2 Distinction from ACNS 2027 (SoK)

ACNS's primary endpoint is the **evidence-boundary coverage matrix** of attestation in tool-using AI systems — a systematic literature taxonomy with independent human coders, inter-rater agreement, and executable counterexample witnesses over published claims. IFIP_SEC's primary endpoint is the **replay acceptance rate across purpose/delegation lineage** — an executable admission-mechanism evaluation over a new synthetic interleaving corpus. Per `GATES/ANTI_SALAMI_REVIEW.md`, the IFIP SEC–ACNS pair is mechanism vs SoK: the SoK must stay independent of this study's self-referential performance results, and this study must not reuse ACNS's literature corpus, taxonomy, or coder outputs as its own evidence. Differentiation assertion: same trust-domain problem space, different research question, different primary endpoint, different independent evaluation design — two studies, not two venues for one manuscript.

### 5.3 Distinction from DIMVA 2027 (detection)

DIMVA's primary endpoint is **probing detection AUC at a fixed false-positive budget** — campaign-level detection over time-series agent event streams with privacy-constrained metadata and unseen-family holdout. IFIP_SEC is **prevention, not detection**: it denies invalid tokens at verification time and measures per-unique-history admission decisions; no detector score, AUCPR, time-to-detect, or campaign-classification metric may appear as an IFIP_SEC endpoint, and no IFIP_SEC admission corpus may serve as DIMVA training/detection data. Per `GATES/ANTI_SALAMI_REVIEW.md`, the IFIP SEC–DIMVA pair is prevention vs detection on independent event streams. Differentiation assertion: detection infers attacker campaigns after the fact; replay closure decides single admissions correctly at the boundary — different endpoint, different dataset, different oracle.

### 5.4 Remaining 2027 venue distinctions (summary)

| Venue | Their primary endpoint | IFIP_SEC non-overlap control |
|---|---|---|
| DSN | crash-consistency violation rate after fault injection | no crash/fault-injection schedules; admission decisions, not recovery |
| COMPSAC | forbidden commit rate under dependency-complete schedules | no dependency-closure concurrency benchmark; capability admission instead |
| PoPETs | revoked-context re-disclosure rate | no cache/prompt redisclosure measurement; admission-time replay only |
| SACMAT | delegation conformance divergence detection rate | no cross-engine conformance testing; single frozen semantics per arm |
| AIME | unsafe clinical action rate under consent/medication changes | no clinical-content vignettes; authorization decisions only |
| PST | forensic reconstructability score | no audit minimization or retention analysis |

### 5.5 Prior manuscripts disclosure

The accepted HEALTHINF work (recorded as accepted in `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`; status re-audited before any submission), the GLHS journal manuscript, GovRed/RIVF, and GovMut/SOICT are disclosed and cited as background where relevant — never silently cannibalized. Positive and negative overlap findings will be published in `research/venue2027/ifip_sec/overlap_audit.md` (dependent task `IFIP_SEC-overlap`).

## 6. Decision

**Decision: GO**

Conditional obligations attached to this GO: (1) the mechanism claim survives only if B1/B2 do not already meet every invariant — otherwise the manuscript reports equivalence and operational trade-offs only, per the blueprint falsification criterion; (2) RQ2 claims require real PostgreSQL 16 with attested backend — SQLite observations are inadmissible for concurrency conclusions; (3) the holdout opens only after the prospective freeze (`IFIP_SEC-freeze`), and no threshold or denominator changes afterwards; (4) if any oracle disagreement, baseline infidelity, or unequal budget is found, the task stops and revises rather than weakening a guardrail. This GO is a scope decision, not a prediction of results and not a guarantee of acceptance.
