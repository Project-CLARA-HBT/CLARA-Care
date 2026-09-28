# GLHS R3 Systems Architecture Map & Formal State Model

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Module:** `services/api/src/clara_api/glhs/`  
**Author / Curator:** Agent B — Systems & Formal Architecture  
**Status:** Frozen Phase 0 Systems Specification  
**Date:** Mon Sep 28 2026  

---

## 1. Executive Systems Overview

GLHS R3 models the boundary between non-deterministic AI inference and transactional health record persistence as an auditable, fail-closed systems boundary.

### 1.1 Architectural Pipeline Flow

```text
+------------------------+
|   Governed Disclosure  |  (THSS Snapshot H compiled: task-minimized state,
|      (Snapshot H)      |   provenance manifest M(H), policy/consent versions)
+-----------+------------+
            |
            v  [API Server: Pre-Dispatch Binding]
+-----------+------------+
| Inference Context      |  (Server-owned binding I: public_id, snapshot_id,
|  Binding (Binding I)   |   projection_digest H_proj, request_envelope_digest H_env,
+-----------+------------+   actor, purpose, task, requested/reported model)
            |
            v  [LLM Model / Agent Inference]
+-----------+------------+
|   Proposal Lineage     |  (Proposal P: proposal_id, root_proposal_id,
|      (Proposal P)      |   inference_binding_id, target_payload_digest,
+-----------+------------+   dependency_vector D(P), origin: model | human_review)
            |
            v  [Admission Gateway: GRWC Evaluation]
+-----------+------------+
|   Admission Contract   |  (Evaluates Admit(P, t_c): verify lineage, exact binding,
|     (GRWC Check)       |   evidence membership, dependency completeness, auth)
+-----------+------------+
            |
            v  [PostgreSQL Transaction: 6-Phase Kernel]
+-----------+------------+
| Atomic Commit Kernel   |  (1. Idempotency -> 2. Lock Acquisition -> 3. Revalidation
|    (commit_kernel)     |   -> 4. Callback -> 5. CAS Increment -> 6. Applied Transition)
+-----------+------------+
            |
            v
+------------------------+
|  Applied Transition &  |  (GlhsAppliedTransition + GlhsTransitionPartitionLink
|  Transactional Outbox  |   + Domain Mutation persisted atomically)
+------------------------+
```

### 1.2 Security & Trust Boundaries

* **Trusted System Boundary (API Server & PostgreSQL):**
  * Prompt compiler and THSS snapshot generator (`gateway.py`, `commitment_thss.py`).
  * Inference context binding engine (`create_inference_context_binding`).
  * Operation dependency contract generator (`dependency_contract.py`).
  * Atomic commit kernel and lock manager (`commit_kernel.py`, `lock_hierarchy.py`).
  * Relational store containing immutable state ledgers and version partitions.

* **Untrusted / Partially Trusted Boundary:**
  * LLM provider endpoints (DeepSeek, OpenAI, Anthropic, etc.).
  * Client browser and mobile application runtimes (`apps/web`, `apps/mobile`).
  * User/Clinician proposal modification forms prior to admission.
  * Model-generated proposal fields (model outputs cannot self-certify binding equality or dependency completeness).

---

## 2. Exact Inference Consumption & Disclosure Projection

### 2.1 Server-Attested Binding Creation

The authoritative inference context binding (`GlhsInferenceContextBinding`) MUST be created by the API server **immediately after final canonical request envelope serialization and prior to dispatching the request to an external LLM provider**.

* **Pre-Dispatch Action:**
  1. Compile bounded THSS snapshot $H$.
  2. Build canonical request envelope (`clara.inference-envelope.v1`).
  3. Hash envelope to produce `request_envelope_digest` ($H_{\text{env}}$).
  4. Hash model-visible health projection to produce `projection_digest` ($H_{\text{proj}}$).
  5. Insert `GlhsInferenceContextBinding` with `status = "PENDING"`, `consumed_thss = True`.
* **Post-Response Finalization:**
  1. Record `reported_model_id`, provider round-trip timing (`request_completed_at`).
  2. Compute `response_digest`.
  3. Transition status to `COMPLETED`.
  * *Failure/Abort Rule:* If the inference call fails, times out, or returns malformed output, the binding is marked `FAILED` or `ABORTED`. Proposals referencing non-`COMPLETED` bindings MUST fail admission closed (`binding_not_completed`).

### 2.2 Two-Digest Architecture

To eliminate ambiguity between snapshot creation and exact inference consumption, GLHS R3 enforces a two-digest verification model:

