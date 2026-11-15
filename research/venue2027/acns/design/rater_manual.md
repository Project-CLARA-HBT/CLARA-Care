# ACNS · Inter-rater coder manual — evidence-boundary coding for the SoK corpus

> **Task:** `ACNS-X05_rater_manual` · **Phase:** `P02` · **Venue:** `acns` · **Status:** registered coder manual; coding NOT executed
> **Paper:** *SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems*
> **Contract:** `clara.venue2027.acns.rater-manual.v1` · **Manual version:** `1.0.0`
> **Depends honored:** `ACNS-schema` (`acns/protocols/study.schema.json`), `ACNS-X01_review_protocol` (`design/sok_review_protocol.md` §6–§8), `ACNS-threat` (evidence lattice, observer positions, trusted components), `ACNS-scope` (novelty contract §3-RQ3).
> **Feeds:** `ACNS-X06_adjudication`, RQ1/RQ3 agreement statistics, witness-gallery targets (`ACNS-X07`).

**Deliverable path note.** The task manifest declares the target path `research/venue2027/acns/design/annotation_handbook.md`. This worktree delivers that same document at the orchestrator-directed path `research/venue2027/acns/design/rater_manual.md`. The two names denote this one document; downstream tasks cite the delivered path.

## 0. Scope declaration (what this document is and is not)

This document is the **pre-registered coder manual** (inter-rater codebook) for the SoK's evidence-boundary coding of the frozen S6 corpus. It fixes, before any coding run: the coding dimensions **C1–C8**, the evidence-boundary codes **`BND_*`**, the decision tree that derives them, the INDETERMINATE retention rules, stable reason codes, the JSON-serializable coding record, and the inter-rater agreement protocol (pilot, freeze, blind allocation, κ computation, adjudication).

- **No coding run has been executed.** No pilot session, no first-pass stream, and no adjudication session exists as of registration. This manual asserts **no κ value, no agreement rate, and no rater identity**. Every observed value enters later, exclusively via `artifacts/venue2027/acns/<run_id>/manifest.json` after `ACNS-freeze`, per the selection protocol's honest-reporting rules (§10) and the blueprint's metrics contract. The run artifact `rater_manual.json` named in the task's evidence list is emitted only by an executed coding run; it does not exist at registration time and is not simulated here.
- **All examples in this manual are constructed teaching sentences**, authored for calibration. None is a quotation from the corpus or from any published record, and none is evidence about any real system. Anchors define how to code; they are not findings.
- **Method commitment, not a result.** Per the anti-salami gate, this manual creates no success guarantee: if coding fails the pre-registered agreement thresholds, the negative result is reported (selection protocol §7, novelty contract §3-RQ3, falsification rule).

### Purpose

Enable two independent human coders to extract claim sentences from the frozen S6 corpus and code them, field by field, into the C1–C8 dimensions and the `BND_*` boundary codes with sufficient precision that (a) inter-rater Cohen's κ on the pre-adjudication stream is a meaningful measure of the taxonomy's reliability (RQ3), and (b) every boundary verdict is derivable from the coded fields and the verbatim quotation alone.

### Allowed input

A coder, when coding one claim, may consult exactly:

1. the **frozen S6 corpus record** (full text plus publisher metadata from the `ACNS-X02` retrieval ledger, with its recorded retrieval date);
2. **this manual, at its frozen version**;
3. the **threat model's** lattice, observer-position and trusted-component definitions (`acns/threat_model.md` §1.2, §3);
4. the coder's own prior coding records for the same claim during a revision pass of the coder's own work.

A coder must **never** consult, during first-pass coding: another rater's labels or justifications; any model/LLM output, including candidate tooling or automated pre-labels; post hoc categories produced after coding; adjudication feedback before the first-pass stream is sealed; any corpus version other than the frozen S6 set. Violations are falsifying defects (§10), not stylistic issues.

### Failure semantics

- An **undecidable field is a valid coded outcome**, not an error: it is recorded as `AMB` (C8) with the field value `INDETERMINATE`, per IND rules (§5).
- A **true defect** is an entry that cannot be coded as written: it is invalidated with a stable reason code from §6 and re-opened; it is never silently dropped, silently re-coded, or counted as a safe rejection.
- Every blocking condition maps to exactly one stable reason code (§6). Unhandled or ad-hoc failure labels are prohibited.

### Version

