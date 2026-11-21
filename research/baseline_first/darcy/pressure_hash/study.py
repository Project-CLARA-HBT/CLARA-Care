"""Matched development replay of material and coarse-pressure routing."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import torch
from scipy.ndimage import uniform_filter

HERE = Path(__file__).resolve().parent
HASHES = {
    "neuraloperator": ["0be662acdb1dab7dfd1a1da0b140e97f75cc94f98a14edcf768abe6968b3b418",
                       "f44a1151802eaf2eac65ddaded1ecf105bac019add0e3d277a3e9939cca1cd8b"],
    "pdeinv241": ["aa25113c4fae58d793152d85b490236050533a7714645c9c99b42d6eb75647a7",
                  "65e73de7be72317c6c7a3fbdfbe0c4a5a2f88358522aeb78d25e76c562b4bf1d"],
}


def verify(data, cohort, fine):
    for size, expected in zip((16, 32), HASHES[cohort]):
        with (data / f"darcy_train_{size}.pt").open("rb") as f:
            assert hashlib.file_digest(f, "sha256").hexdigest() == expected
    if cohort == "pdeinv241":
        coords = 12 + 7 * np.arange(32)
        with (HERE.parent / cohort / "sources.csv").open() as f:
            for row in csv.DictReader(f):
                path = data / Path(row["path"]).name
                with path.open("rb") as raw:
                    assert hashlib.file_digest(raw, "sha256").hexdigest() == row["sha256"]
                with h5py.File(path) as h:
                    a = h["coeff"][:, :, 0]
                    for key, values in (("x", a == a.max()), ("y", h["sol"][:, :, 0])):
                        np.testing.assert_array_equal(fine[key][int(row["index"])], values[np.ix_(coords, coords)])


def pressure_hash(p, split):
    padded = np.pad(p, ((0, 0), (1, 1), (1, 1)), mode="edge")
    gx = (padded[:, 1:-1, 2:] - padded[:, 1:-1, :-2]) / 2
    gy = (padded[:, 2:, 1:-1] - padded[:, :-2, 1:-1]) / 2
    xx, xy, yy = [uniform_filter(t, (1, 3, 3), mode="nearest") for t in (gx*gx, gx*gy, gy*gy)]
    gap = np.hypot(xx - yy, 2 * xy)
    high, low = [np.sqrt(np.maximum(0, (xx + yy + g) / 2)) for g in (gap, -gap)]
    coherence = np.divide(high-low, high+low, out=np.zeros_like(high), where=high+low > 0)
    angle = np.where(gap == 0, 0, 0.5*np.arctan2(2*xy, xx-yy)) % np.pi
    thresholds = [np.median(t[:split]) for t in (high, coherence)]
    groups = (np.floor(4*angle/np.pi).astype(int) % 4)*4
    return groups + 2*(high > thresholds[0]) + (coherence > thresholds[1]), thresholds


def ridge(x, y):
    return np.linalg.solve(x.T @ x + 64*np.eye(x.shape[1]), x.T @ y)


def run(data, cohort, split, end):
    coarse, fine = [torch.load(data / f"darcy_train_{size}.pt", weights_only=True)
                    for size in (16, 32)]
    verify(data, cohort, fine)
    a, p = [coarse[k][:end].numpy().astype(float) for k in ("x", "y")]
    target = fine["y"][:end].numpy().astype(float)
    np.testing.assert_array_equal(p, target[:, ::2, ::2])
    np.testing.assert_array_equal(a, fine["x"][:end, ::2, ::2].numpy())
    assert set(np.unique(a)) == {0, 1}
    grid = np.indices((16, 16))
    pressure, thresholds = pressure_hash(p, split)
    counts = []
    cut = np.zeros((end-split, 16, 16), dtype=bool)
    arms = ("ridge", "pattern", "pressure")
    offset = grid - np.clip(grid - 1, 0, 12)
    baseline = p[split:].repeat(2, 1).repeat(2, 2)
    preds = {arm: baseline.copy() for arm in arms}
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
        cut[:, r, c] = (code[split:] != 0) & (code[split:] != 15)
        groups = {"pattern": code, "pressure": pressure[:, r, c]}
        for arm, group in groups.items():
            for partition, ids in (("fit", group[:split]), ("dev", group[split:])):
                counts.append([cohort, u, v, arm, partition, *np.bincount(ids.ravel(), minlength=16)])
        flat = x.reshape(-1, x.shape[-1])
        n = split*len(r)
        scale = np.sqrt(np.mean(flat[:n]**2, axis=0))
        flat /= np.where(scale > 0, scale, 1)
        for i, j in [(1, 0), (0, 1), (1, 1)]:
            rr, cc = 2*r+i, 2*c+j
            y = (target[:split, rr, cc] - anchor[:split, :, 0]).ravel()
            fitted = flat @ ridge(flat[:n], y)
            residual = y - fitted[:n]
            for arm in arms:
                delta = fitted[n:].copy()
                if arm in groups:
                    ids = groups[arm].ravel()
                    for g in np.unique(ids[:n]):
                        train, dev = ids[:n] == g, ids[n:] == g
                        delta[dev] += flat[n:][dev] @ ridge(flat[:n][train], residual[train])
                preds[arm][:, rr, cc] = anchor[split:, :, 0] + delta.reshape(end-split, -1)
    missing = np.ones((32, 32), dtype=bool)
    missing[::2, ::2] = False
    edge = np.indices((32, 32)).max(axis=0) == 31
    truth = target[split:]
    rows, stats = [], {}
    idx = np.random.default_rng(412).integers(end-split, size=(10000, end-split))
    for region, mask in (("all", missing), ("interior", missing & ~edge), ("exterior", edge),
                         ("interface", missing & cut.repeat(2, 1).repeat(2, 2))):
        losses = {}
        for arm, pred in preds.items():
            np.testing.assert_array_equal(pred[:, ::2, ::2], p[split:])
            losses[arm] = np.linalg.norm((pred-truth)*mask, axis=(1, 2))/np.linalg.norm(truth*mask, axis=(1, 2))
            assert np.isfinite(losses[arm]).all()
            rows.extend([cohort, k, arm, region, loss] for k, loss in enumerate(losses[arm], split))
        a, b = losses["pattern"], losses["pressure"]
        gains = 100*(1-a[idx].mean(axis=1)/b[idx].mean(axis=1))
        stats[region] = dict(means={arm: v.mean() for arm, v in losses.items()},
                             gain_pct=100*(1-a.mean()/b.mean()), ci=np.percentile(gains,[2.5,97.5]).tolist(),
                             wins=int((a<b).sum()), losses=int((a>b).sum()))
    return rows, counts, dict(thresholds=thresholds, regions=stats)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("neuraloperator", "pdeinv241"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    rows, counts, summary = [], [], {}
    for cohort, split, end in (("neuraloperator",512,640), ("pdeinv241",128,192)):
        fields, buckets, summary[cohort] = run(getattr(args, cohort), cohort, split, end)
        rows.extend(fields)
        counts.extend(buckets)
    for name, header, values in [
        ("fields", ["cohort","index","arm","region","relative_l2"], rows),
        ("buckets", ["cohort","row_offset","col_offset","arm","partition",*range(16)], counts),
    ]:
        with (HERE / f"{name}.csv").open("w") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(values)
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
