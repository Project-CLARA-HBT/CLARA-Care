"""Report matched-round savings; reject missing methods or timing cells."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median


def report(path, stage):
    size, candidate = {"first": (5, 3), "frontier": (8, 7), "published": (10, 7)}[stage]
    timings = defaultdict(dict)
    positions = defaultdict(set)
    with path.open() as f:
        for row in csv.DictReader(f):
            key = row["source"], int(row["round"])
            method, pos, ns = map(int, (row["method"], row["position"], row["ns"]))
            if method in timings[key] or pos in positions[key] or ns <= 0:
                raise ValueError(f"invalid timing cell {row}")
            timings[key][method] = ns
            positions[key].add(pos)
    sources = ("NanoArguAna", "NanoFiQA2018", "NanoSCIDOCS")
    methods = set(range(size))
    if timings.keys() != {(s, r) for s in sources for r in range(1, 13)}:
        raise ValueError("incomplete timing rounds")
    for key in timings:
        if timings[key].keys() != methods or positions[key] != methods:
            raise ValueError(f"incomplete crossover at {key}")
    label = "clip" if stage == "first" else "frontier"
    print(f"source,baseline,{label}_median_saving_pct,faster_rounds,slower_rounds")
    for s in sources:
        for m in sorted(methods - {candidate}):
            deltas = [1 - t[candidate] / t[m] for (g, _), t in timings.items() if g == s]
            print(
                f"{s},{m},{100 * median(deltas):.3f},"
                f"{sum(d > 0 for d in deltas)},{sum(d < 0 for d in deltas)}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timings", type=Path)
    parser.add_argument("--stage", choices=["first", "frontier", "published"], default="first")
    args = parser.parse_args()
    report(args.timings, args.stage)
