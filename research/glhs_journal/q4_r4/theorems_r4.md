# Formal Theorems & Proofs: GLHS R4 Assurance Boundaries & Limitations (T1–T4)

**Program:** GLHS R4 — Governed Read-to-Write Continuity (GRWC)  
**Module:** `research/glhs_journal/q4_r4/theorems_r4.md`  
**Author / Curator:** Agent B — Systems & Formal Architecture  
**Status:** Frozen Phase 0 Mathematical Core  
**Date:** Wed Sep 30 2026  

---

## 1. Executive Summary & Mathematical Setting

This document formalizes the four foundational theorems (T1–T4) governing the GLHS R4 architecture. 

In distributed clinical AI systems, there is a recurring architectural fallacy: assuming that cryptographic proofs of inference execution (e.g., cryptographic hash chains, signed JWTs, Macaroons, confidential computing TEEs, or Zero-Knowledge Machine Learning proofs) can replace or subsume database concurrency control and dynamic governance revalidation.

The theorems established here delineate the exact mathematical boundaries of what systems guarantees can and cannot be achieved across the lifecycle of an AI clinical recommendation:

1. **Theorem T1 (Current-State Indistinguishability):** Proves that inference-time cryptographic attestations alone are strictly incapable of distinguishing between fresh and stale clinical states without commit-time transactional revalidation under mutual exclusion.
2. **Theorem T2 (Carrier Sufficiency):** Proves that the Three-Digest Model ($D1, D2, D3$) provides complete tamper-evident carrier sufficiency from the governed disclosure snapshot to the physical transport wire.
3. **Theorem T3 (Dependency Completeness Limitation):** Proves that optimistic concurrency control guarantees are strictly upper-bounded by the completeness of the schema-derived dependency set $D(P)$, formalizing the gap between syntactic database serializability and domain-semantic validity.
4. **Theorem T4 (Semantic Consumption Limitation):** Proves that verified delivery and hardware execution ($L0 \to L3$) do not imply neural semantic consumption of disclosed health facts, establishing the mathematical necessity of independent clinical rule gates (FIDES) and human-in-the-loop review.

---

## 2. Formal Execution Framework & Notation

We define the execution framework as a transition system:

### 2.1 State Space & Time Model
- Let $\mathcal{T} = \mathbb{R}^+$ be continuous physical time.
- Let $S(t) \in \mathcal{S}$ denote the database state of all clinical entities at time $t$. A state $S$ is a mapping from entity partition keys $K$ to version-value pairs: $S: K \to \mathbb{N} \times \mathcal{V}$.
- Let $G(t) \in \mathcal{G}$ denote the dynamic governance state at time $t$, defined as a tuple $\langle p(t), c(t), \mathcal{A}(t) \rangle$ representing the active policy epoch, subject consent epoch, and actor authorization sets.
- A clinical interaction consists of three critical temporal coordinates:
  1. $t_{\text{snap}}$: The instant a Temporal Health State Snapshot (THSS) $H$ is generated and authorized.
  2. $t_{\text{dispatch}}$: The instant the transport request $T$ is transmitted to the inference provider ($t_{\text{snap}} \le t_{\text{dispatch}}$).
  3. $t_c$: The instant a persistent-write proposal $P$ derived from inference is evaluated by the database commit kernel ($t_{\text{dispatch}} < t_c$).

### 2.2 Inference Attestation Tuple
An inference transcript and attestation record is a tuple:
$$\Pi_{\text{infer}} = \langle H, E, T, I, R \rangle$$
where:
- $H$: Governed Disclosure Snapshot.
- $E$: Canonical Semantic Envelope (`clara.inference-envelope.v1`).
- $T$: Exact serialized transport octet stream.
- $I$: Server-owned inference binding ledger record.
- $R$: Optional provider cryptographic receipt ($R \in \mathcal{R} \cup \{\bot\}$).

The attestation level is designated $\lambda(I) \in \{L0, L1, L2, L3\}$ per the R4 hierarchy:
- $L0$: `APPLICATION_ENVELOPE_ONLY`
- $L1$: `TRANSPORT_DISPATCH_ATTESTED`
- $L2$: `PROVIDER_RECEIPT_VERIFIED`
- $L3$: `PROVIDER_EXECUTION_ATTESTED`

---

## 3. Theorem T1: Current-State Indistinguishability

