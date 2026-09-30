# GLHS R4 Novelty Contract & Claim Budget

**Program:** GLHS R4 — Governed Read-to-Write Continuity / Exact-Disclosure Admission  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Author / Curator:** Agent A — Literature & Novelty  
**Status:** Frozen prospective research contract  
**Date:** 2026-09-30  

---

## 1. Executive Summary & Scientific Purpose

The GLHS R4 program establishes a precise, literature-hardened systems contribution: **Governed Read-to-Write Continuity (GRWC)**, also formulated as **Exact-Disclosure Admission**.

In longitudinal health AI and clinical decision support systems, an LLM agent executes an asynchronous, non-deterministic inference pass over a snapshot of patient health records. Between the instant clinical data and governance directives are retrieved for model consumption ($t_1$) and the instant a persistent clinical mutation proposal is submitted for database commit ($t_3$), both the patient's underlying clinical state and their active governance directives (dynamic consent, policy, actor credentials) can drift ($t_2$).

Prior literature separately establishes database concurrency control (OCC, MVCC, SSI), purpose-aware access control (Hippocratic Databases, PBAC, UCON), capability authorization (PCFS, Macaroons), systems and healthcare provenance (Semirings, LPM, W3C PROV, JBI/IJMI provenance), dynamic patient consent (Kaye et al.), clinical AI lifecycle guidelines (FUTURE-AI, SMART), transactional agent memory (MemTX, MemTxn, Cordon, CommitGuard, MasuGate, TOKI), and commitment-bound inference traces / request receipts (CommitLLM, IETF/W3C drafts).

GLHS R4 does **not** claim novelty for any of these established building blocks. Instead, GLHS R4 identifies and solves the single remaining cross-layer systems gap: **verifying that a persistent health mutation proposal is admitted to the clinical database if and only if it remains verifiably continuous with the exact governed disclosure actually supplied to the inference lineage that produced it, while current clinical state and dynamic governance are independently revalidated within the commit transaction.**

---

## 2. Definitive Non-Novelty Declarations (Surrendered Primitives)

To establish unimpeachable scientific integrity, GLHS R4 explicitly disclaims novelty for all individual foundation technologies across the database, security, and AI memory literature. We categorize and surrender each of the 29 constituent mechanisms individually:

### 2.1 Concurrency Control Primitives
1. **Optimistic Concurrency Control (OCC):** Established by Kung & Robinson (*ACM TODS* 1981), Bernstein & Goodman (1981). Staging mutations in private buffers and validating read/write sets at commit time is 45-year-old prior art.
2. **Multi-Version Concurrency Control (MVCC):** Established by Reed (1978), Bernstein & Goodman (1981). Storing multiple physical tuple versions with transaction timestamps is standard database technology.
3. **Serializable Snapshot Isolation (SSI):** Established by Cahill et al. (*ACM SIGMOD* 2008), Ports & Grittner (*PVLDB* 2012). Dynamic tracking of $rw$-antidependencies in PostgreSQL shared memory is prior art.
4. **Database Predicate Locking & SIREAD:** Established by Eswaran et al. (*CACM* 1976), Ports & Grittner (*PVLDB* 2012). Gating phantoms via predicate locks or lock tags is an established database feature.
5. **Row-Level Explicit Locking (`SELECT FOR UPDATE`):** Established by Date (2000), standard SQL. Locking specific rows for update during transactions is standard SQL engineering.
6. **Total-Order Advisory Lock Hierarchies:** Established by Gray & Reuter (1993, *Transaction Processing*). Defining a multi-class total order ($\text{Class 1} \prec \dots \prec \text{Class 7}$) to guarantee acyclic wait-for graphs and deadlock-free execution is textbook two-phase locking.

### 2.2 Relational & Temporal Data Storage
7. **Relational ACID Transactions:** Established by Gray (1981), Bernstein et al. (1987). Multi-table transactional consistency is foundational.
8. **Version Counters & Resource ETags:** Established by RFC 7232, HL7 FHIR R5 ETag specifications (2024). Monotonically increasing version integers on database rows are standard.
9. **Bitemporal Clinical Storage:** Established by Snodgrass et al. (1999), TOKI (arXiv 2026), OMOP/i2b2 architectures. Storing valid clinical time alongside transaction/knowledge time is standard clinical warehouse practice.
10. **Historical State Snapshot Tables:** Established by Snodgrass (1999), standard audit table architectures. Materializing point-in-time state tables is established prior art.

