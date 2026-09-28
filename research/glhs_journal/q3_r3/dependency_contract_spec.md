# Formal Specification: Schema-Derived Dependency Completeness Contract & Conservative Superset Validation

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Module:** `services/api/src/clara_api/glhs/dependency_contract.py` (with `commit_kernel.py`, `commitment_gateway.py`, `lock_hierarchy.py`)  
**Author / Curator:** Agent B — Systems & Formal Architecture  
**Status:** Frozen Phase 3 Systems Specification  
**Date:** Tue Sep 29 2026  
**Contract Version:** `dependency-contract.v1`  
**Formal Invariant Reference:** Invariant $I_{10}$ (`I10_dependency_completeness`) in `formal_invariants_r3.json`

---

## 1. Executive Summary & Problem Formulation

In clinical AI decision support systems, non-deterministic Large Language Model (LLM) agents generate structured mutation proposals across shared patient health state (e.g. initiating, titrating, or discontinuing medications; recording observations; resolving conflicting records; transitioning consent). A critical failure mode in unconstrained agent architectures is **Silent Read/Write Dependency Omission & Multi-Entity Write Skew**:

1. **Unconstrained LLM Dependency Hallucination/Omission:** An LLM agent can fail to declare necessary causal read dependencies (e.g., omitting serum creatinine, renal function, or active concurrent medications during a dosage computation).
2. **Intentional Dependency Stripping (Laundering):** An untrusted client or compromised model can omit entity partitions from its read/write set to bypass Optimistic Concurrency Control (OCC) version revalidation or PostgreSQL lock acquisition.
3. **Under-Locking & Phantom Write-Skew:** If the commit kernel only acquires locks and checks versions for explicitly reported dependencies, concurrent transactions can mutate omitted entities unnoticed, causing corrupt state transitions to commit under stale clinical assumptions.

GLHS R3 prohibits unconstrained LLM-generated dependency vectors by replacing caller-attested dependency sets with a **Schema-Derived Dependency Completeness Contract** (`dependency_contract.py`). The required causal dependency set is derived deterministically from structured application semantics (operation kind, domain, entity semantic keys, governance epochs, and disclosed evidence IDs).

Model-proposed dependencies are permitted **only if they form a verified Conservative Superset** of the schema-derived minimum ($D_{\text{min}} \subseteq D_{\text{prop}}$). Any missing minimum dependency or corrupted version coordinate fails closed immediately with `GlhsInvariantError`.

---

## 2. Mathematical Formalization of the Dependency Contract

Let $\text{Op}$ denote the clinical operation kind, $\mathcal{S}$ denote the structured application scope parameters, and $D$ denote a dependency vector consisting of normalized dependency tuples $d = (\kappa, k, \mu, v, \delta)$, where:
- $\kappa \in \{\text{GOVERNANCE}, \text{ENTITY}, \text{EVIDENCE}, \text{LEASE}\}$ (Dependency Kind)
- $k \in \Sigma^*$ (Canonical Dependency Key)
- $\mu \in \{\text{READ}, \text{WRITE}\}$ (Access Mode)
- $v \in \mathbb{N}_0$ (Observed Partition Version)
- $\delta \in \{0, 1\}^{256} \cup \{\bot\}$ (Observed Cryptographic State / Fingerprint Digest)

### 2.1 Minimum Required Dependency Set Definition

For any clinical operation tuple $(\text{Op}, \mathcal{S})$, the minimum required dependency set $D_{\text{min}}(\text{Op}, \mathcal{S})$ is the disjoint union of three schema-derived partitions:

$$D_{\text{min}}(\text{Op}, \mathcal{S}) = \text{GovernanceDeps}(\text{Op}, \mathcal{S}) \cup \text{EntityDeps}(\text{Op}, \mathcal{S}) \cup \text{EvidenceDeps}(\text{Op}, \mathcal{S})$$

Where:

