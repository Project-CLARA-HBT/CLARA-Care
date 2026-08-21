# Formal Specification of Governance-Snapshot Atomicity (GSA)

**Document Version:** 1.0.0  
**Status:** Canonical Mathematical Specification  
**System:** Governed Learning Health System (GLHS) / CLARA-Care Architecture  
**Target Ledger:** PostgreSQL Canonical Transition Engine  

---

## Abstract

This document presents the formal mathematical specification of **Governance-Snapshot Atomicity (GSA)**, a concurrency control and epistemic isolation property designed for autonomous AI reasoning agents operating over sensitive clinical state spaces. In modern clinical AI architectures, an autonomous agent observes a state snapshot $\Sigma$ at disclosure time $t_{\text{disclose}}$, performs multi-step cognitive or optimization inference over an extended temporal window $[t_{\text{disclose}}, t_{\text{commit}}]$, and subsequently proposes a state transition $P = \langle \Delta S, \operatorname{Deps}(P), \Sigma, \sigma \rangle$ to be committed at $t_{\text{commit}}$.

Standard database serializability (including PostgreSQL Serializable Snapshot Isolation) fails to protect such workflows because patient consent directives, regulatory policies, and multi-resource semantic dependencies mutate concurrently outside the row-level read/write tracking of traditional database transaction engines. GSA formalizes a four-fold invariant guaranteeing **State Isolation**, **Governance Freshness**, **Temporal Lease Validity**, and **Cryptographic Audit Coupling** within an indivisible database transaction. We establish the formal system model, provide rigorous proofs of correctness, deadlock-freedom, crash-recovery atomicity, and cryptographic non-forgeability, and compare GSA against existing distributed authorization and isolation paradigms.

---

## 1. Formal System Model

Let the operational universe be defined over continuous time $\mathbb{T} = \mathbb{R}_{\ge 0}$ (with physical timestamps coordinated via monotonic clocks bounded by maximum synchronization skew $\epsilon_{\text{skew}}$).

### 1.1 Base Universes and Algebraic Sorts

1. **Subjects ($\mathcal{U}$):** The set of distinct patient identities $u \in \mathcal{U}$.
2. **Governance Domains ($\mathcal{D}$):** The set of clinical and administrative policy domains $d \in \mathcal{D}$ (e.g., `self_care`, `clinical_decision_support`, `research_export`, `prescribing`).
3. **Entities ($\mathcal{E}$):** The universe of health assertions, clinical commitment states, diagnostic entries, and medication plans $e \in \mathcal{E}$.
4. **Values ($\mathcal{V}$):** The set of typed attribute payloads and clinical observation terms.
5. **Cryptographic Primitives:**
   - A collision-resistant hash function $\mathbb{H}: \{0,1\}^* \to \{0,1\}^{256}$ (instantiated via SHA-256).
   - An asymmetric digital signature scheme $\Sigma_{\text{sig}} = (\operatorname{KeyGen}, \operatorname{Sign}, \operatorname{Verify})$ providing Existential Unforgeability under Chosen Message Attacks (EUF-CMA).
   - A Merkle tree accumulator $\operatorname{MerkleTree}: \mathcal{P}(\mathcal{E}) \to \{0,1\}^{256}$.

---

### 1.2 State Space and Version Vectors

The clinical health state of a subject $u \in \mathcal{U}$ is modeled as an $n$-dimensional state vector of entity values:

$$S = \langle e_1, e_2, \dots, e_n \rangle \in \mathcal{V}^n, \quad \text{where } e_i \in \mathcal{E}$$

Each entity $e_k \in \mathcal{E}$ is associated with a discrete, monotonically increasing local state version counter $v(e_k) \in \mathbb{N}$. The global state version of the profile is represented by the version vector:

$$V = \langle v(e_1), v(e_2), \dots, v(e_n) \rangle \in \mathbb{N}^n$$

In addition to physical version counters, every entity transition carries explicit **bitemporal coordinates**:
- **Valid Time Interval:** $\mathbb{T}_v = [t_v^{\text{start}}, t_v^{\text{end}}] \subset \mathbb{T}$, representing the period during which the clinical condition or assertion is true in the physical world.
- **Knowledge Time (Recorded Time):** $t_k \in \mathbb{T}$, representing the exact point at which the assertion was durably serialized in the canonical ledger ($t_k = \max(t_{\text{source}}, t_{\text{ingest}})$).

---

### 1.3 Governance State Tuple

The governance context governing access, inference, and mutation for subject $u \in \mathcal{U}$ in domain $d \in \mathcal{D}$ at time $t$ is formalized as:

$$\mathcal{G}(u, d, t) = \langle v_c(u, t), v_\pi(d, t), \tau \rangle$$

Where:
1. **Consent Epoch ($v_c(u, t) \in \mathbb{N}$):** A discrete version counter incremented strictly upon any mutation to the subject's informed consent ledger (including opt-in, scope reduction, purpose revocation, or delegated proxy re-assignment):
   $$v_c(u, t) = \sum_{i=1}^m \mathbf{1}_{\{\text{event } E_i \text{ modifies } \mathcal{C}(u) \text{ at } t_i \le t\}}$$
2. **Policy Epoch ($v_\pi(d, t) \in \mathbb{N}$):** A discrete version counter advancing upon any institutional, regulatory, or algorithmic safety rule update applied to policy domain $d$:
   $$v_\pi(d, t) = \sum_{j=1}^p \mathbf{1}_{\{\text{policy update } \Pi_j \text{ applied to } d \text{ at } t_j \le t\}}$$