1. **Model-Visible Disclosure Projection Digest ($H_{\text{proj}}$):**
   $$\text{projection\_digest} = \text{SHA-256}\left(\text{CanonicalJSON}\left(\text{model\_visible\_projection}\right)\right)$$
   Represents the exact health state projection presented inside the prompt.

2. **Request Envelope Digest ($H_{\text{env}}$):**
   $$\text{request\_envelope\_digest} = \text{SHA-256}\left(\text{CanonicalJSON}\left(\text{CanonicalRequestEnvelope}\right)\right)$$
   Represents the complete, server-owned request payload (excluding transient transport headers/tokens).

### 2.3 Canonical Request Envelope Specification

```json
{
  "schema": "clara.inference-envelope.v1",
  "model_route": "research_tier2_medication_reconciliation",
  "requested_model_id": "deepseek-reasoner",
  "prompt_template_version": "2026.08.19-v1",
  "system_prompt_version": "sys-prompt-clinical-gov.v3",
  "purpose": "treatment_planning",
  "task": "reconcile_medication_order",
  "disclosure": {
    "snapshot_id": "snap_94a8f12c8b1e4a21",
    "projection_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "manifest_digest": "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"
  },
  "model_visible_projection": {
    "profile_id": "phr_10029",
    "active_medications": [],
    "reconciled_commitments": []
  }
}
```

Canonical serialization uses RFC 8785 (JSON Canonicalization Scheme / JCS) via `canonical_json.py` (`profile = "glhs.jcs.v1"`).

---

## 3. Proposal Lineage & Human Adaptation

### 3.1 Immutable Proposal Schema

Every proposal $P$ emitted by or derived from an AI inference pass preserves an explicit lineage chain in `GlhsClinicalCommitmentProposal`:

```text
Proposal P:
  id: int (primary key)
  public_id: str (UUIDv4)
  root_proposal_id: int (references initial model proposal id)
  parent_proposal_id: int | None (references immediate predecessor if edited)
  reviewed_proposal_id: int | None (alias for parent proposal in human review)
  inference_binding_id: int (references GlhsInferenceContextBinding)
  context_binding_mode: "snapshot_bound" | "base_version_only"
  base_state_version: int
  expected_policy_version: str
  expected_consent_version: str
  source_snapshot_id: str
  source_snapshot_digest: str
  dependency_vector_digest: str
  proposal_digest: str
  origin: "model" | "human_review" | "clinician" | "user"
```

### 3.2 Non-Downgradable Lineage Invariant (ARCH-005 / GLHS-B03)

```text
Root Model Proposal (origin="model")
  ├─ inference_binding_id = B_101 (consumed_thss = True)
  └─ context_binding_mode = "snapshot_bound"
        │
        ▼ (Clinician edits dosage in Web UI)
Child Proposal (origin="human_review")
  ├─ root_proposal_id = Root.id
  ├─ parent_proposal_id = Root.id
  ├─ inference_binding_id = B_101 (INHERITED - CANNOT BE STRIPPED)
  └─ context_binding_mode = "snapshot_bound" (MUST REMAIN SNAPSHOT_BOUND)
```

**Anti-Laundering Enforcement Rule:**
Human review or clinician adaptation may modify proposal payload attributes (e.g., adjusting medication frequency or start date). However, human review **MUST NOT**:
1. Strip `inference_binding_id` or set it to `null`.
2. Downgrade `context_binding_mode` from `"snapshot_bound"` to `"base_version_only"`.
3. Substitute a different snapshot ID or snapshot digest.

Any proposal whose root ancestor used a `consumed_thss=True` inference binding MUST undergo full GRWC exact-disclosure verification at commit time. Attempting to bypass continuity via human-review laundering raises `commitment_lineage_base_only_forbidden` or `commitment_lineage_binding_mismatch`.

---

## 4. Operation-Derived Dependency Contracts

To eliminate vulnerabilities where an LLM intentionally or accidentally omits dependencies from its proposal vector, GLHS R3 mandates schema-derived dependency derivation (`dependency_contract.py`).

### 4.1 Dependency Derivation Algorithm