1. **Governance Dependencies:**
   $$\text{GovernanceDeps}(\text{Op}, \mathcal{S}) = \begin{cases} 
   \{d_{\text{policy}}, d_{\text{consent}}\}, & \text{if } \text{requires\_gov}(\text{Op}) \land \text{requires\_consent}(\text{Op}) \\
   \{d_{\text{policy}}\}, & \text{if } \text{requires\_gov}(\text{Op}) \land \neg\text{requires\_consent}(\text{Op}) \\
   \emptyset, & \text{otherwise}
   \end{cases}$$
   where $d_{\text{policy}} = (\text{GOVERNANCE}, \text{"policy\_epoch:"} \parallel \text{domain}, \text{READ}, 0, \delta_{\text{policy}})$  
   and $d_{\text{consent}} = (\text{GOVERNANCE}, \text{"consent:"} \parallel v_{\text{consent}}, \text{READ}, 0, \delta_{\text{consent}})$.

2. **Entity Dependencies:**
   $$\text{EntityDeps}(\text{Op}, \mathcal{S}) = \left\{ (\text{ENTITY}, \text{domain} \parallel \text{":"} \parallel sk, \text{mode}(\text{Op}), v(sk), \delta(sk)) \;\middle|\; sk \in \text{semantic\_keys}(\mathcal{S}) \right\}$$
   subject to the boundary cardinality requirement:
   $$|\text{semantic\_keys}(\mathcal{S})| \ge \text{min\_entity\_count}(\text{Op})$$

3. **Evidence Dependencies:**
   $$\text{EvidenceDeps}(\text{Op}, \mathcal{S}) = \left\{ (\text{EVIDENCE}, \text{"evidence:"} \parallel eid, \text{READ}, 0, \bot) \;\middle|\; eid \in \text{evidence\_ids}(\mathcal{S}) \right\}$$
   subject to the mandatory disclosure requirement:
   $$\text{requires\_evidence}(\text{Op}) \implies |\text{evidence\_ids}(\mathcal{S})| \ge 1$$

---

### 2.2 Conservative Superset Rule

When a proposal or caller supplies a proposed dependency vector $D_{\text{prop}}$, the kernel evaluates validity against $D_{\text{min}}$ via the predicate $\text{ValidDeps}(D_{\text{prop}}, D_{\text{min}})$:

$$\text{ValidDeps}(D_{\text{prop}}, D_{\text{min}}) \iff \left( D_{\text{min}} \subseteq D_{\text{prop}} \right) \land \left( \forall d \in D_{\text{prop}} \setminus D_{\text{min}} : \text{ValidEntity}(d) \land \text{allow\_additional}(\text{Op}) \right)$$

Identity comparison between dependency specifications is defined over the canonical coordinate triple:
$$\text{id}(d) \triangleq (\kappa(d), k(d), \mu(d))$$

For all matching coordinates $d_m \in D_{\text{min}}$ and $d_p \in D_{\text{prop}}$ where $\text{id}(d_m) = \text{id}(d_p)$:
1. **Version Equality Invariant:** $v(d_m) \ne 0 \implies v(d_p) = v(d_m)$
2. **Digest Equality Invariant:** $\delta(d_m) \ne \bot \land \delta(d_p) \ne \bot \implies \delta(d_p) = \delta(d_m)$

---

### 2.3 Formal Invariant $I_{10}$ Definition

From `research/glhs_journal/q3_r3/formal_invariants_r3.json`:

$$\forall p \in \text{Proposals} : \text{MinDependencies}(p.\text{operation\_kind}, p.\text{target}) \subseteq p.\text{dependency\_vector}$$

