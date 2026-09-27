# Refinement Mapping: Formal Governance Model to Production GLHS Substrate

## 1. Overview

This document establishes the formal refinement mapping ($\mathcal{R}: \text{Abstract Model} \to \text{Production Code}$) between the canonical state machine in `evaluation/formal_governance/` and the production GLHS commit substrate in `services/api/src/clara_api/glhs/`:
- `commit_kernel.py` (6-Phase Linearizable OCC Atomic Commit Engine)
- `lock_hierarchy.py` (7-Class Canonical Total-Order Advisory & Row Lock Hierarchy)
- `gateway.py` (Governed State Transition & Policy/Consent Enforcement)

---

## 2. State Coordinate Mapping

| Formal Model Coordinate (`model.State`) | Production Database Model & Code Symbol (`services/api/src/clara_api/`) | Refinement Relationship & Invariant |
| :--- | :--- | :--- |
| `subject`, `actor` | `User.id`, `PhrProfile.user_id`, `PhrProfile.id` | Subject identity anchor. Resolved during Phase 2 lock acquisition (`acquire_profile_and_consent_anchor`). |
| `role`, `purpose`, `task` | `RBACContext.role`, `GlhsCommitContext.purpose`, `operation_kind` | Operation parameters checked in Phase 3 dependency revalidation against authorization tokens. |
| `state_version` | `GlhsStateVersion.state_version`, `GlhsEntityVersionPartition.state_version` | Partition and profile level OCC state version counters. Incremented via CAS in Phase 5. |
| `policy_version` | `GovernancePolicyEpoch.version`, `_effective_policy_version()` | Persisted policy epoch version. Locked under Class 1/2 advisory locks. |
| `consent_version`, `consent_state` | `UserConsent.consent_version`, `UserConsent.status` (`GRANTED`/`REVOKED`) | Subject consent status. Locked under Class 3 User row lock and advisory anchor (`user_consent:<id>`). |
| `snapshot_id`, `digest_valid`, `expiry` | `GlhsSnapshotManifest.snapshot_digest`, timestamp bounds | Cryptographic disclosure snapshot. Verified in `commitment_gateway.py` and `commit_kernel.py`. |
| `disclosed_evidence_set`, `proposal_evidence` | `GlhsEvidence.fingerprint`, `GlhsProposalDependency` (kind `EVIDENCE`) | Evidence dependency set. Verified during Phase 3 dependency revalidation. |
| `proposal_base` | `GlhsClinicalCommitmentProposal.base_state_version` | Expected base state version recorded at proposal creation. Revalidated in Phase 3. |
| `proposal_binding` | Presence of `GlhsProposalDependency` vectors | Proposal dependency vector binding. |
| `idempotency_key`, `committed_keys` | `GlhsAppliedTransition.idempotency_key`, Class 7 Lock | Unique idempotency constraint. Fast-path checked in Phase 1 and lock-verified in Phase 7. |
| `commit_status` | `GlhsAppliedTransition.transition_status` (`COMMITTED`/`REJECTED`) | Persisted commit status. Transactional outbox event dispatched on `COMMITTED`. |

---

## 3. Transition Function Refinement Mapping

### 3.1 `issue_disclosure` $\to$ `gateway.create_snapshot_manifest()`
- **Abstract Function:** `transitions.issue_disclosure(state, evidence, expiry)`
- **Production Endpoint:** `clara_api.glhs.gateway.create_snapshot_manifest()`
- **Refinement Mapping:**
  - Verifies active user consent (`UserConsent.status == "GRANTED"`).
  - Computes `snapshot_digest` via `fast_canonical_digest()`.
  - Persists `GlhsSnapshotManifest` with timestamp-bounded expiry.

### 3.2 `create_proposal` $\to$ `commitment_gateway.create_clinical_commitment_proposal()`
- **Abstract Function:** `transitions.create_proposal(state, binding, evidence, idempotency_key)`
- **Production Endpoint:** `clara_api.glhs.commitment_gateway.create_clinical_commitment_proposal()`
- **Refinement Mapping:**
  - Binds expected `base_state_version = current_state_version(profile_id)`.
  - Normalizes and persists dependency vector rows (`GlhsProposalDependency`).
  - Computes `dependency_vector_digest`. Rejects if binding to an expired or tampered snapshot.

### 3.3 `commit` $\to$ `commit_kernel.execute_atomic_glhs_commit()`
- **Abstract Function:** `transitions.commit(state)`
- **Production Engine:** `clara_api.glhs.commit_kernel.execute_atomic_glhs_commit()`
- **Refinement Mapping (6-Phase Atomic Commit Sequence):**
  - **Phase 1 (Idempotency Pre-check):** Check `GlhsAppliedTransition` for existing `(tenant_id, operation_kind, idempotency_key)`.
  - **Phase 2 (Canonical Lock Acquisition):** Acquire locks in strict total order across 7 classes (`lock_hierarchy.py`).
  - **Phase 3 (Dependency Revalidation):** Verify `expected_base_state_version == base_state_version`, `expected_policy_version == current_policy_version`, `expected_consent_version == current_consent_version`, evidence validity, and entity partition versions.
  - **Phase 4 (Domain Mutation):** Execute domain callback within isolated transaction.
  - **Phase 5 (CAS Version Progression):** Execute atomic update: `UPDATE glhs_entity_version_partitions SET state_version = state_version + 1 WHERE id = :id AND state_version = :expected_version`. Assert `rowcount == 1`.
  - **Phase 6 (Persist Applied Transition):** Insert `GlhsAppliedTransition` and dispatch outbox event.