### 3.1 Intuition
Proponents of decentralized or client-centric agent architectures often argue that if an inference pass is cryptographically sealed (or executed inside an enclave with a signed receipt $R$), the resulting proposal $P$ can be safely committed by simply verifying the cryptographic signature. Theorem T1 proves this is mathematically impossible: because inference is decoupled from the transactional lock engine, an arbitrary number of state or governance mutations can occur in the interval $(t_{\text{snap}}, t_c)$.

### 3.2 Formal Statement

**Theorem T1 (Current-State Indistinguishability).**  
Let $\Pi_{\text{infer}} = \langle H, E, T, I, R \rangle$ be any valid inference transcript and attestation tuple at any attestation level $\lambda(I) \in \{L0, L1, L2, L3\}$, compiled at time $t_{\text{snap}}$. Let $P$ be a proposal descending from $I$. 

Let $\mathcal{D}: \Pi_{\text{infer}} \times \mathcal{P} \to \{\text{Accept}, \text{Reject}\}$ be any decision procedure that does not evaluate the mutable state $S(t_c)$ and governance state $G(t_c)$ under mutual exclusion at commit time $t_c$.

Then there exist two system execution trajectories $\sigma_{\text{clean}}$ and $\sigma_{\text{drift}}$ such that:
1. $\Pi_{\text{infer}}(\sigma_{\text{clean}}) = \Pi_{\text{infer}}(\sigma_{\text{drift}}) = \Pi_{\text{infer}}$ (the inference transcripts and cryptographic proofs are identical);
2. In $\sigma_{\text{clean}}$, the proposal $P$ is clinically and legally valid at $t_c$:
   $$S(t_c) = S(t_{\text{snap}}) \land G(t_c) = G(t_{\text{snap}})$$
3. In $\sigma_{\text{drift}}$, the proposal $P$ is clinically or legally invalid at $t_c$:
   $$S(t_c) \neq S(t_{\text{snap}}) \lor G(t_c) \neq G(t_{\text{snap}})$$
4. The decision procedure $\mathcal{D}$ cannot distinguish between $\sigma_{\text{clean}}$ and $\sigma_{\text{drift}}$:
   $$\mathcal{D}(\Pi_{\text{infer}}(\sigma_{\text{clean}}), P) = \mathcal{D}(\Pi_{\text{infer}}(\sigma_{\text{drift}}), P)$$
   yielding either a false positive admission in $\sigma_{\text{drift}}$ or a false rejection in $\sigma_{\text{clean}}$.

### 3.3 Proof

*Proof.*  
We construct the two trajectories $\sigma_{\text{clean}}$ and $\sigma_{\text{drift}}$ explicitly.

**Step 1: Construction of Shared Prefix.**  
Let $t_0 < t_{\text{snap}} < t_{\text{dispatch}} < t_{\text{resp}} < t_{\text{prop}} < t_c$.
During $[t_0, t_{\text{snap}}]$, both trajectories execute identical operations:
- A patient profile has active medication $M_1$ (`Warfarin 5mg`), state version $v(M_1) = 1$, consent epoch $c = 1$, policy epoch $p = 1$.
- At $t_{\text{snap}}$, disclosure $H$ is compiled: $H.\text{projection}$ includes $M_1$, $H.v_s = 1, H.c_s = 1, H.p_s = 1$.
- At $t_{\text{dispatch}}$, envelope $E$ is serialized to $T$, and dispatched.
- Binding $I$ is persisted with $\lambda(I) = L3$ (hardware execution attested via enclave quote $\Pi_{\text{exec}}$).
- At $t_{\text{resp}}$, response $Y$ recommends adding medication $M_2$ (`Amiodarone 200mg`), which has a critical interaction with $M_1$.
- Proposal $P$ is formulated from $Y$, citing $I$.
Up to time $t_{\text{prop}}$, the state traces of $\sigma_{\text{clean}}$ and $\sigma_{\text{drift}}$ are identical.

**Step 2: Divergence at $t_{\text{drift}} \in (t_{\text{prop}}, t_c)$.**
- In trajectory $\sigma_{\text{clean}}$: No state transitions occur in the interval $(t_{\text{prop}}, t_c)$.
  Therefore:
  $$S(t_c) = S(t_{\text{snap}}), \quad G(t_c) = G(t_{\text{snap}})$$
  The recommendation $M_2$ is evaluated in the exact clinical and legal context in which it was generated.

