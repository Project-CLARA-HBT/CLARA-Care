"""Bounded exhaustive enumerator over canonical governance states.

The enumerator performs breadth-first search from a small set of initial
states, applying every transition with every combination of parameters from the
finite domains defined here.  It:

  * deduplicates canonical states (full ``State`` equality),
  * checks state and transition invariants on every reached state / attempted
    transition,
  * retains minimal (shortest-path) counterexamples per violated invariant,
  * reports unique states, transitions explored, max depth, violations,
    runtime, tool version, and the source SHA of the checked modules.

Run directly::

    python -m evaluation.formal_governance.explore
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
from pathlib import Path

from .invariants import check_i11, state_invariants, transition_invariants
from .model import (
    COMMIT_APPLIED,
    COMMIT_REJECTED,
    CONSENT_GRANTED,
    EVIDENCE_UNIVERSE,
    TTL,
    State,
    initial_state,
)
from .transitions import Outcome, apply

TOOL_VERSION = "w5-formal-assure-v1.0"
DEFAULT_MAX_DEPTH = 5

# Small finite coordinate / parameter domains (bounded exhaustive).
SUBJECTS = ("s0",)
ACTORS = ("a0",)
ROLES = ("r0", "r1")
PURPOSES = ("p0", "p1")
TASKS = ("t0",)
KEYS = (None, "k0")
EVIDENCE_SUBSETS = tuple(
    frozenset(sub)
    for n in range(len(EVIDENCE_UNIVERSE) + 1)
    for sub in combinations(sorted(EVIDENCE_UNIVERSE), n)
)

StateCheck = Callable[[State], list[str]]
TransitionCheck = Callable[[State, str, dict[str, object], Outcome], list[str]]


@dataclass(frozen=True)
class Counterexample:
    """Shortest-path evidence of one invariant violation."""

    invariant: str
    path: tuple[str, ...]
    source: State
    transition: str
    reason: str


def default_initial_states() -> tuple[State, ...]:
    """One clean initial state; coordinates are fixed by the enumerator so the
    reachable space stays small while still covering every transition."""
    return (initial_state(subject="s0", actor="a0", role="r0", purpose="p0", task="t0"),)


def transition_catalog(state: State) -> list[tuple[str, dict[str, object]]]:
    """Every (name, params) pair attempted from a state.

    Transitions that can never be admitted from a state (e.g. expiring a
    non-existent snapshot) are skipped so the enumeration stays bounded, while
    every transition that can *meaningfully* succeed or fail is attempted from
    every state.  Unbound proposals carry no evidence (base-version-only path),
    and a disclosure is issued at most one live snapshot at a time.
    """
    catalog: list[tuple[str, dict[str, object]]] = [
        ("advance_state", {}),
        ("advance_policy", {}),
        ("commit", {}),
        ("replay_proposal", {}),
    ]
    if state.consent_state == CONSENT_GRANTED:
        catalog.append(("revoke_consent", {}))
    if state.has_snapshot:
        catalog.append(("expire_snapshot", {}))
        catalog.append(("corrupt_digest", {}))
    if state.commit_status == COMMIT_REJECTED:
        catalog.append(("retry", {}))
    if state.commit_status == COMMIT_APPLIED:
        catalog.append(("rollback", {}))
    if not state.has_snapshot:
        for evidence in EVIDENCE_SUBSETS:
            catalog.append(("issue_disclosure", {"evidence": evidence, "expiry": TTL}))
    for role in ROLES:
        catalog.append(("change_role", {"role": role}))
    for purpose in PURPOSES:
        catalog.append(("change_purpose", {"purpose": purpose}))
    for key in KEYS:
        catalog.append(
            ("create_proposal", {"binding": False, "evidence": frozenset(), "idempotency_key": key})
        )
    if state.snapshot_alive:
        for evidence in EVIDENCE_SUBSETS:
            for key in KEYS:
                catalog.append(
                    (
                        "create_proposal",
                        {"binding": True, "evidence": evidence, "idempotency_key": key},
                    )
                )
    return catalog


def _label(name: str, params: dict[str, object]) -> str:
    rendered = ",".join(f"{k}={v!r}" for k, v in sorted(params.items()))
    return name if not rendered else f"{name}({rendered})"


def _source_sha() -> str:
    """SHA-256 of the checked modules' source (model/transitions/invariants)."""
    here = Path(__file__).resolve().parent
    digest = sha256()
    for filename in ("model.py", "transitions.py", "invariants.py", "explore.py"):
        digest.update(f"{filename}\n".encode())
        digest.update((here / filename).read_bytes())
    return digest.hexdigest()


