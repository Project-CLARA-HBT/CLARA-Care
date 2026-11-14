# ACNS · Threat, trust and failure model (SoK scope)

> **Task:** `ACNS-threat` · **Phase:** `P01` · **Venue:** `acns` · **Status:** draft register
> **Depends honored:** `ACNS-scope` (signed novelty contract, Decision GO) and `SH-research_ethics` (synthetic-only policy PASS, dataset `synthetic-acns-2027` compliant).
>
> **Paper:** *SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems*
> **Contract:** `clara.venue2027.acns.threat-model.v1` · validator `validate_threat()->Coverage` (`_shared/tools/threat_model.py`, `THREAT_MODEL_VERSION 1.0.0`)
>
> **SoK declaration (scope of this document):** This is the **threat chapter of a Systematization of Knowledge**. Its subject is *attacks on attestation evidence itself* in tool-using AI systems: forged provider receipts, attestation-level downgrade, evidence-boundary gaps (a claim made without supporting proof), unsupported trust transitivity, timestamp-only evidence, and incomplete disclosure. It proposes **no new mechanism, protocol, detector, or attestation scheme**; per the signed novelty contract §1, its only outputs are (a) an attacker/observer model over an evidence-to-claim lattice (assembly, egress, transport acknowledgment, provider-attested receipt, execution trace, semantic consumption), (b) an attack/control paired matrix, and (c) named counterexample witnesses that map where each claim–evidence implication fails absent explicit trust assumptions. Witnesses are *instruments of falsification for implication pairs*, never deployable defenses; no detection/prevention rate will be reported. Cross-study firewall (per `ACNS-scope` §5): this threat model feeds the ACNS SoK only — it consumes no IFIP SEC mechanism inputs and no DIMVA detection telemetry, and its coverage matrix must not be presented as evidence for either sibling study. All empirical values (κ, reproduction rates) are **out of scope here** and enter only later via `artifacts/venue2027/acns/<run_id>/manifest.json` after ACNS-freeze. Synthetic-only: `synthetic-acns-2027` fixtures; no PHI/PII, no real provider calls.

## 1. Attacker and observer capabilities

The unit under attack is an **attestation claim** made by or about a tool-using AI system, e.g. *"the provider acknowledged receipt, therefore the model executed the tool."* The attacker's goal is not (primarily) to make the agent misbehave, but to **manufacture, launder, downgrade, or over-read attestation evidence** so that a relying party (verifier, auditor, requester, reviewer) accepts a claim the evidence does not support. Five attack families are defined in §2; the capability axes below apply across all of them.

### 1.1 Capability axes