- In trajectory $\sigma_{\text{drift}}$: At time $t_{\text{drift}}$, a clinician observes acute bleeding and discontinues $M_1$, committing a state transition:
  $$S' = S \oplus [M_1 \mapsto \text{Discontinued}, v(M_1) \mapsto 2]$$
  Alternatively, the patient revokes research/assistant consent:
  $$G' = G \oplus [c \mapsto 2]$$
  This mutation commits successfully at $t_{\text{drift}} < t_c$.

**Step 3: Evaluation by Decision Procedure $\mathcal{D}$.**  
By definition, $\mathcal{D}$ operates solely on the input tuple $\langle \Pi_{\text{infer}}, P \rangle$:
$$\mathcal{D}: (\Pi_{\text{infer}}, P) \mapsto \{\text{Accept}, \text{Reject}\}$$
Since neither $S(t)$ nor $G(t)$ is an input to $\mathcal{D}$, and because $\Pi_{\text{infer}}$ was finalized and sealed at $t_{\text{resp}} < t_{\text{drift}}$, we have:
$$\Pi_{\text{infer}}(\sigma_{\text{clean}}) \equiv \Pi_{\text{infer}}(\sigma_{\text{drift}})$$
$$P(\sigma_{\text{clean}}) \equiv P(\sigma_{\text{drift}})$$

Therefore:
$$\mathcal{D}(\Pi_{\text{infer}}(\sigma_{\text{clean}}), P) = \mathcal{D}(\Pi_{\text{infer}}(\sigma_{\text{drift}}), P)$$

**Case A:** If $\mathcal{D}$ outputs $\text{Accept}$, then in $\sigma_{\text{drift}}$ the proposal $P$ commits against a revoked consent or an invalid clinical state (where $M_1$ was already discontinued or dose-adjusted), committing a TOCTOU clinical safety violation.  
**Case B:** If $\mathcal{D}$ outputs $\text{Reject}$, then in $\sigma_{\text{clean}}$ the system rejects a perfectly valid proposal, violating clean-path reachability (Invariant I15).

Thus, no decision procedure based solely on inference transcripts and cryptographic proofs can avoid TOCTOU errors without evaluating $S(t_c)$ and $G(t_c)$ at commit time. $\blacksquare$

### 3.4 Systems Corollaries

1. **Corollary 1.1 (Insufficiency of Cryptographic Tokens):** Proof-carrying authorization tokens, Macaroons, signed JWTs, and client-signed transactions cannot prevent stale clinical commits. Mutual exclusion locks and atomic version revalidation at the database storage engine are strictly necessary.
2. **Corollary 1.2 (Insufficiency of ZKML / TEE):** A Zero-Knowledge proof that an LLM executed correctly over inputs $T$ provides zero guarantee that the world described by $T$ is still true when the model's output is written to disk.

---

## 4. Theorem T2: Carrier Sufficiency

### 4.1 Intuition
When health data moves from the database to an external model API, it undergoes projection, envelope formatting, and transport serialization. Theorem T2 proves that the Three-Digest Model ($D1: H_{\text{proj}}$, $D2: H_{\text{sem}}$, $D3: H_{\text{trans}}$) forms an unbroken, tamper-evident cryptographic carrier: no clinical fact can be added, deleted, or substituted on the wire without detection.

### 4.2 Formal Statement

**Theorem T2 (Carrier Sufficiency).**  
Let $H$ be a governed disclosure snapshot with projection $X = \text{ExtractProjection}(H)$ and projection digest $H_{\text{proj}} = \mathcal{H}(\text{JCS}(X))$.  
Let $E$ be a canonical semantic envelope embedding $X$ into its health state partition: $E.E_{\text{proj}} = X$, with semantic digest $H_{\text{sem}} = \mathcal{H}(\text{JCS}(E))$.  
Let $T = \Phi(E)$ be the serialized transport request body generated by deterministic wire serialization $\Phi$, with transport digest $H_{\text{trans}} = \mathcal{H}(T)$.  
Let $\mathcal{H}$ be a cryptographic hash function modeled as a random oracle with security parameter $\kappa$.

