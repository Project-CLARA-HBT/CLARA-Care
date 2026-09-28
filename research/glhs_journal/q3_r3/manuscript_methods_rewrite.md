# Governed Read-to-Write Continuity (GRWC) for Longitudinal Health AI: Systems & Formal Methods Architecture

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Module:** `services/api/src/clara_api/glhs/` (`commit_kernel.py`, `lock_hierarchy.py`, `dependency_contract.py`, `commitment_gateway.py`, `canonical_json.py`, `gateway.py`)  
**Author / Curator:** Agent B — Systems & Formal Architecture  
**Status:** Frozen Phase 10 Manuscript Methods Specification  
**Date:** Tue Sep 29 2026  
**Contract Version:** `clara.inference-envelope.v1` / `dependency-contract.v1` / `clara.canonical-json.v2-rfc8785`  

---

## 1. Introduction & Formal Problem Formulation

In clinical AI decision support systems, non-deterministic Large Language Model (LLM) agents perform goal-directed reasoning over bounded snapshots of patient health data. Existing agent implementations decouple the moment of health state retrieval ($t_{\text{snap}}$) and model prompt dispatch ($t_{\text{dispatch}}$) from the moment a persistent health state proposal is admitted to database storage ($t_c$).

This decoupling introduces three fundamental failure modes:
1. **Context & State Drift:** Underlying clinical observations, medications, or lab values mutate between $t_{\text{snap}}$ and $t_c$, rendering the agent's inference stale or contradictory under active database state $S(t_c)$.
2. **Governance Drift & Consent Revocation:** Active policy epochs, actor role credentials, or patient consent directives mutate between $t_{\text{snap}}$ and $t_c$, allowing proposals generated under revoked consent to commit unnoticed under active governance $G(t_c)$.
3. **Proposal Laundering & Downgrade Attacks:** Model outputs strip provenance headers, omit mandatory causal read/write dependencies to bypass Optimistic Concurrency Control (OCC) validation, or downgrade snapshot-bound proposals to base-version-only write paths to bypass snapshot verification.

GLHS R3 resolves these vulnerabilities by formalizing and operationalizing **Governed Read-to-Write Continuity (GRWC)** (also termed **Exact-Disclosure Admission**). Under GRWC, an AI-generated mutation proposal $P$ is admitted at time $t_c$ if and only if it remains verifiably continuous with the exact governed disclosure supplied to the model inference lineage that produced it, while current state, active governance, and schema-derived dependencies are independently revalidated within the exact same database transaction under canonical PostgreSQL locks.

---

## 2. Formal Mathematical Predicate of GRWC Admission

Let:
* $\mathcal{H}$: Governed Disclosure Object (containing bounded health projections, evidence manifests, policy versions, actor credentials, purpose, task, and valid intervals).
* $\mathcal{I}$: Server-owned, append-only Inference Context Binding record (`GlhsInferenceContextBinding`).
* $P$: Persistent mutation proposal object (`GlhsClinicalCommitmentProposal`).
* $D_{\text{prop}}$: Proposed dependency vector attached to proposal $P$.
* $D_{\text{min}}(\text{Op}, \mathcal{S})$: Deterministic, schema-derived minimum dependency set for operation $\text{Op}$ over scope $\mathcal{S}$.
* $S(t)$: Comprehensive database clinical entity state at time $t$.
* $G(t)$: Dynamic system governance state (policy epoch, active patient consent, actor authorization) at time $t$.
* $t_c$: Timestamp of atomic database write transaction execution.

The formal GRWC admission predicate $\text{Admit}(P, t_c)$ evaluates to $\text{TRUE}$ if and only if all seven underlying conditions hold simultaneously:

$$\begin{aligned}
\text{Admit}(P, t_c) \iff & \text{ValidLineage}(P) \\
& \land \text{AntiDowngrade}(P) \\
& \land \text{ContinuousDisclosure}(P, \mathcal{H}, \mathcal{I}) \\
& \land \text{StateCurrent}(P, S(t_c)) \\
& \land \text{GovCurrent}(P, G(t_c)) \\
& \land \text{DepsComplete}(P) \\
& \land \text{EvidenceCovered}(P, \mathcal{H})
\end{aligned}$$

