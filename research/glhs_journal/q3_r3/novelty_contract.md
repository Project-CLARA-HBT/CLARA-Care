# GLHS R3 Novelty Contract & Claim Budget

**Program:** GLHS R3 — Governed Read-to-Write Continuity  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Author / Curator:** Agent A — Literature & Novelty  
**Status:** Frozen prospective research contract  
**Date:** 2026-09-28  

---

## 1. Executive Summary & Scientific Purpose

The GLHS R3 program marks a decisive transition from broad, unsupportable claims of a generic "co-versioned governance architecture" to a precise, falsifiable, and literature-hardened systems contribution: **Governed Read-to-Write Continuity (GRWC)**.

In health AI and clinical decision support systems, an LLM agent executes an asynchronous, non-deterministic inference pass over a snapshot of patient data. Between the instant data is retrieved for model consumption ($t_1$) and the instant a persistent clinical mutation proposal is submitted for database commit ($t_3$), both the patient's underlying clinical state and their active governance directives (consent, policy, access credentials) can drift ($t_2$).

Prior literature separately addresses database concurrency control (OCC, SSI), purpose access control (Hippocratic Databases, PBAC), capability authorization (PCFS, Macaroons), provenance tracking (Semirings, LPM, W3C PROV, JBI/IJMI health provenance), dynamic consent (Kaye et al.), clinical AI guidelines (FUTURE-AI, SMART), and transactional agent memory (MemTX, MemTxn). 

GLHS R3 does **not** claim novelty for any of these established building blocks. Instead, GLHS R3 identifies and solves the single remaining cross-layer gap: **verifying that a persistent health mutation proposal is admitted if and only if it remains verifiably continuous with the exact governed disclosure actually supplied to the inference lineage that produced it, while current clinical state and dynamic governance are independently revalidated within the commit transaction.**

---

## 2. Definitive Non-Novelty Declarations (Forbidden Novelty Claims)

GLHS R3 explicitly surrenders and forbids claiming novelty for the following mechanisms, data structures, and properties, which are thoroughly established in prior literature:

### 2.1 Optimistic Concurrency Control (OCC)
* **Established by:** Kung & Robinson (ACM TODS 1981), Cahill et al. (SIGMOD 2008), Ports & Grittner (PVLDB 2012), TicToc (SIGMOD 2016).
* **Surrendered Claim:** Staging updates in private workspaces, performing commit-time validation of read/write sets, or detecting stale record overwrites.

### 2.2 Serializable Snapshot Isolation (SSI) & Database TOCTOU Prevention
* **Established by:** Cahill et al. (SIGMOD 2008), Ports & Grittner (PVLDB 2012).
* **Surrendered Claim:** Using relational database transaction isolation, predicate locks, or row/advisory locks in PostgreSQL to prevent write-skew or race conditions inside the storage engine.

### 2.3 Temporal & Bitemporal State Storage
* **Established by:** Snodgrass et al., TOKI (arXiv 2026), mature EHR data warehousing (i2b2, OMOP).
* **Surrendered Claim:** Storing valid-time vs. transaction-time rows, preserving historical versions, or maintaining dual temporal coordinates for audit trails.

### 2.4 Provenance Graphs & Lineage Tracking Alone
* **Established by:** Green et al. (*Provenance Semirings*, PODS 2007), Bates et al. (*LPM*, USENIX Security 2015), W3C PROV (2013), Curcin et al. (JBI 2017), Margheri et al. (IJMI 2020).
* **Surrendered Claim:** Capturing input-to-output derivation graphs, linking recommendations to evidence nodes, or storing execution traces for auditability.

### 2.5 Purpose-Based Access Control (PBAC) & Usage Control
* **Established by:** Agrawal et al. (*Hippocratic Databases*, VLDB 2002), Byun & Li (VLDB Journal 2008), Park & Sandhu (*UCON*, TISSEC 2004).
* **Surrendered Claim:** Annotating queries or tables with purpose tags, restricting data reads by user role/task, or enforcing static usage policies.

### 2.6 Dynamic Patient Consent
* **Established by:** Kaye et al. (EJHG 2015), FUTURE-AI (BMJ 2025), SMART (JAMIA 2026).
* **Surrendered Claim:** Granular patient consent preferences, versioned consent objects, or patient-driven consent revocation workflows.

### 2.7 Proof-Carrying Authorization & Capability Tokens
* **Established by:** Garg et al. (*PCFS*, IEEE S&P 2010), Birgisson et al. (*Macaroons*, NDSS 2014).
* **Surrendered Claim:** Cryptographic authorization tokens carrying context caveats, HMAC capability attenuation, or self-contained access proofs.

### 2.8 Hash Commitments & Canonical Serialization
* **Established by:** Merkle (1979), RFC 8785 (JSON Canonicalization Scheme).
* **Surrendered Claim:** Computing SHA-256 digests over JSON structures or creating tamper-evident cryptographic digests of context buffers.