3. **Authorization Lease ($\tau \subset \mathbb{T}$):** A closed temporal authorization interval:
   $$\tau = [t_{\text{start}}, t_{\text{expire}}], \quad \text{with } \Delta \tau = t_{\text{expire}} - t_{\text{start}} \le \Delta \tau_{\max}$$
   specifying the hard window of epistemic validity within which reasoning outputs derived from disclosed state remain admissible for persistence.

---

### 1.4 Task-Bounded Governed Snapshot ($\Sigma$)

At time $t_{\text{disclose}} \in \mathbb{T}$, when an agent or clinical pipeline requests access to a subject's state to execute an autonomous task $\psi$ in domain $d$, the system compiles a **Task-Bounded Governed Snapshot** $\Sigma$:

$$\Sigma = \langle S_{\text{obs}}, V_{\text{obs}}, v_{c,\text{obs}}, v_{\pi,\text{obs}}, \tau, d_H, R_H \rangle$$

Where:
- $S_{\text{obs}} = \Pi_{\mathcal{E}_{\text{disclose}}}(S) \in \mathcal{V}^m$ ($m \le n$) is the subset of entity states visible under purpose $\phi$ and role authorization.
- $V_{\text{obs}} = \langle v(e_k) \mid e_k \in \mathcal{E}_{\text{disclose}} \rangle \in \mathbb{N}^m$ is the exact version vector at $t_{\text{disclose}}$.
- $v_{c,\text{obs}} = v_c(u, t_{\text{disclose}})$ is the active consent epoch at disclosure.
- $v_{\pi,\text{obs}} = v_\pi(d, t_{\text{disclose}})$ is the active governance policy epoch at disclosure.
- $\tau = [t_{\text{disclose}}, t_{\text{disclose}} + \Delta \tau_{\text{lease}}]$ is the bound lease.
- $d_H = \mathbb{H}(\operatorname{CanonicalJSON}(\Sigma \setminus \{d_H, R_H\}))$ is the cryptographic snapshot digest.
- $R_H = \operatorname{MerkleTree}(\mathcal{E}_{\text{disclose}})$ is the cryptographic Merkle root authenticating the exact evidence set presented to the agent.

---

### 1.5 The Autonomous Inference Window and Transition Proposal

Upon receiving $\Sigma$, the autonomous agent operates over the **Inference Window**:

$$\mathcal{I}_{\text{inference}} = [t_{\text{disclose}}, t_{\text{commit}}]$$

During $\mathcal{I}_{\text{inference}}$, the agent executes cognitive synthesis, clinical guideline traversal, or deep learning inference asynchronously. At $t_{\text{commit}}$, the agent emits a **Transition Proposal** $P$:

$$P = \langle \Delta S, \operatorname{Deps}(P), \Sigma, \sigma \rangle$$

Where:
1. $\Delta S = \{ (e_k, \operatorname{val}_{\text{new}}(e_k), \mathbb{T}_{v,k}) \mid e_k \in \mathcal{E}_{\text{write}} \}$ is the proposed physical mutation set.
2. $\operatorname{Deps}(P) \subseteq \mathcal{E}_{\text{disclose}}$ is the causal read-dependency set—the exact entities whose observed states directly justified the computation of $\Delta S$.
3. $\Sigma$ is the exact snapshot metadata token issued at $t_{\text{disclose}}$.
4. $\sigma = \operatorname{Sign}_{K_{\text{agent}}}(\mathbb{H}(\Delta S \parallel \operatorname{Deps}(P) \parallel d_H \parallel R_H))$ is the cryptographic signature of the proposing agent under private key $K_{\text{agent}}$.

---

### 1.6 Governed State Transition ($\operatorname{GST\_Commit}$)

The transition proposal $P$ is submitted to the canonical database gateway as a **Governed State Transition (GST)**. The transition is evaluated by the atomic commit operator:

$$\operatorname{GST\_Commit}: \mathcal{P}(\mathcal{E}) \times \text{Proposals} \times \mathbb{T} \to \mathcal{P}(\mathcal{E}) \cup \{ \bot \}$$

which executes under an atomic database transaction at $t_{\text{commit}}$. If validation succeeds, the database state advances from $S_{t_{\text{commit}}^-}$ to $S_{t_{\text{commit}}^+}$; otherwise, the transaction is rejected ($\bot$) and rolls back completely with zero side-effects.

---

## 2. Formal Definition: Governance-Snapshot Atomicity (GSA)

Let $\mathcal{H} = (\mathcal{T}, <_{\mathcal{H}})$ be a transaction execution history, where $\mathcal{T} = \{ T_1, T_2, \dots, T_m \}$ is the set of all transactions (both AI agent proposals and concurrent human/external modifications), and $<_{\mathcal{H}}$ is the serialization partial order.

### Definition 1 (Governance-Snapshot Atomicity)

A transaction execution history $\mathcal{H}$ satisfies **Governance-Snapshot Atomicity (GSA)** if and only if for every committed transition proposal $P = \langle \Delta S, \operatorname{Deps}(P), \Sigma, \sigma \rangle$ submitted by an agent with snapshot compiled at $t_{\text{disclose}}$ and committed at $t_{\text{commit}}$, all four of the following invariants hold simultaneously:

```
                  ┌────────────────────────────────────────────────────────┐
                  │          GOVERNANCE-SNAPSHOT ATOMICITY (GSA)           │
                  └────────────────────────────────────────────────────────┘
                                              │
         ┌──────────────────┬─────────────────┴─────────────────┬──────────────────┐
         ▼                  ▼                                   ▼                  ▼
  (a) State          (b) Governance                      (c) Temporal       (d) Audit
      Isolation          Freshness                           Validity           Coupling
  ─────────────────  ─────────────────────────────────   ───────────────    ─────────────────
  ∀ e_k ∈ Deps(P):   v_c(u, t_commit) = v_c,obs          t_commit ≤         Commit(ΔS) ⟺
  V(e_k)_{t_commit}  ∧                                   t_expire           PersistAudit(
  = v_obs(e_k)       v_π(d, t_commit) = v_π,obs                             ⟨d_H, R_H, σ, t⟩)
```