### 2.1 Sub-Predicate Mathematical Specifications

1. **Acyclic Bounded Lineage ($\text{ValidLineage}(P)$):**
   $$\begin{aligned}
   \text{ValidLineage}(P) \iff & \text{Depth}(P) \le \text{MAX\_DEPTH} (4) \land \text{Acyclic}(\text{Lineage}(P)) \\
   & \land \left(P.\text{reviewed\_proposal\_id} \neq \bot \implies P.\text{inference\_binding\_id} = \text{Root}(P).\text{inference\_binding\_id}\right)
   \end{aligned}$$

2. **Anti-Downgrade Invariant ($\text{AntiDowngrade}(P)$):**
   $$\begin{aligned}
   \text{AntiDowngrade}(P) \iff & \left(P.\text{origin} = \text{"model"} \implies P.\text{context\_binding\_mode} = \text{"snapshot\_bound"}\right) \\
   & \land \left(\mathcal{I}_{\text{root}}.\text{consumed\_thss} = \text{True} \implies P.\text{context\_binding\_mode} = \text{"snapshot\_bound"}\right)
   \end{aligned}$$

3. **Continuous Exact Disclosure ($\text{ContinuousDisclosure}(P, \mathcal{H}, \mathcal{I})$):**
   $$\begin{aligned}
   \text{ContinuousDisclosure}(P, \mathcal{H}, \mathcal{I}) \iff & \mathcal{I}.\text{status} = \text{"COMPLETED"} \\
   & \land P.\text{source\_snapshot\_id} = \mathcal{I}.\text{source\_snapshot\_id} = \mathcal{H}.\text{id} \\
   & \land P.\text{source\_snapshot\_digest} = \mathcal{I}.\text{source\_manifest\_digest} = \mathcal{H}.\text{manifest\_digest} \\
   & \land \mathcal{I}.\text{projection\_digest} = \text{SHA-256}\left(\text{JCS}\left(\mathcal{H}.\text{model\_visible\_projection}\right)\right) \\
   & \land \mathcal{I}.\text{request\_envelope\_digest} = \text{SHA-256}\left(\text{JCS}\left(\text{Envelope}\right)\right)
   \end{aligned}$$

4. **Fresh Clinical State ($\text{StateCurrent}(P, S(t_c))$):**
   $$\text{StateCurrent}(P, S(t_c)) \iff \forall d \in D_{\text{prop}} \cap \text{Entities}: d.v_{\text{obs}} = S(t_c)[d.k].v_{\text{current}} \land d.\delta_{\text{obs}} = S(t_c)[d.k].\delta_{\text{current}}$$

5. **Fresh Governance & Consent ($\text{GovCurrent}(P, G(t_c))$):**
   $$\begin{aligned}
   \text{GovCurrent}(P, G(t_c)) \iff & P.\text{expected\_policy\_version} = G(t_c).\text{policy\_epoch}[\text{domain}] \\
   & \land P.\text{expected\_consent\_version} = G(t_c).\text{consent\_version}[\text{user\_id}] \\
   & \land G(t_c).\text{consent\_status}[\text{user\_id}] = \text{"GRANTED"}
   \end{aligned}$$

6. **Schema-Derived Dependency Completeness ($\text{DepsComplete}(P)$):**
   $$\text{DepsComplete}(P) \iff D_{\text{min}}(\text{Op}, \mathcal{S}) \subseteq D_{\text{prop}}$$

7. **Evidence Disclosure Closure ($\text{EvidenceCovered}(P, \mathcal{H})$):**
   $$\text{EvidenceCovered}(P, \mathcal{H}) \iff P.\text{asserted\_evidence\_ids} \subseteq \mathcal{H}.\text{disclosed\_evidence\_ids}$$

---

## 3. Two-Digest Model & Canonical Request Envelope (`clara.inference-envelope.v1`)

