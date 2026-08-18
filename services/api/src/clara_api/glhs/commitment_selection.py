"""Task/purpose-bounded relevance selection for Clinical Commitments (P5).

``select_relevant_commitments`` replaces the compiler's domain-only filter with
a task-bounded selection: only commitments that are the declared target, match
the declared target system/code, or sit inside the resolved dependency closure
are task-relevant.  Same-domain commitments that do not match are recorded as
``task_irrelevant`` exclusions and can never block the task.

Target semantics
----------------
* ``target_semantic_key`` names the target commitment by semantic key.
* ``target`` names it by FHIR-style ``{"system": ..., "code": ...}``.
* When neither is declared (legacy domain-scoped compilation), every
  same-domain visible commitment remains task-relevant and bad-state
  commitments keep their legacy blocking behavior.

Dependency closure
------------------
The closure starts from the caller-provided ``dependencies`` plus the target
commitment's own dependency list, and is resolved across the *visible* set
(any domain).  Dependency semantic keys with no visible commitment are
recorded in ``missing_dependencies``.  Cycles are detected with a bounded DFS
(never hangs), their members are excluded from the closure, and each cycle is
reported as a list of semantic keys in ``dependency_cycles``.

All output tuples are sorted so identical inputs always produce identical
output (and therefore identical snapshot digests).
"""

from __future__ import annotations

from typing import Any

BLOCKING_EVIDENCE_STATES = frozenset({"CONFLICTED", "INSUFFICIENT_EVIDENCE"})
TASK_IRRELEVANT_REASON = "task_irrelevant"


def _commitment_id(commitment: dict[str, Any]) -> str:
    return str(commitment["commitment_id"])


def _matches_target(
    commitment: dict[str, Any],
    *,
    target_semantic_key: str | None,
    target: dict[str, Any] | None,
) -> bool:
    if target_semantic_key is not None:
        if str(commitment.get("semantic_key")) == str(target_semantic_key):
            return True
    if target is not None:
        commitment_target = commitment.get("target")
        if isinstance(commitment_target, dict) and isinstance(target, dict):
            if commitment_target.get("system") == target.get("system") and commitment_target.get(
                "code"
            ) == target.get("code"):
                return True
    return False


def _closure_edges(
    visible_by_key: dict[str, dict[str, Any]],
    seeds: tuple[str, ...],
) -> tuple[set[str], set[str], list[tuple[str, ...]]]:
    """Resolve the dependency closure with cycle detection.

    Returns ``(closure, missing, cycles)`` where ``closure`` excludes every
    semantic key that participates in a cycle, ``missing`` holds dependency
    keys with no visible commitment, and ``cycles`` holds the detected cycles
    as semantic-key paths (first element repeated at the end).
    """

    seen: set[str] = set()
    in_cycle: set[str] = set()
    cycles: list[tuple[str, ...]] = []

    def visit(key: str, path: list[str]) -> None:
        if key in path:
            # Back edge: a dependency on the current DFS path forms a cycle.
            cycle = tuple(path[path.index(key):] + [key])
            cycles.append(cycle)
            in_cycle.update(cycle)
            return
        if key in in_cycle or key in seen:
            return
        commitment = visible_by_key.get(key)
        if commitment is None:
            return
        seen.add(key)
        path.append(key)
        for dependency in commitment.get("dependencies") or ():
            visit(str(dependency), path)
        path.pop()

    for seed in seeds:
        visit(seed, [])

    missing: set[str] = set()
    closure: set[str] = set()
    pending = list(seeds)
    expanded: set[str] = set()
    while pending:
        key = pending.pop(0)
        if key in expanded or key in in_cycle:
            continue
        commitment = visible_by_key.get(key)
        if commitment is None:
            missing.add(key)
            continue
        closure.add(key)
        expanded.add(key)
        for dependency in commitment.get("dependencies") or ():
            dependency_key = str(dependency)
            if dependency_key in in_cycle:
                continue
            if visible_by_key.get(dependency_key) is None:
                missing.add(dependency_key)
            elif dependency_key not in expanded:
                pending.append(dependency_key)
    return closure, missing, cycles


def select_relevant_commitments(
    visible: tuple[dict[str, Any], ...],
    *,
    task: str,
    purpose: str,
    allowed_domains: frozenset[str],
    target_semantic_key: str | None = None,
    target: dict[str, Any] | None = None,
    dependencies: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Select the task-relevant commitments from a bitemporal visible set.

    ``task`` and ``purpose`` are accepted for signature stability with the
    compiler; selection is bounded by the declared target/closure and the
    authorized domains.
    """

    visible_by_key = {str(item.get("semantic_key")): item for item in visible}
    target_declared = target_semantic_key is not None or target is not None
    target_commitment: dict[str, Any] | None = None
    for item in visible:
        if _matches_target(
            item, target_semantic_key=target_semantic_key, target=target
        ):
            target_commitment = item
            break

    seeds: list[str] = [str(dependency) for dependency in dependencies]
    if target_commitment is not None:
        seeds.extend(str(dependency) for dependency in target_commitment.get("dependencies") or ())
    closure, missing, cycles = _closure_edges(visible_by_key, tuple(seeds))

    same_domain = sorted(
        (item for item in visible if item.get("domain") in allowed_domains),
        key=_commitment_id,
    )

    relevant: list[dict[str, Any]] = []
    irrelevant: list[dict[str, Any]] = []
    for item in same_domain:
        is_target = target_declared and _matches_target(
            item, target_semantic_key=target_semantic_key, target=target
        )
        in_closure = str(item.get("semantic_key")) in closure
        if is_target or in_closure or not target_declared:
            relevant.append(item)
        else:
            irrelevant.append(item)

    blocking: list[dict[str, Any]] = []
    for item in relevant:
        is_target = target_declared and _matches_target(
            item, target_semantic_key=target_semantic_key, target=target
        )
        in_closure = str(item.get("semantic_key")) in closure
        if item.get("evidence_state") not in BLOCKING_EVIDENCE_STATES:
            continue
        if is_target or in_closure or not target_declared:
            blocking.append(item)

    visible_conflicts_irrelevant = tuple(
        sorted(
            _commitment_id(item)
            for item in irrelevant
            if item.get("evidence_state") == "CONFLICTED"
        )
    )
    sorted_cycles = tuple(
        sorted(cycles, key=lambda cycle: tuple(str(key) for key in cycle))
    )
    return {
        "relevant": tuple(relevant),
        "irrelevant_exclusions": tuple(
            {"commitment_id": _commitment_id(item), "reason": TASK_IRRELEVANT_REASON}
            for item in irrelevant
        ),
        "blocking": tuple(blocking),
        "visible_conflicts_irrelevant": visible_conflicts_irrelevant,
        "dependency_ids": tuple(sorted(closure)),
        "missing_dependencies": tuple(sorted(missing)),
        "dependency_cycles": sorted_cycles,
        "blocked": bool(blocking),
        "target_commitment": target_commitment,
    }