---

### Invariant (a): State Isolation (Causal Read-Dependency Invariance)

No conflicting write $w(e_k)$ on any causal dependency entity $e_k \in \operatorname{Deps}(P)$ is serialized in $\mathcal{H}$ between snapshot disclosure time $t_{\text{disclose}}$ and transaction commit time $t_{\text{commit}}$:

$$\forall e_k \in \operatorname{Deps}(P), \quad \nexists w(e_k) \in \mathcal{H} \text{ such that } t_{\text{disclose}} <_{\mathcal{H}} w(e_k) <_{\mathcal{H}} t_{\text{commit}}$$

Equivalently, in terms of version vectors:

$$\forall e_k \in \operatorname{Deps}(P), \quad V(e_k)_{t_{\text{commit}}} = v_{\text{obs}}(e_k)$$

*Violation Condition:* If a concurrent transaction $T_{\text{ext}}$ writes to entity $e_1 \in \operatorname{Deps}(P)$ at $t_{\text{int}} \in (t_{\text{disclose}}, t_{\text{commit}})$, advancing $v(e_1)$ from $2 \to 3$, then $\operatorname{GST\_Commit}(P)$ must abort with a `stale_state_version_conflict`.

---

### Invariant (b): Governance Freshness (Policy and Consent Stability)

No governance mutation $\mathcal{G}_{\text{mut}}$ modifying the patient's consent epoch $v_c(u)$ or the domain policy epoch $v_\pi(d)$ is serialized in $\mathcal{H}$ between $t_{\text{disclose}}$ and $t_{\text{commit}}$:

$$\nexists \mathcal{G}_{\text{mut}} \in \mathcal{H} \text{ such that } t_{\text{disclose}} <_{\mathcal{H}} \mathcal{G}_{\text{mut}} <_{\mathcal{H}} t_{\text{commit}}$$

Equivalently:

$$v_c(u, t_{\text{commit}}) = v_{c,\text{obs}} \quad \land \quad v_\pi(d, t_{\text{commit}}) = v_{\pi,\text{obs}}$$

*Violation Condition:* If the patient revokes consent for `self_care` at $t_{\text{revoke}} \in (t_{\text{disclose}}, t_{\text{commit}})$, advancing $v_c(u)$ from $7 \to 8$, or if a clinical policy rule is updated advancing $v_\pi(d)$ from $3 \to 4$, then $\operatorname{GST\_Commit}(P)$ must abort with `governance_epoch_drift` or `consent_revoked_during_inference`.

---

### Invariant (c): Temporal Validity (Lease Enclosure)

The physical serialization time $t_{\text{commit}}$ must not exceed the authorization lease expiry timestamp $t_{\text{expire}}$ established in snapshot $\Sigma$:

$$t_{\text{commit}} \le t_{\text{expire}}$$

*Violation Condition:* If long-running model reasoning or queuing delays cause inference to exceed $\Delta \tau_{\text{lease}}$, such that $t_{\text{commit}} > t_{\text{expire}}$, then $\operatorname{GST\_Commit}(P)$ must fail-closed with `authorization_lease_expired`.

---

### Invariant (d): Audit Coupling (Indivisible Cryptographic Commitment)

The physical mutation of clinical entities $\Delta S$ and the durable registration of the cryptographic audit witness tuple:

$$\mathcal{W}_{\text{audit}} = \langle d_H, R_H, \sigma, K_{\text{agent}}, \operatorname{Deps}(P), t_{\text{commit}} \rangle$$

are persisted **atomically within the same database commit**:

$$\operatorname{Commit}(\Delta S) \iff \operatorname{PersistCommitment}(\mathcal{W}_{\text{audit}})$$

$$\operatorname{Rollback}(\Delta S) \iff \operatorname{Rollback}(\mathcal{W}_{\text{audit}})$$

*Violation Condition:* It is physically impossible under any execution path or crash state for the database to contain the clinical mutation $\Delta S$ without the exact corresponding cryptographic audit witness $\mathcal{W}_{\text{audit}}$, or vice versa.

---

## 3. Protocol Mechanics and Unified Canonical Lock Hierarchy ($\mathcal{L}_{\text{canonical}}$)

To enforce Invariants (a)–(d) deterministically without deadlocks or phantom anomalies on append-only ledgers, the database engine enforces a **Unified Canonical Lock Hierarchy**.

### 3.1 The Append-Only Ledger Phantom Problem

Standard relational database systems (PostgreSQL, MySQL, Oracle) implementing row-level locking via `SELECT ... FOR UPDATE` suffer from the **Phantom Read / Phantom Insert Problem** when applied to immutable append-only governance ledgers:

1. Let user consent records live in an append-only ledger `user_consents`.
2. A transaction $T_{\text{GST}}$ reads the latest active consent row $r_k$ with `SELECT * FROM user_consents WHERE user_id = :uid ORDER BY id DESC LIMIT 1 FOR UPDATE`. This places an exclusive row lock on row $r_k$.
3. Concurrently, transaction $T_{\text{revoke}}$ executes `INSERT INTO user_consents (user_id, status, version) VALUES (:uid, 'revoked', k+1)`.
4. Because $T_{\text{revoke}}$ is inserting a **new** physical row $r_{k+1}$, standard row-level lock managers do not detect a conflict on $r_k$.
5. $T_{\text{revoke}}$ commits.
6. $T_{\text{GST}}$ proceeds to commit, falsely believing it held exclusive access to the subject's consent state, violating Invariant (b).