`1.0.0` — registered manual, frozen for pilot use. The pilot and freeze discipline is defined in §8.3: the manual may be revised **during development only**; once frozen for main labeling, any change requires a dated, versioned amendment recorded before the affected coding stage runs (selection protocol §10). The manual version is stamped into every coding record (§7).

## 1. Definitions

### 1.1 Evidence classes and lattice levels

The evidence lattice (threat model §1.2) orders what observable evidence can show. Each evidence class has a lattice level and a distinct observer:

| Level | Evidence class | What the observer sees | What it can never show alone |
|---|---|---|---|
| `L0` `ASSUMED` | Assembly | Agent host only (attacker-controlled under A2): intent/plan, composed payload | Anything about transmission or execution |
| `L1` `ASSEMBLED` | Egress | Bytes left the sender's buffer; server-side observers see arrival, not composition | Provider processing; model execution |
| `L1.5` | Transport acknowledgment | Sender-side TCP/TLS stack: bytes sent / transport ACK | Application-level receipt; content received |
| `L2` `ACKNOWLEDGED` | Provider-attested receipt | Verifier via provider signature anchored in pinned roots: signed statement "received bytes with digest D at time T" | Execution, semantics, side effects |
| `L3` `EXECUTED` | Execution trace | Trusted execution environment only: attested tool invocation + inputs | Downstream effects outside the TEE |
| `L4` `COMMITTED` | Semantic consumption | Persisting service's own logs, verifiable only to that service: side effect recorded | That the *model* semantically consumed the result |

Level ordering for coding is `L0 < L1 < L1.5 < L2 < L3 < L4`. `L1.5` (transport acknowledgment) is a distinct evidence class, not a claim-strength upgrade of `L1`.

### 1.2 Observation axis

The observation axis records **who could actually observe** the evidence a claim rests on: the agent host, the transport stack, the provider, the TEE, the persisting service, or the benchmark harness itself (harness-internal). Published papers are observed from outside: a reader sees only what authors disclose, so corpus coding inherits exactly the `L0`/`L1` visibility unless the paper documents stronger evidence (threat model §1.2, closing paragraph). A claim whose only support is harness-internal observation is coded at the harness-internal observer position, never as provider-side or TEE-side evidence.

### 1.3 Trust axis

The trust axis records **which trusted parties a claim presupposes and whether they are named**: e.g., provider signing keys pinned by digest (TC1-style pinned roots), the receipt-verification procedure (TC2), the TEE manufacturer's root of trust (TC3), the log operator, the verifier, the benchmark harness author. A claim that presupposes an unnamed party (e.g., "the provider confirms…" with no key-pinning or verification procedure disclosed) is coded with the trust axis marked unnamed; unnamed presupposed trust caps the demonstrable level per D5.

### 1.4 Claim, boundary, and the coding object

The **coding object** is one extracted claim sentence (C1) from one frozen corpus record, double-coded by two independent human coders. The **evidence boundary** of a claim is the relation between the strongest lattice level the claim asserts and the strongest level its record's actual evidence demonstrates. The boundary codes `BND_*` (§3) label that relation; they must be derivable from the C1 quotation plus the C2–C6 fields (selection protocol §8.2). A boundary code with no supporting quotation is invalid and re-opened (`BOUNDARY_REOPENED`).

## 2. Coding dimensions (C1–C8)

The dimensions are fixed by the selection protocol §6; this manual elaborates each with decision rules and anchors. One coding record carries exactly one value per dimension for one claim.

### C1 — Claim extraction

**Definition.** Short **verbatim** claim sentences (≤ 2 lines each) with a page/section reference. Paraphrase-only entries are invalid (selection protocol §6, C1).

**Decision rules.**

- Quote exactly; preserve the record's own wording, including hedging ("may", "ensures", "guarantees") — hedges are coding signal, not noise.
- Split compound sentences into one coding object per distinct claim; each keeps its own locator.
- Record the locator (page or section) for every quotation.
- Do not merge claims from different sections into one entry; do not code a claim the record does not make.

**Anchors (constructed).**

- **Anchor C1-A1 (valid).** Quotation: "Every tool invocation is acknowledged by a signed provider receipt." Locator: "§4.2, p. 7". Verbatim, ≤ 2 lines, located → valid C1 entry.
- **Anchor C1-A2 (invalid).** Coder writes: "The system has good receipt practices." No verbatim basis in the record → reason code `EXTRACT_NO_VERBATIM`; entry re-opened.
- **Anchor C1-A3 (invalid).** Verbatim quotation present but no page/section → `EXTRACT_NO_LOCATOR`; entry re-opened.