To eliminate ambiguity between snapshot creation at $t_{\text{snap}}$ and LLM execution at $t_{\text{dispatch}}$, GLHS R3 enforces a two-digest cryptographic binding architecture anchored by the canonical request envelope `clara.inference-envelope.v1`.

### 3.1 Two-Digest Cryptographic Architecture

1. **Model-Visible Health Projection Digest ($H_{\text{proj}}$):**
   $$H_{\text{proj}} = \text{SHA-256}\left(\text{JCS}\left(\text{envelope.health\_state\_projection}\right)\right)$$
   Represents the exact health state data formatted for consumption by the LLM prompt. At commit time $t_c$, the kernel verifies that the proposal's cited binding contains a `projection_digest` equal to $H_{\text{proj}}$.

2. **Full Canonical Request Envelope Digest ($H_{\text{env}}$):**
   $$H_{\text{env}} = \text{SHA-256}\left(\text{JCS}\left(\text{clara.inference-envelope.v1}\right)\right)$$
   Represents the entire 5-partition server payload dispatched across the network, excluding dynamic authorization tokens, transport UUIDs, and network timestamps.

```text
+-----------------------------------------------------------------------------------+
|                        clara.inference-envelope.v1                                |
+-----------------------------------------------------------------------------------+
| 1. System Prompt Partition (system_prompt)                                        |
|    - prompt_template_version, system_prompt_version, base_system_prompt_digest   |
+-----------------------------------------------------------------------------------+
| 2. Health State Projection Partition (health_state_projection) [H_proj Target]    |
|    - profile_id, active_medications, conditions, labs, THSS manifest ref          |
+-----------------------------------------------------------------------------------+
| 3. Conversation Context Partition (conversation_context)                          |
|    - message_history: [{"role": "user"|"assistant", "content": "..."}]            |
+-----------------------------------------------------------------------------------+
| 4. Task Instructions Partition (task_instructions)                                |
|    - purpose, task, task_parameters, expected_output_schema                       |
+-----------------------------------------------------------------------------------+
| 5. Runtime Parameters Partition (runtime_parameters)                              |
|    - model_route, requested_model_id, provider, temperature, max_tokens           |
+-----------------------------------------------------------------------------------+
```

### 3.2 Partition Isolation Semantics

* **Partition 1 (`system_prompt`):** Seals system instructions, clinical safety rules, and role definitions. Any prompt template update alters $H_{\text{env}}$.
* **Partition 2 (`health_state_projection`):** Houses patient health state compiled from the Temporal Health State Snapshot (THSS). Serves as the target for $H_{\text{proj}}$.
* **Partition 3 (`conversation_context`):** Isolates dialogue turns to prevent historical conversation tampering from altering health projections.
* **Partition 4 (`task_instructions`):** Binds purpose (e.g. `treatment_planning`) and task (e.g. `reconcile_medication_order`). Prevents cross-task binding reuse.
* **Partition 5 (`runtime_parameters`):** Seals model parameters (`model_route`, `requested_model_id`, `temperature`), enabling deterministic audit of provider targets.

### 3.3 Server-Attested Binding Ledger (`GlhsInferenceContextBinding`)

Inference bindings are persisted in an append-only, server-owned relational ledger before provider dispatch:

```text
               +-----------------------------------+
               |               INIT                |
               |  (In-memory request construction) |
               +-----------------+-----------------+
                                 |
                                 |  create_inference_context_binding(status="PENDING")
                                 v
               +-----------------------------------+
               |              PENDING              |
               |  (Persisted pre-dispatch record)  |
               +--------+-----------------+--------+
                        |                 |
     finalize_...()     |                 |  fail_...() / timeout / abort
     (provider success) |                 |  (provider failure / error)
                        v                 v
     +--------------------+             +--------------------+
     |     COMPLETED      |             |  FAILED / ABORTED  |
     | (Terminal Success) |             |  (Terminal Failure)|
     +--------------------+             +--------------------+
```