### 3.4 `replay_proposal` $\to$ `execute_atomic_glhs_commit()` (Phase 1 & Phase 7)
- **Abstract Function:** `transitions.replay_proposal(state)`
- **Production Logic:** Phase 1 / Phase 7 idempotency check in `execute_atomic_glhs_commit()`.
- **Refinement Mapping:** If `idempotency_key` is already in `GlhsAppliedTransition`, returns existing commit result without re-executing mutations or advancing versions (`idempotent_replay = True`).

### 3.5 `retry` $\to$ Proposal Re-submission
- **Abstract Function:** `transitions.retry(state)`
- **Production Logic:** Re-submitting a proposal after an OCC conflict or rejection.
- **Refinement Mapping:** Re-runs full Phase 2-3 admission checks. If coordinates or state are stale, rejects fail-closed with `GlhsInvariantError`.

### 3.6 `rollback` $\to$ Compensating Transaction / DB Abort
- **Abstract Function:** `transitions.rollback(state)`
- **Production Logic:** Transactional `db.rollback()` or administrative compensating transition.
- **Refinement Mapping:** Aborts uncommitted mutations or applies an explicit compensating transition record.

---

## 4. Invariants Refinement Matrix (I1 - I11)

| Formal Invariant | Abstract Formal Check | Production Code Check (`commit_kernel.py` / `lock_hierarchy.py` / `gateway.py`) |
| :--- | :--- | :--- |
| **I1: No Stale Base Commit** | `proposal_base == state_version` | `commit_kernel.py:613-615`: `if expected_base_state_version != base_state_version: raise GlhsInvariantError("stale_base_state_version")` |
| **I2: No Post-Revocation Commit** | `consent_state == "granted"` | `commit_kernel.py:608-611`, `gateway.py:565`: `if expected_consent_version != current_consent_version: raise GlhsInvariantError(...)`. Consent revocation acquires Class 3 exclusive lock (`acquire_consent_lock_anchor`), serializing consent updates. |
| **I3: No Wrong Coordinate Commit** | `proposal_coord == active_coord` | `commit_kernel.py:458-480`: Owner profile/user verification & RBAC domain parameter checks under Class 3 locks. |
| **I4: No Expired/Tampered Snapshot** | `snapshot_alive` | `commit_kernel.py:661-689`, `gateway.py`: Evidence timestamp validation (`valid_from <= now <= valid_to`) and SHA-256 fingerprint verification. |
| **I5: No Undisclosed Evidence** | `proposal_ev <= disclosed_ev` | `commit_kernel.py:661-689`: DB lookup of evidence fingerprints under profile scope; missing evidence raises `missing_evidence`. |
| **I6: Idempotent Replay One Transition** | $S' = S \land \Delta v = 0$ | `commit_kernel.py:389-407`: Returns `GlhsCommitResult(idempotent_replay=True)` without partition version increment. |
| **I7: Commit Advances Version Once** | $v' = v + 1$ | `commit_kernel.py:760-779`: `successor_version = predecessor_version + 1` enforced via CAS update statement. |
| **I8: Rejected Does Not Advance** | $S'.\text{canonical} = S.\text{canonical}$ | `commit_kernel.py`: Failed Phase 1-3 validation raises `GlhsInvariantError`, triggering DB rollback. No state changes persist. |
| **I9: Admitted Reconstructable** | $\text{apply}(S) = \text{Outcome}$ | Deterministic 6-phase commit engine with canonical JSON digests (`fast_canonical_digest()`). |
| **I10: Current Policy in Admission** | `proposal_policy == policy_version` | `commit_kernel.py:603-606`: `if expected_policy_version != current_policy_version: raise GlhsInvariantError("stale_policy_version")` |
| **I11: Clean Commit Reachable** | $\text{Path}(\text{init} \to \text{committed})$ | Verified by integration tests (`services/api/tests/test_glhs_commit_kernel.py`). |

---

## 5. Lock Hierarchy Refinement (Phantom Prevention)

Abstract serialization is refined to the 7-Class Total Order Lock Hierarchy (`lock_hierarchy.py`):
$$\text{Class 1} \prec \text{Class 2} \prec \text{Class 3} \prec \text{Class 4} \prec \text{Class 5} \prec \text{Class 6} \prec \text{Class 7}$$

1. **Class 1 (Tenant/Global Policy):** `pg_advisory_xact_lock_shared("policy_epoch:__global__")`
2. **Class 2 (Domain Policy):** `pg_advisory_xact_lock_shared("policy_epoch:<domain>")`
3. **Class 3 (Subject Consent & Profile):** `SELECT FOR SHARE` on `User(user_id)` and `PhrProfile(profile_id)`, plus advisory locks `user_consent:<user_id>` and `phr_profile:<profile_id>`.
4. **Class 4 (Evidence/Source):** Advisory locks on evidence keys.
5. **Class 5 (Entity Partitions):** `SELECT FOR SHARE` (READ) / `SELECT FOR UPDATE` (WRITE) on `GlhsEntityVersionPartition` in canonical lexicographical order $\prec_{\text{lex}}$.
6. **Class 6 (Lease/Reservation):** Advisory locks on lease keys.
7. **Class 7 (Idempotency Key):** `pg_advisory_xact_lock("idempotency:<tenant>:<op>:<key>")`.
