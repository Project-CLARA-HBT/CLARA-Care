"""Verify pairing across all four development passes and summarize the GPU arm."""

import csv
from pathlib import Path

from .conditional import ARMS, NEW_ARMS, compare

KERNEL_METHODS = ("all_linear", "temperature_kernel", "joint_kernel", "additive_kernel")


def main():
    root = Path(__file__).resolve().parent
    rows = []
    mask_starts = {}
    for directory in ("periodic_results", "conditional_results", "kernel_results"):
        with (root / directory / "losses.csv").open() as handle:
            for row in csv.DictReader(handle):
                mask = row["station"], row["week"], row["hours"]
                if mask_starts.setdefault(mask, row["start"]) != row["start"]:
                    raise ValueError("inconsistent outage start across methods")
                rows.append(row)
    compare(rows, (*ARMS, *NEW_ARMS, *KERNEL_METHODS))


if __name__ == "__main__":
    main()