* **ORM Immutability Listener (`_protect_glhs_inference_binding_content`):** Intercepts `before_update` on `GlhsInferenceContextBinding`. Allows modification ONLY to lifecycle fields (`status`, `reported_model_id`, `request_completed_at`, `response_digest`, `binding_digest`). Any attempt to alter $H_{\text{proj}}$, $H_{\text{env}}$, snapshot ID, actor, purpose, or task raises `ValueError("GLHS ledger rows are immutable...")`.
* **ORM Delete Guard (`_reject_glhs_ledger_mutation`):** Rejects `before_delete` events fail-closed.

---

## 4. 6-Phase Atomic Commit Kernel & 7-Class Lock Hierarchy

All GLHS clinical state transitions execute through `execute_atomic_glhs_commit()` in `services/api/src/clara_api/glhs/commit_kernel.py`. The kernel guarantees that revalidation, GRWC verification, domain writes, and CAS progression run atomically within a single PostgreSQL transaction.

### 4.1 The 6-Phase Atomic Commit Sequence

```text
+-------------------------------------------------------------------------------------------------+
|                                 GLHS R3 Transactional Boundary                                  |
+-------------------------------------------------------------------------------------------------+
|  Phase 1: Idempotency Pre-Check  --->  Phase 2: Canonical Lock Acquisition                     |
|                                        - Advisory Locks (Global Policy, Domain Policy, Idem Key)|
|                                        - Row Locks (User, Profile FOR SHARE; Partitions)        |
+-------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|  Phase 3: Centralized GRWC Admission Verifier (under PostgreSQL locks inside SAME transaction)   |
|  - evaluate_grwc_admission(db, profile_id, proposal_id, ...)                                    |
|  - Acyclic Lineage Traversal & Depth Guard (depth <= 4, cycle detection)                       |
|  - Immutable Lineage Chain (root_proposal_id, parent_proposal_id, inference_binding_id)         |
|  - Anti-Downgrade Enforcement (consumed_thss=True forbids context_binding_mode=base_version_only)|
|  - Exact Disclosure Continuity (source_snapshot_id & source_snapshot_digest matching)           |
|  - Governance & Review Authority Revalidation                                                   |
+-------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|  Phase 4: Domain Mutation Callback  --->  Phase 5: CAS Increment WRITE Partitions (v -> v + 1)  |
+-------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|  Phase 6: Applied Transition & Transactional Outbox Persistence (COMMITTED State Persisted)    |
+-------------------------------------------------------------------------------------------------+
```

#### Phase 1: Fast Idempotency Pre-Check
Queries `GlhsAppliedTransition` by `(tenant_id, operation_kind, idempotency_key)` or `proposal_id`.
* If matching record with identical `request_digest` exists $\implies$ return cached `GlhsCommitResult` (`idempotent_replay = True`).
* If `request_digest` differs $\implies$ abort with `GlhsInvariantError("idempotency_key_reused")`.

#### Phase 2: Canonical Lock Acquisition (7-Class Lock Hierarchy)
Acquires total-ordered advisory and row locks to eliminate deadlocks and prevent TOCTOU phantom drift.

#### Phase 3: Freshness & Centralized GRWC Admission Revalidation
Revalidates state, policy, consent, dependencies, evidence, and proposal lineage while holding PostgreSQL locks:
* `expected_base_state_version == current_version`
* `expected_policy_version == current_policy_version`
* `expected_consent_version == current_consent_version`
* Partition versions $v_{\text{obs}} == v_{\text{db}}$ and state digests match.
* Evidence interval `valid_from <= now <= valid_to` and `revoked_at IS NULL`.
* Executes `evaluate_grwc_admission(db, profile_id, proposal_id, ...)`.

#### Phase 4: Domain Mutation Callback Execution
Invokes `mutation_callback(commit_context)`, supplying `GlhsCommitContext` with verified `GrwcAdmissionResult`. Inserts domain version and transition rows (e.g. `GlhsClinicalCommitmentVersion`).

