"""Fit patch-specific linear stencils using exact or Hamming-weighted examples."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch

ARMS = ("hamming9", "count9", "exact9", "hamming4")
BITS = np.array([i.bit_count() for i in range(512)])
ROOT = Path(__file__).resolve().parents[1]


def codes(a, row, col, width, lead):
    # Shift the entire window at the perimeter to retain distinct observations.
    top = np.clip(row - lead, 0, 16 - width)
    left = np.clip(col - lead, 0, 16 - width)
    digits = a[:, top[:, None] + np.repeat(np.arange(width), width),
               left[:, None] + np.tile(np.arange(width), width)]
    return digits.astype(int) @ (1 << np.arange(width**2))


def predict(x, y, code, n, arm):
    train_codes, groups = np.unique(code[:n], return_inverse=True)
    eval_codes, which = np.unique(code[n:], return_inverse=True)
    d = x.shape[1]
    stats = np.empty((len(train_codes), d, d+1))
    joined = np.column_stack([x[:n], y])
    for k in range(len(train_codes)):
        keep = groups == k
        stats[k] = x[:n][keep].T @ joined[keep]
    if arm == "count9":
        distance = abs(BITS[eval_codes, None] - BITS[train_codes])
    else:
        distance = BITS[eval_codes[:, None] ^ train_codes]
    weights = np.power(0.125, distance)
    if arm == "exact9":
        weights = (distance == 0).astype(float)
        weights[weights.sum(axis=1) == 0] = 1
    pooled = (weights @ stats.reshape(len(stats), -1)).reshape(-1, d, d+1)
    beta = np.linalg.solve(pooled[:, :, :d] + 4 * np.eye(d), pooled[:, :, d:])
    return np.einsum("nd,nd->n", x[n:], beta[which, :, 0])


def run(cache, fit, total):
    coarse, fine = [torch.load(cache/f"darcy_train_{n}.pt", weights_only=True) for n in (16,32)]
    p, a = [coarse[k][:total].numpy().astype(float) for k in ("y","x")]
    truth = fine["y"][:total].numpy()
    np.testing.assert_array_equal(p, truth[:, ::2, ::2])
    np.testing.assert_array_equal(a, fine["x"][:total, ::2, ::2].numpy())
    grid = np.indices((16,16))
    offset = grid - np.clip(grid-1, 0, 12)
    preds = {arm:p[fit:].repeat(2,1).repeat(2,2) for arm in ARMS}
    for u,v in np.unique(offset.reshape(2,-1).T, axis=0):
        r,c = np.where((offset[0] == u) & (offset[1] == v))
        rows = r[:,None]-u + np.repeat(np.arange(4),4)
        cols = c[:,None]-v + np.tile(np.arange(4),4)
        anchor = p[:,r,c,None]
        x = np.concatenate([p[:,rows,cols]-anchor,anchor,np.ones_like(anchor)],axis=-1)
        x = x.reshape(-1,x.shape[-1])
        n = fit * len(r)
        rms = np.sqrt((x[:n]**2).mean(0))
        x = x / np.where(rms > 0,rms,1)
        bit9 = codes(a,r,c,3,1).ravel()
        bit4 = codes(a,r,c,2,0).ravel()
        for i,j in [(0,1),(1,0),(1,1)]:
            rr,cc = 2*r+i,2*c+j
            y = (truth[:fit,rr,cc] - anchor[:fit,:,0]).ravel()
            for arm in ARMS:
                z = predict(x,y,bit4 if arm == "hamming4" else bit9,n,arm)
                preds[arm][:,rr,cc] = anchor[fit:,:,0] + z.reshape(-1,len(r))
    missing = np.ones((32,32),bool)
    missing[::2,::2] = False
    exterior = np.indices((32,32)).max(axis=0)==31
    scores = {}
    for arm, estimate in preds.items():
        np.testing.assert_array_equal(estimate[:,::2,::2],p[fit:])
        parts = []
        for mask in [missing, missing & ~exterior, exterior]:
            actual = truth[fit:, mask].astype(float)
            parts.append(np.linalg.norm(estimate[:,mask]-actual,axis=1)/np.linalg.norm(actual,axis=1))
        scores[arm] = np.stack(parts,axis=1)
    return scores


def prior_scores(name, fit, count):
    paths = (["material_patterns", "conv_control", "stencil_dev", "multiscale_dev"]
             if name == "neuralop" else ["pdeinv241", "pdeinv241/cnn"])
    out = {}
    for folder in paths:
        with (ROOT/folder/"fields.csv").open() as f:
            for row in csv.DictReader(f):
                if "arm" not in row:
                    # Identical prior arms are already present in stencil_dev.
                    continue
                seq = out.setdefault(folder+"/"+row["arm"], [])
                assert int(row.get("training_index",row.get("index"))) == len(seq)+fit
                seq.append(float(row["all"]))
    assert all(len(seq) == count for seq in out.values())
    return out


def main(local, external, out):
    out.mkdir(exist_ok=True, parents=True)
    with (out/"fields.csv").open("w") as f:
        writer = csv.writer(f,lineterminator="\n")
        writer.writerow(["archive","index","arm","all","interior","exterior"])
        summary = {}
        for name,cache,fit,total in [("neuralop",local,512,640),("pdeinv",external,128,192)]:
            scores = run(cache,fit,total)
            base = prior_scores(name,fit,total-fit)
            for arm,values in scores.items():
                writer.writerows((name,i,arm,*v) for i,v in enumerate(values,fit))
                base[arm] = values[:,0]
            actual = scores["hamming9"][:,0]
            sampled = np.random.default_rng(412).integers(len(actual),size=(10000,len(actual)))
            summary[name] = {}
            for arm, values in base.items():
                v = np.asarray(values)
                reps = 100*(1-actual[sampled].mean(axis=1)/v[sampled].mean(axis=1))
                summary[name][arm] = dict(mean=v.mean(),gain_pct=100*(1-actual.mean()/v.mean()),
                                          wins=int((actual<v).sum()),interval_pct=np.percentile(reps,[2.5,97.5]).tolist())
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for key in ("local","external","out"):
        ap.add_argument(key,type=Path)
    args = ap.parse_args()
    main(args.local,args.external,args.out)
