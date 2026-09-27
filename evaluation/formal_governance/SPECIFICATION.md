# Formal Governance Assurance: Model Specification (E08)

## 1. Overview & Architectural Scope

The Formal Governance Assurance workstream (E08) defines a canonical, finite state machine modeling the formal invariants of governed commits within the CLARA Clinical Agent for Retrieval & Analysis system (GLHS substrate).

The model isolates the decision-critical coordinates governing state transitions:
- **Who:** `subject`, `actor`, `role`
- **For what:** `purpose`, `task`
- **Against which versions:** `state_version`, `policy_version`, `consent_version`, `consent_state`
- **Under which authorization artifacts:** `snapshot_id`, `digest_valid`, `expiry`, `disclosed_evidence_set`, `proposal_base`, `proposal_binding`, `proposal_evidence`
- **With what outcome:** `idempotency_key`, `committed_keys`, `commit_status`, `origin`

---

## 2. Canonical Coordinate Domains & Finite State Space

To enable bounded exhaustive model checking, all coordinate domains are finite and saturating:

| Coordinate | Domain / Bound | Description |
| :--- | :--- | :--- |
| `subject`, `actor`, `task` | `{"s0"}`, `{"a0"}`, `{"t0"}` | Fixed single entities for standard sweep |
| `role` | `{"r0", "r1"}` | Subject role coordinates |
| `purpose` | `{"p0", "p1"}` | Purpose coordinates |
| `state_version` | `{0, 1}` (saturates at `MAX_VERSION=1`) | Version counter |
| `policy_version` | `{0, 1}` (saturates at `MAX_VERSION=1`) | Policy epoch counter |
| `consent_version` | `{0, 1}` (saturates at `MAX_VERSION=1`) | Consent revision counter |
| `consent_state` | `{"granted", "revoked"}` | Active consent state |
| `snapshot_id` | `str | None` | Deterministic SHA-256 disclosure digest |
| `digest_valid` | `bool` | Integrity bit for disclosure snapshot |
| `expiry` | `{None, 0 (EXPIRED), 1 (TTL)}` | Snapshot expiration sentinel |
| `disclosed_evidence_set` | Subsets of `{"e0", "e1"}` | Disclosed evidence universe |
| `proposal_base` | `{None, 0, 1}` | Observed base state version at proposal creation |
| `proposal_binding` | `bool` | Whether proposal binds to disclosure snapshot |
| `proposal_evidence` | Subsets of `{"e0", "e1"}` | Required evidence set in proposal |
| `idempotency_key` | `{None, "k0"}` | Client idempotency token |
| `commit_status` | `{"none", "applied", "rejected", "rolled_back"}` | Transaction status |

---

## 3. Transition Function Catalog

