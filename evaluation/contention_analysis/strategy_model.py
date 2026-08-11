"""Deterministic version-granularity mechanism model; never production state."""

from __future__ import annotations

from dataclasses import dataclass

STRATEGIES = ("profile_global", "resource_partition", "dependency_hybrid")


@dataclass(frozen=True)
class ModelProposal:
    proposal_id: str
    resource_partition: str
    dependencies: frozenset[str]


def proposals(workload: str, concurrency: int) -> tuple[ModelProposal, ...]:
    if workload not in {"same_dependency", "unrelated_slots"}:
        raise ValueError("unknown_contention_workload")
    if concurrency < 1:
        raise ValueError("contention_concurrency_invalid")
    return tuple(
        ModelProposal(
            proposal_id=f"proposal-{index}",
            resource_partition=(
                "medication:shared" if workload == "same_dependency" else f"medication:{index}"
            ),
            dependencies=frozenset(
                {"medication:shared"}
                if workload == "same_dependency"
                else {f"medication:{index}"}
            ),
        )
        for index in range(concurrency)
    )


def evaluate(strategy: str, items: tuple[ModelProposal, ...]) -> dict[str, int]:
    """Apply one deterministic simultaneous-batch abstraction.

    Every proposal observes version zero. Ordering by proposal ID is only a
    deterministic winner selection; this model does not estimate latency.
    """

    if strategy not in STRATEGIES:
        raise ValueError("unknown_version_strategy")
    accepted: list[ModelProposal] = []
    true_stale = 0
    false_stale = 0
    for item in sorted(items, key=lambda proposal: proposal.proposal_id):
        if strategy == "profile_global":
            overlaps = bool(accepted)
        elif strategy == "resource_partition":
            overlaps = any(
                prior.resource_partition == item.resource_partition for prior in accepted
            )
        else:
            overlaps = any(prior.dependencies & item.dependencies for prior in accepted)
        if not overlaps:
            accepted.append(item)
            continue
        if any(prior.dependencies & item.dependencies for prior in accepted):
            true_stale += 1
        else:
            false_stale += 1
    return {
        "attempts": len(items),
        "accepted": len(accepted),
        "true_stale": true_stale,
        "false_stale": false_stale,
    }


def matrix(workloads: tuple[str, ...], levels: tuple[int, ...]) -> list[dict[str, object]]:
    return [
        {
            "workload": workload,
            "concurrency": concurrency,
            "strategy": strategy,
            **evaluate(strategy, proposals(workload, concurrency)),
        }
        for workload in workloads
        for concurrency in levels
        for strategy in STRATEGIES
    ]
