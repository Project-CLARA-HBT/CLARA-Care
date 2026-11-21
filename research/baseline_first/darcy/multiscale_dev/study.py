"""Run from this directory with extracted training members in /tmp."""
import csv

import numpy as np
import torch
from scipy.ndimage import map_coordinates


def load(size):
    data = torch.load(f"/tmp/darcy_train_{size}.pt", weights_only=True)
    return [data[key][:640].numpy().astype(float) for key in ("x", "y")]


def corners(field):
    padded = np.pad(field, ((0, 0), (0, 1), (0, 1)), mode="edge")
    return np.stack([padded[:, i:i+16, j:j+16] for i, j in
                     [(0, 0), (0, 1), (1, 0), (1, 1)]], axis=-1)


a, p = load(16)
af, target = load(32)
for coarse, fine in [(a, af), (p, target)]:
    np.testing.assert_array_equal(coarse, fine[:, ::2, ::2])

coords = np.minimum(np.indices((32, 32)) / 2, 15)
pred = {name: np.stack([map_coordinates(field, coords, order=order,
                                        mode="nearest") for field in p[512:]])
        for name, order in [("bilinear", 1), ("bicubic", 3)]}
np.testing.assert_allclose(pred["bicubic"][:, ::2, ::2], p[512:], atol=1e-12)
pred["bicubic"][:, ::2, ::2] = p[512:]
pressure = corners(p)
gates = {"pressure_control": (pressure > pressure.mean(-1, keepdims=True)),
         "coefficient": corners(a)}
for name in gates:
    pred[name] = pred["bilinear"].copy()
for i, j in [(0, 1), (1, 0), (1, 1)]:
    weights = np.outer([1-i/2, i/2], [1-j/2, j/2]).ravel()
    base = pressure @ weights
    diff = pressure - base[..., None]
    residual = target[:, i::2, j::2] - base
    for name, gate in gates.items():
        features = np.concatenate([diff, diff * (gate - gate.mean(-1, keepdims=True))], -1)
        beta = np.linalg.lstsq(features[:512].reshape(-1, 8),
                               residual[:512].ravel(), rcond=None)[0]
        pred[name][:, i::2, j::2] = base[512:] + features[512:] @ beta

mask = np.ones((32, 32), dtype=bool)
mask[::2, ::2] = False
truth = target[512:, mask]
scores = {}
for name, values in pred.items():
    np.testing.assert_array_equal(values[:, ::2, ::2], p[512:])
    scores[name] = np.linalg.norm(values[:, mask]-truth, axis=1) / np.linalg.norm(truth, axis=1)
    print(name, scores[name].mean())
with open("fields.csv", "w", newline="") as stream:
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["training_index", *scores])
    writer.writerows(zip(range(512, 640), *scores.values()))