Transitions are pure functions: $\text{apply}(S, T, P) \to \text{Outcome}(\text{admitted}: \text{bool}, S', \text{reason}: \text{str}, \text{idempotent}: \text{bool})$.

1. **`issue_disclosure(state, evidence, expiry)`**: Generates a snapshot digest bound to current coordinates. Rejected if `consent_state != "granted"`.
2. **`create_proposal(state, binding, evidence, idempotency_key)`**: Records current coordinates as expected proposal base. Rejected if `binding` is requested without alive snapshot or with undisclosed evidence.
3. **`advance_state(state)`**: Advances `state_version` by 1 (saturating).
4. **`advance_policy(state)`**: Advances `policy_version` by 1 (saturating).
5. **`revoke_consent(state)`**: Changes `consent_state` to `"revoked"` and advances `consent_version`.
6. **`change_role(state, role)`**: Updates subject role.
7. **`change_purpose(state, purpose)`**: Updates transaction purpose.
8. **`expire_snapshot(state)`**: Sets `expiry` to `EXPIRED` sentinel.
9. **`corrupt_digest(state)`**: Sets `digest_valid` to `False`.
10. **`commit(state)`**: Executes atomic commit predicate. On success, advances `state_version`, clears in-flight proposal/snapshot, records `idempotency_key`, and sets `commit_status="applied"`. On failure, records `commit_status="rejected"` without altering canonical state coordinates.
11. **`replay_proposal(state)`**: Re-submits proposal. If `idempotency_key` is already committed, returns `idempotent=True` with state unchanged. Otherwise re-runs admission predicate.
12. **`retry(state)`**: Re-attempts a previously rejected commit (`commit_status == "rejected"`). Re-evaluates admission predicate fail-closed.
13. **`rollback(state)`**: Decrements `state_version` by 1 iff `commit_status == "applied"`.

---

## 4. Formal Invariant Definitions (I1 - I11)

All 11 invariants are machine-checkable invariants evaluated independently of transition admission:

- **I1 (No Stale Base Commit):** A bound proposal cannot commit if `proposal_base != state_version`.
  $$\forall S \xrightarrow{\text{commit}} S', \quad S.\text{proposal\_base} = S.\text{state\_version}$$
- **I2 (No Post-Revocation Commit):** No commit can succeed if `consent_state != "granted"` or `proposal_consent_version != consent_version`.
  $$\forall S \xrightarrow{\text{commit}} S', \quad S.\text{consent\_state} = \text{"granted"} \land S.\text{proposal\_consent\_version} = S.\text{consent\_version}$$
- **I3 (No Wrong Coordinate Commit):** No commit can succeed if proposal coordinates (`actor`, `role`, `purpose`, `task`) differ from active state coordinates.
  $$\forall S \xrightarrow{\text{commit}} S', \quad S.\text{proposal\_coord} = S.\text{active\_coord}$$
- **I4 (No Expired/Tampered Snapshot Commit):** A bound commit requires a valid, unexpired disclosure snapshot (`has_snapshot \land digest_valid \land expiry > 0`).
- **I5 (No Undisclosed Evidence):** Proposal evidence must be a subset of disclosed evidence (`proposal_evidence \subseteq disclosed_evidence_set`).
- **I6 (Idempotent Replay One Transition):** Re-executing an already committed idempotency key yields $S' = S$ with zero version advance.
- **I7 (Commit Advances Once):** An admitted non-replay commit advances `state_version` by exactly 1 ($S'.\text{state\_version} = \text{bump}(S.\text{state\_version})$).
- **I8 (Rejected Does Not Advance):** A rejected transition preserves canonical coordinates ($S'.\text{canonical} = S.\text{canonical}$).
- **I9 (Admitted Transition Reconstructable):** Deterministic re-application of the same transition to source state yields identical outcome ($\text{apply}(S, T, P) = \text{Outcome}$).
- **I10 (Current Policy in Admission):** No commit can succeed if `proposal_policy_version != policy_version`.
- **I11 (Clean Commit Reachable):** A valid proposal constructed from a clean initial state can successfully commit ($\text{Path}(\text{initial} \to \text{committed}) \text{ exists}$).

---

## 5. Verification Methodology Distinction

| Dimension | Bounded Exhaustive Exploration | Property-Based Testing (Hypothesis) | Universal Formal Proof (TLA+/Lean) |
| :--- | :--- | :--- | :--- |
| **Search Space** | 100% complete sweep of all reachable states up to depth $d$ | Stochastically sampled paths across open domains | Infinite state space symbolic verification |
| **Guarantee** | Zero counterexamples within bounded radius ($d \le 6$) | High probabilistic confidence; may miss sparse edge cases | Universal mathematical proof for all states |
| **Execution Time** | Seconds ($\sim 2.45$s for $d=5$, $\sim 11.0$s for $d=6$) | Seconds to minutes depending on sample count | Seconds to hours (solver-dependent) |
| **Role in E08** | Primary verification engine (`explore.py`) | Secondary input space validation | Theoretical semantic foundation |

---

## 6. Code Hash Binding & Reproducibility

Every exploration report binds the SHA-256 digests of the four core implementation files:
- `evaluation/formal_governance/model.py`
- `evaluation/formal_governance/transitions.py`
- `evaluation/formal_governance/invariants.py`
- `evaluation/formal_governance/explore.py`

This ensures full auditability and immutability of the governance model.