### 2.3 Access, Purpose & Consent Governance
11. **Purpose-Based Access Control (PBAC):** Established by Byun & Li (*VLDB Journal* 2008), Agrawal et al. (*Hippocratic Databases*, *VLDB* 2002). Gating read access by clinical task and declared purpose is prior art.
12. **Usage Control (UCON) Continuous Revalidation:** Established by Park & Sandhu (*ACM TISSEC* 2004). Continuously monitoring subject and environmental conditions is prior art.
13. **Dynamic Patient Consent Preferences:** Established by Kaye et al. (*EJHG* 2015), FUTURE-AI (*BMJ* 2025). Granular, patient-driven revocable consent models are established health informatics guidelines.
14. **Patient Consent Revocation Workflows:** Established by SMART on FHIR (2026), international health data regulations. Aborting data processing upon consent revocation is standard practice.

### 2.4 Provenance & Derivation Lineage
15. **Retrospective Provenance Derivation Graphs:** Established by Moreau et al. (*W3C PROV*, 2013). Graph models of activities, entities, and agents (`wasDerivedFrom`) are standard descriptive models.
16. **Provenance Semirings:** Established by Green et al. (*ACM PODS* 2007). Algebraic structures tracking computational derivation polynomials are established database theory.
17. **OS Kernel Audit Lineage (LPM):** Established by Bates et al. (*USENIX Security* 2015), CamFlow (2017). Reference monitors capturing provenance in OS kernels are prior art.
18. **Healthcare Provenance Resource Mapping:** Established by HL7 FHIR `Provenance` and `AuditEvent` resource profiles (2024), Curcin et al. (*JBI* 2017). Storing clinical author, target, and evidence links is standard medical informatics.

### 2.5 Cryptography, Tokens & Serialization
19. **Proof-Carrying Authorization (PCFS):** Established by Garg et al. (*IEEE S&P* 2010). Accompanying storage requests with constructive proofs of authorization is established systems security.
20. **Contextual Capability Tokens (Macaroons):** Established by Birgisson et al. (*NDSS* 2014). Cryptographic bearer tokens with chained contextual caveats and HMAC attenuation are prior art.
21. **Signed Read-Set Tokens / Precondition Tokens:** Established by DynamoDB conditional check writes, RFC 7232 If-Match tokens. Carrying read version digests in a client token to validate at write time is standard practice.
22. **Cryptographic Hashes & Merkle Digest Trees:** Established by Merkle (1979). Cryptographic SHA-256 hashing of message structures is foundational.
23. **JSON Canonicalization Scheme (JCS):** Established by RFC 8785 (IETF 2020). Deterministic byte-level serialization of JSON payloads is an established standard.
24. **Append-Only Immutable Ledgers & Nonces:** Established by standard systems security audit logging and cryptographic blockchains. Appending transition records with unique request nonces is prior art.

### 2.6 Agent Memory & Neural Systems
25. **Persistent LLM Conversational Memory:** Established by Wu et al. (*LongMemEval*, *ICLR* 2025), Li et al. (*HealthClaw*, arXiv 2026). Storing multi-turn dialogue facts across patient sessions is prior art.
26. **Transactional Agent Memory & Staged Belief Commits:** Established by Li et al. (*MemTX*, arXiv 2026), Cui et al. (*MemTxn*, arXiv 2026), *Cordon* (arXiv 2026), *CommitGuard* (arXiv 2026), Peng & Wu (*MasuGate*, arXiv 2026). Staging agent beliefs in private buffers and gating tool calls is established agent systems literature.
27. **Global Knowledge Base Source Citation Checking:** Established by Cui et al. (*MemTxn*, 2026), BioRAG (2025). Checking whether model claims cite valid records in a global database is prior art.
28. **THSS as a Standalone Data Structure:** Surrendered as an implementation projection envelope, not an abstract data structure innovation.
29. **Schema-Derived Dependency Vectors $D(P)$ Alone:** Compiling required table/column access sets from database schemas is standard query compilation.

---

## 3. Contrast with Recent 2026 Preprints & Internet-Drafts

Recent concurrent literature (mid-to-late 2026) has advanced agent transactions, trace commitments, and request receipts. GLHS R4 clearly demarcates its contribution against these nearest neighbors:

