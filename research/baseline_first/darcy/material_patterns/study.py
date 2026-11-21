"""Development replay for coefficient-pattern gated pressure interpolation."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.ensemble import HistGradientBoostingRegressor

SPLIT = 512
END = 640
ARMS = ("ridge", "population", "pattern", "boost_pattern")


def fit_ridge(x, y):
    gram = x.T @ x
    return np.linalg.solve(gram + np.eye(gram.shape[0]) * 64, x.T @ y)


def group_model(x, y, code, sites):
    flat = x.reshape(-1, x.shape[-1])
    n = SPLIT * sites
    scale = np.sqrt(np.mean(flat[:n] ** 2, axis=0))
    x = flat / np.where(scale > 0, scale, 1)
    code = code.ravel()
    fitted = x @ fit_ridge(x[:n], y)
    residual = y - fitted[:n]
    preds = {"ridge": fitted[n:].copy()}
    for name, groups in [("population", np.unpackbits(code[:, None], axis=1).sum(1)),
                         ("pattern", code)]:
        out = fitted[n:].copy()
        for g in np.unique(groups[:n]):
            train = groups[:n] == g
            dev = groups[n:] == g
            if dev.any():
                out[dev] += x[n:][dev] @ fit_ridge(x[:n][train], residual[train])
        preds[name] = out
    inputs = np.column_stack([x, code])
    booster = HistGradientBoostingRegressor(max_iter=60, max_leaf_nodes=15,
                                             early_stopping=False, random_state=0)
    booster.fit(inputs[:n], y)
    preds["boost_pattern"] = booster.predict(inputs[n:])
    return preds


def run(data):
    coarse, fine = [torch.load(data / f"darcy_train_{size}.pt", weights_only=True)
                    for size in (16, 32)]
    a, p = [coarse[k][:END].numpy().astype(float) for k in ("x", "y")]
    target = fine["y"][:END].numpy().astype(float)
    np.testing.assert_array_equal(p, target[:, ::2, ::2])
    np.testing.assert_array_equal(a, fine["x"][:END, ::2, ::2].numpy())
    assert set(np.unique(a)) == {0, 1}
    grid = np.indices((16, 16))
    offset = grid - np.clip(grid - 1, 0, 12)
    baseline = p[SPLIT:].repeat(2, 1).repeat(2, 2)
    preds = {arm: baseline.copy() for arm in ARMS}
    for u, v in np.unique(offset.reshape(2, -1).T, axis=0):
        r, c = np.where((offset[0] == u) & (offset[1] == v))
        rows = r[:, None] - u + np.repeat(np.arange(4), 4)
        cols = c[:, None] - v + np.tile(np.arange(4), 4)
        anchor = p[:, r, c, None]
        bits = a[:, rows, cols]
        diff = p[:, rows, cols] - anchor
        x = np.concatenate([diff, anchor, bits, diff * (bits - a[:, r, c, None]),
                            np.ones_like(anchor)], axis=-1)
        corner = np.stack([a[:, np.minimum(r, 14) + i, np.minimum(c, 14) + j]
                           for i, j in [(0, 0), (0, 1), (1, 0), (1, 1)]], axis=-1)
        code = (corner @ [1, 2, 4, 8]).astype(np.uint8)
        for i, j in [(1, 0), (0, 1), (1, 1)]:
            rr, cc = 2*r+i, 2*c+j
            y = (target[:SPLIT, rr, cc] - anchor[:SPLIT, :, 0]).ravel()
            for name, delta in group_model(x, y, code, len(r)).items():
                preds[name][:, rr, cc] = anchor[SPLIT:, :, 0] + delta.reshape(END-SPLIT, -1)
    masks = np.ones((32, 32), dtype=bool)
    masks[::2, ::2] = False
    outer = np.indices((32, 32)).max(axis=0) == 31
    scores = {}
    for name, pred in preds.items():
        np.testing.assert_array_equal(pred[:, ::2, ::2], p[SPLIT:])
        splits = []
        for mask in [masks, masks & ~outer, outer]:
            truth = target[SPLIT:, mask]
            splits.append(np.linalg.norm(pred[:, mask]-truth, axis=1)/np.linalg.norm(truth, axis=1))
        scores[name] = np.column_stack(splits)
    return scores


def summarize(scores, out):
    out.mkdir(exist_ok=True, parents=True)
    with (out / "fields.csv").open("w") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["training_index", "arm", "all", "interior", "exterior"])
        for arm, values in scores.items():
            w.writerows((i, arm, *row) for i, row in enumerate(values, SPLIT))
    prior = {}
    with (Path(__file__).resolve().parents[1] / "stencil_dev/fields.csv").open() as f:
        for row in csv.DictReader(f):
            samples = prior.setdefault(row["arm"], [])
            assert int(row["training_index"]) == len(samples) + SPLIT
            samples.append(float(row["all"]))
    candidate = scores["pattern"][:, 0]
    rng = np.random.default_rng(412)
    resamples = rng.integers(len(candidate), size=(10000, len(candidate)))
    comparisons = {}
    for arm, values in {**prior, **{k: v[:, 0] for k, v in scores.items()}}.items():
        ref = np.asarray(values)
        assert len(ref) == END - SPLIT
        gains = 100*(1-candidate[resamples].mean(axis=1)/ref[resamples].mean(axis=1))
        comparisons[arm] = {"mean": ref.mean(), "gain_pct": 100*(1-candidate.mean()/ref.mean()),
                            "interval_pct": np.percentile(gains, [2.5, 97.5]).tolist(),
                            "wins": int(np.sum(candidate < ref))}
    (out / "comparisons.json").write_text(json.dumps(comparisons, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    summarize(run(args.data), args.out)