```text
Input: DependencyGenerationInput(operation_kind, domain, semantic_keys, policy_version, consent_version, evidence_ids)
   │
   ├─► 1. Lookup Operation Dependency Rule (_OPERATION_RULES[operation_kind])
   ├─► 2. Generate mandatory GOVERNANCE dependencies:
   │        - policy_epoch:<domain> (READ)
   │        - consent:<version> (READ)
   ├─► 3. Generate mandatory ENTITY dependencies:
   │        - <domain>:<semantic_key> (WRITE or READ based on rule)
   ├─► 4. Generate mandatory EVIDENCE dependencies:
   │        - evidence:<evidence_id> (READ)
   └─► 5. Canonical Sort & Hash:
            Sort by (dependency_kind, dependency_key, access_mode)
            Compute dependency_vector_digest via fast_canonical_digest()
```

### 4.2 Conservative Superset Policy

* **Minimum Required Vector ($D_{\text{min}}$):** Computed deterministically by the API server from operation semantics.
* **Caller-Submitted Vector ($D_{\text{caller}}$):** May include additional entity/evidence dependencies (enabling conservative supersets).
* **Validation Rule:**
  $$D_{\text{min}} \subseteq D_{\text{caller}}$$
  If $D_{\text{caller}}$ omits any entry present in $D_{\text{min}}$, commit is rejected with `dependency_missing`.

---

## 5. 6-Phase Atomic Commit Kernel (`commit_kernel.py`)

All GLHS state mutations run through `execute_atomic_glhs_commit` inside a single PostgreSQL database transaction:

```text
===============================================================================
PHASE 1: FAST IDEMPOTENCY PRE-CHECK
===============================================================================
- Query `GlhsAppliedTransition` by (tenant_id, operation_kind, idempotency_key).
- If existing record found:
    - If request_digest matches -> return cached GlhsCommitResult (idempotent_replay = True).
    - If request_digest differs -> raise GlhsInvariantError("idempotency_key_reused").

===============================================================================
PHASE 2: CANONICAL LOCK ACQUISITION (7-Class Lock Hierarchy)
===============================================================================
- Resolve profile owner user ID.
- Build canonical LockPlan across Classes 1-7:
    Class 1: Advisory Lock on Tenant/Global Policy Anchor (`pg_advisory_xact_lock_shared`)
    Class 2: Advisory Lock on Domain Policy Anchor (`pg_advisory_xact_lock_shared`)
    Class 3: Row Lock FOR SHARE on `User` & `PhrProfile` (Subject Consent Anchor)
    Class 4: Advisory Locks on Evidence Sources
    Class 5: Row Locks on `GlhsEntityVersionPartition` (FOR SHARE on READ, FOR UPDATE on WRITE)
             acquired in strict lexicographical order: (domain ASC, semantic_key ASC)
    Class 6: Advisory Locks on Leases/Reservations
    Class 7: Advisory Lock FOR EXCLUSIVE on Idempotency Key
- Re-check idempotency under acquired locks to prevent concurrent race duplicates.

===============================================================================
PHASE 3: FRESHNESS & DEPENDENCY REVALIDATION UNDER LOCKS
===============================================================================
- Revalidate Expected Base State Version: `expected_base_state_version == current_version`.
- Revalidate Policy Epoch: `expected_policy_version == current_policy_version`.
- Revalidate Consent Epoch: `expected_consent_version == current_consent_version`.
- Revalidate Per-Partition Entity Versions & State Digests.
- Revalidate Evidence Validity Intervals (`valid_from <= now <= valid_to`) and Revocation Status.
- Revalidate GRWC Invariants via `evaluate_grwc_admission()`.

===============================================================================
PHASE 4: DOMAIN MUTATION CALLBACK EXECUTION
===============================================================================
- Invoke `mutation_callback(commit_context)`.
- Execute domain table writes (e.g., insert `GlhsClinicalCommitmentVersion`).
- Collect mutation result object.

===============================================================================
PHASE 5: CAS VERSION PROGRESSION ON WRITE PARTITIONS
===============================================================================
- For each WRITE partition coordinate (in lexicographical order):
    `successor_version = predecessor_version + 1`
    UPDATE `glhs_entity_version_partitions`
    SET `state_version` = `successor_version`, `updated_at` = `now`
    WHERE `id` = partition.id AND `state_version` = predecessor_version;
- Assert `rowcount == 1`. If 0, raise `GlhsInvariantError("cas_version_conflict")`.
- Record `GlhsTransitionPartitionLink` with predecessor/successor digests.

===============================================================================
PHASE 6: APPLIED TRANSITION & TRANSACTIONAL OUTBOX PERSISTENCE
===============================================================================
- Insert `GlhsAppliedTransition` record capturing:
    `proposal_id`, `request_digest`, `result_digest`, `dependency_vector_digest`,
    `disclosure_digest`, `transition_status = "COMMITTED"`.
- Insert Transactional Outbox Event via `add_outbox()` (`glhs.transition.applied`).
- Flush transaction. (Caller executes DB commit).
===============================================================================
```

