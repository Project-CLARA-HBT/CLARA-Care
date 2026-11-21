"""Compare conditional temperature reconstruction on registered outage masks."""

import argparse
import csv
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from .periodic_bridge import ARMS, daily_profiles
from .run import HASHES, LENGTHS, SPLIT, WEEK, load, windows

NEW_ARMS = ("pooled_ridge", "neighbor16", "soft_experts", "hard_experts")


def example(target, start, length, profile):
    """Read only observed flanks when building features and bridge."""
    gap = np.arange(start, start + length)
    before = np.arange(start - 24, start)
    after = np.arange(start + length, start + length + 24)
    context = np.concatenate([before, after])
    adjusted = target[context] - profile[context % 24]
    left, right = adjusted[23:25]
    slope = (right - left) / (length + 1)
    deviations = adjusted - left - (context - start + 1) * slope
    phase = 2 * np.pi * (start % 24) / 24
    features = np.r_[
        deviations, target[before[-1]], target[after[0]], slope, np.sin(phase), np.cos(phase)
    ]
    volatility = np.sqrt(np.mean(np.diff(adjusted.reshape(2, 24), axis=1) ** 2))
    base = profile[gap % 24] + left + (gap - start + 1) * slope
    return features, volatility, base


def cases(target, length, scoring, profile):
    for i, n in windows(len(target), scoring):
        if n == length:
            features, vol, bridge = example(target, i, n, profile)
            yield i, features, vol, bridge


def evaluate(cache):
    for station in HASHES:
        times, data = load(cache, station)
        target = data[:, -1]
        trend = np.median(target[24:SPLIT] - target[: SPLIT - 24]) / 24
        profile = daily_profiles(target, np.arange(SPLIT).reshape(-1, 24), trend).mean(axis=0)
        for length in LENGTHS:
            idx, features, vol, base = zip(*cases(target, length, False, profile), strict=True)
            scaler = StandardScaler().fit(features)
            x = scaler.transform(features)
            y = np.stack([target[i : i + length] for i in idx]) - base
            threshold = np.median(vol)
            spread = np.subtract(*np.percentile(vol, [75, 25]))
            high = np.asarray(vol) > threshold
            models = [
                Ridge(alpha=30).fit(x[keep], y[keep]) for keep in (np.ones_like(high), ~high, high)
            ]
            for start, raw, v, baseline in cases(target, length, True, profile):
                masked = target.copy()
                masked[start : start + length] = np.nan
                masked_case = example(masked, start, length, profile)
                for observed, checked in zip((raw, v, baseline), masked_case, strict=True):
                    np.testing.assert_array_equal(observed, checked)
                query = scaler.transform([raw])
                closest = np.argsort(np.sum((x - query) ** 2, axis=1), kind="stable")[:16]
                pool, calm, variable = [m.predict(query)[0] for m in models]
                # Linear transition over one training IQR, centered at its median.
                weight = (
                    np.clip(0.5 + (v - threshold) / spread, 0, 1)
                    if spread
                    else float(v > threshold)
                )
                forecasts = (
                    pool,
                    y[closest].mean(axis=0),
                    calm * (1 - weight) + variable * weight,
                    variable if v > threshold else calm,
                )
                for method, correction in zip(NEW_ARMS, forecasts, strict=True):
                    error = baseline + correction - target[start : start + length]
                    yield dict(
                        station=station,
                        week=start // WEEK,
                        start=times[start],
                        hours=length,
                        method=method,
                        mae=np.abs(error).mean(),
                        squared_error_sum=error @ error,
                    )


def compare(rows):
    methods = (*ARMS, *NEW_ARMS)
    grid = {
        (int(r["week"]), r["station"], int(r["hours"]), r["method"]): float(r["mae"]) for r in rows
    }
    weeks = sorted({k[0] for k in grid})
    if len(rows) != len(grid) or len(rows) != len(weeks) * len(HASHES) * len(LENGTHS) * len(
        methods
    ):
        raise ValueError("incomplete or duplicate observations")
    means = np.array(
        [
            [np.mean([grid[w, s, h, m] for s in HASHES for h in LENGTHS]) for m in methods]
            for w in weeks
        ]
    )
    n = len(weeks)
    starts = np.random.default_rng(712).integers(n, size=(10000, (n + 3) // 4))
    idx = ((starts[:, :, None] + np.arange(4)) % n).reshape(10000, -1)[:, :n]
    print("method,macro_mae,relative_reduction,lower_95,upper_95")
    for j, m in enumerate(methods):
        diff = means[:, j] - means[:, -1]
        avg = means[:, j].mean()
        low, high = np.percentile(diff[idx].mean(axis=1), [2.5, 97.5])
        print(f"{m},{avg:.6f},{diff.mean() / avg:.6f},{low:.6f},{high:.6f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("cache", "previous", "output"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    with args.previous.open() as f:
        before = list(csv.DictReader(f))
    new = list(evaluate(args.cache))
    with args.output.open("x", newline="") as f:
        writer = csv.DictWriter(f, new[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(new)
    compare(before + new)