def explore(
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    initial_states: tuple[State, ...] | None = None,
    state_check_extra: StateCheck | None = None,
    transition_check_extra: TransitionCheck | None = None,
) -> dict[str, object]:
    """Run the bounded exhaustive enumeration and return a report dict."""
    starts = default_initial_states() if initial_states is None else initial_states
    started = time.perf_counter()

    seen: dict[State, int] = {}
    parent: dict[State, tuple[State, str] | None] = {}
    queue: deque[State] = deque()
    for st in starts:
        if st not in seen:
            seen[st] = 0
            parent[st] = None
            queue.append(st)

    transitions_attempted: set[tuple[State, str, State, bool, str]] = set()
    transition_counts: dict[str, int] = {}
    violations: dict[str, Counterexample] = {}
    admitted_commits = 0
    idempotent_replays = 0
    rejected = 0
    admitted = 0
    max_depth_reached = 0

    def record_violation(invariant: str, cur: State, name: str, outcome: Outcome) -> None:
        if invariant in violations:
            return
        path: tuple[str, ...] = ()
        node: State | None = cur
        while node is not None:
            prev = parent.get(node)
            if prev is None:
                break
            node, step_label = prev
            path = (step_label,) + path
        violations[invariant] = Counterexample(
            invariant=invariant,
            path=path + (name,),
            source=cur,
            transition=name,
            reason=outcome.reason,
        )

    for st in starts:
        for inv in state_invariants(st):
            record_violation(inv, st, "<initial>", Outcome(True, st, "initial"))

    while queue:
        cur = queue.popleft()
        depth = seen[cur]
        if depth >= max_depth:
            continue
        for name, params in transition_catalog(cur):
            outcome = apply(cur, name, **params)
            label = _label(name, params)
            transitions_attempted.add((cur, label, outcome.state, outcome.admitted, outcome.reason))
            transition_counts[name] = transition_counts.get(name, 0) + 1
            if outcome.admitted:
                admitted += 1
                if outcome.idempotent:
                    idempotent_replays += 1
                elif outcome.reason == "committed":
                    admitted_commits += 1
            else:
                rejected += 1

            for inv in state_invariants(outcome.state):
                record_violation(inv, cur, name, outcome)
            for inv in transition_invariants(cur, name, params, outcome):
                record_violation(inv, cur, name, outcome)
            if state_check_extra is not None:
                for inv in state_check_extra(outcome.state):
                    record_violation(inv, cur, name, outcome)
            if transition_check_extra is not None:
                for inv in transition_check_extra(cur, name, params, outcome):
                    record_violation(inv, cur, name, outcome)

            # Enqueue any genuinely new state.  This includes the rejected-commit
            # marker states (from which ``retry`` is reachable) and the fresh
            # post-transition states; idempotent replays and no-op rejections map
            # back to the source and are already ``seen``.
            nxt = outcome.state
            if nxt not in seen:
                seen[nxt] = depth + 1
                parent[nxt] = (cur, label)
                queue.append(nxt)
                max_depth_reached = max(max_depth_reached, depth + 1)

    runtime = time.perf_counter() - started
    canonical_sets = {st.canonical for st in seen}
    return {
        "tool_version": TOOL_VERSION,
        "source_sha": _source_sha(),
        "max_depth": max_depth,
        "max_depth_reached": max_depth_reached,
        "states": len(seen),
        "distinct_canonical_coordinates": len(canonical_sets),
        "transitions_explored": len(transitions_attempted),
        "transition_counts": dict(sorted(transition_counts.items())),
        "admitted": admitted,
        "rejected": rejected,
        "admitted_commits": admitted_commits,
        "idempotent_replays": idempotent_replays,
        "violation_count": len(violations),
        "violations": sorted(
            (v.invariant, v.path, v.source, v.transition, v.reason) for v in violations.values()
        ),
        "i11_clean_commit_reachable": check_i11(starts[0]),
        "runtime_seconds": round(runtime, 4),
    }


def main() -> None:
    report = explore()
    print("== W5 formal/exhaustive assurance: bounded enumeration ==")
    for key, value in report.items():
        if key == "violations":
            continue
        print(f"  {key}: {value}")
    for violation in report["violations"]:
        print(f"  VIOLATION {violation}")


if __name__ == "__main__":
    main()
