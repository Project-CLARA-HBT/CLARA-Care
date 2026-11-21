"""Materialize fixed-point scores and public positive flags in a private scratch file."""

import argparse
from pathlib import Path

import numpy as np


def quantize(values):
    values = values.astype(np.float64)
    span = np.ptp(values)
    return (
        np.rint(65535 * (values - values.min()) / span).astype(int)
        if span
        else np.zeros(len(values), int)
    )


def records(path):
    for name in ("NanoArguAna", "NanoFiQA2018", "NanoSCIDOCS"):
        with np.load(path / (name + ".npz")) as data:
            docs = data["docs"]
            if list(docs) != sorted(set(docs)):
                raise ValueError("unstable document ordering")
            for i, q in enumerate(data["queries"]):
                keep = docs != q
                pos = np.isin(docs[keep], data["positive"][data["positive"][:, 0] == q, 1])
                yield (
                    name,
                    str(q),
                    quantize(data["sparse"][i, keep]),
                    quantize(data["dense"][i, keep]),
                    pos,
                )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scores", type=Path)
    p.add_argument("out", type=Path)
    a = p.parse_args()
    with a.out.open("x") as f:
        for name, q, x, y, pos in records(a.scores):
            print(name, q, len(pos), file=f)
            np.savetxt(f, np.column_stack([x, y, pos]), fmt="%i")