#### Phase 5: CAS Version Progression on Write Partitions
For each WRITE partition in lexicographical order:
$$v_{\text{succ}} = v_{\text{pred}} + 1$$
Executes `UPDATE glhs_entity_version_partitions SET state_version = :succ WHERE id = :id AND state_version = :pred`. Asserts `rowcount == 1`. If `0`, raises `GlhsInvariantError("cas_version_conflict")`. Persists `GlhsTransitionPartitionLink` linking predecessor and successor state digests.

#### Phase 6: Applied Transition & Outbox Persistence
Inserts `GlhsAppliedTransition` with status `"COMMITTED"`, computes final result digest, and emits outbox event `glhs.transition.applied` via `add_outbox()`.

---

### 4.2 7-Class Governance Lock Hierarchy (`lock_hierarchy.py`)

To guarantee strict total-order lock acquisition across all transactional write paths, locks are acquired in ascending order of class rank:

$$\text{Class 1} \prec \text{Class 2} \prec \text{Class 3} \prec \text{Class 4} \prec \text{Class 5} \prec \text{Class 6} \prec \text{Class 7}$$

| Class Rank | Lock Domain | Mechanism & SQL Execution | Purpose & Target |
| :---: | :--- | :--- | :--- |
| **Class 1** | Tenant / Global Policy | `pg_advisory_xact_lock_shared(h(tenant))` | Serializes global policy advances against transaction validation. |
| **Class 2** | Domain Policy Anchor | `pg_advisory_xact_lock_shared(h("policy_epoch:" \| domain))` | Prevents phantom policy advances on append-only policy tables. |
| **Class 3** | Subject Consent & Profile | `SELECT ... FOR SHARE` on `User` & `PhrProfile` | Prevents concurrent consent revocations/grants during validation. |
| **Class 4** | Evidence Source Anchor | `pg_advisory_xact_lock_shared(h("evidence:" \| eid))` | Serializes evidence invalidation/revocation against commit. |
| **Class 5** | Entity Version Partitions | `SELECT ... FOR UPDATE` (WRITE) / `FOR SHARE` (READ) on `GlhsEntityVersionPartition` | Acquired in strict lexicographical order: `(domain ASC, semantic_key ASC)`. |
| **Class 6** | Lease & Reservation | `pg_advisory_xact_lock_shared(h("lease:" \| key))` | Coordinates reservation state leases. |
| **Class 7** | Idempotency Key Lock | `pg_advisory_xact_lock(h("idempotency:" \| key))` | Exclusive lock gating concurrent identical request executions. |

#### Advisory Lock Hash Pair Construction
Advisory lock strings are hashed using SHA-256 into two signed 32-bit integers (`int4`, `int4`) to avoid PostgreSQL 32-bit `hashtext` collision risks:
```python
def key_to_advisory_lock_pair(key: str | int) -> tuple[int, int]:
    digest = hashlib.sha256(str(key).encode("utf-8")).digest()
    k1, k2 = struct.unpack("!ii", digest[:8])
    return k1, k2
```

---

## 5. Schema-Derived Dependency Contract (`dependency_contract.py`)

To eliminate vulnerabilities where an untrusted client or LLM agent intentionally or accidentally omits causal dependencies to evade OCC version checks or lock acquisition, GLHS R3 mandates **Schema-Derived Dependency Completeness**.

### 5.1 Mathematical Derivation & Conservative Superset Rule

For any clinical operation tuple $(\text{Op}, \mathcal{S})$, the minimum required dependency set $D_{\text{min}}(\text{Op}, \mathcal{S})$ is computed deterministically by the API server:

$$D_{\text{min}}(\text{Op}, \mathcal{S}) = \text{GovernanceDeps}(\text{Op}, \mathcal{S}) \cup \text{EntityDeps}(\text{Op}, \mathcal{S}) \cup \text{EvidenceDeps}(\text{Op}, \mathcal{S})$$

When a proposal or caller supplies $D_{\text{prop}}$, the kernel evaluates validity against $D_{\text{min}}$ via $\text{ValidDeps}(D_{\text{prop}}, D_{\text{min}})$:

$$\text{ValidDeps}(D_{\text{prop}}, D_{\text{min}}) \iff \left( D_{\text{min}} \subseteq D_{\text{prop}} \right) \land \left( \forall d \in D_{\text{prop}} \setminus D_{\text{min}} : \text{ValidEntity}(d) \land \text{allow\_additional}(\text{Op}) \right)$$

If $D_{\text{prop}}$ omits any required item in $D_{\text{min}}$, or attempts to introduce extra entities on a closed-schema operation (e.g. `CONSENT_TRANSITION`), admission fails closed immediately with `dependency_contract_omission` or `dependency_contract_unexpected_extra`.

### 5.2 Operation Dependency Rules Registry (`_OPERATION_RULES`)

| Operation Kind | Governance Epoch Req. | Consent Ver. Req. | Evidence IDs Req. | Entity Access Mode | Min Entity Count | Conservative Superset Allowed |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `COMMIT_PROPOSAL` | **True** | **True** | **True** | `WRITE` | 1 | **True** |
| `ACTIVATE_ASSERTION` | **True** | **True** | **True** | `WRITE` | 1 | **True** |
| `SUPERSEDE_ASSERTION` | **True** | **True** | **False** | `WRITE` | 1 | **True** |
| `RESOLVE_CONFLICT` | **True** | **True** | **False** | `WRITE` | 1 | **True** |
| `RECONCILE_MEDICATION` | **True** | **True** | **True** | `WRITE` | 1 | **True** |
| `IMPORT_FHIR_BUNDLE` | **True** | **True** | **False** | `WRITE` | 1 | **True** |
| `RECORD_OBSERVATION` | **True** | **True** | **True** | `WRITE` | 1 | **True** |
| `CONSENT_TRANSITION` | **True** | **True** | **False** | `READ` | 0 | **False** |

---

## 6. Proposal Lineage & Non-Downgradable Adaptation (`commitment_gateway.py`)

### 6.1 Proposal Lineage Structure

Every proposal $P$ emitted by an LLM agent or clinician review preserves an immutable structural lineage chain:

```text
Root Model Proposal (origin="model")
  ├─ proposal_id = 101
  ├─ root_proposal_id = 101
  ├─ parent_proposal_id = NULL
  ├─ inference_binding_id = B_501 (consumed_thss = True)
  └─ context_binding_mode = "snapshot_bound"
        │
        ▼ (Clinician adapts dosage in Web UI)
Child Adapted Proposal (origin="human_review")
  ├─ proposal_id = 102
  ├─ root_proposal_id = 101 (INHERITED)
  ├─ parent_proposal_id = 101
  ├─ inference_binding_id = B_501 (INHERITED - IMMUTABLE)
  └─ context_binding_mode = "snapshot_bound" (CANNOT BE DOWNGRADED)
```

### 6.2 Anti-Laundering Invariant (ARCH-005 / GLHS-B03)

Human review or clinician adaptation may modify clinical payload parameters (e.g. adjusting drug dosage or administration route). However, human review **MUST NOT**:
1. Strip `inference_binding_id` or set it to `null`.
2. Downgrade `context_binding_mode` from `"snapshot_bound"` to `"base_version_only"`.
3. Substitute a different snapshot ID or snapshot digest.

Any proposal whose root ancestor used a `consumed_thss=True` inference binding MUST undergo full GRWC exact-disclosure verification at commit time $t_c$. Attempting to bypass continuity via human-review laundering raises `commitment_lineage_base_only_forbidden` or `commitment_lineage_binding_mismatch`.

---

## 7. RFC 8785 Canonical JSON Profile (`clara.canonical-json.v2-rfc8785`)

All cryptographic digests ($H_{\text{proj}}$, $H_{\text{env}}$, dependency vector digests, snapshot digests, and result digests) are rendered deterministically using **RFC 8785 JSON Canonicalization Scheme (JCS)** via `services/api/src/clara_api/glhs/canonical_json.py` (`PROFILE_V2_RFC8785`).

### 7.1 Byte-Level Serialization Rules