### 3.1 MemTX (2026) & MemTxn (2026): Agent Beliefs vs. Governed Continuity
* **MemTX (Li et al., arXiv 2026):** Introduces transactional belief commit for stateful agent memory, staging updates in private workspaces and gating irreversible tool calls.
  - *Distinction:* MemTX focuses on generic belief consistency and tool gating within an agent runtime. It lacks healthcare consent governance, clinical entity bitemporality, and exact disclosure projection gating at the database commit boundary.
* **MemTxn (Cui et al., arXiv 2026):** Proposes a transaction boundary for source-supported memory updates, requiring that proposed facts cite supporting sources in the underlying store.
  - *Critical Distinction:* **Global Source Support vs. Exact-Disclosure Projection ($H_{\text{proj}}$)**. MemTxn evaluates whether an assertion is supported by *ANY* valid record existing in the knowledge base/database. In contrast, GLHS R4 enforces that every asserted evidence item was contained in the **EXACT model-visible governed disclosure projection ($H_{\text{proj}}$)** supplied to the specific inference request that produced the proposal, while current state and mutable governance are revalidated at commit. If an evidence record exists globally in the database but was masked, redacted, or omitted from the inference prompt due to consent or policy filtering, a proposal asserting that evidence is strictly **REJECTED** under GRWC.

### 3.2 CommitLLM (2026): Commitment-Bound Traces vs. Live Write-Admission
* **CommitLLM (arXiv 2026):** Binds LLM prompt inputs to execution traces using cryptographic hash trees to ensure reproducibility and post-hoc auditability of agent reasoning steps.
  - *Distinction:* CommitLLM generates passive, post-hoc verifiable audit traces. It does not provide an atomic database write-admission kernel that prevents stale overwrites, validates cross-layer dependency freshness against concurrent writers, or evaluates dynamic patient consent at the moment of persistence.

### 3.3 IETF & W3C Internet-Drafts (2026): Dispatch Receipts vs. Commit Kernel
* **IETF Draft (`draft-ietf-oauth-llm-dispatch-receipts-01`, 2026):** Standardizes signed request-hash receipts issued by LLM providers attesting that payload hash $H$ was received.
* **W3C Community Group Report (2026):** Proposes cryptographic inference-chain attestation for linking multi-step agent context hashes.
  - *Distinction:* These drafts address protocol-level transport attestation (attesting that a model provider or downstream consumer handled payload $H$). GLHS R4 addresses the database commit admission boundary: connecting that server-attested dispatch receipt to a relational transaction engine that revalidates clinical state drift and patient consent revocation before durable writes are admitted.

---

## 4. The Narrow Novelty Boundary: Governed Read-to-Write Continuity (GRWC)

The primary and singular scientific contribution of GLHS R4 is the formalization, operationalization, and empirical evaluation of **Governed Read-to-Write Continuity (GRWC)** (Exact-Disclosure Admission).

### 4.1 Formal Invariant Definition

Let:
* $H$: Governed Disclosure Object, comprising:
  - $H_{\text{proj}}$: The exact model-visible projection (clinical text, attributes, evidence items) presented to the LLM.
  - $M(H)$: Disclosed evidence manifest included in $H$.
  - $\text{pol}(H)$: Active governance policy versions at disclosure time.
  - $\text{act}(H)$: Authenticated actor credentials, role, purpose, and task.
  - $\text{valid}(H)$: Bitemporal validity interval.
* $I$: Server-owned Inference Context Binding proving that the LLM request actually supplied $H_{\text{proj}}$ (e.g., via server-attested dispatch receipt or provider attestation).
* $P$: Persistent Write Proposal generated by the LLM inference lineage.
* $D(P)$: Operation-derived semantic state dependency vector required for $P$.
* $E(P)$: Set of clinical evidence items asserted or referenced by proposal $P$.
* $S(t)$: Database clinical state at time $t$.
* $G(t)$: Dynamic governance state (patient consent, role policies, access rules) at time $t$.
* $t_c$: Timestamp of database write admission transaction execution.

An AI-generated persistent proposal $P$ is admitted at time $t_c$ if and only if:

$$\begin{aligned}
\text{Admit}(P, t_c) \iff \exists H, I: \; & \text{Issued}(H) \\
& \land \text{SuppliedToInference}(I, H) \\
& \land \text{ProposalDescendsFrom}(P, I) \\
& \land \text{ExactDisclosure}(P, I, H) \\
& \land \text{EvidenceCovered}(E(P), M(H)) \\
& \land \text{DependencyComplete}(D(P)) \\
& \land \text{StateCurrent}(D(P), S(t_c)) \\
& \land \text{GovernanceCurrent}(P, G(t_c)) \\
& \land \text{DisclosureAdmissibleAtCommit}(H, t_c)
\end{aligned}$$

