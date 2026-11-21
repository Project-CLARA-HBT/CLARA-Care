"""One-month-ahead rolling development screen on the original Monash Car Parts file."""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from statsforecast.models import ADIDA, IMAPA, TSB, CrostonSBA

DATA_MD5 = "7b104f4549c0b10ad22299304d5fee63"
GRIDS = {"tsb": [0.05, 0.1, 0.2], "boost": [7, 15, 31], "shrink": [4, 16, 64]}


def load(path):
    raw = path.read_bytes()
    assert hashlib.md5(raw).hexdigest() == DATA_MD5
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        lines = archive.read(archive.namelist()[0]).decode().splitlines()
    series = {}
    for line in lines[lines.index("@data") + 1 :]:
        if not line.strip():
            continue
        name, start, values = line.split(":")
        assert start == "1998-01-01 00-00-00" and name not in series
        series[name] = [np.nan if v == "?" else int(v) for v in values.split(",")]
    assert len(series) == 2674 and {len(x) for x in series.values()} == {51}
    ids = sorted(series, key=lambda s: hashlib.sha256(s.encode()).digest())[:256]
    return ids, np.array([series[i] for i in ids])


def history(prefix):
    missing = np.flatnonzero(np.isnan(prefix))
    return prefix[(missing[-1] + 1 if len(missing) else 0) :]


def features(h):
    sold = np.flatnonzero(h > 0)
    n = len(h)
    freq = len(sold) / n if n else 0
    age = n - 1 - sold[-1] if len(sold) else -1
    last = h[sold[-1]] if len(sold) else 0
    fbin = int(np.searchsorted([0, 0.1, 0.25, 0.5, 0.75], freq))
    abin = int(np.searchsorted([0, 1, 3, 7], age)) if age >= 0 else -1
    return [freq, age, n, last], (fbin, abin)


def lower_median(counts):
    target = sum(counts.values()) / 2
    cumul = 0
    for y in sorted(counts):
        cumul += counts[y]
        if cumul >= target:
            return y
    return 0


def distributions(y, t):
    pooled, cells = defaultdict(Counter), defaultdict(Counter)
    rows, targets = [], []
    for series in y:
        for j in range(1, t):
            h = history(series[:j])
            if not len(h) or np.isnan(series[j]):
                continue
            x, key = features(h)
            v = int(series[j])
            pooled[key[0]][v] += 1
            cells[key][v] += 1
            rows.append(x)
            targets.append(v)
    return pooled, cells, rows, targets


def local_forecasts(h):
    arms = {"sba": CrostonSBA(), "adida": ADIDA(), "imapa": IMAPA()}
    arms.update({f"tsb_{a}": TSB(alpha_d=a, alpha_p=a) for a in GRIDS["tsb"]})
    return {k: float(arm.forecast(y=h, h=1)["mean"][0]) for k, arm in arms.items()}


def run_origin(y, t, ids):
    pooled, cells, train_x, train_y = distributions(y, t)
    histories = [history(s[:t]) for s in y]
    all_x = [features(h)[0] for h in histories]
    boosts = {}
    for leaves in GRIDS["boost"]:
        model = HistGradientBoostingRegressor(
            loss="absolute_error",
            max_leaf_nodes=leaves,
            max_iter=60,
            early_stopping=False,
            random_state=0,
        ).fit(train_x, train_y)
        boosts[leaves] = np.maximum(model.predict(all_x), 0)
    results = []
    for i, h in enumerate(histories):
        x, key = features(h)
        global_dist = pooled[key[0]] or sum(pooled.values(), Counter())
        cell = cells[key]
        pred = {
            "zero": 0,
            "median": float(np.median(h)) if len(h) else 0,
            "frequency": lower_median(global_dist),
            "age_raw": lower_median(cell or global_dist),
        }
        for weight in GRIDS["shrink"]:
            # Integer weights avoid roundoff in choosing the lower median at an exact tie.
            n = sum(global_dist.values())
            counts = {
                v: cell[v] * n + global_dist[v] * weight for v in cell.keys() | global_dist.keys()
            }
            pred[f"shrink_{weight}"] = lower_median(counts)
        pred.update({f"boost_{k}": float(values[i]) for k, values in boosts.items()})
        if len(h):
            pred.update(local_forecasts(h))
        else:
            pred.update(
                dict.fromkeys(["sba", "adida", "imapa", *[f"tsb_{a}" for a in GRIDS["tsb"]]], 0)
            )
            pred = dict.fromkeys(pred, 0)
        assert all(np.isfinite(v) and v >= 0 for v in pred.values())
        truth = y[i, t]
        results.append(
            {
                "sku": ids[i],
                "month": t + 1,
                "truth": "" if np.isnan(truth) else int(truth),
                "history": len(h),
                "freq_bin": key[0],
                "age_bin": key[1],
                **pred,
            }
        )
    return results


def error(rows, arm):
    return sum(abs(r["truth"] - r[arm]) for r in rows if r["truth"] != "")


def main(archive, out):
    ids, y = load(archive)
    tuning = [r for t in range(35, 43) for r in run_origin(y, t, ids)]
    chosen = {
        k: min(values, key=lambda v: error(tuning, f"{k}_{v}")) for k, values in GRIDS.items()
    }
    scored = [r for t in range(43, 51) for r in run_origin(y, t, ids)]
    out.mkdir(parents=True, exist_ok=True)
    arms = [
        "zero",
        "median",
        "sba",
        "adida",
        "imapa",
        "frequency",
        "age_raw",
        *[f"{k}_{v}" for k, v in chosen.items()],
    ]
    prepared = []
    for r in tuning + scored:
        # Publish derived errors without redistributing the original archive or quantity labels.
        row = {k: r[k] for k in ("sku", "month", "history", "freq_bin", "age_bin")}
        row["observed"] = int(r["truth"] != "")
        row["nonzero"] = int(row["observed"] and r["truth"] > 0)
        for k in r.keys() - {"sku", "month", "truth", "history", "freq_bin", "age_bin"}:
            row[k] = abs(r["truth"] - r[k]) if row["observed"] else ""
        prepared.append(row)
    with (out / "errors.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(prepared[0]))
        writer.writeheader()
        writer.writerows(prepared)
    d = {
        "archive_md5": DATA_MD5,
        "versions": {p: version(p) for p in ["numpy", "statsforecast", "scikit-learn"]},
        "selected_series": len(ids),
        "tuned": chosen,
        "eval": {k: error(scored, k) for k in arms},
        "observed": sum(r["truth"] != "" for r in scored),
        "missing": sum(r["truth"] == "" for r in scored),
        "valid_series": len({r["sku"] for r in scored if r["truth"] != ""}),
        "eval_months": {
            t: {k: error([r for r in scored if r["month"] == t], k) for k in arms}
            for t in range(44, 52)
        },
    }
    (out / "summary.json").write_text(json.dumps(d, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args()
    main(args.archive, args.out)