**Hard-Reject Guard:** If $\exists d \in D_{\text{min}} : d \notin D_{\text{prop}}$, or if $\text{allow\_additional}(\text{Op}) = \text{False}$ and $D_{\text{prop}} \setminus D_{\text{min}} \ne \emptyset$, or if version/digest tampering is detected, the transaction aborts with fail-closed exceptions:
- `dependency_contract_omission`
- `dependency_contract_unexpected_extra`
- `dependency_contract_insufficient_entities`
- `dependency_contract_evidence_required`
- `dependency_contract_version_mismatch`
- `dependency_contract_digest_mismatch`
- `dependency_contract_unknown_operation`

---

## 3. Operation Dependency Rules Matrix (`_OPERATION_RULES`)

The table below specifies the declared dependency shape across all 8 clinical operation families defined in `_OPERATION_RULES` (plus the internal gateway transition operations):

| Operation Kind (`operation_kind`) | Governance Epoch Required (`requires_governance`) | Consent Version Required (`requires_consent`) | Evidence IDs Required (`requires_evidence`) | Entity Access Mode (`entity_access_mode`) | Min Entities (`min_entity_count`) | Conservative Superset Allowed (`allow_additional_entities`) | Clinical Context & Semantics |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`COMMIT_PROPOSAL`** | **True** | **True** | **True** | `WRITE` | 1 | **True** | Primary model-generated commitment transition proposal. |
| **`ACTIVATE_ASSERTION`** | **True** | **True** | **True** | `WRITE` | 1 | **True** | Activation of an asserted clinical condition or allergy. |
| **`SUPERSEDE_ASSERTION`** | **True** | **True** | **False** | `WRITE` | 1 | **True** | Supersession/deprecation of a superseded clinical assertion. |
| **`RESOLVE_CONFLICT`** | **True** | **True** | **False** | `WRITE` | 1 | **True** | Clinical conflict adjudication between divergent records. |
| **`RECONCILE_MEDICATION`** | **True** | **True** | **True** | `WRITE` | 1 | **True** | Medication reconciliation against prescription evidence. |
| **`IMPORT_FHIR_BUNDLE`** | **True** | **True** | **False** | `WRITE` | 1 | **True** | Batch ingestion and normalization of external FHIR bundle. |
| **`RECORD_OBSERVATION`** | **True** | **True** | **True** | `WRITE` | 1 | **True** | Logging vital signs, lab results, and patient measurements. |
| **`CONSENT_TRANSITION`** | **True** | **True** | **False** | `READ` | 0 | **False** | Modification to patient consent state; strict closed schema. |
| *`COMMIT_COMMITMENT_TRANSITION`* | True | True | False | `WRITE` | 1 | True | Gateway-level commitment state mutation. |
| *`APPLY_TRANSITION`* | False | False | False | `WRITE` | 0 | True | Low-level kernel transition without governance wrapping. |

---

## 4. Systems Architecture & Integration Pipeline

