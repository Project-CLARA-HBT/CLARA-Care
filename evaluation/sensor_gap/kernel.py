"""Run the registered equipment gap kernel experiment on a CUDA device."""

import argparse
import csv
import json
import platform
from itertools import product
from pathlib import Path

import numpy as np
import torch

from .conditional import example
from .periodic_bridge import daily_profiles
from .run import HASHES, LENGTHS, SPLIT, WEEK, load, windows

ARMS = ("all_linear", "temperature_kernel", "joint_kernel", "additive_kernel")


def tensor(x):
    return torch.as_tensor(np.asarray(x), device="cuda", dtype=torch.float64)


def build(data, starts, length, profile_end):
    end = profile_end // 24 * 24
    target = data[:, -1]
    slope = np.median(target[24:end] - target[: end - 24]) / 24
    profile = daily_profiles(target, np.arange(end).reshape(-1, 24), slope).mean(axis=0)
    features, excursions, responses = [], [], []
    for i in starts:
        f, _, bridge = example(target, i, length, profile)
        features.append(f)
        loads = data[i : i + length, :-1]
        alpha = np.arange(1, length + 1)[:, None] / (length + 1)
        line = data[i - 1, :-1] * (1 - alpha) + data[i + length, :-1] * alpha
        excursions.append((loads - line).reshape(6, -1, 6).mean(axis=1).ravel())
        responses.append(target[i : i + length] - bridge)
    return tuple(map(tensor, (features, excursions, responses)))


def standardized(values, n):
    sd = values[:n].std(dim=0, correction=0)
    return (values - values[:n].mean(dim=0)) / torch.where(sd > 1e-9, sd, 1.0)


def distances(values, n):
    d = torch.cdist(values, values[:n]).square()
    positive = d[:n][
        torch.triu(torch.ones_like(d[:n], dtype=torch.bool), diagonal=1) & (d[:n] > 1e-12)
    ]
    return d / positive.median().clamp_min(1e-12)


def errors(dataset, n, settings):
    temp_features, load_features, y = dataset
    temp_features = standardized(temp_features, n)
    load_features = standardized(load_features, n)
    joint = torch.cat((temp_features, load_features), dim=1)
    df, dl, dj = (distances(x, n) for x in (temp_features, load_features, joint))
    center = y[:n].mean(dim=0)
    centered = y[:n] - center
    for arm, bw, penalty in settings:
        if arm == "all_linear":
            gram = joint.T[:, :n] @ joint[:n]
            gram.diagonal().add_(penalty)
            pred = joint[n:] @ torch.linalg.solve(gram, joint[:n].T @ centered)
        else:
            if arm == "additive_kernel":
                k = (torch.exp(-df / bw) + torch.exp(-dl / bw)) / 2
            else:
                k = torch.exp(-(df if arm == "temperature_kernel" else dj) / bw)
            k[:n].diagonal().add_(penalty)
            pred = k[n:] @ torch.linalg.solve(k[:n], centered)
        yield (arm, bw, penalty), (pred + center - y[n:]).cpu().numpy()


def run(cache, out):
    out.mkdir(exist_ok=False, parents=True)
    settings = [("all_linear", 0, a) for a in (3, 30, 300)] + list(
        product(ARMS[1:], (0.5, 1.0, 2.0), (0.01, 0.1, 1.0))
    )
    metadata = dict(
        python=platform.python_version(),
        platform=platform.release(),
        gpu=torch.cuda.get_device_name(),
        torch=str(torch.__version__),
        cuda=torch.version.cuda,
        source_sha256=HASHES,
        validation={},
    )
    with (out / "losses.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            ("station", "week", "start", "hours", "method", "mae", "squared_error_sum"),
            lineterminator="\n",
        )
        writer.writeheader()
        for station in HASHES:
            times, data = load(cache, station)
            for length in LENGTHS:
                train = [i for i, n in windows(len(times), False) if n == length]
                test = [i for i, n in windows(len(times), True) if n == length]
                valid = train[len(train) * 3 // 4 :]
                fit = [i for i in train if i < valid[0] - WEEK]
                dev = build(data, fit + valid, length, valid[0] - 24 - WEEK)
                scores = {
                    key: np.abs(err).mean().item() for key, err in errors(dev, len(fit), settings)
                }
                best = [
                    min((key for key in settings if key[0] == arm), key=scores.get) for arm in ARMS
                ]
                metadata["validation"][f"{station}_{length}"] = {
                    "selected": best,
                    "fit": len(fit),
                    "validate": len(valid),
                    "scores": [[*k, v] for k, v in scores.items()],
                }
                final = build(data, train + test, length, SPLIT)
                for (arm, _, _), e in errors(final, len(train), best):
                    for start, err in zip(test, e, strict=True):
                        writer.writerow(
                            dict(
                                station=station,
                                week=start // WEEK,
                                start=times[start],
                                hours=length,
                                method=arm,
                                mae=float(np.abs(err).mean()),
                                squared_error_sum=float(err @ err),
                            )
                        )
    metadata["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
    (out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache", type=Path)
    p.add_argument("out", type=Path)
    a = p.parse_args()
    run(a.cache, a.out)
