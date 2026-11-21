"""Replay one cold arm. stdout and stderr are the two observed egress pipes."""

import json
import os
import sys
from pathlib import Path
from time import perf_counter_ns

from evaluation.venue2027.popets.candidate import CacheEntry, RevocationCompleteCache
from evaluation.venue2027.popets.dispatch_fixture import History
from evaluation.venue2027.popets.dispatch_sender import recompute
from evaluation.venue2027.popets.sgd_workload import histories


def send(history: History, arm: str) -> list:
    if arm not in ("B1", "B2", "B4"):
        raise ValueError(arm)
    graph = RevocationCompleteCache() if arm == "B4" else None
    projections: dict[str, CacheEntry | str] = {}
    barrier = next((s for s in history.sources if s.retired is not None), None)
    costs = []
    for request in history.requests:
        start = perf_counter_ns()
        if barrier and barrier.retired is not None and request.time >= barrier.retired:
            if graph:
                graph.revoke(history.subject, barrier.purpose, 0)
            elif arm == "B1":
                projections.clear()
            barrier = None
        key = f"state/{request.source}"
        hit = False
        if graph:
            hit = graph.get(key, request.purpose, 0).status == "HIT"
        elif arm == "B1":
            hit = key in projections
        if hit:
            entry = projections[key]
            value = entry.value if isinstance(entry, CacheEntry) else entry
        else:
            value = recompute(history, request)
            if value is not None and graph:
                parent = f"source/{request.source}"
                graph.put(parent, value, [(history.subject, request.purpose, 0)])
                projections[key] = graph.put(
                    key, value, [("queue", request.purpose, 0)], derived_from=(parent,)
                )
            elif value is not None and arm == "B1":
                projections[key] = value
        if value is None:
            os.write(2, request.id.encode() + b"\n")
            operation = "deny"
        else:
            os.write(1, f"{request.id}\t{value}\n".encode())
            operation = "hit" if hit else "build"
        costs.append([request.id, operation, perf_counter_ns() - start])
    return costs


if __name__ == "__main__":
    arm, shape, cost_path = sys.argv[1:]
    records = [r for h in histories(json.loads(Path(shape).read_bytes())) for r in send(h, arm)]
    Path(cost_path).write_text(json.dumps(records, separators=(",", ":")))
