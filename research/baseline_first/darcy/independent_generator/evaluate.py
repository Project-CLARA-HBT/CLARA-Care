"""Replay the frozen candidate and controls on generated fields."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from pathlib import Path
import runpy

import numpy as np

HERE = Path(__file__).resolve().parent


def evaluate_cnn(data, output):
    runpy.run_path(str(HERE.parent / "conv_control/study.py"))["main"](data, output)


def evaluate(data, output):
    output.mkdir(exist_ok=True, parents=True)
    cnn = output / "cnn"
    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(evaluate_cnn, data, cnn)
        scores = runpy.run_path(str(HERE.parent / "material_patterns/study.py"))["run"](data)
        future.result()
    with (cnn / "fields.csv").open() as f:
        for row in csv.DictReader(f):
            arm = "cnn_" + row["arm"]
            values = scores.setdefault(arm, [])
            assert int(row["training_index"]) == 512 + len(values)
            values.append([float(row[axis]) for axis in ("all", "interior", "exterior")])
    with (output / "fields.csv").open("w") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["index", "arm", "all", "interior", "exterior"])
        for arm, values in scores.items():
            writer.writerows((i, arm, *row) for i, row in enumerate(values, 512))
    draws = np.random.default_rng(412).integers(128, size=(10000, 128))
    summary = {}
    for arm, values in scores.items():
        arr = np.asarray(values)
        cand = scores["pattern"]
        gain = 100 * (1 - cand[draws].mean(axis=1) / arr[draws].mean(axis=1))
        summary[arm] = {"means": arr.mean(axis=0).tolist(),
                        "candidate_gain_pct": (100*(1-cand.mean(axis=0)/arr.mean(axis=0))).tolist(),
                        "interval95": np.percentile(gain, [2.5, 97.5], axis=0).T.tolist(),
                        "candidate_wins": (cand < arr).sum(axis=0).tolist()}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    evaluate(args.data, args.output)