**Common failure.** Coding a paraphrased "gist" as C1. The boundary code depends on the record's exact wording; paraphrase destroys the C3 derivation.

### C2 — Evidence class

**Definition.** Which of the six lattice classes the record's evidence for this claim belongs to: assembly, egress, transport acknowledgment, provider-attested receipt, execution trace, semantic consumption (selection protocol §6, C2).

**Decision rules.**

- Identify **all** evidence classes the record presents in support of the claim; code the class of the **strongest** evidence actually presented as the primary C2 value, and list the others in the record's `evidence_classes_mentioned`.
- A class counts only if the record **documents** it, not merely names it. Naming "TEE attestation" in future work is not execution-trace evidence.
- If no class is documented for the claim, C2 is `INDETERMINATE` with C8 = `AMB`.

**Anchors (constructed).**

- **Anchor C2-A1.** Record shows a verification procedure checking provider signatures against pinned keys and displays a sample receipt with digest binding → C2 = provider-attested receipt.
- **Anchor C2-A2.** Record's "evidence" is the benchmark harness's own success flag printed at the end of an agent run → C2 = assembly with C5 = harness-internal (harness-internal observation is L0/L1 visibility; it is never provider-attested receipt).

### C3 — Lattice level claimed

**Definition.** The strongest lattice level the record **asserts** for this claim, read from the claim's wording alone (selection protocol §6, C3).

**Decision rules.**

- Read only the C1 quotation (plus its immediate sentence for anaphora); do not import charity from elsewhere in the record.
- Map wording to the strongest level the sentence asserts: "we assume/compose" → `L0`; "the request left the agent / was sent" → `L1`; "the connection/transport acknowledged" → `L1.5`; "the provider received/acknowledged (with digest)" → `L2`; "the tool executed/was executed (attested)" → `L3`; "the result was consumed/committed/applied" → `L4`.
- If the sentence asserts no level ("the system is secure"), the claim has no decidable level: C3 = `INDETERMINATE`, C8 = `AMB`.

**Anchors (constructed).**

- **Anchor C3-A1.** Claim: "Because the provider signs every request acknowledgement, our agent's tool calls are verified end-to-end." The sentence asserts verification of the tool call itself → C3 = `L3` (execution), even though the evidence named in the sentence is a receipt.

### C4 — Lattice level demonstrated

**Definition.** The strongest lattice level the record's **actual evidence** supports for this claim (selection protocol §6, C4).

**Decision rules.**

- Derive C4 only from the D3 evidence inventory (C2 class, C5 observer, C6 trust parties), never from the claim's wording.
- Apply the class-to-level ceiling: assembly → `L0`; egress → `L1`; transport acknowledgment → `L1.5`; provider-attested receipt (digest-bound, signature verified against pinned roots) → `L2`; execution trace inside a TEE → `L3`; persisting-service side-effect log → `L4`.
- Apply the trust cap: evidence whose verification presupposes an unnamed party or an unpinned key caps at `L0` per the threat model's TOFU rule (unpinned keys are L0 evidence).
- Harness-internal instrumentation caps at `L1` regardless of what the harness prints.

**Anchors (constructed).**

- **Anchor C4-A1.** Record documents signature verification against pinned provider keys with digest binding → C4 = `L2` for receipt-scope claims.
- **Anchor C4-A2.** Record's receipt samples are shown but no verification procedure or key pinning is disclosed → C4 caps at `L0` (unnamed trust), C6 records the unnamed presupposition, C8 = `AMB`.

### C5 — Observer axis

**Definition.** Who could observe the evidence (selection protocol §6, C5): agent host / transport stack / provider / TEE / persisting service / harness-internal.

**Decision rules.** Code the observer of the **evidence**, not the observer of the claim. If the record does not disclose the observer position, C5 = `INDETERMINATE` with C8 = `AMB` — do not default to the most favorable observer.

**Anchors (constructed).**

- **Anchor C5-A1.** Record states its evaluation harness logs tool-call success flags internally → C5 = harness-internal.
- **Anchor C5-A2.** Record shows provider-side signed acknowledgements → C5 = provider (verifier via signature).

### C6 — Trust axis

**Definition.** Which trusted parties the claim presupposes, and whether they are named (selection protocol §6, C6).

