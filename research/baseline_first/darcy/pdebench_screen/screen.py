"""Verify the official archive before testing binary-stencil compatibility."""
import argparse
import csv
from hashlib import file_digest
from pathlib import Path

import h5py
import numpy as np
import torch


def main(path, out):
    with path.open("rb") as f:
        assert file_digest(f, "md5").hexdigest() == "81694ed31306ff2e5f6b76349b0b4389"
    with h5py.File(path, "r") as h:
        assert h["nu"].shape == (10000, 128, 128)
        assert h["tensor"].shape == (10000, 1, 128, 128)
        material = h["nu"][:192]
        pressure = h["tensor"][:192,0]
    assert np.isfinite(material).all() and np.isfinite(pressure).all()
    levels = [np.unique(x) for x in material]
    with (out/"levels.csv").open("w") as f:
        w = csv.writer(f,lineterminator="\n")
        w.writerow(["train_index","distinct_values","minimum","maximum"])
        w.writerows((i,len(v),v[0],v[-1]) for i,v in enumerate(levels))
    domain = np.unique(np.concatenate(levels))
    if len(domain) != 2:
        print("Binary protocol stops. Distinct levels per field:",min(map(len,levels)),max(map(len,levels)))
        return
    for n, stride in [(32,4),(16,8)]:
        a = material[:,::stride,::stride] == domain[1]
        p = pressure[:,::stride,::stride]
        torch.save({"x":torch.from_numpy(a.copy()),"y":torch.from_numpy(p.copy())},
                   path.parent / f"darcy_train_{n}.pt")
    print("Binary protocol eligible")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args()
    main(args.path,args.out)