```text
+-------------------------------------------------------------------------------------------------------+
|                                    1. Model / Agent Proposal Generation                               |
|                                                                                                       |
|  - Agent computes clinical recommendation (e.g. dosage adjustment, conflict resolution)               |
|  - Agent outputs proposed mutation: domain, semantic_keys, evidence_ids, proposed_dependencies (opt) |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|                                    2. Schema-Derived Dependency Derivation                            |
|                                                                                                       |
|  DependencyGenerationInput(operation_kind, domain, semantic_keys, policy_version, consent_ver, ...)   |
|         |                                                                                             |
|         v                                                                                             |
|  generate_dependency_vector(input)                                                                    |
|    - Resolves _OPERATION_RULES[operation_kind]                                                        |
|    - Synthesizes D_min = GovDeps U EntityDeps U EvidenceDeps                                          |
|    - Computes Canonical JSON generation_digest                                                        |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|                                    3. Superset Validation & Proposal Sealing                          |
|                                                                                                       |
|  validate_proposed_dependencies(minimum=D_min, proposed=D_prop, operation_kind=op)                    |
|    - Asserts D_min \subseteq D_prop (fails closed on omission)                                        |
|    - Asserts extra entities allowed for operation (fails on unauthorized extra)                       |
|    - Asserts observed_version and observed_digest consistency                                         |
|    - Returns GeneratedDependencyVector(is_superset=True/False, extra_keys=(...))                      |
|  _persist_proposal_dependencies() writes GlhsProposalDependency rows to PostgreSQL                    |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|                                    4. Phase 2: Lock Hierarchy Formulation                             |
|                                                                                                       |
|  build_lock_plan() resolves all vector items into total-ordered advisory and row lock acquisitions:  |
|    - Class 1: Global Policy Anchor                                                                    |
|    - Class 2: Domain Policy Anchor                                                                    |
|    - Class 3: Subject & Profile Anchors                                                               |
|    - Class 4: Evidence Anchors                                                                        |
|    - Class 5: Entity Version Partitions (FOR UPDATE / FOR SHARE in (domain, key) order)               |
|    - Class 6: Lease Anchors                                                                           |
|    - Class 7: Idempotency Key Anchor                                                                  |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|                                    5. Phase 3: Kernel Revalidation Under Locks                        |
|                                                                                                       |
|  execute_atomic_glhs_commit() in commit_kernel.py:                                                    |
|    - Revalidates policy epoch version == current_policy_version                                       |
|    - Revalidates consent epoch version == current_consent_version                                     |
|    - Revalidates entity partition state_version == dep.observed_version                              |
|    - Revalidates entity state_digest == dep.observed_digest                                           |
|    - Revalidates evidence valid_from <= now <= valid_to and revoked_at is NULL                        |
|    - Evaluates GRWC admission verifier (evaluate_grwc_admission)                                      |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+-------------------------------------------------------------------------------------------------------+
|                                    6. Phase 4 - 6: Atomic Commit & CAS Progression                     |
|                                                                                                       |
|  - Domain mutation callback executed                                                                  |
|  - CAS version increment on all WRITE partitions: v -> v + 1                                          |
|  - Persists GlhsAppliedTransition with dependency metadata envelope & outbox event                   |
+-------------------------------------------------------------------------------------------------------+
```

---

## 5. Audit Envelope & Canonical Verification

Every generated or validated dependency vector produces a canonical audit envelope structured via RFC-8785 canonical JSON formatting (`CANONICALIZATION_PROFILE = "RFC-8785/JCS-SHA256"`):

```json
{
  "contract_version": "dependency-contract.v1",
  "operation_kind": "COMMIT_PROPOSAL",
  "domain": "medications",
  "semantic_keys": [
    "lisinopril",
    "metformin"
  ],
  "evidence_ids": [
    "ev-clinical-001"
  ],
  "policy_version": "glhs.v1",
  "consent_version": "disclaimer.v3",
  "dep_count": 5
}
```

The generation digest $\delta_{\text{gen}} = \text{fast\_canonical\_digest}(\text{envelope})$ is durably persisted inside the proposal seal and `GlhsAppliedTransition` record, guaranteeing non-repudiation and cryptographic provenance across the entire read-to-write lifecycle.

---

## 6. Verification and Regression Testing

The dependency contract is covered by unit and regression test suites in `services/api/tests/test_dependency_completeness.py`, validating:
1. Deterministic dependency derivation and digest repeatability.
2. Hard rejection of unknown operation kinds (`GlhsInvariantError("dependency_contract_unknown_operation")`).
3. Strict fail-closed rejection for omission of governance, entity, or evidence dependencies (`GlhsInvariantError("dependency_contract_omission")`).
4. Acceptance of conservative supersets when `allow_additional_entities = True`.
5. Rejection of unauthorized extra dependencies on closed-schema operations (e.g., `CONSENT_TRANSITION`).
6. Detection and immediate abort on observed version tampering (`GlhsInvariantError("dependency_contract_version_mismatch")`) and digest corruption (`GlhsInvariantError("dependency_contract_digest_mismatch")`).
7. Complete audit metadata envelope emission.