**Decision rules.** List every party whose honesty the claim requires to hold (provider, key-pinner, TEE manufacturer, log operator, harness author, verifier). Mark `all_named = true` only if the record identifies each party and its establishment mechanism (pinning, registration, audit). A claim requiring trust in an unnamed party is coded `all_named = false` and feeds the D5 trust cap.

**Anchors (constructed).**

- **Anchor C6-A1.** Claim: "Receipts are verified against the provider's published signing key." Presupposed parties: provider (named), publisher of the key (named mechanism: publication). `all_named = true`.
- **Anchor C6-A2.** Claim: "The attestation is trustworthy." No verifier, root, or establishment mechanism named → `all_named = false`; trust axis undecidable → C6 contributes `AMB`.

### C7 — Claim type

**Definition.** Existence claim, boundary claim, or performance claim (selection protocol §6, C7). Performance claims are context, never corpus-anchored endpoints.

**Decision rules.**

- **Existence claim:** asserts that an evidence artifact/relationship exists or occurred ("receipts are issued", "traces are attested").
- **Boundary claim:** asserts what the evidence proves or does not prove ("the receipt proves execution").
- **Performance claim:** asserts a measure ("blocks X% of injections"). Code it, but it never anchors a coverage-matrix cell and never serves as a corpus endpoint.

**Anchors (constructed).**

- **Anchor C7-A1.** "Signed receipts are issued for every tool invocation" → existence.
- **Anchor C7-A2.** "A transport ACK is not proof of execution" → boundary claim (and a correct one — a negative boundary claim can be `BND_VALID`).
- **Anchor C7-A3.** "Our pipeline achieves the highest success rate among evaluated agents" → performance; context only.

### C8 — Ambiguity flag

**Definition.** `AMB` when a code is not decidable from the text; the record keeps the ambiguous flag rather than a coerced value (selection protocol §6, C8).

**Decision rules.** Set C8 = `AMB` iff **any** of C2–C7 or the boundary code is `INDETERMINATE` for this claim. The flag and the undecidable field travel together; a bare `AMB` without a named undecidable field is itself a defect (`FIELD_UNDECIDABLE` without a field named). See §5 for the retention rules.

**Anchor (constructed).**

- **Anchor C8-A1.** Claim: "Tool calls are verified end-to-end." Record discloses neither observer position nor trust establishment → C2/C5/C6 undecidable → C8 = `AMB`, affected fields = `INDETERMINATE`, boundary = `BND_INDETERMINATE` (§9, example E3).

## 3. Evidence-boundary codes (`BND_*`)

The four boundary codes are fixed by the selection protocol §8.2. Each is derived from the coded fields; none is assigned by impression. The derivation rules below are the manual's binding elaboration of the protocol's rubric.

### BND_VALID

**Definition.** The claim does not exceed its evidence class under the lattice: the strongest level asserted (C3) is at or below the strongest level demonstrated (C4), and the claim's wording stays inside the matched level's semantics.

**Derivation.** From the decision tree (§4, D7): `C3 ≤ C4` and the claim's verbs/objects do not exceed the matched level's semantics (a receipt-scope sentence must stay at receipt scope; "verified end-to-end" wording exceeds a receipt-level match).

**Anchors (constructed).**

- **Anchor BND_VALID-A1.** Claim: "Requests submitted to the provider are bound to a digest and acknowledged by a provider signature." C3 = `L2`; evidence: documented signature verification against pinned roots with digest binding, C4 = `L2`; wording stays at receipt scope → `BND_VALID`.
- **Anchor BND_VALID-A2 (negative boundary claim).** Claim: "A transport acknowledgment is not evidence that the model executed the tool." The claim asserts a boundary the lattice itself supports → `BND_VALID` (C7 = boundary claim).

**Contrast.** If the same receipt evidence were cited for "the tool executed", the identical evidence yields `BND_OVERREAD` — the boundary code follows the claim, not the evidence alone.

### BND_OVERREAD

**Definition.** The claim exceeds its evidence: C3 > C4, or the wording implies a level above the matched level's semantics. These are the witness-gallery targets (`ACNS-X07`).

**Derivation.** From D7: `C3 > C4`; or `C3 = C4` with wording implying more than the matched level (verb/object test of D7).

**Anchors (constructed).**