Where:
1. $\text{ExactDisclosure}(P, I, H) \iff \text{hash}(H_{\text{proj}}) = I.\text{disclosure\_digest}$
2. $\text{EvidenceCovered}(E(P), M(H)) \iff \forall e \in E(P): e \in M(H)$
3. $\text{StateCurrent}(D(P), S(t_c)) \iff \forall d \in D(P): S(t_c)[d.\text{id}].\text{version} = d.\text{read\_version}$
4. $\text{GovernanceCurrent}(P, G(t_c)) \iff G(t_c).\text{consent\_active}(P.\text{patient}) \land G(t_c).\text{policy\_valid}(P.\text{task}, P.\text{actor})$

### 4.2 The Critical Distinction: Exact Consumed Disclosure vs. Global Source Support

In a **source-supported** system (e.g., MemTxn):
$$\text{SourceSupported}(P, S) \iff \forall e \in E(P): e \in S$$
Even if evidence item $e$ was never visible to the model (e.g., redacted because patient consent was temporarily restricted at read time), the update would be accepted because $e$ exists somewhere in the database.

In **GLHS R4 Exact-Disclosure Admission (GRWC)**:
$$\text{GRWC}(P, H, S(t_c)) \iff \forall e \in E(P): (e \in H_{\text{proj}} \land e \in S(t_c).\text{current})$$
The update is admitted **only** if $e$ was part of the exact model-visible disclosure projection $H_{\text{proj}}$ provided to that inference run AND remains fresh at commit time. This prevents **undisclosed evidence poisoning**, prompt injection masquerading as unread EHR data, and stale evidence resurrection.

### 4.3 Explicit Out-of-Scope Boundary: Neural Model Internal Consumption

**Crucial Systems Scope Boundary:**  
Semantic consumption by the neural model is explicitly **OUT OF SCOPE**.

GLHS R4 does **NOT** prove or attempt to prove:
* That the neural model causal attention heads attended to the disclosed tokens.
* That the LLM reasoned solely from the supplied context rather than parametric training priors.
* That the neural network did not hallucinate clinical facts while executing.

Instead, GLHS R4 proves **server-attested disclosure supply and dispatch continuity**:
* The application server verifies and attests that the exact governed disclosure projection $H_{\text{proj}}$ was dispatched to the inference interface.
* The application server verifies that proposal $P$ carries cryptographic proof of descent from that specific dispatch binding $I$.
* The database kernel revalidates that the state and governance underlying $H_{\text{proj}}$ remain unviolated at commit time $t_c$.

### 4.4 Strongest Defensible Guarantees

When $\text{Admit}(P, t_c) = \text{TRUE}$, the system guarantees:
1. **Server-Attested Disclosure Continuity:** Proposal $P$ was produced by an inference lineage dispatched with the exact projection digest recorded in $I$, witnessed before external model provider dispatch.
2. **Dynamic Governance Revalidation:** Patient consent, policy version, and actor authorization remain active and unrevoked at commit time $t_c$ under relational database lock protection.
3. **No Undisclosed Evidence Poisoning:** Every evidence element asserted by $P$ was contained in $H_{\text{proj}}$; global presence in the database does not satisfy admission if omitted from the prompt envelope.
4. **Non-Downgradable Lineage:** Human adaptation or post-inference routing cannot strip the root inference binding $I$ to bypass admission enforcement via a base-only write path.

### 4.5 What GRWC Explicitly Does NOT Claim or Guarantee

GRWC does **NOT** guarantee or prove:
* **Clinical Correctness:** It does not prove the model's diagnostic or therapeutic recommendations are medically sound or efficacious.
* **Internal LLM Causal Isolation:** It cannot prove that the LLM reasoned *only* from the supplied disclosure without relying on parametric training weights or hallucinatory priors.
* **Database / OS Kernel Compromise:** It does not protect against a root compromise of the PostgreSQL database server or operating system kernel.
* **Arbitrary External Writers:** It governs AI proposal commit paths; non-compliant legacy writers directly executing raw SQL bypassing the commit kernel will bypass checks unless database triggers/views enforce the invariant.

---

## 5. Nearest-Neighbor Literature Comparison Matrix

