"""Evaluate the two registered Gaussian smoothers on matched observed flanks."""

import argparse
import csv
import itertools
import json
import platform
from pathlib import Path

import numpy as np
from scipy.linalg import solve, toeplitz

from ..run import HASHES, LENGTHS, SPLIT, WEEK, load, windows

SETTINGS = {
    "structural": list(itertools.product((0, 0.01, 0.1), (0, 1, 10), (0.1, 1, 4))),
    "autoregressive": list(itertools.product((1, 6, 12, 24, 48), (0, 0.01, 0.1))),
}


def trend_covariance(size, slope_variance):
    time = np.arange(size)
    lag = time[:, None] - time
    level_shocks = (lag > 0).astype(float)
    slope_shocks = np.maximum(0, lag - 1)
    return (
        1e4
        + np.outer(time, time)
        + level_shocks @ level_shocks.T
        + slope_variance * (slope_shocks @ slope_shocks.T)
    )


def structural_covariance(size, settings):
    slope, harmonic, noise = settings
    distance = np.abs(np.subtract.outer(np.arange(size), np.arange(size)))
    phase = 2 * np.pi * distance / 24
    seasonal = harmonic * np.exp(-distance / 36) * (np.cos(phase) + 0.5 * np.cos(2 * phase))
    return trend_covariance(size, slope) + seasonal + noise * np.eye(size)


def autoregressive_covariance(size, residual, settings):
    order, ridge = settings
    series = residual - residual.mean()
    gamma = np.array(
        [series[i:] @ series[: len(series) - i] / len(series) for i in range(order + 1)]
    )
    gamma[0] *= 1 + ridge
    coefficients = solve(toeplitz(gamma[:order]), gamma[1:], assume_a="pos")
    tail = list(gamma)
    while len(tail) < size:
        tail.append(coefficients @ tail[-order:][::-1])
    return toeplitz(tail[:size])


def predict(family, settings, target, train_end, starts, length):
    clock = np.array([target[i:train_end:24].mean() for i in range(24)])
    residual = target[:train_end] - clock[np.arange(train_end) % 24]
    size = 48 + length
    if family == "structural":
        covariance = structural_covariance(size, settings) * max(1e-8, np.var(np.diff(residual)))
    else:
        covariance = autoregressive_covariance(size, residual, settings)
    flank = np.r_[0:24, 24 + length : size]
    gap = np.arange(24, 24 + length)
    weights = solve(
        covariance[np.ix_(flank, flank)], covariance[np.ix_(flank, gap)], assume_a="pos"
    )
    offsets = np.array(starts)[:, None] - 24
    observed = offsets + flank
    return (target[observed] - clock[observed % 24]) @ weights + clock[(offsets + gap) % 24]


def run(cache, out):
    out.mkdir(parents=True, exist_ok=False)
    log = {
        "source_sha256": HASHES,
        "python": platform.python_version(),
        "platform": platform.release(),
        "numpy": np.__version__,
        "validation": {},
    }
    rows = []
    for station in HASHES:
        dates, data = load(cache, station)
        target = data[:, -1]
        for length in LENGTHS:
            train = [i for i, k in windows(len(dates), False) if k == length]
            valid = train[len(train) * 3 // 4 :]
            train_end = valid[0] - 24 - WEEK
            test = [i for i, k in windows(len(dates), True) if k == length]
            score_rows = []
            best = {}
            valid_truth = target[np.array(valid)[:, None] + np.arange(length)]
            for family, grid in SETTINGS.items():
                for setting in grid:
                    try:
                        forecasts = predict(family, setting, target, train_end, valid, length)
                        score = float(np.abs(forecasts - valid_truth).mean())
                        if not np.isfinite(score):
                            raise ValueError("nonfinite validation error")
                    except (np.linalg.LinAlgError, ValueError) as exc:
                        score_rows.append(dict(family=family, settings=setting, failure=str(exc)))
                        continue
                    score_rows.append(dict(family=family, settings=setting, mae=score))
                    if family not in best or score < best[family][0]:
                        best[family] = (score, setting)
                if family not in best:
                    raise ValueError(f"no fit for {station} {length} {family}")
            selected = min(best, key=lambda family: best[family][0])
            log["validation"][f"{station}_{length}"] = dict(
                train_end=train_end,
                first_validation=valid[0],
                count=len(valid),
                settings=score_rows,
                best=best,
                selected=selected,
            )
            for family in SETTINGS:
                forecasts = predict(family, best[family][1], target, SPLIT, test, length)
                for start, pred in zip(test, forecasts, strict=True):
                    error = pred - target[start : start + length]
                    row = dict(
                        station=station,
                        week=start // WEEK,
                        start=dates[start],
                        hours=length,
                        method=family,
                        mae=float(np.abs(error).mean()),
                        squared_error_sum=float(error @ error),
                    )
                    rows.append(row)
                    if family == selected:
                        rows.append(dict(row, method="validation_selected"))
    with (out / "losses.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (out / "validation.json").write_text(json.dumps(log, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    run(args.cache, args.out)