- **Anchor BND_OVERREAD-A1 (receipt → execution).** Claim: "Because the provider returned a signed acknowledgment, the agent's tool executed successfully." Evidence: provider-attested receipt only, C4 = `L2`; C3 = `L3` → `BND_OVERREAD`. The receipt proves receipt; execution is outside its class (lattice table §1.1).
- **Anchor BND_OVERREAD-A2 (transport ACK → application receipt).** Claim: "The service confirms every submission, as shown by our TCP-level acknowledgements." C3 = `L2` ("confirms" asserts application-level receipt); C4 = `L1.5` → `BND_OVERREAD`.
- **Anchor BND_OVERREAD-A3 (verifiable-log inclusion → processing).** Claim: "Every prompt is processed correctly, as recorded in our transparency log." Log inclusion shows what was submitted, not what processing occurred; C3 = `L4`, C4 ≤ `L2` → `BND_OVERREAD`.

**Contrast.** Overread is a property of the **published claim**, not of the authors' system: a record may implement sound evidence flows and still publish an overreading sentence; the code attaches to the sentence.

### BND_UNDERREAD

**Definition.** The record's evidence supports more than the claim asserts: C4 > C3. A coverage insight, not a fault (selection protocol §8.2).

**Derivation.** From D7: `C4 > C3` with the claim wording otherwise inside its asserted level's semantics.

**Anchor (constructed).**

- **Anchor BND_UNDERREAD-A1.** Record documents TEE-attested execution traces (C4 = `L3`) but the claim sentence asserts only "the provider acknowledged receiving the request" (C3 = `L2`) → `BND_UNDERREAD`. The mapped cell for coverage gains an `L3` anchor the claim did not use.

**Contrast.** If the underreading sentence *also* mis-scopes its own claim ("acknowledged … therefore attested"), the wording test at D7 applies first and the code is `BND_OVERREAD`; underread is coded only when the sentence is simply weaker than its evidence.

### BND_INDETERMINATE

**Definition.** The boundary is not decidable from the text; the claim is retained, never coerced (selection protocol §8.2).

**Derivation.** From D7/D8: any input needed for the C3-vs-C4 comparison is `INDETERMINATE` after the ambiguity sweep (undecidable claimed level, undecidable evidence class, undecidable observer/trust basis), and adjudication (§8.6) does not resolve it.

**Anchor (constructed).**

- **Anchor BND_INDETERMINATE-A1.** Claim: "Tool calls are verified end-to-end." Record discloses no observer position, no verification procedure, no named trust party; C3 and C4 both undecidable → `BND_INDETERMINATE`, C8 = `AMB` (§9, example E3).

**Contrast.** `BND_INDETERMINATE` is not a third verdict between valid and overread "when in doubt"; it is reserved for claims whose text under-determines the coding inputs. If the text decides C3 and C4, the boundary is decided, whichever way it falls.

## 4. Decision tree

Apply in order; each step consumes only the inputs named. Both coders run this tree independently and blindly (§8.2).

- **D1 — Select the coding object.** One claim sentence from one frozen S6 corpus record; claims are clustered within the publication for analysis but coded one by one.
- **D2 — Extract verbatim (C1).** Quote the sentence ≤ 2 lines with locator. No verbatim basis → `EXTRACT_NO_VERBATIM`; no locator → `EXTRACT_NO_LOCATOR`; either invalidates the entry and re-opens extraction. Split compound claims and continue one branch per claim.
- **D3 — Inventory the evidence.** From the record only: list every documented evidence artifact supporting this claim → C2 class(es) (strongest primary), C5 observer position, C6 presupposed parties and whether named.
- **D4 — Assign the claimed level (C3).** From the C1 wording alone, map to the strongest level the sentence asserts (§2, C3 mapping). Undecidable wording → `INDETERMINATE`.
- **D5 — Assign the demonstrated level (C4).** From D3 only: apply the class-to-level ceiling, then the trust cap (unnamed/unpinned presupposed trust caps at `L0`; harness-internal caps at `L1`). Undecidable → `INDETERMINATE`.
- **D6 — Assign the claim type (C7).** Existence / boundary / performance. Performance claims are coded and flagged context-only.
- **D7 — Derive the boundary code.**
  1. If C3, C4, or a needed C2/C5/C6 input is `INDETERMINATE` → boundary = `BND_INDETERMINATE`.
  2. Else if C3 > C4 → `BND_OVERREAD`.
  3. Else if C4 > C3 → `BND_UNDERREAD`.
  4. Else (`C3 = C4`) apply the wording test: if the sentence's verbs/objects imply a level above the matched level's semantics → `BND_OVERREAD`; otherwise → `BND_VALID`.