---

### 3.2 Canonical Lock Ordering Definition

To eliminate phantom governance races and guarantee deadlock-free serializability, every database transaction modifying or verifying state in GLHS must acquire locks according to the strict total order $\mathcal{L}_{\text{canonical}}$:

$$\mathcal{L}_{\text{canonical}} \triangleq \operatorname{PolicyAnchor}(d) \prec \operatorname{ProfileAndConsentAnchor}(u) \prec_{\text{lex}} \operatorname{EntityPartitions}(u, k) \prec \operatorname{LeaseState}(l)$$

```
               CANONICAL LOCK HIERARCHY (L_canonical)
               ══════════════════════════════════════
  
  Level 1: Policy Lock Anchor
           pg_advisory_xact_lock(hashtext('policy_epoch:' || domain))
           pg_advisory_xact_lock(hashtext('policy_epoch:__global__'))
                           │
                           ▼
  Level 2: Profile & Consent Lock Anchor
           pg_advisory_xact_lock(hashtext('phr_profile:' || profile_id))
           pg_advisory_xact_lock(hashtext('user_consent:' || user_id))
           SELECT id FROM phr_profiles WHERE id = :profile_id FOR UPDATE
           SELECT id FROM users WHERE id = :user_id FOR UPDATE
                           │
                           ▼
  Level 3: Entity Partitions (Strict Lexicographical Order)
           ∀ (domain, semantic_key) ∈ Deps(P) sorted by (domain, key):
               SELECT * FROM glhs_entity_version_partitions
               WHERE profile_id = :pid AND domain = :dom AND semantic_key = :k
               FOR UPDATE
                           │
                           ▼
  Level 4: Authorization Lease & Dynamic Context
           Acquire in-memory / row-level Wound-Wait dynamic lease
```

---

### 3.3 The $\operatorname{GST\_Commit}$ Verification Algorithm

```text
Algorithm 1: Governed State Transition Commit (GST_Commit)
Input: Database Session db, Proposal P = ⟨ΔS, Deps(P), Σ, σ⟩, System Clock t_now
Output: Success(TransitionRecord) or Abort(ErrorCode)

1:  Begin Database Transaction Tx
2:  // Phase 1: Lock Acquisition under L_canonical
3:  AcquirePolicyLockAnchor(db, P.domain)
4:  AcquireProfileAndConsentAnchor(db, P.profile_id)
5:  
6:  // Phase 2: Temporal Lease Verification (Invariant c)
7:  t_commit ← CurrentSystemTimestamp()
8:  if t_commit > P.Σ.t_expire then
9:      Rollback Tx
10:     return Abort("authorization_lease_expired")
11: end if
12: 
13: // Phase 3: Cryptographic Witness Verification (Invariant d)
14: expected_d_H ← Hash(CanonicalJSON(P.Σ))
15: if P.Σ.d_H ≠ expected_d_H then
16:     Rollback Tx
17:     return Abort("snapshot_digest_mismatch")
18: end if
19: if not VerifySignature(K_agent, P.σ, Hash(ΔS ∥ Deps(P) ∥ P.Σ.d_H ∥ P.Σ.R_H)) then
20:     Rollback Tx
21:     return Abort("invalid_agent_cryptographic_signature")
22: end if
23: 
24: // Phase 4: Governance Freshness Verification (Invariant b)
25: v_π_current ← QueryEffectivePolicyEpoch(db, P.domain, for_update=True)
26: v_c_current ← QueryEffectiveConsentEpoch(db, P.profile.user_id, P.purpose, for_update=True)
27: if v_π_current ≠ P.Σ.v_π_obs then
28:     Rollback Tx
29:     return Abort("governance_policy_epoch_drift")
30: end if
31: if v_c_current ≠ P.Σ.v_c_obs then
32:     Rollback Tx
33:     return Abort("consent_epoch_drift_or_revoked")
34: end if
35: 
36: // Phase 5: Entity Partition Locks and State Isolation (Invariant a)
37: sorted_partitions ← SortLexicographically(Deps(P) ∪ Targets(ΔS))
38: for each (domain, key) in sorted_partitions do
39:     partition ← LockEntityPartition(db, P.profile_id, domain, key, for_update=True)
40:     if (domain, key) ∈ Deps(P) then
41:         if partition.state_version ≠ P.Σ.V_obs(domain, key) then
42:             Rollback Tx
43:             return Abort("stale_entity_state_version_conflict")
44:         end if
45:     end if
46: end for
47: 
48: // Phase 6: Atomic State Mutation & Audit Commitment (Invariant d)
49: for each (domain, key, new_val, T_v) in ΔS do
50:     AdvancePartitionVersion(db, partition)
51:     PersistEntityState(db, domain, key, new_val, T_v, t_k = t_commit)
52: end for
53: AdvanceGlobalProfileStateVersion(db, P.profile_id)
54: audit_row ← PersistAuditWitness(db, ⟨P.Σ.d_H, P.Σ.R_H, P.σ, K_agent, Deps(P), t_commit⟩)
55: Commit Tx
56: return Success(audit_row)
```

---

## 4. Comprehensive Comparison with Existing Paradigms