If an adversary $\mathcal{A}$ running in probabilistic polynomial time (PPT) modifies the clinical content $X$ to $X' \neq X$, producing modified envelope $E'$ and transport wire payload $T'$, then:
$$\Pr\left[ \mathcal{H}(\text{JCS}(X')) = H_{\text{proj}} \lor \mathcal{H}(\text{JCS}(E')) = H_{\text{sem}} \lor \mathcal{H}(T') = H_{\text{trans}} \right] \le \frac{3 \cdot q_{\mathcal{H}}}{2^\kappa}$$
where $q_{\mathcal{H}}$ is the number of hash queries made by $\mathcal{A}$.

Furthermore, if the commit kernel asserts:
$$\text{ExactDisclosure}(P, I, H) \land I.\text{projection\_digest} = H_{\text{proj}} \land I.\text{request\_envelope\_digest} = H_{\text{sem}} \land I.\text{transport\_payload\_digest} = H_{\text{trans}}$$
then $T$ is **carrier-sufficient**: the exact clinical projection $X$ disclosed in $H$ was preserved without modification throughout the transport pipeline.

### 4.3 Proof

*Proof.*  
We prove carrier sufficiency via a sequence of cryptographic reductions.

**Step 1: Projection Integrity ($D1$).**  
Let $X$ and $X'$ be two distinct clinical projections such that $X \neq X'$.  
By the determinism of RFC 8785 JSON Canonicalization Scheme (JCS):
$$X \neq X' \implies \text{JCS}(X) \neq \text{JCS}(X')$$
Under the random oracle model for $\mathcal{H} = \text{SHA-256}$, the probability that $\mathcal{H}(\text{JCS}(X')) = \mathcal{H}(\text{JCS}(X)) = H_{\text{proj}}$ is bounded by the collision probability:
$$\Pr\left[\mathcal{H}(\text{JCS}(X')) = H_{\text{proj}}\right] \le \frac{q_{\mathcal{H}}}{2^\kappa}$$
For SHA-256, $\kappa = 256$, rendering this probability negligible ($\le 2^{-128}$ under birthday bounds).

**Step 2: Envelope Inclusion & Structural Propagation ($D2$).**  
The canonical envelope $E$ is defined by the 5-tuple:
$$E = \langle E_{\text{sys}}, X, E_{\text{ctx}}, E_{\text{task}}, E_{\text{params}} \rangle$$
Since $X$ is directly embedded in $E$, any change $X \to X'$ yields $E' \neq E$.  
Again, by JCS determinism and collision resistance of $\mathcal{H}$:
$$\Pr\left[\mathcal{H}(\text{JCS}(E')) = H_{\text{sem}}\right] \le \frac{q_{\mathcal{H}}}{2^\kappa}$$

**Step 3: Transport Serialization Integrity ($D3$).**  
The serialization function $\Phi: \mathcal{E} \to \mathcal{T}$ maps the structured envelope to wire bytes $T = \Phi(E)$.  
Suppose an in-transit network adversary modifies the payload on the wire from $T$ to $T'$ ($T' \neq T$) in an attempt to alter clinical facts delivered to the provider (for example, replacing `Warfarin 5mg` with `Warfarin 50mg`).  
The transport digest recorded in the server-owned binding $I$ is:
$$I.\text{transport\_payload\_digest} = \mathcal{H}(T) = H_{\text{trans}}$$
For the modified wire payload $T'$ to be admitted under verification, the adversary must find $T' \neq T$ such that $\mathcal{H}(T') = H_{\text{trans}}$.  
By second-preimage resistance of SHA-256:
$$\Pr\left[\mathcal{H}(T') = H_{\text{trans}}\right] \le \frac{q_{\mathcal{H}}}{2^\kappa}$$

**Step 4: Union Bound.**  
Applying the union bound across the three verification checks:
$$\Pr[\text{Tamper undetected}] \le \Pr[\text{Coll}(D1)] + \Pr[\text{Coll}(D2)] + \Pr[\text{Coll}(D3)] \le \frac{3 \cdot q_{\mathcal{H}}}{2^\kappa}$$
Since this probability is cryptographically negligible, the verification of the Three-Digest cascade guarantees that $T$ carried the exact clinical projection $X$ from $H$ across the transport boundary. $\blacksquare$

### 4.4 Systems Corollaries

1. **Corollary 2.1 (Egress Provenance Non-Repudiation):** If an external provider claims that it received an incorrect or hallucinated patient history, the server-owned binding $I$ containing $H_{\text{trans}} = \mathcal{H}(T)$ provides non-repudiable mathematical evidence of the exact wire payload transmitted.
2. **Corollary 2.2 (Decoupling Prompt Updates from Clinical Lineage):** Updating system prompt guardrails $E_{\text{sys}}$ changes $D2$ and $D3$, but preserves $D1$. This allows prompt maintenance without invalidating historical clinical projection digests.

---

## 5. Theorem T3: Dependency Completeness Limitation

### 5.1 Intuition
In GLHS R3 and R4, the commit kernel revalidates the dependency vector $D(P)$ under locks:
$$\text{StateCurrent}(P, S(t_c)) \iff \forall \langle k, v, \delta \rangle \in D(P) : S(t_c)[k].\text{version} = v$$
Does this guarantee that the resulting state transition is semantically valid? Theorem T3 establishes the fundamental systems limitation: **optimistic concurrency control only guarantees serializability over the entities explicitly declared in $D(P)$**. If the schema-derived dependency function $\text{MinDependencies}(P)$ omits a causally relevant clinical factor, syntactic serializability holds, but clinical semantic invalidity occurs.

### 5.2 Formal Statement

**Theorem T3 (Dependency Completeness Limitation).**  
Let $\mathcal{U}$ be the universe of clinical entity partitions in the patient health record.  
Let $\mathcal{C}_{\text{true}}(P) \subseteq \mathcal{U}$ denote the true causal semantic dependency set of proposal $P$ (i.e. the set of all entities whose state can clinically invalidate $P$).  
Let $D(P) \subseteq \mathcal{U}$ be the declared dependency set verified by the commit kernel.  
Suppose $D(P)$ is **incomplete**:
$$\exists e^* \in \mathcal{C}_{\text{true}}(P) \setminus D(P)$$

Then there exists an interleaved execution schedule $\Sigma$ involving proposal transaction $T_P$ and concurrent transaction $T_{\text{ext}}$ such that:
1. Schedule $\Sigma$ is strictly **conflict-serializable** with respect to $D(P)$ and satisfies the R4 Base Invariant:
   $$\text{Admit}(P, t_c) = \text{TRUE}$$
2. The committed state transition produced by $T_P$ violates clinical semantic validity:
   $$\text{ClinicallyValid}(P, S(t_c)) = \text{FALSE}$$

### 5.3 Proof

*Proof.*  
We construct the execution schedule $\Sigma$ and counterexample state transition.

**Step 1: Clinical Domain Modeling.**  
Let the clinical operation be:
$$P = \text{"Prescribe Ciprofloxacin 500mg PO BID"}$$
The true causal dependencies for safe administration of Ciprofloxacin include:
1. $e_1 = \text{ActiveMedications}$ (target write partition).
2. $e_2 = \text{RenalFunction}$ (eGFR / Serum Creatinine, required for dose adjustment).
3. $e^* = \text{CardiacQTInterval}$ (ECG QTc measurement, due to fatal torsades de pointes risk).
Thus, $\mathcal{C}_{\text{true}}(P) = \{e_1, e_2, e^*\}$.

**Step 2: Incomplete Schema Dependency Specification.**  
Suppose the dependency generation function $\text{MinDependencies}(\text{"prescribe\_antibiotic"})$ defines:
$$D(P) = \{e_1, e_2\}$$
omitting $e^*$ (so $e^* \in \mathcal{C}_{\text{true}}(P) \setminus D(P)$).

**Step 3: Interleaved Schedule $\Sigma$.**  
Consider the timeline of events:
- **$t_1$ ($t_{\text{snap}}$):** Agent reads patient state $S(t_1)$. $S(t_1)[e^*].\text{QTc} = 420\text{ms}$ (normal, version $v(e^*) = 1$). $S(t_1)[e_1]$ has version $1$, $S(t_1)[e_2]$ has version $1$.
- **$t_2$ ($t_{\text{dispatch}}$):** Model generates proposal $P$ to prescribe Ciprofloxacin based on normal QTc at $t_1$.
- **$t_3$ ($t_{\text{concurrent}}$):** A concurrent cardiology transaction $T_{\text{ext}}$ processes a new ECG showing severe drug-induced QT prolongation ($\text{QTc} = 530\text{ms}$). $T_{\text{ext}}$ updates partition $e^*$:
  $$S(t_3)[e^*].\text{version} = 2, \quad S(t_3)[e^*].\text{QTc} = 530\text{ms}$$
  $T_{\text{ext}}$ acquires lock on $e^*$, commits, and releases lock.
- **$t_4$ ($t_c$):** Proposal transaction $T_P$ enters the Phase 3 Commit Kernel holding locks on $D(P) = \{e_1, e_2\}$.
  The kernel evaluates:
  $$S(t_c)[e_1].\text{version} = 1 = D(P)[e_1].\text{version}$$
  $$S(t_c)[e_2].\text{version} = 1 = D(P)[e_2].\text{version}$$
  Because $e^* \notin D(P)$, partition $e^*$ is neither locked nor checked.
  $\text{StateCurrent}(P, S(t_c))$ evaluates to $\text{TRUE}$.
  The kernel commits $P$, incrementing $v(e_1) \to 2$.

**Step 4: Analysis of Serializability vs Semantic Validity.**  
- *Database Serializability:* In the conflict graph of $D(P)$, there are no cycles. $T_{\text{ext}}$ and $T_P$ touch disjoint partition sets ($D(T_{\text{ext}}) \cap D(T_P) = \emptyset$). The schedule is strictly serializable with equivalent serial order $(T_{\text{ext}}, T_P)$.
- *Clinical Validity:* At $t_c$, patient has $\text{QTc} = 530\text{ms}$. Prescribing Ciprofloxacin at this state poses an immediate lethal risk of ventricular arrhythmia. Therefore:
  $$\text{ClinicallyValid}(P, S(t_c)) = \text{FALSE}$$

Hence, the guarantee of semantic correctness is upper-bounded by the completeness of $D(P)$. $\blacksquare$

### 5.4 Systems Corollaries

1. **Corollary 3.1 (Dependency Contract Primacy):** Transactional correctness in GLHS R4 cannot rely on generic database locking alone; it requires domain-specific **Dependency Contracts** (`dependency_contract.py`) that strictly cover all clinical risk factors.
2. **Corollary 3.2 (Conservative Over-Approximation):** If an operation has uncertain causal reach, the dependency generation function must conservatively over-approximate $D(P)$ (e.g., locking the profile summary anchor) to preserve safety, trading concurrency throughput for clinical validity.

---

## 6. Theorem T4: Semantic Consumption Limitation

### 6.1 Intuition
In modern AI systems literature, there is a dangerous tendency to conflate **carrier/execution attestation** with **model reasoning correctness**. Hardware vendors and Web3/ZKML protocols advertise that an enclave or ZK-proof proves "verifiable AI". Theorem T4 proves an absolute negative result: **even a perfect Level 3 hardware attestation ($\text{PROVIDER\_EXECUTION\_ATTESTED}$) provides ZERO mathematical guarantee that the model semantically consumed, understood, or adhered to the disclosed clinical facts $H$**.

### 6.2 Formal Statement

**Theorem T4 (Semantic Consumption Limitation).**  
Let $\mathcal{M}_\theta: \mathcal{V}^* \to \Delta(\mathcal{V})$ be a parameterized autoregressive language model with parameter vector $\theta \in \mathbb{R}^d$ and vocabulary $\mathcal{V}$.  
Let $T$ be a transport payload containing disclosure tokens $X_H = \text{Tokenize}(H)$ and prompt tokens $X_{\text{prompt}}$, such that the input token sequence is $X = (X_{\text{prompt}}, X_H)$.  
Let $I$ be an inference binding with maximal attestation level $\lambda(I) = L3$ (`PROVIDER_EXECUTION_ATTESTED`), accompanied by a valid execution proof $\Pi_{\text{exec}}$ verifying that output tokens $Y = (y_1, \dots, y_m)$ were generated by evaluating $\mathcal{M}_\theta$ over $X$:
$$\text{VerifyProof}(\Pi_{\text{exec}}, \mathcal{M}_\theta, X, Y) = \text{TRUE}$$

Then:
$$\text{AttestationLevel}(I) = L3 \not\implies \text{SemanticUseByModel}(H)$$

Specifically, there exist parameter configurations $\theta$ and input structures $X$ such that:
1. The execution proof $\Pi_{\text{exec}}$ is perfectly valid;
2. The output $Y$ is statistically independent of or directly contradicts the clinical disclosure $H$:
   $$\mathcal{I}(Y; X_H \mid X_{\text{prompt}}) = 0 \quad \text{or} \quad \text{Contradicts}(Y, H) = \text{TRUE}$$
   where $\mathcal{I}(\cdot ; \cdot)$ denotes mutual information.

### 6.3 Proof

*Proof.*  
We prove this by examining the mechanistic structure of transformer self-attention and autoregressive generation.

**Step 1: Attention Allocation & Attention Sink Phenomenon.**  
In an $L$-layer multi-head self-attention transformer, the representation at layer $l$, head $h$, and query position $j$ is computed as:
$$z_{l, h, j} = \sum_{k=1}^{j} A_{l, h}(j, k) \cdot V_{l, h} x_k$$
where the attention weight matrix is:
$$A_{l, h}(j, k) = \frac{\exp\left(\frac{q_{l, h, j}^T k_{l, h, k}}{\sqrt{d_k}}\right)}{\sum_{u=1}^{j} \exp\left(\frac{q_{l, h, j}^T k_{l, h, u}}{\sqrt{d_k}}\right)}$$

Let $K_H \subset \{1, \dots, |X|\}$ be the set of token indices corresponding to $X_H$.  
Let $K_{\text{sink}} \subset \{1, \dots, |X|\}$ be initial prompt tokens (the "attention sink", e.g., token 0 or system prompt delimiters).  
It is a well-established empirical and mathematical property of trained transformers (Xiao et al., 2023; Miller, 2024) that attention heads can allocate arbitrary mass to sink tokens or instruction tokens:
$$\sum_{k \in K_H} A_{l, h}(j, k) < \epsilon$$
for an arbitrarily small $\epsilon > 0$, across all layers $l \in \{1, \dots, L\}$ and heads $h$.  
In this regime, the output token representations $z_{L, h, j}$ have gradient with respect to disclosure tokens bounded by:
$$\left\| \frac{\partial z_{L, h, j}}{\partial x_k} \right\| = \mathcal{O}(\epsilon) \quad \forall k \in K_H$$
As $\epsilon \to 0$, the output distribution $p_\theta(Y \mid X)$ becomes functionally independent of $X_H$:
$$p_\theta(Y \mid X_{\text{prompt}}, X_H) = p_\theta(Y \mid X_{\text{prompt}}) \implies \mathcal{I}(Y; X_H \mid X_{\text{prompt}}) = 0$$

**Step 2: Parametric Prior Dominance & Hallucination.**  
The log-probability of generating token $y$ can be decomposed into the contribution of pre-trained parametric weights $\theta$ (the language prior) and in-context disclosure $X_H$:
$$\log p_\theta(y \mid X) = \mathbf{w}_y^T f_\theta(X_{\text{prompt}}, X_H)$$
If the pre-trained prior for a common clinical misconception or generic clinical recommendation is strongly encoded in $\theta$ (e.g. recommending `Aspirin` for all adult chest pain without checking for active GI bleeding disclosed in $X_H$), the logit difference between the generic prior and the counter-indicated disclosure can dominate the softmax:
$$p_\theta(y_{\text{prior}} \mid X) \gg p_\theta(y_{\text{safe}} \mid X)$$
The model outputs $y_{\text{prior}}$, directly contradicting the active bleeding ulcer documented in $H$:
$$\text{Contradicts}(Y, H) = \text{TRUE}$$

**Step 3: Verification of the Execution Proof.**  
The cryptographic or TEE attestation verifier $\text{VerifyProof}(\Pi_{\text{exec}}, \mathcal{M}_\theta, X, Y)$ checks only:
1. Did CPU/GPU with public key $\text{PK}_{\text{tee}}$ execute the instruction set?
2. Do the hash of weights $\mathcal{H}(\theta)$ and hash of input $\mathcal{H}(X)$ match the claimed values?
3. Did the forward pass produce logits that sample to $Y$?

All three checks evaluate to $\text{TRUE}$. The hardware executed the exact floating-point matrix multiplications specified by $\theta$ on tokens $X$.  
Yet, as established in Steps 1 and 2, the model ignored $X_H$ or contradicted $H$.

Therefore:
$$\text{AttestationLevel}(I) = L3 \not\implies \text{SemanticUseByModel}(H) \quad \blacksquare$$

### 6.4 Systems Corollaries

1. **Corollary 4.1 (Non-Sufficiency of Verifiable Inference):** Zero-Knowledge Machine Learning (ZKML) and TEE confidential computing are strictly **transport- and execution-layer proofs**. They cannot prove that an LLM acted as a safe, rational clinical agent.
2. **Corollary 4.2 (Mandatory Orthogonal Guardrails):** To prevent clinical harm, the system must deploy **deterministic post-inference semantic verification gates**:
   - **FIDES Verification:** Deterministic clinical rule checks blocking un-disclosed drug dosages and drug-drug interactions (DDI).
   - **Evidence Scope Closure (Invariant I07/I14):** Mathematical verification that proposal evidence claims are bounded by snapshot disclosures.
   - **Human Clinician Review:** Mandatory review workflows for high-risk clinical actions.

---

## 7. Unified Assurance Boundary Matrix

The table below synthesizes Theorems T1–T4, detailing what each architectural layer mathematically proves, what it fails to prove, and which downstream GLHS mechanism provides the necessary enforcement.

| Layer / Mechanism | Theorem | What Is Formally Proven | What Is NOT Proven | Required Orthogonal Enforcement |
| :--- | :--- | :--- | :--- | :--- |
| **Three-Digest Cascade** ($D1, D2, D3$) | **T2 (Carrier Sufficiency)** | The transport payload $T$ carries the exact clinical projection $X$ disclosed in $H$ without byte modification across the network boundary. | Does not prove that the provider received $T$, or that $T$ was fed into GPU memory. | Level $L1/L2$ transport and receipt logging. |
| **Transport Dispatch Attestation** ($L1$) | **T2** | The server executed an egress socket write with payload $T$ matching $H_{\text{trans}}$ at timestamp $t_{\text{dispatch}}$. | Does not prove provider receipt, provider execution, or model understanding. | Level $L2$ provider signed receipt. |
| **Provider Receipt Verification** ($L2$) | **T2** | Upstream provider received and acknowledged payload matching $H_{\text{trans}}$. | Does not prove execution without model quantization, substitution, or pruning. | Level $L3$ hardware TEE attestation. |
| **Hardware TEE / ZKML Attestation** ($L3$) | **T4 (Semantic Consumption Limitation)** | The exact model architecture $\mathcal{M}_\theta$ executed forward pass on token sequence $X$ producing output $Y$. | **Does NOT prove semantic adherence, attention allocation, factual accuracy, or clinical safety.** | **FIDES verification, Invariants I07/I14, clinical rules, clinician review.** |
| **Database OCC Revalidation** (Phase 3 Kernel) | **T1 (Current-State Indistinguishability)** | At commit time $t_c$, clinical state $S(t_c)$ and governance state $G(t_c)$ match observation coordinates in $D(P)$. | **Does NOT prove semantic validity if $D(P)$ is incomplete with respect to clinical causality.** | **Rigorous Schema Dependency Contracts (Theorem T3).** |
| **Dependency Contracts** (`dependency_contract.py`) | **T3 (Dependency Completeness Limitation)** | The dependency vector $D(P)$ covers all modeled causal entity partitions for the operation kind. | Does not prove unmodeled real-world clinical factors outside the database schema. | Conservative lock coarsening & expert medical ontology modeling. |

---

## 8. Conclusion: The Layered Safety Invariant of GLHS R4

Theorems T1–T4 demonstrate that clinical safety in autonomous or semi-autonomous AI systems cannot be reduced to a single silver-bullet mechanism. 

- **Cryptography and TEEs** (Theorems T2 & T4) provide *carrier integrity and execution non-repudiation*, but cannot guarantee *clinical rationality*.
- **Database OCC and Advisory Locks** (Theorem T1) eliminate *TOCTOU race conditions and state staleness*, but only over *modeled dependencies* (Theorem T3).
- **Domain Guardrails and Human Review** (Corollaries 4.2 & 3.1) enforce *clinical safety*, anchored by the mathematical guarantees of the lower layers.

By combining the **Three-Digest Model**, **Attestation Hierarchy**, **Dependency Contracts**, and **Atomic Commit Kernel**, GLHS R4 achieves an airtight, provably grounded assurance boundary for healthcare AI.
