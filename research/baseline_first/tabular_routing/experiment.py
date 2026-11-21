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
writer = csv.writer(sys.stdout)
writer.writerow(["k", "policy", "dev_log_loss", "median_ms_full_dev"])


def run(k, policy):
    score = batches @ rw + rb
    count = len(batches)*k
    if policy == "whole":
        selected = score.mean(1).argsort(descending=True)
        indices = (selected[:, None]*64 + torch.arange(64, device="cuda")).flatten()[:count]
    else:
        indices = (score.topk(k).indices + 64*torch.arange(len(batches), device="cuda")[:, None]).flatten()
    flat = batches.flatten(0, 1)
    pred = (flat @ cw + cb).sigmoid()
    if k:
        # Execute each nonempty expert batch separately.
        for ids in indices.split(64 if policy == "whole" else k):
            h = flat[ids]
            for w, b in weights[:-1]:
                h = (h @ w + b).relu()
            w, b = weights[-1]
            pred[ids] = (h @ w + b).flatten().sigmoid()
    return pred


for k in (0, 1, 2, 4, 8, 16, 32, 64):
    for policy in ("topk", "whole"):
        timings = []
        for repeat in range(8):
            torch.cuda.synchronize()
            start = time.perf_counter()
            pred = run(k, policy)
            torch.cuda.synchronize()
            timings.append(1000*(time.perf_counter()-start))
        writer.writerow([k, policy, loss(pred.cpu().numpy(), y[dev]).mean(), statistics.median(timings[2:])])