- **D8 — Ambiguity sweep (C8).** For every coded field ask: is this decidable from the record's text alone? Any no → that field = `INDETERMINATE` and C8 = `AMB`. A coercion-free record may carry several `INDETERMINATE` fields.
- **D9 — Write and seal the record.** Emit the coding record (§7) into the coder's first-pass stream. First-pass streams are sealed before any adjudication (§8.4).

Every boundary code must trace to its C1 quotation; a boundary code whose quotation cannot be produced is invalid and re-opened (`BOUNDARY_REOPENED`).

## 5. INDETERMINATE rules

- **IND1 — When.** A field takes `INDETERMINATE` exactly when the record's text does not decide it under §2's decision rules — including silence, ambiguous wording, and evidence asserted but not documented. Doubt created by *coder fatigue or missing effort* is not indeterminacy; re-read the record first.
- **IND2 — Retention.** A claim that cannot be classified with agreement after adjudication is retained as `INDETERMINATE`/`AMB` and reported in the ambiguous-claim fraction (selection protocol §7). `INDETERMINATE` entries stay in the corpus ledger; nothing is dropped.
- **IND3 — No coercion.** Coercing an unresolvable code to a definite value to raise κ is prohibited and is a falsifying defect (selection protocol §7; `rq_and_estimands.yaml` RQ3 confounders). This applies to adjudicators too: an adjudicator who cannot resolve a conflict leaves the field `INDETERMINATE` with a ledger entry, and does not vote it into a definite value.
- **IND4 — Flag coupling.** C8 = `AMB` iff at least one field is `INDETERMINATE`; the record names which fields.
- **IND5 — Escalation.** A field a coder cannot decide alone is coded `INDETERMINATE` in the first pass; it is not pre-discussed with the other coder (blind allocation, §8.2). Adjudication may resolve it or confirm it as retained ambiguity (§8.6).
- **IND6 — Boundary coupling.** A claim with an `INDETERMINATE` input to D7 takes `BND_INDETERMINATE` even if all *other* fields are definite.
- **IND7 — Reporting.** The retained-ambiguous fraction after adjudication is a reported secondary metric (RQ3); it is computed from the sealed streams, never hand-set.

## 6. Stable reason codes

| Reason code | Condition | Effect |
|---|---|---|
| `EXTRACT_NO_VERBATIM` | Entry is paraphrase-only or the quotation cannot be located in the record | Entry invalid; re-open extraction (D2) |
| `EXTRACT_NO_LOCATOR` | Verbatim quotation lacks page/section reference | Entry invalid; re-open extraction (D2) |
| `FIELD_UNDECIDABLE` | A C2–C7 or boundary input not decidable from text | Field = `INDETERMINATE`; C8 = `AMB` (not an error) |
| `BOUNDARY_REOPENED` | Boundary code lacks a supporting quotation | Code invalid; re-code from D2 |
| `CONFLICT_ADJUDICATION_REQUIRED` | Post-first-pass disagreement on C2–C7 or boundary code | Route to third-coder adjudication (§8.6) |
| `ADJ_UNAVAILABLE` | No third coder available within the adjudication window | Record retained with flag; counted in the ambiguous fraction; never silently dropped or silently included |
| `MANUAL_AMENDMENT_POST_FREEZE` | Attempted post-freeze manual change without a dated, versioned amendment | Change rejected; re-register amendment first (§8.3, protocol §10) |

Reason codes are recorded in the coding record's `reason_codes` list; they are never stripped from exported ledgers.

## 7. Coding record (JSON-serializable)

One record per (claim, coder, pass). All fields are JSON-serializable; the record schema is `clara.venue2027.acns.coding-record.v1` and is stamped with the frozen manual version. Template (placeholder values in angle brackets are field descriptions, not data):

