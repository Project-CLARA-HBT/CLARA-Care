"""Run in a directory containing the verified development bearing ZIP."""
import hashlib
import io
import json
import zipfile

import numpy as np
from scipy.io import wavfile
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler


def features(data):
    rate, samples = wavfile.read(io.BytesIO(data))
    assert rate == 16000 and samples.ndim == 1
    frames = np.lib.stride_tricks.sliding_window_view(samples, 512)[::256]
    power = abs(np.fft.rfft(frames * np.hanning(512)))[:, :256] ** 2
    bands = np.log1p(power.reshape(len(frames), 32, 8).mean(axis=2))
    return np.r_[bands.mean(axis=0), bands.std(axis=0)]


path = "dev_bearing.zip"
with open(path, "rb") as stream:
    assert hashlib.file_digest(stream, "md5").hexdigest() == "b4b750604c096d50586520a2fe6359a7"
with zipfile.ZipFile(path) as archive:
    names = sorted(n for n in archive.namelist() if "section_00_" in n and n.endswith(".wav"))
    train = [n for n in names if "/train/" in n and "_source_" in n][:32]
    train += [n for n in names if "/train/" in n and "_target_" in n]
    test = [n for n in names if "/test/" in n]
    x, z = (np.stack([features(archive.read(n)) for n in files]) for files in (train, test))
scaler = StandardScaler().fit(x)
x, z = scaler.transform(x), scaler.transform(z)
model = KMeans(4, random_state=42, n_init=20).fit(x)
dist = (z[:, None] - model.cluster_centers_) ** 2
groups = [x[model.labels_ == i] for i in range(4)]
counts = np.array([len(g) for g in groups])[:, None]
variances = np.stack([g.var(axis=0) for g in groups])
pool = np.average(variances, weights=counts.ravel(), axis=0)
scores = {"NN": cdist(z, x).min(axis=1), "centroid": dist.sum(axis=2).min(axis=1)}
for name, var in [("pool", pool), ("local", variances),
                  ("fixed", (variances + pool) / 2),
                  ("shrink", (counts * variances + 10 * pool) / (counts + 10))]:
    scores[name] = (dist / np.maximum(var, 0.05)).sum(axis=2).min(axis=1)
y = np.array(["_anomaly_" in n for n in test])
source = np.array(["_source_" in n for n in test])
out = {"train": len(x), "test": len(z), "cluster_counts": counts.ravel().tolist(), "methods": {}}
for name, s in scores.items():
    # DCASE domain AUC compares domain normals against all anomalies.
    aucs = [roc_auc_score(y[m], s[m]) for m in (source | y, ~source | y)]
    p = roc_auc_score(y, s, max_fpr=0.1)
    out["methods"][name] = dict(source=aucs[0], target=aucs[1], pauc=p,
                                harmonic=3 / sum(1 / v for v in [*aucs, p]))
# Preserve pairing and class/domain counts across all control comparisons.
rng = np.random.default_rng(42)
strata = [np.flatnonzero((source == d) & (y == a))
          for d in (True, False) for a in (True, False)]
out["test_counts_source_anomaly_normal_then_target"] = [len(i) for i in strata]
diffs = {name: [] for name in scores if name != "shrink"}
for _ in range(1000):
    idx = np.concatenate([rng.choice(i, len(i)) for i in strata])
    boot = {name: roc_auc_score(y[idx], s[idx], max_fpr=0.1)
            for name, s in scores.items()}
    for name in diffs:
        diffs[name].append(boot["shrink"] - boot[name])
out["shrink_minus_control"] = {
    name: {"difference": out["methods"]["shrink"]["pauc"] - out["methods"][name]["pauc"],
           "clip_bootstrap_95": np.quantile(values, [.025, .975]).tolist()}
    for name, values in diffs.items()
}
print(json.dumps(out, indent=2))
