"""Run in stencil_dev with single-thread BLAS and OpenMP."""
import csv
import io
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

# Replay the frozen prior code, capturing its CSV in memory.
prior = Path("../multiscale_dev/study.py").read_text()
scope = {"open": lambda *args, **kwargs: io.StringIO()}
exec(compile(prior, "multiscale_dev/study.py", "exec"), scope)
a, p, target, pred = (scope[k] for k in ("a", "p", "target", "pred"))
names = ["cubic_extrap", "pressure_stencil", "material_stencil", "boundary_only", "boost"]
pred.update({k: p[512:].repeat(2, 1).repeat(2, 2) for k in names})
grid = np.indices((16, 16))
offset = grid - np.clip(grid - 1, 0, 12)


def weights(x):
    return np.array([np.prod([(x-j)/(i-j) for j in range(4) if j != i])
                     for i in range(4)])


for di, dj in [(1, 0), (0, 1), (1, 1)]:
    for u, v in np.unique(offset.reshape(2, -1).T, axis=0):
        r, c = np.where((offset[0] == u) & (offset[1] == v))
        rows = r[:, None] - u + np.repeat(np.arange(4), 4)
        cols = c[:, None] - v + np.tile(np.arange(4), 4)
        patch = p[:, rows, cols]
        base = patch @ np.outer(weights(u+di/2), weights(v+dj/2)).ravel()
        rr, cc = 2*r+di, 2*c+dj
        y = (target[:512, rr, cc] - base[:512]).ravel()
        diff = patch - p[:, r, c, None]
        interaction = diff * (a[:, rows, cols] - a[:, r, c, None])
        full = np.concatenate([diff, interaction], axis=-1)
        pred["cubic_extrap"][:, rr, cc] = base[512:]
        for name, features in [(names[1], diff), (names[2], full), (names[4], full)]:
            x = features[:512].reshape(len(y), -1)
            z = features[512:].reshape(128*len(r), -1)
            if name == "boost":
                model = HistGradientBoostingRegressor(max_iter=60, max_leaf_nodes=15,
                    early_stopping=False, random_state=0).fit(x, y)
                correction = model.predict(z)
            else:
                correction = z @ np.linalg.lstsq(x, y, rcond=1e-10)[0]
            pred[name][:, rr, cc] = base[512:] + correction.reshape(128, -1)
        pred["boundary_only"][:, rr, cc] = np.where((rr == 31) | (cc == 31),
            pred["material_stencil"][:, rr, cc], base[512:])

missing = scope["mask"]
exterior = np.indices(missing.shape).max(axis=0) == 31
with open("fields.csv", "w") as stream:
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["training_index", "arm", "all", "interior", "exterior"])
    for name, values in pred.items():
        np.testing.assert_array_equal(values[:, ::2, ::2], p[512:])
        scores = []
        for mask in [missing, missing & ~exterior, exterior]:
            truth = target[512:, mask]
            scores.append(np.linalg.norm(values[:, mask]-truth, axis=1) /
                          np.linalg.norm(truth, axis=1))
        writer.writerows(zip(range(512, 640), [name]*128, *scores))
        print(name, *np.mean(scores, axis=1), flush=True)