| Feature / Guarantee | PostgreSQL SSI (Cahill et al. 2008) | Google Zanzibar (Tang et al. 2019) | HL7 FHIR REST (`If-Match` / ETag) | OPA / AWS Cedar Policy Engines | **Governance-Snapshot Atomicity (GSA)** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Concurrency Mechanism** | SIREAD locks & `rw`-antidependency cycle detection | Snapshot reads with Zookies & Spanner TrueTime | Single-resource Optimistic Concurrency Control (OCC) | Stateless / External policy cache | **Strict Strong 2PL + Stable Governance Anchors** |
| **Governance Mutation Tracking** | ❌ None (treats consent/policy tables as generic data) | ⚠️ ACL snapshot evaluation (decoupled from commit) | ❌ None (application-level logic only) | ⚠️ Evaluated at request gate (decoupled from DB commit) | **✅ First-Class Consent/Policy Epoch Tracking** |
| **Cross-Resource Causal Isolation** | ✅ Full serializability for database row operations | ❌ Read-only ACL check; no data write atomicity | ❌ Coarse single-resource; no cross-resource multi-entity atomicity | ❌ None | **✅ Multi-Entity DAG Read-Dependency Isolation** |
| **Inference Window Protection** | ❌ Aborts on `rw`-conflict; no explicit lease bounding | ❌ No write transaction coupling | ❌ Fails on single-row ETag mismatch only | ❌ Vulnerable to Time-of-Check to Time-of-Use (TOCTOU) | **✅ Epistemic Lease Interval $\tau = [t_{\text{start}}, t_{\text{expire}}]$** |
| **Append-Only Phantom Defense** | ⚠️ Relies on predicate index locks (fails on unindexed appends) | ⚠️ Snapshot consistency only | ❌ None | ❌ None | **✅ Stable Transactional Advisory Lock Anchors** |
| **Cryptographic Audit Coupling** | ❌ None (audit logging is independent or deferred) | ❌ Audit logs external to Spanner transaction | ❌ Provenance resource created via separate REST calls | ❌ Logs evaluation decision outside data write | **✅ Indivisible Atomic WAL Persistence $\langle \Delta S, \mathcal{W}_{\text{audit}} \rangle$** |
| **Merkle Evidence Integrity** | ❌ None | ❌ None | ❌ None | ❌ None | **✅ Merkle Root $R_H$ & Snapshot Digest $d_H$ Binding** |

---

### Detailed Architectural and Theoretical Distinctions

#### 1. PostgreSQL SSI (Serializable Snapshot Isolation)
PostgreSQL SSI detects conflicts by tracking `SIREAD` locks on data pages and identifying cycles in the serialization graph ($T_1 \xrightarrow{rw} T_2 \xrightarrow{rw} T_1$). However:
- **Semantic Blindness:** SSI only tracks physical tuples accessed within an active SQL transaction. Because an AI agent's inference window $[t_{\text{disclose}}, t_{\text{commit}}]$ spans seconds to minutes, holding open an active PostgreSQL SSI transaction during inference causes severe table-level `SIREAD` lock bloat, phantom aborts, and catastrophic performance degradation.
- **External Governance Invisibility:** If consent is revoked via an external transaction that inserts into `user_consents`, an SSI transaction reading data rows will commit without detecting a conflict because no `rw`-antidependency was established on the consent tuple.

#### 2. Google Zanzibar
Google Zanzibar provides planetary-scale authorization consistency using **Zookies** (consistent snapshot tokens containing Spanner TrueTime timestamps $t_{\text{auth}}$). However:
- **Write Decoupling:** Zanzibar only answers authorization queries ($\text{check}(u, \text{relation}, o)$). It is completely decoupled from the underlying storage engine performing the data mutation.
- **TOCTOU Gap:** If Zanzibar verifies that agent $A$ is authorized to modify patient record $R$ at $t_1$, patient consent may be revoked at $t_2$, and the agent commits the physical write to a distinct database at $t_3$. Zanzibar cannot abort the write at $t_3$ inside the relational database transaction.

#### 3. HL7 FHIR RESTful Architecture
HL7 FHIR relies on HTTP `ETag` and `If-Match` headers for OCC:
- **Single-Resource Bound:** ETags protect single resources (e.g., `Patient/123`). An AI inference step consuming 40 distinct clinical assertions (`Observation`, `Condition`, `MedicationRequest`) cannot atomically validate 40 ETags and persist 5 modified resources in a single atomic FHIR REST invocation without custom proprietary orchestrators.
- **Lack of Governance Epochs:** FHIR `Consent` resources have no atomic transactional binding to individual REST write operations on `Condition` or `MedicationStatement`.

#### 4. OPA (Open Policy Agent) / AWS Cedar
OPA and AWS Cedar evaluate fine-grained authorization policies:
- **Out-of-Band Evaluation:** Authorization occurs at the API gateway layer prior to database transaction dispatch.
- **Uncoupled Execution:** Between the moment OPA approves a request ($\text{Decision} = \text{ALLOW}$) and the execution of the database transaction, the policy or patient consent may have mutated, introducing an unbridgeable TOCTOU race condition.

---

## 5. Theoretical Foundations and Formal Proofs

### Theorem 1 (Correctness & Deadlock Freedom under SS2PL with $\mathcal{L}_{\text{canonical}}$)

Let $\mathcal{T}$ be a set of concurrently executing transactions in GLHS, consisting of arbitrary mixtures of:
- Governed State Transitions $\operatorname{GST\_Commit}(P_i)$,
- Consent Mutations $\operatorname{MutateConsent}(u)$,
- Policy Epoch Advances $\operatorname{AdvancePolicy}(d)$, and
- Direct Clinical Writes $\operatorname{WriteEntity}(e_k)$.

