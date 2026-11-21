"""Run on a CUDA host with bank-full.csv as the first argument."""
import csv
import statistics
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler

data = pd.read_csv(sys.argv[1], sep=";")
y = data.pop("y").eq("yes").astype(int).to_numpy()
data.pop("duration")
train, rest = train_test_split(np.arange(len(y)), test_size=.4, stratify=y, random_state=9)
cal, dev = train_test_split(rest, test_size=.5, stratify=y[rest], random_state=9)
encode = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore"), data.select_dtypes("object").columns),
    ("num", StandardScaler(), data.select_dtypes("number").columns),
], sparse_threshold=0)
encode.fit(data.iloc[train])
x = encode.transform(data)
cheap = LogisticRegression(max_iter=500).fit(x[train], y[train])
expert = MLPClassifier(hidden_layer_sizes=(64, 32), early_stopping=True, random_state=9).fit(x[train], y[train])


def loss(prob, target):
    prob = np.clip(prob.astype(float), 1e-10, 1-1e-10)
    return -np.where(target, np.log(prob), np.log1p(-prob))


benefit = loss(cheap.predict_proba(x[cal])[:, 1], y[cal]) - loss(expert.predict_proba(x[cal])[:, 1], y[cal])
router = Ridge().fit(x[cal], benefit)


def gpu(a):
    return torch.as_tensor(a, dtype=torch.float32, device="cuda")


weights = [(gpu(w), gpu(b)) for w, b in zip(expert.coefs_, expert.intercepts_)]
cw, cb = gpu(cheap.coef_[0]), gpu(cheap.intercept_)
rw, rb = gpu(router.coef_), gpu(router.intercept_)
dev = dev[:len(dev)//64*64]
batches = gpu(x[dev]).reshape(-1, 64, x.shape[1])
# A group is the dispatch unit. All policies see the same resident rows.
def route(k, policy, horizon):
    outputs = []
    for group in batches.split(horizon):
        flat = group.flatten(0, 1)
        pred = (flat @ cw + cb).sigmoid()
        if k:
            if k == 64:
                h = flat
            else:
                count = len(group) * k
                if policy == "confidence":
                    ids = (pred - .5).abs().topk(count, largest=False).indices
                else:
                    score = (flat @ rw + rb).reshape(-1, 64)
                    offsets = torch.arange(64, device="cuda")
                    if policy == "whole":
                        order = score.mean(1).argsort(descending=True)
                        ids = (64 * order[:, None] + offsets).flatten()[:count]
                    elif policy == "local":
                        base = torch.arange(len(group), device="cuda") * 64
                        ids = (base[:, None] + score.topk(k).indices).flatten()
                    else:
                        ids = score.flatten().topk(count).indices
                h = flat[ids]
            for w, b in weights[:-1]:
                h = (h @ w + b).relu()
            w, b = weights[-1]
            expert_prob = (h @ w + b).flatten().sigmoid()
            if k == 64:
                pred = expert_prob
            else:
                pred[ids] = expert_prob
        outputs.append(pred)
    return torch.cat(outputs)


writer = csv.writer(sys.stdout)
writer.writerow(["horizon", "k", "policy", "loss", "median_ms"])
for horizon in (8, 141):
    cases = [(k, p) for k in (0, 1, 2, 4, 8, 16, 32, 64)
             for p in ("whole", "local", "confidence", "benefit")]
    rng = np.random.default_rng(9)
    samples = {case: [] for case in cases}
    quality = {}
    for repeat in range(8):
        for i in rng.permutation(len(cases)):
            case = cases[i]
            torch.cuda.synchronize()
            start = time.perf_counter()
            pred = route(*case, horizon)
            torch.cuda.synchronize()
            elapsed = 1000 * (time.perf_counter() - start)
            if repeat >= 2:
                samples[case].append(elapsed)
            if repeat == 0:
                quality[case] = loss(pred.cpu().numpy(), y[dev]).mean()
    for case in cases:
        writer.writerow([horizon, *case, quality[case], statistics.median(samples[case])])