| Mechanism / Property | OCC (1981) | SSI (2008) | PBAC (2008) | Macaroons (2014) | W3C PROV (2013) | Dynamic Consent (2015) | MemTX (2026) | MemTxn (2026) | CommitLLM (2026) | GLHS R4 (GRWC) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Optimistic Validation** | Yes | Yes | No | No | No | No | Yes | Yes | No | **Yes** |
| **Relational Serialization** | Yes | Yes | No | No | No | No | Yes | Yes | No | **Yes (PostgreSQL)** |
| **Purpose / Role Access Control** | No | No | Yes | Partial | No | Partial | No | No | No | **Yes** |
| **Capability / Caveat Tokens** | No | No | No | Yes | No | No | No | No | No | **Baseline (MIN_TOKEN)** |
| **Derivation Provenance** | No | No | No | No | Yes | No | Partial | Yes | Yes | **Yes (Lineage)** |
| **Dynamic Patient Consent** | No | No | No | No | No | Yes | No | No | No | **Yes** |
| **Agent Belief Staging** | No | No | No | No | No | No | Yes | Yes | No | **Yes** |
| **Global Source Support** | No | No | No | No | No | No | No | **YES** | No | **No (Superseded by Exact)** |
| **Inference Trace Commitment** | No | No | No | No | No | No | No | No | **YES** | **Yes (Server-Attested)** |
| **Exact-Disclosure Projection ($H_{\text{proj}}$)** | No | No | No | **YES (C3)** | No | No | No | **NO** | No | **YES (Core Novelty)** |
| **Undisclosed Evidence Rejection** | No | No | No | **YES (C3)** | No | No | No | **NO** | No | **YES (Core Novelty)** |
| **Same-Tx Governance Revalidation** | No | No | Partial | **YES (C3)** | No | No | No | No | No | **YES (Core Novelty)** |

---

## 6. The Novelty Outcome Rule & Comparator Baseline Fair Evaluation (C3 vs. C4)

To prevent circular reasoning or claiming artificial mechanism superiority over compact capability tokens, GLHS R4 prospectively codifies the **Novelty Outcome Rule**:

### 6.1 Formal Definition of C3 (`SIGNED_EXACT_DISCLOSURE_TOKEN`)
Comparator **C3** represents an un-handicapped, state-of-the-art capability token modeled on Macaroons (*Birgisson et al., NDSS 2014*) and Proof-Carrying File Systems (*Garg et al., IEEE S&P 2010*):
- C3 carries an authenticated HMAC signature over $\langle H_{\text{proj}}, \text{purpose}, \text{task}, \text{actor}, R_{\text{readset}}, t_{\text{expires}} \rangle$.
- C3 incorporates explicit read-set entity version caveats ($R_{\text{readset}}$) to ensure it is not handicapped against database write-skew or concurrent version collisions.

### 6.2 Binding Novelty Outcome Rule
> **If C3 (`SIGNED_EXACT_DISCLOSURE_TOKEN`) matches C4 (`FULL_GRWC`) in decision safety (zero invalid admissions across all tested adversarial schedules in E16), GLHS R4 explicitly surrenders any claim of decision-safety superiority over compact capability tokens and restricts its claims strictly to:**
> 1. Full-lifecycle state-machine governance (handling asynchronous reviews, multi-agent adaptations, and human overrides);
> 2. Server-attested two-digest dispatch receipts ($H_{\text{proj}}, H_{\text{env}}$);
> 3. Tamper-evident non-downgradable proposal lineage;
> 4. Bit-exact forensic audit reconstructability without reliance on external client-held token caches.

Novelty is anchored in the **Governed Read-to-Write Continuity invariant**, not in the particular data structure chosen to carry it.

---

## 7. Strict Claim Budget

To enforce absolute scientific integrity in manuscript writing, documentation, and presentations, GLHS R4 establishes a binding **Claim Budget**. Every claim MUST fall within the Allowed Claims and MUST NOT violate any Forbidden Claim rules.