If all transactions acquire locks strictly in accordance with $\mathcal{L}_{\text{canonical}}$ under Strict Strong Two-Phase Locking (SS2PL), then:
1. Every committed execution history $\mathcal{H}$ satisfies Governance-Snapshot Atomicity (GSA).
2. The system is provably free of deadlocks ($\operatorname{Cycle}(\mathcal{W}) = \emptyset$, where $\mathcal{W}$ is the transaction wait-for graph).

---

#### Proof of Theorem 1

##### Part 1: Invariant Preservation (GSA Correctness)

We prove that under $\mathcal{L}_{\text{canonical}}$, no transaction violating Invariants (a), (b), (c), or (d) can commit.

1. **Proof of Invariant (a) [State Isolation]:**
   - Suppose, for contradiction, that a transition proposal $P$ commits at $t_{\text{commit}}$, but there exists an entity $e_k \in \operatorname{Deps}(P)$ such that a concurrent transaction $T_{\text{ext}}$ executed $w(e_k)$ serialized at $t_{\text{ext}} \in (t_{\text{disclose}}, t_{\text{commit}})$.
   - By protocol definition, $T_{\text{ext}}$ acquired an exclusive lock on $\operatorname{EntityPartition}(u, e_k)$ and incremented $v(e_k)$ from $v_0 \to v_1$ ($v_1 > v_0$).
   - When $\operatorname{GST\_Commit}(P)$ executes, Line 39 of Algorithm 1 acquires an exclusive row lock on $\operatorname{EntityPartition}(u, e_k)$ via `SELECT ... FOR UPDATE`.
   - Line 41 verifies $\operatorname{partition.state\_version} = v_{\text{obs}}(e_k)$.
   - Since $T_{\text{ext}}$ committed, the database reads $v_1$. But $v_{\text{obs}}(e_k) = v_0 \ne v_1$.
   - The condition at Line 41 evaluates to false, causing the transaction to execute `Rollback Tx` and abort at Line 43.
   - This contradicts the assumption that $P$ committed. Thus, Invariant (a) holds.

2. **Proof of Invariant (b) [Governance Freshness & Phantom Freedom]:**
   - Suppose a consent mutation transaction $T_{\text{consent}}$ revokes consent at $t_{\text{mut}} \in (t_{\text{disclose}}, t_{\text{commit}})$.
   - Under $\mathcal{L}_{\text{canonical}}$, $T_{\text{consent}}$ MUST acquire $\operatorname{ProfileAndConsentAnchor}(u)$ before inserting or modifying rows in `user_consents`.
   - $\operatorname{GST\_Commit}(P)$ also acquires $\operatorname{ProfileAndConsentAnchor}(u)$ at Line 4 before evaluating active consent.
   - By the mutual exclusion property of transactional advisory locks and row locks on `phr_profiles`, $T_{\text{consent}}$ and $\operatorname{GST\_Commit}(P)$ cannot execute concurrently in their critical sections.
   - If $T_{\text{consent}}$ serializes before $\operatorname{GST\_Commit}(P)$, then when $\operatorname{GST\_Commit}(P)$ reads the consent epoch at Line 26 under the lock, it observes $v_{c,\text{current}} = v_{c,\text{obs}} + 1$. Line 31 evaluates to true and executes `Rollback Tx`, aborting the transition.
   - If $T_{\text{consent}}$ attempts to serialize after $\operatorname{GST\_Commit}(P)$, it is blocked until $\operatorname{GST\_Commit}(P)$ commits.
   - Thus, no governance mutation can interleave undetected. Phantom inserts are strictly prevented by the stable lock anchor. Invariant (b) holds.

3. **Proof of Invariant (c) [Temporal Validity]:**
   - Direct from Line 8 of Algorithm 1: If $t_{\text{commit}} > t_{\text{expire}}$, the transaction unconditionally aborts. Invariant (c) holds.

4. **Proof of Invariant (d) [Audit Coupling]:**
   - In Algorithm 1, Lines 49–54 execute inside a single relational database transaction `Tx`.
   - By the Atomicity and Durability (ACID) properties of the database engine (enforced via the Write-Ahead Log), either both the entity mutations $\Delta S$ (Line 51) and the audit witness record $\mathcal{W}_{\text{audit}}$ (Line 54) are flushed to durable storage, or neither is. Invariant (d) holds.

---

##### Part 2: Deadlock Freedom

Let $\mathcal{W} = (V_{\mathcal{W}}, E_{\mathcal{W}})$ be the directed Wait-For Graph, where vertices $V_{\mathcal{W}} = \mathcal{T}$ represent active transactions, and a directed edge $(T_1 \to T_2) \in E_{\mathcal{W}}$ exists if and only if $T_1$ is blocked waiting for a lock held by $T_2$.

1. A deadlock exists if and only if $\mathcal{W}$ contains a directed cycle:
   $$T_1 \to T_2 \to \dots \to T_k \to T_1$$
2. Define the lock mapping function $\lambda: \text{Locks} \to \mathbb{N}$ mapping every lock in the system to a discrete integer representing its position in the strict total order $\mathcal{L}_{\text{canonical}}$:
   - For all Policy Anchors: $\lambda(\operatorname{PolicyAnchor}(d)) = 1000 + \operatorname{hash}(d)$.
   - For all Profile Anchors: $\lambda(\operatorname{ProfileAnchor}(u)) = 2000 + u$.
   - For all Entity Partitions: $\lambda(\operatorname{Partition}(u, \text{dom}, k)) = 3000 + \operatorname{rank}_{\text{lex}}(u, \text{dom}, k)$.
   - For all Lease States: $\lambda(\operatorname{LeaseState}(l)) = 4000 + l$.