1. **UTF-16 Code Unit Key Sorting:** Dictionary keys are sorted by UTF-16 code unit order (`s.encode("utf-16-be")`).
2. **Strict Character Escaping:** Control characters (U+0000–U+001F) and quotes/backslashes are escaped using standard JCS escape sequences (`\"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t`, `\uXXXX`).
3. **Surrogate Pair Guard:** Lone surrogates in strings (U+D800–U+DFFF) are explicitly rejected (`ValueError("canonical_json_lone_surrogate")`).
4. **Number Formatting:** Floats and Decimals are formatted per ECMAScript `Number::toString` specification. In profile `clara.canonical-json.v2-rfc8785`, positive exponential notation explicitly includes the positive sign `+` (e.g. `1e+21`).
5. **IEEE 754 Safe Integer Bound:** Integers MUST lie within $[-9007199254740991, 9007199254740991]$ ($[-2^{53}+1, 2^{53}-1]$). Values outside this range raise `ValueError("canonical_json_integer_out_of_ijson_range")`.
6. **Timezone Representation:** Datetime values require explicit timezones and are normalized to UTC in ISO-8601 format with microsecond precision (`YYYY-MM-DDTHH:MM:SS.ffffffZ`).

---

## 8. Standardized Rejection Reason Code Mapping

GLHS R3 standardizes 8 stable rejection reason codes across all API entry points, commit kernel phases, database constraints, and evaluation schedules:

| Reason Code | Category | Fail-Closed Scenario & Trigger Condition | Architectural Enforcement Point |
| :--- | :--- | :--- | :--- |
| `commitment_lineage_base_only_forbidden` | Lineage Anti-Downgrade | Proposal descending from `consumed_thss=True` root attempts `context_binding_mode="base_version_only"`, or model-origin proposal attempts base-only write path. | `commit_kernel.py`: `evaluate_grwc_admission()`; `commitment_gateway.py`: `_require_lineage_binding()` |
| `commitment_lineage_binding_required` | Lineage Integrity | Proposal referencing snapshot lacks `inference_context_binding_id`, or human review strips root binding reference. | `commit_kernel.py`: `evaluate_grwc_admission()`; `commitment_gateway.py`: `_require_lineage_binding()` |
| `commitment_lineage_snapshot_mismatch` | Snapshot Identity | Descendant proposal `source_snapshot_id` differs from root proposal or binding `source_snapshot_id`. | `commit_kernel.py`: `evaluate_grwc_admission()`; `commitment_gateway.py`: `_require_lineage_binding()` |
| `commitment_lineage_manifest_mismatch` | Disclosure Integrity | Proposal `source_snapshot_digest` differs from authoritative binding `source_manifest_digest`. | `commit_kernel.py`: `evaluate_grwc_admission()`; `commitment_gateway.py`: `_require_lineage_binding()` |
| `commitment_lineage_cycle_detected` | Graph Integrity | Cyclic `reviewed_proposal_id` parent references detected during lineage graph traversal (e.g., $A \to B \to A$). | `commit_kernel.py`: `evaluate_grwc_admission()`; `commitment_gateway.py`: `_resolve_proposal_lineage_root()` |
| `commitment_lineage_depth_exceeded` | Graph Integrity | Proposal lineage depth exceeds limit ($\text{depth} > \text{MAX\_PROPOSAL\_LINEAGE\_DEPTH} = 4$). | `commit_kernel.py`: `evaluate_grwc_admission()`; `commitment_gateway.py`: `_resolve_proposal_lineage_root()` |
| `commitment_review_downgrade_forbidden` | Human Adaptation Guard | Human review payload attempts to downgrade snapshot-bound model proposal to base-version-only or strip snapshot binding fields. | `commit_kernel.py`: `evaluate_grwc_admission()`; `commitment_gateway.py`: `review_model_commitment_proposal()` |
| `commitment_review_authority_required` | Governance Authority | Reviewer actor role lacks required domain authority specified in `CommitmentDomainPolicy.actor_roles`. | `commit_kernel.py`: `evaluate_grwc_admission()`; `commitment_gateway.py`: `review_model_commitment_proposal()` |

