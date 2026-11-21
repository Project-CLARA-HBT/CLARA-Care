"""Check saved replay schedules without using the candidate simulator."""

import json
import sys
from pathlib import Path


def check(directory):
    tasks = json.loads((directory / "next.json").read_bytes())["tasks"]
    rows = json.loads((directory / "results.json").read_bytes())
    expected = {
        (n, m)
        for n in (2, 4, 8)
        for m in ("lexical", "longest", "critical", "portfolio", "swap", "constraint")
    }
    for row in rows:
        slots, starts = row["slots"], row["starts"]
        expected.remove((slots, row["method"]))
        if starts.keys() != tasks.keys():
            raise ValueError("task coverage")
        finishes = {k: t + tasks[k]["finish"] - tasks[k]["start"] for k, t in starts.items()}
        if max(finishes.values()) != row["makespan"] or min(starts.values()) != 0:
            raise ValueError("schedule bounds")
        for key, start in starts.items():
            if any(finishes[k] > start for k in tasks[key]["parents"]):
                raise ValueError("precedence")
            if sum(t <= start < finishes[k] for k, t in starts.items()) > slots:
                raise ValueError("slot use")
        if slots == 4:
            print(directory.name, row["method"], row["makespan"])
    if expected:
        raise ValueError("missing arm")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        check(Path(arg))