3. Under the $\mathcal{L}_{\text{canonical}}$ protocol, every transaction $T_i \in \mathcal{T}$ acquires locks in strictly monotonically increasing order of $\lambda$:
   $$\forall T_i, \quad \text{if } T_i \text{ requests lock } L_b \text{ while holding } L_a, \text{ then } \lambda(L_a) < \lambda(L_b)$$
4. Suppose there exists a cycle $T_1 \to T_2 \to \dots \to T_k \to T_1$.
   - $T_1 \to T_2 \implies \lambda(\text{held by } T_2) < \lambda(\text{requested by } T_1)$.
   - Transitivity across the cycle implies $\lambda(L_1) < \lambda(L_2) < \dots < \lambda(L_k) < \lambda(L_1)$, meaning $\lambda(L_1) < \lambda(L_1)$, which is a contradiction.
5. Therefore, $\mathcal{W}$ is an acyclic directed graph ($\operatorname{Cycle}(\mathcal{W}) = \emptyset$), and the system is provably deadlock-free. $\blacksquare$

---

### Theorem 2 (Crash-Recovery & Epistemic Atomicity under WAL / ARIES)

Let the storage subsystem implement Write-Ahead Logging (WAL) under ARIES recovery principles (repeating history during Redo, rolling back uncommitted transactions during Undo).

Under arbitrary crash failure at any physical timestamp $t_{\text{crash}}$, the system satisfies **Epistemic Atomicity**:
1. No uncommitted or partially applied transition proposal $P$ is ever visible in recovered state $S_{\text{recovered}}$.
2. Every committed transition proposal $P$ in $S_{\text{recovered}}$ possesses an immutable, complete audit record $\mathcal{W}_{\text{audit}}$ containing the exact cryptographic hash $d_H$ and Merkle root $R_H$.

---

#### Proof of Theorem 2

1. **Log Record Structure:**
   Every $\operatorname{GST\_Commit}(P)$ operation writes the following sequence of atomic WAL records:
   $$\operatorname{WAL}_1 = \langle \text{BEGIN\_XACT}, T_{\text{gst}}, t_{\text{commit}} \rangle$$
   $$\operatorname{WAL}_{2,k} = \langle \text{UPDATE}, T_{\text{gst}}, \operatorname{Table}(e_k), \text{old\_val}_k, \text{new\_val}_k \rangle \quad \forall e_k \in \operatorname{Targets}(\Delta S)$$
   $$\operatorname{WAL}_3 = \langle \text{INSERT}, T_{\text{gst}}, \text{glhs\_audit\_witness}, \mathcal{W}_{\text{audit}} \rangle$$
   $$\operatorname{WAL}_4 = \langle \text{COMMIT\_XACT}, T_{\text{gst}}, \text{LSN}_{\text{flush}} \rangle$$

2. **Case Analysis over Failure Points:**
   - **Case 1: Crash occurs before $\operatorname{WAL}_4$ reaches non-volatile storage ($t_{\text{crash}} < \text{Flush}(\operatorname{WAL}_4)$).**
     - During ARIES Analysis Phase, $T_{\text{gst}}$ is classified as an active (uncommitted) loser transaction.
     - During Redo Phase, logged changes up to the crash are rolled forward to restore page consistency.
     - During Undo Phase, the engine traverses backward along $\text{PrevLSN}$ and reverses every mutation $\operatorname{WAL}_{2,k}$ and $\operatorname{WAL}_3$, restoring all entity versions to $v_{\text{obs}}(e_k)$ and removing any partial audit entries.
     - State is identical to pre-transition state.
   - **Case 2: Crash occurs after $\operatorname{WAL}_4$ is durably flushed ($t_{\text{crash}} \ge \text{Flush}(\operatorname{WAL}_4)$).**
     - During Analysis Phase, $T_{\text{gst}}$ is identified as committed.
     - During Redo Phase, all updates $\Delta S$ and the insertion of $\mathcal{W}_{\text{audit}}$ are redone to disk pages if not already flushed.
     - $T_{\text{gst}}$ is not undone.
     - Both $\Delta S$ and $\mathcal{W}_{\text{audit}}$ are present and consistent in $S_{\text{recovered}}$.

3. Thus, Epistemic Atomicity is preserved across all crash trajectories. $\blacksquare$

---

### Theorem 3 (Cryptographic Non-Forgeability & Tamper Resistance)

Let $\lambda \in \mathbb{N}$ be the cryptographic security parameter. Let the hash function $\mathbb{H}$ be collision-resistant and the signature scheme $\Sigma_{\text{sig}}$ be EUF-CMA secure.

The probability that an adversary $\mathcal{A}$ running in Probabilistic Polynomial Time (PPT) can cause the database engine to commit a transition $P^*$ such that:
1. $P^*$ was not generated by an authorized agent holding $K_{\text{agent}}$, or
2. $P^*$ mutates state based on tampered evidence not present in snapshot $\Sigma$,

is bounded by a negligible function in $\lambda$:

$$\Pr[\operatorname{GST\_Commit}(P^*) = \text{Success} \mid P^* \text{ forged or tampered}] \le \operatorname{negl}(\lambda)$$

---

#### Proof of Theorem 3

We model the verification as an adversarial game between Challenger $\mathcal{C}$ and PPT Adversary $\mathcal{A}$:

1. **Game Setup:**
   - $\mathcal{C}$ runs $\operatorname{KeyGen}(1^\lambda) \to (K_{\text{agent}}, K_{\text{agent}}^{\text{pub}})$.
   - $\mathcal{C}$ initializes snapshot $\Sigma = \langle S_{\text{obs}}, V_{\text{obs}}, v_{c,\text{obs}}, v_{\pi,\text{obs}}, \tau, d_H, R_H \rangle$ and gives $\Sigma$ and $K_{\text{agent}}^{\text{pub}}$ to $\mathcal{A}$.
   - $\mathcal{A}$ has access to a signing oracle $\mathcal{O}_{\text{sign}}(\cdot)$ simulating legitimate agent runs.