### 6.1 Allowed Claims (When Supported by Prospective Evidence)
* $\checkmark$ *"Operationalizes an Exact-Disclosure Admission / Governed Read-to-Write Continuity (GRWC) invariant for longitudinal health AI."*
* $\checkmark$ *"Enforces that persistent AI mutations are admitted only when verifiably continuous with the exact governed disclosure projection ($H_{\text{proj}}$) supplied to model inference."*
* $\checkmark$ *"Within tested audited routes and frozen database schedules ($N = \dots$), zero improper commits were observed (upper 95% Clopper-Pearson bound: \dots%)."*
* $\checkmark$ *"Bounded formal model exploration (depth $d = \dots$) verified state-space invariants $I_1-I_{15}$ without counterexamples."*
* $\checkmark$ *"Evaluated against a minimal capability/token baseline (`MIN_READSET_TOKEN`), establishing the trade-offs of compact credentials versus full lineage tracking."*
* $\checkmark$ *"Demonstrated under real PostgreSQL serializable execution under simulated clinical write contention."*
* $\checkmark$ *"Differentiates exact-disclosure admission from global source-supported updates by rejecting proposals referencing valid database evidence that was omitted from the model prompt."*

### 6.2 Forbidden Claims (Strict Publication Blockers)
* $\times$ **NO "First" Claims:** Do NOT claim to be the "first provenance-aware health AI", "first transactional AI memory", "first governed agent system", or "first co-versioned medical system".
* $\times$ **NO Absolute Security / Elimination Claims:** Do NOT state that "TOCTOU is eliminated", "race conditions are impossible", "formally proven secure", or "tamper-proof".
* $\times$ **NO Medical Efficacy Claims:** Do NOT claim the system is "clinically safe", "diagnostically accurate", "regulatory compliant", or a "doctor replacement".
* $\times$ **NO Neural Causal Reasoning Claims:** Do NOT claim that GLHS proves what the neural network "thought", "attended to", or "internally calculated". Semantic consumption is explicitly out of scope.
* $\times$ **NO Mechanism Uniqueness:** Do NOT claim that GLHS or THSS is "uniquely necessary" or the "only possible solution".
* $\times$ **NO Provider Equivalence without Ledger:** Do NOT report real Claude/Gemini/DeepSeek provider performance based on mock/synthetic responses.
* $\times$ **NO Simulation Presentation as Production:** Do NOT report simulated PostgreSQL thread lock benchmarks as real PostgreSQL performance.
* $\times$ **NO Agent Self-Adjudication as Peer Review:** Do NOT describe internal LLM or multi-agent evaluations as "independent peer review" or "human clinician validation".

---

## 7. Manuscript Rewrite Directives for Phase 10

When updating the manuscript in Phase 10:

1. **Title Alignment:**
   > **GLHS: Exact-Disclosure Admission for Governed Read-to-Write Continuity in Longitudinal Health AI**
2. **Abstract:** Focus strictly on the cross-layer problem ($t_1 \to t_2 \to t_3$ drift), the GRWC invariant, exact-disclosure projection versus global source support, and bounded empirical evaluation results.
3. **Related Work Structure:** Organize into 8 distinct subsections matching the 8 literature categories in Section 2 & Section 3. Conclude with the explicit Central Gap statement:
   > *"Prior work separately establishes transactional freshness, purpose-aware authorization, dynamic consent, provenance, proof-carrying access, clinical-AI lifecycle governance, transactional agent memory, and commitment-bound inference traces. The remaining boundary addressed here is narrower: whether a persistent health mutation proposal is admitted if and only if it remains verifiably continuous with the exact governed disclosure projection ($H_{\text{proj}}$) actually supplied to the inference that produced its lineage, while current clinical state and dynamic governance are independently revalidated within the commit transaction."*
4. **Contribution Hierarchy:**
   * **Contribution 1:** The GRWC / Exact-Disclosure Admission Invariant and formal model.
   * **Contribution 2:** A concrete longitudinal health implementation using server-owned inference bindings, dependency contracts, and PostgreSQL commit-kernel validation.
   * **Contribution 3:** Empirical evaluation (component factorials, minimal token comparison, PostgreSQL TOCTOU, bounded TLA+ formal model).

---

## 8. Automated CI & Gate Enforcement

The claim budget and novelty contract are enforced via automated CI linter scripts. Any pull request or manuscript build containing forbidden claim phrases (e.g., "first provenance-aware", "TOCTOU eliminated", "tamper-proof", "formally proven secure", "clinically safe", "internal neural consumption proven") will **fail CI build gates immediately**.

```text
[PASS] Phase 0 Literature & Novelty Audit complete.
[PASS] Novelty contract frozen at research/glhs_journal/q4_r4/novelty_contract_r4.md.
[PASS] Literature matrix frozen at research/glhs_journal/q4_r4/literature_matrix_r4.json.
[PASS] Claim budget frozen at research/glhs_journal/q4_r4/claim_budget_r4.json.
```
