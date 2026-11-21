"""Evaluate leave-one-recording-out development selectors on numeric features."""
import json
from pathlib import Path
import sys

import numpy as np


def evaluate(rows, registered):
    assert len(rows) == len(registered) == 168
    for row, original in zip(rows, registered, strict=True):
        assert {k: row[k] for k in original} == original
    errors = np.array([r["errors_by_rank"] for r in rows])
    features = np.array([r["features"] for r in rows])
    assert features.shape == (168, 5, 2) and np.isfinite(features).all()
    risk = np.array([r["within_list_edit_sums"] for r in rows])
    recordings = np.array([r["recording"] for r in rows])
    speakers = np.array([r["speaker"] for r in rows])
    report = []
    for recording in np.unique(recordings):
        held = recordings == recording
        fit = ~held
        assert set(speakers[held]).isdisjoint(speakers[fit])
        item = {"recording": int(recording)}
        def record(name, scores):
            choices = scores.argmax(axis=1)
            losses = errors[np.arange(len(rows)), choices]
            item[name] = int(losses[held].sum())

        acoustic, lm = features.transpose(2, 0, 1)
        weights = [0, .01, .03, .1, .3, 1, 3, 10]
        def tuning_loss(weight):
            rank = (acoustic[fit] + weight * lm[fit]).argmax(axis=1)
            return errors[fit][np.arange(sum(fit)), rank].sum()
        weight = min(weights, key=tuning_loss)
        item["lm_weight"] = weight
        record("tuned_lm", acoustic + weight * lm)
        for name, matrix in (("matched", features), ("with_consensus", np.dstack((features, -risk)))):
            x = matrix - matrix.mean(axis=1, keepdims=True)
            scale = x[fit].std(axis=(0, 1)).clip(min=1e-8)
            x = x / scale
            design = x[fit].reshape(-1, x.shape[-1])
            target = (errors[fit].mean(axis=1, keepdims=True) - errors[fit]).ravel()
            beta = np.linalg.solve(design.T @ design + np.eye(x.shape[-1]), design.T @ target)
            record(name, x @ beta)
        item["rank1"] = int(errors[held, 0].sum())
        record("medoid", -risk)
        report.append(item)
    return report


if __name__ == "__main__":
    inputs = [json.loads(Path(p).read_text())["rows"] for p in sys.argv[1:]]
    print(json.dumps(evaluate(*inputs), indent=2))