- **A1 — Network position:** passive off-path eavesdropper; active on-path attacker (MitM) who can drop, delay, reorder, duplicate, or substitute tool-call bytes; DNS/CDN-level redirector. At evidence level L2 (`DISPATCHED`/`ACKNOWLEDGED`) and below, all are unprivileged.
- **A2 — Endpoint compromise of untrusted ends:** full control of the agent host *outside* the attested execution environment (assembly/egress buffer, local tool registry, config). The attacker can reassemble requests, alter serialized payloads pre-dispatch, or suppress egress; they control everything below the attestation boundary.
- **A3 — Provider-side power (semi-trusted adversary):** a colluding or compromised provider endpoint that can issue **receipts for bytes it never durably processed** (transport acknowledgment ≠ processing), reorder or re-serve internally, serve stale cached completions, or misattribute which model/agent produced an output. Honest-but-curious is the floor; issuance-capable is the adversarial setting.
- **A4 — Model agency (the model as adversary):** the LLM agent itself has goal-directed agency, prompt-injection reach into tool arguments, and can act *differently* from the attested plan: substitute a tool, alter arguments post-attestation, or induce the operator harness to emit evidence-shaped events without performing the work ("evidence theater"). The agent can also re-use prior authorized interactions wholesale (§1.1 A5).
- **A5 — Artifact re-use power:** capture-and-reuse of legitimately signed artifacts: whole request/receipt pairs, session tickets, nonce-bearing receipts re-presented in a different context, tenant, purpose, or time. Includes cutting-and-pasting a valid receipt for request X as "proof" about request Y.
- **A6 — Insider / observer manipulation:** legitimate participants with partial authority: operators who archive selectively, corpus curators quoting claims out of evidence context (the SoK's core corpus risk), benchmark harness authors whose "observer" is inside the agent loop, reviewers over-reading published claims; plus external observers (auditors, downstream requesters) who must decide what published evidence proves.
- **A7 — Time control:** attacker influence over observed time: delayed delivery, clock skew across parties, artifact resubmission across schedule boundaries (key rotation, consent/policy epochs), and revocation-lag windows (§5).

### 1.2 Observer positions (what can actually be seen)

Observation axes follow the study lattice; each evidence class has a distinct observer:

| Evidence class | Who can observe | What the observer sees | What it can never show alone |
|---|---|---|---|
| Assembly (L0 `ASSUMED`) | Agent host only (attacker-controlled under A2) | Intent/plan, composed payload | Anything about transmission or execution |
| Egress (L1 `ASSEMBLED`) | Agent host; server-side observers see arrival, not composition | Bytes left the sender's buffer | Provider processing; model execution |
| Transport acknowledgment (L1.5) | Sender-side TCP/TLS stack | Bytes sent / transport ACK | Application-level receipt; content received |
| Provider-attested receipt (L2 `ACKNOWLEDGED`) | Verifier via provider signature, anchored in pinned roots (§3) | Signed statement "received bytes with digest D at time T" | Execution, semantics, side effects |
| Execution trace (L3 `EXECUTED`) | Trusted execution environment only (§3) | Attested tool invocation + inputs | Downstream effects outside the TEE |
| Semantic consumption (L4 `COMMITTED`) | Persisting service's own logs, verifiable only to that service | Side effect recorded | That the *model* semantically consumed the result |

Published papers are observed from outside: a reader sees only what the authors disclose, so corpus coding (RQ1/RQ3) inherits exactly the L0/L1 visibility unless the paper documents stronger evidence. The ambiguity this creates (e.g., ACNS-CASE-02/05/06) is retained as `INDETERMINATE` rather than coerced to PASS.

## 2. Attack family and control matrix

Paired matrix per validator contract: every family carries both a **clean** control (the implication the evidence *does* support under stated trust) and an **adversarial** case (the witness demonstrating where the implication fails). "Expected oracle verdict" is the `truth.json` label for the adversarial cell; expected verdicts are frozen before execution, never repaired post hoc. Capabilities A1–A7 and trusted components TC1–TC6 (§3) parameterize the rows; family-specific prose follows the table.

| Attack family | Case | Actor/observer | Capability | Control (clean) | Adversarial case | Expected oracle verdict |
|---|---|---|---|---|---|---|
| revocation_timing | paired | relying party vs A7+TC1 | time-shifted reliance after revocation lag | clean: receipt verified under pinned roots during validity window and against current schedule state is accepted at L2; claim stays "received" | adversarial: same receipt re-relied 24h after signing-key revocation with no schedule check; verifier accepts and asserts continuity | REJECT: staleness undetected without verification-time schedule check; claim capped at L1 |
| replay | paired | relying party vs A5+TC2 | receipt transplanted across contexts | clean: receipt with nonce, digest, purpose and tenant bound to request R1 verifies once for R1 at L2 | adversarial: same signed receipt re-presented for request R2 (new arguments, same tenant); signature still verifies | REJECT: signature validity ≠ context binding; nonce/digest check must fail closed |
| model_agency | paired | relying party vs A4+TC3 | agent diverts work post-attestation | clean: TEE-attested tool execution of binary B on measured input I yields an L3 claim exactly for (B,I), reported with TCB statement | adversarial: agent swaps tool B→C or mutates arguments after assembly attestation; harness still emits "executed" evidence event | REJECT: attestation binds execution mechanics, not model intent; the L3 claim does not extend to semantic consumption |
| purpose_scope | paired | relying party vs A6+TC2 | evidence crosses purpose/tenant boundary | clean: consent/receipt minted for purpose P1, tenant T1, is accepted only for scope-matched P1/T1 requests | adversarial: P1-scoped evidence re-presented to authorize P2 (self-care → administration) in another tenant; scope fields ignored | REJECT: authority does not transit purpose/tenant boundaries without explicit re-authorization |
| insider_or_observer | paired | external reader vs A6+TC5 | selective/out-of-context disclosure | clean: disclosed provider receipt with pinned-root verification, quoted with its exact claim scope, classifies at L2 | adversarial: paper quotes a valid receipt as proof that "the model executed the tool"; reader accepts the L2→L4 implication | REJECT: evidence-boundary gap; disclosure completeness is the reader's burden; classified as overclaim |

The five families are the register's **attack** rows; the six evidence classes (L0–L4 plus transport acknowledgment) are the control surface. Any future family must be added here with both cells before witnesses are built for it.

### 2.1 Family notes

- **`revocation_timing`** — attacks *time validity* of evidence. Claim under attack: "the receipt was valid when relied upon." Uses A7 (+A3): evidence is minted under key/consent/policy epoch K and relied upon after K is revoked or superseded; the relying party has no schedule semantics, so staleness is undetectable. Boundary: no evidence class above includes a verification-time check against revocation/schedule state (§5).
- **`replay`** — attacks *context binding* of evidence. Claim under attack: "this receipt proves this request in this context." Uses A5 (+A3): a valid receipt for context C1 is re-presented for C2 (different nonce/tenant/purpose/arguments). The signature verifies; the claim is still false. Boundary: signature validity ≠ first-use-in-context validity; transport acknowledgment carries no context at all.
- **`model_agency`** — attacks *the attested actor itself*. Claim under attack: "execution was attested, therefore the model acted as intended." Uses A4: the agent (or injected content steering it) diverts work between attestation points — tool swapped, arguments mutated post-attestation, or harness emits evidence events without work. Even L3 binds *that* code ran *on* *some* input; it does not bind semantic intent. Boundary: attestation attests execution mechanics, never model intent or semantic consumption.
- **`purpose_scope`** — attacks *purpose/tenant scoping* of claims. Claim under attack: "evidence minted for purpose P1 covers use under P2." Uses A6 (+A5): consent/authority artifacts and receipts cross purpose or tenant boundaries; over-broad claims inherit stale or foreign authority. Boundary: evidence validity is scoped by the authority under which it was minted; crossing scopes voids the implication without explicit re-authorization.
- **`insider_or_observer`** — attacks *the human/disclosure channel*. Claim under attack: "published/disclosed evidence shows the system attests X." Uses A6: selective disclosure, out-of-context quotation, an observer colocated with the attacker (benchmark harness inside the agent loop), or a provider's self-reported receipt with no independent anchor. This is the family that motivates the SoK itself: the corpus's attestation claims are exactly where this attack succeeds most often. Boundary: disclosure completeness is itself evidence the reader must verify, not assume.

## 3. Trusted components

Enumerated per evidence class; each trust anchor must be **pinned and independently verifiable**, otherwise the corresponding claims collapse to the level below.

- **TC1 — Pinned attestation roots.** A frozen set of trust anchors (per-context root of trust for remote attestation; provider receipt-verification public keys pinned by digest). All receipt verification chains to a pinned root; unpinned or TOFU-received keys are treated as L0 evidence only. Roots are versioned; rotation and revocation schedules are part of the root record (§5).
- **TC2 — Receipt verification procedure.** Deterministic offline check: canonicalize → verify signature chain to TC1 → check digest binding to the dispatched bytes → check nonce/context fields (anti-`replay`) → check purpose/tenant scope fields (anti-`purpose_scope`) → check against revocation/schedule state at verification time (anti-`revocation_timing`). Any failed or absent check **fails closed** with a stable reason code; it is never downgraded to a weaker claim class.
- **TC3 — Trusted execution environment for L3.** The only component that can upgrade claims to `EXECUTED`: attests the exact tool binary, measured inputs, and isolation of the execution. Absent TC3, all "execution" claims are capped at L2.
- **TC4 — Honest provider issuance (bounded).** The provider endpoint is trusted **only** for accurate issuance of receipts over bytes actually received, under pinned keys, with monotonic nonce/cursor — not for correct model behavior, semantic correctness, or non-reissuance of old receipts (that is what nonce/context checks must catch). Under A3 the issuance trust collapses and L2 claims degrade to L1.
- **TC5 — Independent oracle authority (human coders + adjudication).** Per `ACNS-scope` §3 and the ethics policy: two independent human coders apply the frozen codebook; a third-party adjudication stream is sealed before analysis. No internal LLM agent is represented as an independent reviewer; a candidate tool may never certify its own oracle labels.
- **TC6 — Fixture determinism.** `synthetic-acns-2027` fixtures with pinned generator version and seed; `case.json`/`truth.json`/`observed.json` are produced under the ACNS-CASE contract, `truth.json` fixed before witness execution and never imported from candidate code.

**Trust-independence rule:** TC5/TC6 are *outside* the candidate tooling; TC1–TC4 are *inside* the deployed evidence path and are exactly what the attack families stress. If any trusted component is removed, the paired matrix (§2) names which claim–evidence implication collapses.

## 4. Excluded domains

Out of scope, with the reason the boundary matters for the SoK's claims:

- **ED1 — Hardware root-of-trust compromise.** Defeat of the TEE/CPU root keys itself (physical/side-channel, firmware implant). If TC1/TC3 roots are broken, *no* evidence class survives, so the taxonomy's interesting boundaries (L2→L4) become vacuous; the study treats hardware-root compromise as catastrophic and unmodeled, consistent with RFC 9334's division of responsibility.
- **ED2 — Cryptographic primitive breakage.** Chosen-prefix collisions, lattice attacks on the signature algorithms, quantum breakage. Assumed secure primitives; the SoK maps *evidence-semantics* boundaries, not crypto strength.
- **ED3 — Provider internal execution integrity beyond receipt semantics.** Whether the provider *actually* ran model M correctly on the bytes is exactly the L2→L3 gap the SoK documents; modeling provider-side execution internals would require TC3-grade attestation inside the provider, which the study assumes absent and treats as an open boundary, not a solved problem.
- **ED4 — Content-level prompt injection and jailbreak effectiveness.** How to craft injections is ToolEmu/AgentDojo territory (baseline B2). The SoK uses agency effects only as the A4 capability, abstracted as "the agent may act differently from the attested plan."
- **ED5 — Clinical efficacy and care quality.** Per the ethics contract: no clinical endpoint, no patient data, no clinical-effectiveness claim; attestation claims in clinical framing appear only as motivation for why overclaims matter.
- **ED6 — Benchmark leaderboard construction.** The matrix is a coding instrument over literature, not a runnable benchmark with held-out splits (novelty contract F6); building one is a separate future study.

## 5. Revocation and schedule time

Time semantics are a first-class part of the model, not an afterthought:

- **Mint time vs verify time.** Every receipt/attestation carries mint time `t_m` (inside the signed artifact); validity is evaluated at **verification time** `t_v` against the schedule state of the anchoring root. Evidence never "is valid"; it *was* valid at `t_m` and *is* accepted only if checks pass at `t_v`.
- **Revocation lag window.** Between a revocation event and verifier-visible propagation there is a window `Δ_rev` in which revoked-but-not-yet-propagated evidence verifies. `revocation_timing` attacks live in this window; witnesses must state the assumed `Δ_rev` and the verifier's schedule source.
- **Schedule boundaries.** Key rotation epochs, consent/policy epochs, and corpus freeze dates are schedule boundaries. Evidence minted under epoch K presented under K′ must fail closed unless re-anchored. Consent/policy epochs align with CLARA's consent-gate semantics; the corpus freeze date is a schedule boundary for which corpus items count as "published claims" (pre-registered 2019–2026 window).
- **Clock assumptions.** No hidden clock: `t_v` is injected (fixture-provided); cross-party skew is bounded and declared in each witness's trust assumptions. Timestamps alone are **not** sufficient evidence for any claim above L1 (§6, gap G6).
- **Corpus-time semantics.** For literature coding, "as of" = paper publication date; a system's *current* security posture is not codable evidence — only what the paper's evidence supported at its own `t_m`.

## 6. Evidence-boundary gap register (SoK core)

The SoK's central instrument: for each claimed implication, the boundary condition whose absence makes it false. This register is what the witness gallery (`ACNS-X07`) operationalizes and what corpus coding (RQ1) classifies published claims against.

| # | Claimed implication | Boundary condition required | Failure family | Witness sketch |
|---|---|---|---|---|
| G1 | transport acknowledgment ⇒ provider processed | provider-signed receipt anchored in pinned roots | replay / insider_or_observer | transport ACK re-used as "received+processed" |
| G2 | provider receipt ⇒ model executed tool | TEE-attested execution (TC3) | model_agency | receipt quoted as execution proof (§2 row `model_agency`) |
| G3 | execution trace ⇒ semantic consumption persisted | persisting service's own verified record | model_agency / replay | "executed" event with no committed side effect |
| G4 | signature validity ⇒ context validity (single use) | nonce + digest + purpose/tenant binding checked at verify time | replay / purpose_scope | receipt transplanted across requests (§2 row `replay`) |
| G5 | valid at mint ⇒ valid at rely | verification-time schedule check | revocation_timing | post-revocation reliance (§2 row `revocation_timing`) |
| G6 | timestamp presence ⇒ event ordering/proof | monotonic source + bounded skew + context binding | revocation_timing / replay | timestamp-only "proof" of ordering across untrusted clocks |
| G7 | evidence at level Ln ⇒ all claims at Ln+1 | explicit trust assumption naming the missing component | any family | per-edge: removing the named trusted component collapses the implication |
| G8 | authority minted for P1 ⇒ authority for P2 | explicit re-authorization at the boundary | purpose_scope | purpose/tenant crossing (§2 row `purpose_scope`) |
| G9 | published claim ⇒ claim supported by paper's evidence | extraction manual applied to the paper's actual evidence | insider_or_observer | out-of-context quotation classified as overclaim (§2 row `insider_or_observer`) |

Nine gaps is the pre-registered register version (`clara.venue2027.acns.threat-model.v1`); additions require a paired clean/adversarial row in §2 first.

## 7. Oracle and actor authority

All authorities are defined explicitly below (the negative control in the task contract is the *absence* of this definition — an unresolvable authority must be treated as a blocker, never as a safe default):

- **Oracle authority for the threat model itself:** this document's failure claims (matrix verdicts, gap register) are **design-time, frozen-before-execution labels**, produced by the human coder/adjudication path of TC5; they are inputs to `ACNS-X07`, not outputs of any candidate tooling. They are falsifiable at execution time under RQ2's reproduction-rate endpoint; if a witness fails to reproduce its label, the *result is reported*, and the label is not repaired to match.
- **Actor authority in deployed semantics (what each actor may decide):**
  - *Verifier (relying party)* — may accept evidence **only** via TC2's full check chain; every check failure is a stable reason code, never a silent downgrade; it may never accept "digest match alone" as clinical reasoning proof.
  - *Provider* — may attest **only** bytes received under TC4's bounded issuance trust; it has no authority over execution, semantic, or intent claims.
  - *TEE* — sole authority for L3 `EXECUTED` upgrades (TC3).
  - *Agent/model* — has **no** authority over any attestation claim about itself; its self-reports are L0 evidence.
  - *Human coders/adjudicator* — sole authority for corpus truth labels; candidate tooling may never certify its own labels.
  - *Reader/reviewer* — inherits exactly the paper-disclosed evidence; accepting an implication without its §6 boundary condition is the classified overclaim.
- **Undefined-authority handling:** if an actor or oracle cannot be located in the authority map above, the case is `UNDEFINED_AUTHORITY` → the case is BLOCKED for coding, recorded with a stable reason code and counted in the denominator; it is never silently treated as a pass, a rejection, or a safe default.

## 8. Falsification and stop rules

- The matrix and gap register are falsifiable: any witness that reproduces its REJECT label confirms a boundary; any that does not is reported as a negative result under RQ2, never repaired.
- If corpus coding maps all claims onto RFC 9334/PROV/B2 categories with no residual cases (no new cases and insights), the SoK contribution is withdrawn per `ACNS-scope` §7 — this threat model then serves only as background context, not a claimed contribution.
- Stop and revise if: a clean control is ever presented as an adversarial result (or vice versa); an oracle imports candidate code; an undefined authority is counted as a safe rejection; or any observed metric is asserted in this design-time document.

## 9. Version and provenance

- Contract `clara.venue2027.acns.threat-model.v1` against validator `THREAT_MODEL_VERSION 1.0.0`; families `revocation_timing, replay, model_agency, purpose_scope, insider_or_observer`; nine-gap register G1–G9.
- Base SHA `f35af111cc04588c8c35705a53b47c4586db137d`; depends `ACNS-scope` (PASS) and `SH-research_ethics` (PASS).
- All empirical outcomes (κ, reproduction rate, coverage) are excluded from this design-time document and route exclusively through `artifacts/venue2027/acns/<run_id>/manifest.json` after freeze.