### 2.9 Persistent LLM Agent Memory & Staged Belief Commits
* **Established by:** LongMemEval (ICLR 2025), MemTX (arXiv 2026), MemTxn (arXiv 2026), Cordon (arXiv 2026).
* **Surrendered Claim:** Transactional staging of LLM beliefs, rollback of failed agent states, source citation checking, or persistent long-term agent memory.

### 2.10 THSS Merely as a Data Structure
* **Surrendered Claim:** Claiming that the Temporal Health State Snapshot (THSS) is a novel data structure. THSS is an implementation mechanism (a concrete data record/projection profile), not an abstract scientific contribution.

---

## 3. The Narrow Novelty Boundary: Governed Read-to-Write Continuity (GRWC)

The single, precise scientific contribution of GLHS R3 is the formalization, operationalization, and empirical evaluation of **Governed Read-to-Write Continuity (GRWC)**, also referred to as **Exact-Disclosure Admission**.

### 3.1 Formal Invariant Definition

Let:
* $H$: Governed Disclosure Object (containing bounded health projections, evidence manifests, policy versions, actor credentials, purpose, task, valid intervals).
* $I$: Server-owned Inference Context Binding proving that the LLM request actually supplied $H$.
* $P$: Persistent Write Proposal generated by the LLM inference lineage.
* $D(P)$: Operation-derived semantic state dependency vector required for $P$.
* $M(H)$: Disclosed evidence manifest included in $H$.
* $S(t)$: Database state at time $t$.
* $G(t)$: Dynamic governance state (policy, consent, actor authorization) at time $t$.
* $t_c$: Point of database write admission transaction execution.

An AI-generated persistent proposal $P$ is admitted at time $t_c$ if and only if:

$$\begin{aligned}
\text{Admit}(P, t_c) \iff \exists H, I: \; & \text{Issued}(H) \\
& \land \text{SuppliedToInference}(I, H) \\
& \land \text{ProposalDescendsFrom}(P, I) \\
& \land \text{ExactDisclosure}(P, I, H) \\
& \land \text{EvidenceCovered}(P, H) \\
& \land \text{DependencyComplete}(P) \\
& \land \text{StateCurrent}(P, S(t_c)) \\
& \land \text{GovernanceCurrent}(P, G(t_c)) \\
& \land \text{DisclosureAdmissibleAtCommit}(H, t_c)
\end{aligned}$$

### 3.2 Strongest Defensible Guarantees

When $\text{Admit}(P, t_c)$ evaluates to $\text{TRUE}$, the system guarantees that:
1. **Server-Attested Consumption:** The proposal $P$ was produced by an inference lineage that received the exact model-visible disclosure projection digest recorded in $I$, as witnessed by the application server before provider dispatch.
2. **Dynamic Revalidation:** All clinical entity versions in $D(P)$, active consent versions, system policies, and actor credentials remain current at commit time $t_c$ under database lock protection.
3. **No Undisclosed Evidence Poisoning:** Every evidence item asserted by $P$ was contained in the model-visible disclosure $H$ actually supplied to inference; global presence in the database does not satisfy admission if omitted from $H$.
4. **Non-Downgradable Lineage:** Human adaptation or post-inference filtering cannot strip the root inference binding $I$ to bypass admission enforcement via a base-only write path.

### 3.3 What GRWC Explicitly Does NOT Claim or Guarantee

GRWC does **NOT** guarantee or prove:
* **Clinical Correctness:** It does not prove the model's diagnostic or therapeutic recommendations are medically sound.
* **Internal LLM Causal Isolation:** It cannot prove that the LLM reasoned *only* from the supplied disclosure without relying on parametric training weights or hallucinatory priors.
* **Database/Application Store Compromise:** It does not protect against a root compromise of the application database server or underlying OS kernel.
* **Arbitrary External Writers:** It governs AI proposal commit paths; non-compliant legacy writers bypassing the commit kernel will bypass checks unless database triggers/views enforce the invariant.

---

## 4. Nearest-Neighbor Literature Comparison Matrix

| Property / Feature | OCC (1981) | SSI (2008) | PBAC (2008) | PCFS / Macaroons (2010/14) | LPM / W3C PROV (2013/15) | Dynamic Consent (2015) | MemTX / MemTxn (2026) | GLHS R3 (GRWC) |
|---|---|---|---|---|---|---|---|---|
| **Optimistic Validation** | Yes | Yes | No | No | No | No | Yes | **Yes** |
| **Relational Serialization** | Yes | Yes | No | No | No | No | Yes | **Yes (PostgreSQL)** |
| **Purpose / Role Access Control** | No | No | Yes | Partial | No | Partial | No | **Yes** |
| **Capability / Caveat Tokens** | No | No | No | Yes | No | No | No | **Comparator (E03)** |
| **Derivation Provenance** | No | No | No | No | Yes | No | Partial | **Yes (Lineage)** |
| **Dynamic Patient Consent** | No | No | No | No | No | Yes | No | **Yes** |
| **Agent Belief Staging** | No | No | No | No | No | No | Yes | **Yes** |
| **Exact Consumed-Disclosure Binding** | No | No | No | No | No | No | No | **YES (Core Novelty)** |
| **Undisclosed Evidence Rejection** | No | No | No | No | No | No | No | **YES (Core Novelty)** |
| **Same-Tx Governance Revalidation** | No | No | Partial | No | No | No | No | **YES (Core Novelty)** |

