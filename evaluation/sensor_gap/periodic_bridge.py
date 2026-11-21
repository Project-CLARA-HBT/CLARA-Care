"""Evaluate the frozen periodic shape correction on the first study's masks."""

import argparse
import csv
from pathlib import Path

import numpy as np

from .run import HASHES, LENGTHS, METHODS, SPLIT, load, windows

ARMS = (*METHODS, "two_days", "training_profile", "six_days", "reliability")


def daily_profiles(target, indices, slope):
    values = target[indices] - slope * (indices - indices[:, :1])
    centered = values - values.mean(axis=1, keepdims=True)
    return np.take_along_axis(centered, np.argsort(indices % 24, axis=1), axis=1)


def predict(target, start, length, training_profile):
    left = np.arange(start - 72, start).reshape(3, 24)
    right = np.arange(start + length, start + length + 72).reshape(3, 24)
    delta = np.concatenate([np.diff(target[idx], axis=0).ravel() for idx in (left, right)])
    days = daily_profiles(target, np.concatenate([left, right]), np.median(delta) / 24)
    first, second = days[::2].mean(axis=0), days[1::2].mean(axis=0)
    energy = (first @ first + second @ second) / 2
    weight = np.clip((first @ second) / energy, 0, 1) if energy > 0 else 0.0
    t = np.arange(start, start + length)
    ends = np.array([start - 1, start + length])
    line = np.interp(t, ends, target[ends])
    predictions = {}
    for name, profile in (
        ("two_days", days[[2, 3]].mean(axis=0)),
        ("training_profile", training_profile),
        ("six_days", days.mean(axis=0)),
        ("reliability", weight * days.mean(axis=0)),
    ):
        predictions[name] = line + profile[t % 24] - np.interp(t, ends, profile[ends % 24])
    return predictions


def verify_exact_family():
    t = np.arange(800)
    target = 7.0 + 0.2 * t + np.sin(2 * np.pi * t / 24)
    for length in LENGTHS:
        for phase in range(24):
            start = 400 + phase
            masked = target.copy()
            masked[start : start + length] = np.nan
            pred = predict(masked, start, length, np.zeros(24))
            for name in ("two_days", "six_days", "reliability"):
                np.testing.assert_allclose(pred[name], target[start : start + length], atol=1e-10)


def compare(cache, original):
    with original.open() as f:
        rows = list(csv.DictReader(f))
    for station in HASHES:
        times, measurements = load(cache, station)
        target = measurements[:, -1]
        idx = np.arange(SPLIT).reshape(-1, 24)
        slope = np.median(target[24:SPLIT] - target[: SPLIT - 24]) / 24
        profile = daily_profiles(target, idx, slope).mean(axis=0)
        for start, length in windows(len(times), True):
            masked = target.copy()
            masked[start : start + length] = np.nan
            for method, pred in predict(masked, start, length, profile).items():
                err = pred - target[start : start + length]
                rows.append(
                    dict(
                        station=station,
                        week=start // 168,
                        start=times[start],
                        hours=length,
                        method=method,
                        mae=np.abs(err).mean(),
                        squared_error_sum=err @ err,
                    )
                )
    return rows


def summarize(rows):
    grid = {}
    for r in rows:
        key = (int(r["week"]), r["station"], int(r["hours"]), r["method"])
        if key in grid:
            raise ValueError("duplicate mask and method")
        grid[key] = float(r["mae"])
    weeks = sorted({k[0] for k in grid})
    means = np.array(
        [
            [np.mean([grid[w, s, h, m] for s in HASHES for h in LENGTHS]) for m in ARMS]
            for w in weeks
        ]
    )
    n = len(weeks)
    rng = np.random.default_rng(712)
    starts = rng.integers(n, size=(10000, (n + 3) // 4))
    indices = ((starts[:, :, None] + np.arange(4)) % n).reshape(10000, -1)[:, :n]
    print("baseline,macro_mae,relative_reduction,paired_diff_lower,paired_diff_upper")
    for j, name in enumerate(ARMS):
        diff = means[:, j] - means[:, -1]
        low, high = np.percentile(diff[indices].mean(axis=1), [2.5, 97.5])
        avg = means[:, j].mean()
        print(f"{name},{avg:.6f},{diff.mean() / avg:.6f},{low:.6f},{high:.6f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ["cache", "original", "output"]:
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    verify_exact_family()
    results = compare(args.cache, args.original)
    with args.output.open("x", newline="") as f:
        writer = csv.DictWriter(f, results[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    summarize(results)
