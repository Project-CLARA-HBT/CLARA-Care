"""Reconcile per-outage losses, validation selections and paired weekly intervals."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from ..run import HASHES, LENGTHS


def summarize(results, previous):
    selected = "validation_selected"
    primary = "temperature_kernel"
    grid = {}
    for data in [*previous, results / "losses.csv"]:
        with data.open() as handle:
            for row in csv.DictReader(handle):
                key = row["station"], int(row["hours"]), int(row["week"])
                values = grid.setdefault(key, {"start": row["start"]})
                if values["start"] != row["start"] or row["method"] in values:
                    raise ValueError(f"mispaired loss {key}")
                values[row["method"]] = float(row["mae"])
    validation = json.loads((results / "validation.json").read_text())["validation"]
    methods = sorted(next(iter(grid.values())).keys() - {"start"})
    if len(methods) != 19 or len(grid) != 174:
        raise ValueError("incomplete method or mask set")
    weeks = range(73, 102)
    for s in HASHES:
        for h in LENGTHS:
            info = validation[f"{s}_{h}"]
            best = min((r for r in info["settings"] if "mae" in r), key=lambda r: r["mae"])
            assert best["family"] == info["selected"]
            for w in weeks:
                row = grid[s, h, w]
                assert row.keys() == {"start", *methods}
                assert row[selected] == row[best["family"]]
    idx = np.random.default_rng(712).integers(29, size=(10000, 8))
    blocks = ((idx[:, :, None] + np.arange(4)) % 29).reshape(10000, -1)[:, :29]
    weekly = {
        m: np.array([np.mean([grid[s, h, w][m] for s in HASHES for h in LENGTHS]) for w in weeks])
        for m in methods
    }
    print(
        "method,macro_mae,relative_reduction_vs_method,paired_diff_low,paired_diff_high,selected_wins,ties,selected_losses"
    )
    for m in methods:
        differences = [r[m] - r[selected] for r in grid.values()]
        diff = weekly[m] - weekly[selected]
        low, high = np.percentile(diff[blocks].mean(axis=1), [2.5, 97.5])
        print(
            f"{m},{weekly[m].mean():.8f},{diff.mean() / weekly[m].mean():.8f},{low:.8f},{high:.8f},"
            f"{sum(d > 0 for d in differences)},{sum(d == 0 for d in differences)},{sum(d < 0 for d in differences)}"
        )
    assert primary in methods


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("previous", type=Path, nargs=3)
    args = parser.parse_args()
    summarize(args.results, args.previous)