---

## 6. 7-Class Governance Lock Hierarchy (`lock_hierarchy.py`)

To prevent deadlocks and eliminate TOCTOU race conditions (including phantom insertions into append-only ledgers), lock acquisition enforces a strict total ordering:

$$\text{Class 1} \prec \text{Class 2} \prec \text{Class 3} \prec \text{Class 4} \prec \text{Class 5} \prec \text{Class 6} \prec \text{Class 7}$$

```text
+---------+----------------------------+---------------------------------+-------------------------+
| Class   | Description                | Lock Mechanism                  | Scope                   |
+---------+----------------------------+---------------------------------+-------------------------+
| Class 1 | Tenant Global Policy       | pg_advisory_xact_lock_shared    | tenant_global_policy    |
| Class 2 | Domain Policy Anchor       | pg_advisory_xact_lock_shared    | policy_epoch:<domain>   |
| Class 3 | Subject Consent & Profile  | SELECT ... FOR SHARE on User    | user_consent:<user_id>  |
| Class 4 | Evidence Source Anchor     | pg_advisory_xact_lock_shared    | evidence:<evidence_id>  |
| Class 5 | Entity Version Partitions  | SELECT ... FOR UPDATE / SHARE   | profile:domain:key (lex)|
| Class 6 | Lease & Reservation        | pg_advisory_xact_lock_shared    | lease:<lease_key>       |
| Class 7 | Idempotency Key Lock       | pg_advisory_xact_lock           | idempotency:<key>       |
+---------+----------------------------+---------------------------------+-------------------------+
```

### 6.1 Phantom Prevention on Append-Only Ledgers

Standard `SELECT ... FOR UPDATE` on append-only tables (such as `governance_policy_epochs` or `user_consents`) does NOT prevent phantom inserts because new rows do not exist at query execution time. 

GLHS R3 solves phantom drift by pairing row reads with **transactional advisory lock anchors** on Class 1, Class 2, and Class 3 coordinates:
- Policy advances acquire `pg_advisory_xact_lock(EXCLUSIVE)` on Class 2 anchor.
- Consent updates acquire `pg_advisory_xact_lock(EXCLUSIVE)` on Class 3 anchor.
- State mutation transitions acquire `pg_advisory_xact_lock_shared` on Class 1, 2, 3 anchors.

This forces policy/consent updates to serialize against concurrent GST/Commitment transaction validation, guaranteeing zero phantom governance drift.

### 6.2 Advisory Lock Hash Function

Advisory lock keys are hashed using SHA-256 into two signed 32-bit integers (`int4`, `int4`) to eliminate 32-bit `hashtext` collision risks:

```python
def key_to_advisory_lock_pair(key: str | int) -> tuple[int, int]:
    digest = hashlib.sha256(str(key).encode("utf-8")).digest()
    k1, k2 = struct.unpack("!ii", digest[:8])
    return k1, k2
```

---

## 7. Mathematical GRWC Admission Predicate & Rejection Protocol

### 7.1 Formal GRWC Admission Formula

$$\begin{aligned}
\text{Admit}(P, t_c) \iff & \text{ValidLineage}(P) \\
& \land \text{ContinuousDisclosure}(P, H, I) \\
& \land \text{StateCurrent}(P, S(t_c)) \\
& \land \text{GovCurrent}(P, G(t_c)) \\
& \land \text{DepsComplete}(P) \\
& \land \text{EvidenceCovered}(P, H)
\end{aligned}$$

Where:

1. **$\text{ValidLineage}(P)$:**
   $$\begin{aligned}
   \text{ValidLineage}(P) \iff & (P.\text{origin} = \text{"model"} \implies P.\text{binding\_id} \neq \text{null} \land P.\text{mode} = \text{"snapshot\_bound"}) \\
   & \land (P.\text{root\_proposal\_id} \neq \text{null} \implies \text{Ancestor}(P.\text{root}) \land P.\text{binding\_id} = P.\text{root}.\text{binding\_id})
   \end{aligned}$$

