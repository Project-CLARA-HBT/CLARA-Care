"""Derive the CP-SAT baseline priority using only historical durations."""

import json
import sys
from pathlib import Path

from ortools.sat.python import cp_model


def solve(jobs, slots):
    model = cp_model.CpModel()
    lengths = {key: row["finish"] - row["start"] for key, row in jobs.items()}
    horizon = sum(lengths.values())
    starts = {k: model.new_int_var(0, horizon - dur, k) for k, dur in lengths.items()}
    intervals = [model.new_fixed_size_interval_var(starts[k], dur, k) for k, dur in lengths.items()]
    model.add_cumulative(intervals, [1] * len(intervals), slots)
    for key, row in jobs.items():
        for parent in row["parents"]:
            model.add(starts[parent] + lengths[parent] <= starts[key])
    end = model.new_int_var(1, horizon, "finish")
    model.add_max_equality(end, [starts[k] + dur for k, dur in lengths.items()])
    model.minimize(end)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_deterministic_time = 2
    status = solver.solve(model)
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        raise ValueError(solver.status_name(status))
    return dict(
        status=solver.status_name(status),
        bound=solver.best_objective_bound,
        makespan=solver.value(end),
        wall_seconds=solver.wall_time,
        priority=sorted(starts, key=lambda k: (solver.value(starts[k]), k)),
    )


if __name__ == "__main__":
    tasks = json.loads(Path(sys.argv[1]).read_bytes())["tasks"]
    print(json.dumps({slots: solve(tasks, slots) for slots in (2, 4, 8)}, indent=2))
