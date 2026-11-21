"""Reproduce the frozen retrospective transformer outage study."""

import argparse
import csv
import hashlib
import io
import math
import urllib.request
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor

REV = "1d16c8f4f943005d613b5bc962e9eeb06058cf07"
HASHES = {
    "ETTh1": "f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066",
    "ETTh2": "a3dc2c597b9218c7ce1cd55eb77b283fd459a1d09d753063f944967dd6b9218b",
}
LENGTHS = (6, 24, 72)
METHODS = ("linear", "seasonal", "direct", "residual")
WEEK = 168
SPLIT = 72 * WEEK


def load(cache, station):
    path = cache / f"{station}.csv"
    if path.exists():
        data = path.read_bytes()
    else:
        url = f"https://raw.githubusercontent.com/zhouhaoyi/ETDataset/{REV}/ETT-small/{path.name}"
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != HASHES[station]:
        raise ValueError(f"Unexpected source digest for {station}")
    if not path.exists():
        path.write_bytes(data)
    reader = csv.reader(io.StringIO(data.decode()))
    if next(reader) != ["date", "HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"]:
        raise ValueError("Unexpected sensor columns")
    rows = np.array(list(reader))
    times = rows[:, 0].astype("datetime64[s]")
    values = rows[:, 1:].astype(float)
    if not np.isfinite(values).all() or not (np.diff(times) == np.timedelta64(1, "h")).all():
        raise ValueError("Incomplete hourly record")
    return rows[:, 0], values


def windows(size, scoring):
    lo, hi = (SPLIT, size // WEEK * WEEK) if scoring else (0, SPLIT)
    step = WEEK if scoring else 24
    for length in LENGTHS:
        rng = np.random.default_rng(20261121 + length + 1000 * scoring)
        choices = WEEK - length + 1 if scoring else 24
        for base in range(lo + WEEK, hi - WEEK, step):
            yield base + int(rng.integers(choices)), length


def features(loads, temperature, start, length):
    idx = np.arange(start, start + length)
    left, right = temperature[start - 1], temperature[start + length]
    position = (idx - start + 1) / (length + 1)
    line = left + position * (right - left)
    shift = math.ceil(length / 24) * 24
    season = (temperature[idx - shift] + temperature[idx + shift]) / 2
    phase = 2 * np.pi * (idx % 24) / 24
    mean_load = sum(loads[idx - offset] for offset in range(6)) / 6
    return np.column_stack(
        (
            loads[idx],
            mean_load,
            np.sin(phase),
            np.cos(phase),
            np.full(length, left),
            np.full(length, right),
            position,
            np.full(length, length),
            line,
            season,
        )
    )


def evaluate(station, times, values):
    loads, target = values[:, :-1], values[:, -1]
    train = list(windows(len(times), False))
    x = np.vstack([features(loads, target, i, n) for i, n in train])
    y = np.concatenate([target[i : i + n] for i, n in train])
    models = [
        ExtraTreesRegressor(n_estimators=96, min_samples_leaf=5, random_state=42, n_jobs=1).fit(
            x, response
        )
        for response in (y, y - x[:, -2])
    ]
    records = []
    for start, length in windows(len(times), True):
        block = features(loads, target, start, length)
        line, season = block[:, -2], block[:, -1]
        predictions = (line, season, models[0].predict(block), line + models[1].predict(block))
        for method, pred in zip(METHODS, predictions, strict=True):
            error = pred - target[start : start + length]
            records.append(
                dict(
                    station=station,
                    week=start // WEEK,
                    start=times[start],
                    hours=length,
                    method=method,
                    mae=np.abs(error).mean(),
                    squared_error_sum=error @ error,
                )
            )
    return records


def report(records):
    weeks = sorted({r["week"] for r in records})
    losses = np.empty((len(weeks), len(HASHES), len(LENGTHS), len(METHODS)))
    losses.fill(np.nan)
    for r in records:
        losses[
            weeks.index(r["week"]),
            list(HASHES).index(r["station"]),
            LENGTHS.index(r["hours"]),
            METHODS.index(r["method"]),
        ] = r["mae"]
    if not np.isfinite(losses).all() or losses.size != len(records):
        raise ValueError("Incomplete paired results")
    cells = losses.mean(axis=0)
    lines = [
        "# Held-out development comparison",
        "",
        f"{len(weeks)} paired weeks per record. Each cell reports mean absolute error.",
        "",
        "| Record | Hours | Linear | Seasonal | Direct forest | Residual forest |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for station, station_cells in zip(HASHES, cells, strict=True):
        for length, row in zip(LENGTHS, station_cells, strict=True):
            lines.append(f"| {station} | {length} | " + " | ".join(f"{v:.4f}" for v in row) + " |")
    primary = cells.mean(axis=(0, 1))
    lines.append("| **Macro MAE** | | " + " | ".join(f"{v:.4f}" for v in primary) + " |")
    lines += [
        "",
        "| Baseline | MAE reduction | Relative reduction | Paired 95% interval (MAE units) |",
        "| --- | ---: | ---: | ---: |",
    ]
    rng = np.random.default_rng(712)
    n = len(weeks)
    starts = rng.integers(n, size=(10000, math.ceil(n / 4)))
    indices = ((starts[:, :, None] + np.arange(4)) % n).reshape(10000, -1)[:, :n]
    weekly = losses.mean(axis=(1, 2))
    passed = True
    for j, method in enumerate(METHODS[:-1]):
        diff = primary[j] - primary[-1]
        relative = diff / primary[j]
        paired = weekly[:, j] - weekly[:, -1]
        low, high = np.percentile(paired[indices].mean(axis=1), [2.5, 97.5])
        lines.append(f"| {method} | {diff:.4f} | {relative:.2%} | [{low:.4f}, {high:.4f}] |")
        passed &= low > 0 and relative >= 0.05
    decision = "met" if passed else "missed"
    lines += ["", f"The residual forest {decision} the frozen superiority criterion."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    records = []
    for station in HASHES:
        records.extend(evaluate(station, *load(args.cache, station)))
    summary = report(records)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "losses.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    (args.out / "comparison.md").write_text(summary)


if __name__ == "__main__":
    main()