```json
{
  "record_schema": "clara.venue2027.acns.coding-record.v1",
  "manual_version": "1.0.0",
  "corpus_record_id": "<S6 corpus record id from the ACNS-X02 retrieval ledger>",
  "claim_id": "<corpus_record_id>::q<nnn>",
  "coder_role": "C1",
  "pass": "first",
  "c1_quotation": "<verbatim quotation, at most 2 lines>",
  "c1_locator": "<page/section reference>",
  "c2_evidence_class": "<assembly|egress|transport_acknowledgment|provider_attested_receipt|execution_trace|semantic_consumption|INDETERMINATE>",
  "c3_level_claimed": "<L0|L1|L1.5|L2|L3|L4|INDETERMINATE>",
  "c4_level_demonstrated": "<L0|L1|L1.5|L2|L3|L4|INDETERMINATE>",
  "c5_observer_axis": "<agent_host|transport_stack|provider|tee|persisting_service|harness_internal|INDETERMINATE>",
  "c6_trust_axis": {
    "presupposed_parties": ["<party descriptions or empty>"],
    "all_named": false,
    "undecidable": false
  },
  "c7_claim_type": "<existence|boundary|performance|INDETERMINATE>",
  "c8_ambiguity_flag": "<NONE|AMB>",
  "boundary_code": "<BND_VALID|BND_OVERREAD|BND_UNDERREAD|BND_INDETERMINATE>",
  "evidence_classes_mentioned": [],
  "reason_codes": [],
  "justification": "<one-line coder justification, no PII>"
}
```

Records carry no patient identifiers, no credentials, and no free-text beyond the quotation, locator and justification (no-PII telemetry rule). `coder_role` is the pseudonymous role (§8.1), never a person's name.

## 8. Inter-rater agreement protocol

### 8.1 Rater roles and independence

- Exactly **two independent human coders** code the corpus, under the pseudonymous roles **C1** and **C2**. A **third independent human** acts as adjudicator when conflicts arise.
- Rater identities are recorded only in the sealed adjudication ledger (`ACNS-X06`); analysis outputs, coding records and this manual carry roles only.
- **No internal LLM agent is represented as an independent reviewer** (blueprint oracle; novelty contract §3-RQ1/RQ3). Model output may never pre-label, seed, or suggest codes.

### 8.2 Blind allocation

- Both coders code the **entire** frozen claim set; there is no split-sample shortcut.
- Coders work from separated working copies and never see each other's labels, justifications, model predictions, candidate tooling outputs, or post hoc categories during first-pass coding (selection protocol §8.2 negative control: "Rater sees model predictions/other rater labels, post hoc categories" is the forbidden condition this protocol exists to prevent).
- Coding order is randomized at publication level under the pre-registered seed fixed in `rq_and_estimands.yaml` (RQ3 confounders); the seed and procedure are recorded in the run manifest at execution time.
- Adjudication feedback never reaches a coder before that coder's first-pass stream is sealed.

### 8.3 Pilot and freeze

- **Pilot:** the two coders independently pilot the manual on **20 sources** drawn from the frozen corpus set.
- **Development only:** the pilot's disagreements are used to revise this manual **during development only**; every revision bumps the manual version and is logged.
- **Freeze:** once the pilot's residual disagreements are calibration notes rather than manual defects, the manual is **frozen before main labels** (task pass gate: "Versioned codebook and blind allocation"). Post-freeze changes require a dated, versioned amendment recorded before the affected stage runs; post-hoc criteria changes are forbidden (selection protocol §10).
- The pilot produces no reportable agreement statistic; pilot data never enters the main κ stream.

### 8.4 First pass and sealing

Each coder independently codes every claim (decision tree §4) into a first-pass stream of coding records. When both streams are complete they are **sealed**: the sealed pre-adjudication streams are the input to the agreement statistics (§8.5) and are never edited afterwards. Any post-seal correction is a new, dated record, not an edit.

### 8.5 Agreement statistics rules

- **Primary (RQ3):** inter-rater Cohen's κ on claim classification, computed on the **pre-adjudication first-pass stream** from raw coder records (nominal, two raters; cluster bootstrap over claims; the exact estimator, CI method and multiplicity budget are fixed in `rq_and_estimands.yaml` RQ3 and are not restated or re-derived here).
- **Reported alongside:** pre-adjudication raw agreement, disagreement resolution rate, and the retained-ambiguous fraction; adjudicated labels are reported separately from the primary κ estimate (selection protocol §7).
- **Per-field κ** (C2, C3, C4, boundary code) is descriptive, not gated.
- **No numeric threshold or observed value appears in this manual.** The pre-registered absolute reliability floor and the margin against the B3-style generic-coding comparator are fixed in `rq_and_estimands.yaml` (RQ3) and `ACNS-rq_registry`/`ACNS-freeze`; this manual delegates to them verbatim. Every observed statistic enters exclusively via `artifacts/venue2027/acns/<run_id>/manifest.json` after `ACNS-freeze`. Fabricating, previewing, or hand-copying any such value into documents or ledgers is a falsifying defect (§10).
- If the corpus yields fewer double-coded claims than the registered planning floor, the shortfall is disclosed and the comparison is downgraded to estimation — the disclosure duty, not the number, belongs to this manual.

