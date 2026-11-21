"""Download and authenticate only the registered PDEInvBench training files."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
from pathlib import Path
import time

import h5py
import numpy as np
import requests
import torch

REPO = "DabbyOWL/PDE_Inverse_Problem_Benchmarking"
PIN = "98b5332fef39da6b9d110a7f62702499ff913a14"
TRAIN = "darcy-flow-241/train/"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def catalog():
    url = f"https://huggingface.co/api/datasets/{REPO}/tree/{PIN}/{TRAIN.rstrip('/')}?limit=1000"
    rows = []
    while url:
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        rows.extend(r for r in response.json() if r["type"] == "file" and r["path"].endswith(".h5"))
        url = response.links.get("next", {}).get("url")
    assert len(rows) >= 192 and len({r["path"] for r in rows}) == len(rows)
    return sorted(rows, key=lambda r: digest(r["path"].encode()))[:192]


def fetch(row, cache):
    path = row["path"]
    assert path.startswith(TRAIN) and Path(path).parent.as_posix() == TRAIN.rstrip("/")
    expected = row["lfs"]["oid"]
    file = cache / Path(path).name
    if not file.exists() or digest(file.read_bytes()) != expected:
        for attempt in range(4):
            try:
                response = requests.get(f"https://huggingface.co/datasets/{REPO}/resolve/{PIN}/{path}",
                                        timeout=(15, 60))
                response.raise_for_status()
                assert digest(response.content) == expected
                tmp = file.with_suffix(".partial")
                tmp.write_bytes(response.content)
                tmp.replace(file)
                break
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
    with h5py.File(file, "r") as h:
        a, p = (h[k][:, :, 0] for k in ["coeff", "sol"])
    assert a.shape == p.shape == (241, 241) and np.isfinite(p).all()
    vals = np.unique(a)
    assert len(vals) == 2, f"{path} has {len(vals)} coefficient values"
    coords = 12 + 7 * np.arange(32)
    return (a == vals[1])[np.ix_(coords, coords)], p[np.ix_(coords, coords)], expected, path, vals


def prepare(cache, local, manifest):
    cache.mkdir(exist_ok=True, parents=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(lambda r: fetch(r, cache), catalog()))
    a, p = (np.stack([row[j] for row in rows]) for j in (0, 1))
    assert np.isfinite(a).all() and np.unique(np.stack([r[4] for r in rows]), axis=0).shape[0] == 1
    coarse = a[:, ::2, ::2]
    masks = [digest(np.packbits(m).tobytes()) for m in coarse]
    assert len(set(masks)) == len(masks)
    for samples in [p, p[:, ::2, ::2]]:
        assert len({digest(s.tobytes()) for s in samples}) == len(rows)
    old = torch.load(local / "darcy_train_16.pt", weights_only=True)["x"][:640].numpy().astype(bool)
    prior = {digest(np.packbits(m).tobytes()) for m in [*old, *~old]}
    with manifest.open("w") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["index","partition","path","sha256","coarse_mask_sha256","prior_mask_match"])
        for i, row in enumerate(rows):
            writer.writerow([i,"fit" if i < 128 else "score",row[3],row[2],masks[i],masks[i] in prior])
    for n, stride in [(32,1),(16,2)]:
        torch.save({"x":torch.tensor(a[:, ::stride, ::stride].copy()),
                    "y":torch.tensor(p[:, ::stride, ::stride].copy())}, cache / f"darcy_train_{n}.pt")
    print("count",len(rows),"coefficients",rows[0][4],"cross-archive matches",len(set(masks)&prior))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["cache","local","manifest"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    prepare(args.cache, args.local, args.manifest)
