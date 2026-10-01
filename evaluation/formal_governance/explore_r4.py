"""Bounded Exhaustive State-Space Explorer for GLHS R4 Invariants (I16–I24).

Implements BFS exploration over the R4 state space checking:
- I16: Current-State Insufficiency Counterexample (Theorem T1)
- I17: Global Source Support vs. Disclosed Support Separation (Theorem T2)
- I18: Two-Digest Transport Independence
- I19: Non-Malleable Lineage Continuity
- I20: Anti-Laundering Human Review Gate
- I21: Canonical Lock Hierarchy Deadlock Freedom
- I22: Dynamic Governance Precedence
- I23: Deterministic Replay Parity
- I24: Clean Path Reachability
"""

from __future__ import annotations

import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.formal_governance.model_r4 import (
    R4Binding,
    R4Proposal,
    R4State,
    check_r4_invariants,
    evaluate_c0,
    evaluate_c1,
    evaluate_c2,
    evaluate_c3,
    evaluate_c4,
)


def explore_r4(max_depth: int = 6) -> dict[str, Any]:
    """Execute BFS bounded state-space exploration up to max_depth."""
    t0 = time.perf_counter()

    init_binding = R4Binding(
        public_id="b0",
        status="PENDING",
        snapshot_version=1,
        consent_epoch=1,
        policy_epoch=1,
        disclosed_evidence=("e0", "e1"),
        h_proj="hash_e0_e1",
        h_sem="hash_sem_init",
        h_trans="hash_trans_init",
        attestation_level="L0_ENVELOPE",
    )
    init_state = R4State(
        db_state_version=1,
        db_consent_epoch=1,
        db_policy_epoch=1,
        db_evidence=("e0", "e1", "e2"),
        bindings=(init_binding,),
        proposals=(),
    )

    visited: set[R4State] = {init_state}
    queue: deque[tuple[R4State, int]] = deque([(init_state, 0)])

    transitions_explored = 0
    violations_detected: list[str] = []
    deadlock_detected = False

    while queue:
        current, depth = queue.popleft()

        # Invariant verification
        v = check_r4_invariants(current)
        if v:
            violations_detected.extend(v)

        if depth >= max_depth:
            continue

        # Generate successors
        successors: list[R4State] = []

        # 1. Mutate DB state
        if current.db_state_version < 3:
            successors.append(
                R4State(
                    db_state_version=current.db_state_version + 1,
                    db_consent_epoch=current.db_consent_epoch,
                    db_policy_epoch=current.db_policy_epoch,
                    db_evidence=current.db_evidence,
                    bindings=current.bindings,
                    proposals=current.proposals,
                )
            )

        # 2. Revoke consent
        if current.db_consent_epoch < 3:
            successors.append(
                R4State(
                    db_state_version=current.db_state_version,
                    db_consent_epoch=current.db_consent_epoch + 1,
                    db_policy_epoch=current.db_policy_epoch,
                    db_evidence=current.db_evidence,
                    bindings=current.bindings,
                    proposals=current.proposals,
                )
            )

        # 3. Update policy epoch
        if current.db_policy_epoch < 3:
            successors.append(
                R4State(
                    db_state_version=current.db_state_version,
                    db_consent_epoch=current.db_consent_epoch,
                    db_policy_epoch=current.db_policy_epoch + 1,
                    db_evidence=current.db_evidence,
                    bindings=current.bindings,
                    proposals=current.proposals,
                )
            )

        # 4. Dispatch FSM transitions
        new_bindings = list(current.bindings)
        binding_modified = False
        for i, b in enumerate(current.bindings):
            if b.status == "PENDING":
                new_bindings[i] = R4Binding(
                    public_id=b.public_id,
                    status="DISPATCHED",
                    snapshot_version=b.snapshot_version,
                    consent_epoch=b.consent_epoch,
                    policy_epoch=b.policy_epoch,
                    disclosed_evidence=b.disclosed_evidence,
                    h_proj=b.h_proj,
                    h_sem=b.h_sem,
                    h_trans="hash_trans_outbound",
                    attestation_level="L1_TRANSPORT",
                )
                binding_modified = True
                break
            elif b.status == "DISPATCHED":
                new_bindings[i] = R4Binding(
                    public_id=b.public_id,
                    status="COMPLETED",
                    snapshot_version=b.snapshot_version,
                    consent_epoch=b.consent_epoch,
                    policy_epoch=b.policy_epoch,
                    disclosed_evidence=b.disclosed_evidence,
                    h_proj=b.h_proj,
                    h_sem=b.h_sem,
                    h_trans=b.h_trans,
                    attestation_level=b.attestation_level,
                )
                binding_modified = True
                break

        if binding_modified:
            successors.append(
                R4State(
                    db_state_version=current.db_state_version,
                    db_consent_epoch=current.db_consent_epoch,
                    db_policy_epoch=current.db_policy_epoch,
                    db_evidence=current.db_evidence,
                    bindings=tuple(new_bindings),
                    proposals=current.proposals,
                )
            )

        # 5. Generate Proposals if completed binding exists
        completed_b = next((b for b in current.bindings if b.status == "COMPLETED"), None)
        if completed_b and len(current.proposals) < 3:
            # Clean proposal
            p_clean = R4Proposal(
                proposal_id=f"p_clean_{len(current.proposals)}",
                binding_id=completed_b.public_id,
                base_state_version=completed_b.snapshot_version,
                consent_epoch=completed_b.consent_epoch,
                policy_epoch=completed_b.policy_epoch,
                asserted_evidence=completed_b.disclosed_evidence,
                observed_projection=completed_b.h_proj,
            )
            # Attack proposal: substituted projection (I16)
            p_sub = R4Proposal(
                proposal_id=f"p_sub_{len(current.proposals)}",
                binding_id=completed_b.public_id,
                base_state_version=completed_b.snapshot_version,
                consent_epoch=completed_b.consent_epoch,
                policy_epoch=completed_b.policy_epoch,
                asserted_evidence=completed_b.disclosed_evidence,
                observed_projection="hash_substituted_projection",
            )
            # Attack proposal: undisclosed evidence (I17)
            p_undisclosed = R4Proposal(
                proposal_id=f"p_undisc_{len(current.proposals)}",
                binding_id=completed_b.public_id,
                base_state_version=completed_b.snapshot_version,
                consent_epoch=completed_b.consent_epoch,
                policy_epoch=completed_b.policy_epoch,
                asserted_evidence=("e0", "e2"),  # e2 not disclosed
                observed_projection=completed_b.h_proj,
            )

            for p_cand in (p_clean, p_sub, p_undisclosed):
                if p_cand not in current.proposals:
                    successors.append(
                        R4State(
                            db_state_version=current.db_state_version,
                            db_consent_epoch=current.db_consent_epoch,
                            db_policy_epoch=current.db_policy_epoch,
                            db_evidence=current.db_evidence,
                            bindings=current.bindings,
                            proposals=current.proposals + (p_cand,),
                        )
                    )

        # 6. Commit proposal if admissible under C4
        for p in current.proposals:
            if evaluate_c4(current, p):
                successors.append(
                    R4State(
                        db_state_version=current.db_state_version + 1,
                        db_consent_epoch=current.db_consent_epoch,
                        db_policy_epoch=current.db_policy_epoch,
                        db_evidence=current.db_evidence,
                        bindings=current.bindings,
                        proposals=tuple(pr for pr in current.proposals if pr != p),
                    )
                )

        if not successors and depth < max_depth:
            deadlock_detected = True

        for succ in successors:
            transitions_explored += 1
            if succ not in visited:
                visited.add(succ)
                queue.append((succ, depth + 1))

    duration_s = time.perf_counter() - t0
    return {
        "max_depth": max_depth,
        "distinct_states_explored": len(visited),
        "transitions_explored": transitions_explored,
        "invariant_violations": len(violations_detected),
        "violations_list": violations_detected,
        "deadlock_detected": deadlock_detected,
        "duration_seconds": round(duration_s, 4),
    }


if __name__ == "__main__":
    for d in (3, 4, 5):
        res = explore_r4(max_depth=d)
        print(f"Depth d={d}: {res['distinct_states_explored']} states, {res['transitions_explored']} transitions, {res['invariant_violations']} violations in {res['duration_seconds']}s")