---

## 5. Strict Claim Budget

To enforce absolute integrity in manuscript writing and presentation, GLHS R3 establishes a binding **Claim Budget**. Every statement in the manuscript, abstract, documentation, and presentations MUST fall within the Allowed Claims and MUST NOT contain any Forbidden Claims.

### 5.1 Allowed Claims (When Supported by Prospective Evidence)
* $\checkmark$ *"Operationalizes an Exact-Disclosure Admission / Governed Read-to-Write Continuity (GRWC) invariant for longitudinal health AI."*
* $\checkmark$ *"Enforces that persistent AI mutations are admitted only when verifiably continuous with the exact governed disclosure supplied to model inference."*
* $\checkmark$ *"Within tested audited routes and frozen database schedules ($N = \dots$), zero improper commits were observed."*
* $\checkmark$ *"Bounded formal model exploration (depth $d = \dots$) verified state-space invariants $I_1-I_{15}$ without counterexamples."*
* $\checkmark$ *"Evaluated against a minimal capability/token baseline (`MIN_READSET_TOKEN`), establishing the trade-offs of compact credentials versus full lineage tracking."*
* $\checkmark$ *"Demonstrated under real PostgreSQL serializable execution under simulated clinical write contention."*

### 5.2 Forbidden Claims (Strict Publication Blockers)
* $\times$ **NO "First" Claims:** Do NOT claim to be the "first provenance-aware health AI", "first transactional AI memory", "first governed agent system", or "first co-versioned medical system".
* $\times$ **NO Absolute Security / Elimination Claims:** Do NOT state that "TOCTOU is eliminated", "race conditions are impossible", "formally proven secure", or "tamper-proof".
* $\times$ **NO Medical Efficacy Claims:** Do NOT claim the system is "clinically safe", "diagnostically accurate", or "regulatory compliant".
* $\times$ **NO Claim of Mechanism Uniqueness:** Do NOT claim that GLHS or THSS is "uniquely necessary" or the "only possible solution".
* $\times$ **NO Provider Equivalence without Ledger:** Do NOT report real Claude/Gemini provider performance based on mock/synthetic responses.
* $\times$ **NO Simulation Presentation as Production:** Do NOT report simulated PostgreSQL thread lock benchmarks as real PostgreSQL performance.
* $\times$ **NO Agent Self-Adjudication as Peer Review:** Do NOT describe internal LLM or multi-agent evaluations as "independent peer review" or "human clinical validation".

---

## 6. Manuscript Rewrite Directives for Phase 10

When updating the manuscript in Phase 10:

1. **Title Alignment:** Adopt the conservative title:
   > **GLHS: Exact Disclosure Binding for Governed Persistent Writes in Longitudinal Health AI**
2. **Abstract:** Focus strictly on the cross-layer problem ($t_1 \to t_2 \to t_3$ drift), the GRWC invariant, the real system realization, and bounded empirical evaluation results.
3. **Related Work Structure:** Organise into 7 distinct subsections matching the 7 neighbor domains in Section 2 & Section 4. Conclude with the explicit Central Gap sentence:
   > *"Prior work separately establishes transactional freshness, purpose-aware authorization, dynamic consent, provenance, proof-carrying access, clinical-AI lifecycle governance, and transactional agent memory. The remaining boundary addressed here is narrower: whether a later persistent mutation can be admitted only when it remains verifiably continuous with the exact governed disclosure actually supplied to the inference that produced its lineage, while current state and governance are revalidated at commit."*
4. **Contribution Hierarchy:**
   * Contribution 1: The GRWC / Exact-Disclosure Admission Invariant.
   * Contribution 2: A concrete longitudinal health implementation using server-owned inference bindings, dependency contracts, and PostgreSQL kernel validation.
   * Contribution 3: Empirical evaluation (component factorials, minimal token comparison, PostgreSQL TOCTOU, bounded TLA+ formal model).

---

## 7. Automated CI & Gate Enforcement

The claim budget and novelty contract are enforced via automated CI linter script `scripts/ops/lint_glhs_claims.py`.

Any pull request or manuscript build containing forbidden claim phrases (e.g., "first provenance-aware", "TOCTOU eliminated", "tamper-proof", "formally proven secure", "clinically safe") will **fail CI build gates immediately**.

```text
[PASS] Phase 0 Literature & Novelty Audit complete.
[PASS] Novelty contract frozen at research/glhs_journal/q3_r3/novelty_contract.md.
[PASS] Literature matrix frozen at research/glhs_journal/q3_r3/literature_matrix.json.
```