### 8.6 Conflict adjudication

- **Screening conflicts** (if any screening-stage coding is performed downstream): any disagreement advances the record (conservative inclusion) and increments `SCREEN_CONFLICT`; advancing on conflict is never treated as agreement.
- **Coding conflicts (C2–C7, boundary code):** per-field disagreement → third-coder adjudication within **14 days**; the adjudicator is neither C1 nor C2 for that record and receives both justifications blind-coded, without the other rater's final label where separation is feasible.
- If no third coder is available in the window, the record is retained with flag `ADJ_UNAVAILABLE` and counted in the ambiguous fraction — never silently dropped or silently included.
- Every conflict, its resolution, date and adjudicator identity are published in the append-only adjudication ledger (`ACNS-X06`), sealed before analysis; the post-adjudication label is final and the boundary code re-derived under D7 if any input field changed.

### 8.7 What would falsify the agreement protocol

- A coder seeing the other's labels, model predictions, or post hoc categories before sealing.
- κ computed on adjudicated labels and presented as the pre-adjudication primary estimate.
- Coerced `INDETERMINATE` labels, or an ambiguous fraction that shrank without adjudication records explaining it.
- A holdout opened before the manual freeze, or any output selectively dropped.
- Any agreement statistic appearing anywhere before its run manifest exists.

## 9. Ambiguous worked examples

All constructed; each ends in retention, not coercion.

- **E1 (partial disclosure).** Claim: "Our receipts are cryptographically verifiable." The record shows a receipt sample and mentions signatures, but discloses no verification procedure and no key establishment. C2 = provider-attested receipt (a receipt exists); C4 undecidable without the verification procedure → C8 = `AMB`, C4 = `INDETERMINATE`, boundary = `BND_INDETERMINATE` (D7 rule 1). Retained; adjudication may resolve it or confirm retention.
- **E2 (hedge decides).** Claim: "Tool calls may optionally be attested by the deployment's TEE." The record's system has no TEE; the sentence describes a deployment option. C3 is not decidable as an assertion about the evaluated system → C3 = `INDETERMINATE`, C8 = `AMB`, boundary = `BND_INDETERMINATE`. Coding it `BND_VALID` or `BND_OVERREAD` would coerce a modal claim into a definite one.
- **E3 (under-disclosed harness).** Claim: "The agent's actions are fully auditable." The record's only evidence is the harness's internal log of tool-call flags. C5 = harness-internal (cap `L1`); "fully auditable" asserts audit semantics the harness log cannot show; C3 = `INDETERMINATE` (no decidable level) and the boundary is not decidable from the text → `BND_INDETERMINATE`, C8 = `AMB`. If adjudication instead fixes C3 = `L4` ("fully auditable" as semantic-consumption claim), the boundary re-derives to `BND_OVERREAD` under D7 rule 2 — the change is made by adjudication with a ledger entry, never by the coder re-writing the first pass.

## 10. Falsifying defects (negative control register)

Each item below is the failure mode this manual is designed to make detectable; any occurrence is reported as a defect, not smoothed over:

1. A rater sees model predictions, the other rater's labels, or post hoc categories (the task's negative control).
2. An `INDETERMINATE` code coerced to a definite value, by coder or adjudicator, for any reason including raising κ.
3. An agreement statistic asserted without an executed run manifest (`artifacts/venue2027/acns/<run_id>/manifest.json`).
4. A boundary code without a supporting quotation surviving a complete independently labeled schedule.
5. A manual revision after freeze without a dated, versioned amendment.
6. An adjudication ledger edited after sealing, or an `ADJ_UNAVAILABLE` record silently dropped or silently included.

## 11. Execution status and honest reporting

**No coding run, pilot session, or adjudication session has been executed** as of this manual's registration (base commit `e2f63ccb…`, 2026-11-15 task wave). All structures above are the registered instrument. The executed pilot and main coding must replace this status with real session records, sealed streams, and the run manifest before any agreement claim exists; until then, no κ value, agreement rate, ambiguous fraction, or rater identity may be asserted anywhere in the ACNS study documents. Any failure to meet the registered thresholds downstream is reported as a negative result per the blueprint falsification rule; this manual creates no success guarantee.