---

## 9. Verification & Formal Invariant Mapping ($I_{01}$–$I_{15}$)

The formal architecture maps directly to the 15 verified state-space invariants in `formal_invariants_r3.json`:

| Invariant ID | Name | Formal TLA+ Definition Summary | Python Implementation Anchor | Target Experiment |
| :---: | :--- | :--- | :--- | :---: |
| **$I_{01}$** | `state_isolation` | $\forall a: \text{Committing}(a) \implies \text{VersionsMatch}(a)$ | `commit_kernel.py`: Phase 3 | E04, E08 |
| **$I_{02}$** | `governance_freshness` | $\forall a: \text{Committing}(a) \implies \text{EpochsCurrent}(a)$ | `commit_kernel.py`: Phase 3 | E04, E08 |
| **$I_{03}$** | `phantom_free` | $\forall a: \text{Drifted}(a) \implies \text{Aborted}(a)$ | `lock_hierarchy.py`: Class 1-3 Anchors | E04, E08 |
| **$I_{04}$** | `deadlock_free` | $\neg \exists a: \text{Cycle}(\text{WaitForGraph})$ | `lock_hierarchy.py`: Total Order 1-7 | E08, E09 |
| **$I_{05}$** | `idempotency_atomicity` | $\forall t_1, t_2 \in \text{Transitions}: \text{SameKey} \implies \text{SameId}$ | `commit_kernel.py`: Phase 1 & 2 | E04, ARCH-011 |
| **$I_{06}$** | `cas_monotonicity` | $\forall \text{link}: v_{\text{succ}} = v_{\text{pred}} + 1$ | `commit_kernel.py`: Phase 5 | E04, E08 |
| **$I_{07}$** | `evidence_closure` | $\forall p: \text{AssertedEv}(p) \subseteq \text{DisclosedEv}(p)$ | `gateway.py`: `validate_exact_disclosure_dependency()` | E01, E02 |
| **$I_{08}$** | `binding_immutability` | $\forall b \in \text{Bindings}: b' = b \land \text{NoDeletes}$ | `models.py`: ORM Immutability Listeners | E01, E06 |
| **$I_{09}$** | `lineage_preservation` | $\forall p \in \text{Review}: p.\text{binding\_id} = \text{Root}(p).\text{binding\_id}$ | `commitment_gateway.py`: `_require_lineage_binding()` | E01, E06 |
| **$I_{10}$** | `dependency_completeness` | $\forall p: D_{\text{min}}(p.\text{op}) \subseteq p.\text{dep\_vector}$ | `dependency_contract.py`: `generate_dependency_vector()` | E05 |
| **$I_{11}$** | `no_weak_route_downgrade` | $\forall p: \text{ModelOriginOrAncestry}(p) \implies \text{SnapshotBound}(p)$ | `commitment_gateway.py`: `validate_base_proposal_context()` | E06 |
| **$I_{12}$** | `exact_inference_disclosure_continuity` | $\forall p, c: \text{Admitted}(p, c) \implies \text{MatchingProjectionDigest}(p, b)$ | `gateway.py` & `commitment_gateway.py` | E01, E02, E08 |
| **$I_{13}$** | `non_downgradable_human_lineage` | $\forall p \in \text{HumanReview}: \text{PreservesRootBindingAndSnapshot}(p)$ | `commit_kernel.py`: `evaluate_grwc_admission()` | E01, E06, E08 |
| **$I_{14}$** | `undisclosed_evidence_rejection` | $\forall e \in p.\text{ev}: e \notin \mathcal{H} \implies \neg \text{Admit}(p)$ | `gateway.py`: `validate_exact_disclosure_dependency()` | E01, E08 |
| **$I_{15}$** | `clean_path_reachability` | $\forall p: \text{Valid}(p) \land \neg \text{Conflict}(p) \implies \Diamond \text{Committed}(p)$ | `commit_kernel.py`: `execute_atomic_glhs_commit()` | E01, E04, E08 |

---
*(End of document — `manuscript_methods_rewrite.md`)*