2. **Adversarial Objectives:**
   $\mathcal{A}$ wins if it outputs a proposal $P^* = \langle \Delta S^*, \operatorname{Deps}^*, \Sigma^*, \sigma^* \rangle$ such that $\operatorname{GST\_Commit}(P^*) = \text{Success}$ and either:
   - **Event $E_1$ (Signature Forgery):** $\sigma^*$ is valid under $K_{\text{agent}}^{\text{pub}}$ for a payload $\Delta S^*$ never submitted to $\mathcal{O}_{\text{sign}}$.
   - **Event $E_2$ (Evidence Tampering / Snapshot Collision):** $\Sigma^*$ uses altered evidence $\mathcal{E}^* \ne \mathcal{E}_{\text{disclose}}$ but yields $\mathbb{H}(\Sigma^*) = d_H$ or $\operatorname{MerkleTree}(\mathcal{E}^*) = R_H$.

3. **Probability Bound:**
   $$\Pr[\mathcal{A} \text{ wins}] \le \Pr[E_1] + \Pr[E_2]$$
   - By the EUF-CMA security of $\Sigma_{\text{sig}}$:
     $$\Pr[E_1] = \operatorname{Adv}_{\Sigma_{\text{sig}}}^{\text{EUF-CMA}}(\mathcal{A}) \le \operatorname{negl}_1(\lambda)$$
   - By the collision resistance of $\mathbb{H}$ and the Merkle tree construction:
     $$\Pr[E_2] = \operatorname{Adv}_{\mathbb{H}}^{\text{CR}}(\mathcal{A}) \le \operatorname{negl}_2(\lambda)$$
   - Combining both bounds:
     $$\Pr[\mathcal{A} \text{ wins}] \le \operatorname{negl}_1(\lambda) + \operatorname{negl}_2(\lambda) = \operatorname{negl}(\lambda)$$

4. Thus, the cryptographic witness mechanism guarantees that no unauthorized or tampered transition proposal can pass $\operatorname{GST\_Commit}$. $\blacksquare$

---

## 6. Implementation Mapping and Architecture in CLARA-Care

The mathematical specification of GSA is implemented directly in the `services/api` layer of CLARA-Care. The table below provides the direct mapping from theoretical constructs to production database tables and code modules:

| Mathematical Construct | Symbolic Notation | PostgreSQL Table / Column | Python Implementation Reference |
| :--- | :--- | :--- | :--- |
| **Profile State Anchor** | $S, V$ | `phr_profiles.id`, `glhs_state_versions` | `clara_api.glhs.lock_hierarchy.acquire_profile_and_consent_anchor` |
| **Entity Partition** | $e_k, v(e_k)$ | `glhs_entity_version_partitions` | `clara_api.glhs.lock_hierarchy.lock_entity_partitions` |
| **Policy Epoch** | $v_\pi(d)$ | `governance_policy_epochs.version` | `clara_api.glhs.lock_hierarchy.acquire_policy_lock_anchor` |
| **Consent Epoch** | $v_c(u)$ | `user_consents.version`, `user_consents.status` | `clara_api.glhs.gateway._governed_consent_version` |
| **Task Snapshot** | $\Sigma$ | `glhs_snapshot_manifests` | `clara_api.glhs.commitment_gateway.validate_snapshot_manifest` |
| **Snapshot Digest** | $d_H$ | `glhs_snapshot_manifests.manifest_digest` | `clara_api.glhs.commitment_gateway._canonical_digest` |
| **Evidence Merkle Root** | $R_H$ | `glhs_inference_context_bindings.evidence_set_digest` | `clara_api.glhs.commitment_gateway.validate_exact_disclosure_dependency` |
| **Transition Proposal** | $P$ | `glhs_clinical_commitment_proposals` | `clara_api.glhs.commitment_gateway.create_commitment_proposal` |
| **Audit Witness** | $\mathcal{W}_{\text{audit}}$ | `glhs_clinical_commitment_transitions` | `clara_api.glhs.commitment_gateway.apply_commitment_transition` |
| **Atomic Commit Gate** | $\operatorname{GST\_Commit}$ | Single Database Transaction (`Session.commit`) | `clara_api.glhs.gateway.apply_transition` |

---

## 7. Verification and Audit Checklist

For any new service, agent, or gateway interacting with GLHS, the following invariants must be verified via property-based and concurrency tests:

- [x] **Strict Lock Acquisition Order:** All writes acquire locks in strict $\mathcal{L}_{\text{canonical}}$ order:
  $$\operatorname{PolicyAnchor} \prec \operatorname{ProfileAnchor} \prec_{\text{lex}} \operatorname{EntityPartitions} \prec \operatorname{LeaseState}$$
- [x] **Advisory Lock Phantom Defense:** Append-only tables (`user_consents`, `governance_policy_epochs`) are guarded by transactional advisory locks (`pg_advisory_xact_lock`).
- [x] **Re-check under Lock:** Current policy epoch and consent status are re-queried with `FOR UPDATE` semantics *after* lock acquisition.
- [x] **Hard Lease Rejection:** Transactions where $t_{\text{commit}} > t_{\text{expire}}$ are rejected fail-closed before entity mutation.
- [x] **Atomic Audit Flush:** State mutation and audit record insertion are executed in the identical SQLAlchemy database session commit.