2. **$\text{ContinuousDisclosure}(P, H, I)$:**
   $$\begin{aligned}
   \text{ContinuousDisclosure}(P, H, I) \iff & I.\text{status} = \text{"COMPLETED"} \\
   & \land I.\text{snapshot\_id} = H.\text{id} \\
   & \land I.\text{projection\_digest} = H.\text{projection\_digest} \\
   & \land I.\text{manifest\_digest} = H.\text{manifest\_digest} \\
   & \land P.\text{source\_snapshot\_digest} = H.\text{snapshot\_digest}
   \end{aligned}$$

3. **$\text{StateCurrent}(P, S(t_c))$:**
   $$\text{StateCurrent}(P, S(t_c)) \iff P.\text{base\_state\_version} = S(t_c).\text{version}$$

4. **$\text{GovCurrent}(P, G(t_c))$:**
   $$\begin{aligned}
   \text{GovCurrent}(P, G(t_c)) \iff & P.\text{expected\_policy\_version} = G(t_c).\text{policy\_version} \\
   & \land P.\text{expected\_consent\_version} = G(t_c).\text{consent\_version} \\
   & \land P.\text{purpose} = G(t_c).\text{purpose} \land P.\text{actor\_user\_id} = G(t_c).\text{actor\_user\_id}
   \end{aligned}$$

5. **$\text{DepsComplete}(P)$:**
   $$\text{DepsComplete}(P) \iff D_{\text{min}}(\text{Operation}(P)) \subseteq P.\text{dependency\_vector}$$

6. **$\text{EvidenceCovered}(P, H)$:**
   $$\text{EvidenceCovered}(P, H) \iff P.\text{asserted\_evidence\_ids} \subseteq H.\text{disclosed\_evidence\_ids}$$

### 7.2 Complete Rejection Code Mapping

| Rejection Code | Category | Violation Condition |
|---|---|---|
| `binding_missing` | Binding | Inference context binding record missing or null. |
| `binding_not_completed` | Binding | Binding status is `PENDING`, `FAILED`, or `ABORTED`. |
| `binding_profile_mismatch` | Binding | Binding `profile_id` differs from commit target profile. |
| `binding_actor_mismatch` | Binding | Binding `actor_user_id` differs from current commit actor. |
| `binding_purpose_mismatch` | Binding | Binding `purpose` differs from active commit scope purpose. |
| `binding_task_mismatch` | Binding | Binding `task` differs from active commit scope task. |
| `snapshot_missing` | Disclosure | Referenced snapshot record not found in database. |
| `snapshot_identity_mismatch` | Disclosure | Snapshot ID in proposal differs from binding snapshot ID. |
| `projection_digest_mismatch` | Disclosure | Computed $H_{\text{proj}}$ differs from binding projection digest. |
| `manifest_digest_mismatch` | Disclosure | Computed $M(H)$ digest differs from binding manifest digest. |
| `request_envelope_mismatch` | Disclosure | Canonical request envelope digest $H_{\text{env}}$ mismatch. |
| `evidence_undisclosed` | Evidence | Asserted evidence ID was omitted from model disclosure $H$. |
| `dependency_missing` | Dependency | Proposal dependency vector omits required minimum schema keys. |
| `dependency_version_stale` | Freshness | Observed entity state version != current DB state version under locks. |
| `policy_stale` | Governance | Expected policy version != active DB policy epoch under locks. |
| `consent_stale` | Governance | Expected consent version != active DB consent version under locks. |
| `consent_revoked` | Governance | Patient consent revoked for given domain/purpose prior to commit. |
| `role_changed` | Governance | Actor role privileges altered between inference and commit. |
| `snapshot_expired` | Expiry | Commit timestamp $t_c > \text{snapshot.expires\_at}$. |
| `lineage_downgrade` | Lineage | Human-edited proposal attempted to strip root inference binding. |
| `idempotency_replay` | Idempotency | Duplicate submission detected; return cached execution result. |

---

## 8. Verification & Test Suite Traceability

The systems architecture is verified across Python integration and unit test suites:

* **Commit Kernel:** `services/api/tests/test_glhs_commit_kernel.py`
* **Lock Hierarchy:** `services/api/tests/test_glhs_lock_hierarchy.py`
* **Inference Binding:** `services/api/tests/test_glhs_inference_context_binding.py`
* **Mandatory THSS Binding:** `services/api/tests/test_glhs_mandatory_thss_binding.py`
* **Entity Partition Concurrency:** `services/api/tests/test_glhs_entity_partition_concurrency.py`
* **Phantom Concurrency & TOCTOU:** `services/api/tests/test_glhs_phantom_concurrency.py`
* **Canonical JSON & Digests:** `services/api/tests/test_glhs_canonical_json.py`
