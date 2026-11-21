"""Generate development tensors with the unmodified upstream solver and kernels."""
import argparse
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import numpy as np
import torch
import warp

REV = "5af5afd818bf2f120b61fbf4ad920759bfdc8372"


def generate_chunk(start):
    from physicsnemo.datapipes.benchmarks.darcy import Darcy2D

    np.random.seed(702341)
    for _ in range(start):
        np.random.randint(np.iinfo(np.uint64).max, dtype=np.uint64)
    stream = iter(Darcy2D(resolution=32, batch_size=8, device="cpu",
                          convergence_threshold=1e-8, iterations_per_convergence_check=50))
    material, pressure = [], []
    for _ in range(5):
        batch = next(stream)
        k = batch["permeability"][:, 0]
        assert set(torch.unique(k).tolist()) == {0.5, 2.0}
        material.append((k == 2).byte())
        pressure.append(batch["darcy"][:, 0].clone())
    return torch.cat(material).numpy(), torch.cat(pressure).numpy()


def generate(source, output):
    assert subprocess.check_output(["git", "-C", source, "rev-parse", "HEAD"], text=True).strip() == REV
    subprocess.run(["git", "-C", source, "diff", "--exit-code", "HEAD", "--", "physicsnemo/datapipes"], check=True)
    # Load only upstream datapipes, bypassing unrelated package-wide ML imports.
    for name in ("physicsnemo", "physicsnemo.datapipes", "physicsnemo.datapipes.benchmarks"):
        package = ModuleType(name)
        package.__path__ = [str(source.joinpath(*name.split(".")))]
        sys.modules[name] = package
    from physicsnemo.datapipes.benchmarks.darcy import Darcy2D

    # Each process advances the same upstream one-draw-per-batch seed stream.
    with get_context("fork").Pool(16) as pool:
        batches = pool.map(generate_chunk, range(0, 80, 5))
    x, y = [torch.from_numpy(np.concatenate(parts)) for parts in zip(*batches)]
    assert torch.isfinite(y).all() and (y > 0).all()
    assert len({row.numpy().tobytes() for row in x}) == len(x)
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output / "fields.npz", material=x.numpy(), pressure=y.numpy())
    for size, step in [(16, 2), (32, 1)]:
        torch.save({"x": x[:, ::step, ::step].contiguous(), "y": y[:, ::step, ::step].contiguous()},
                   output / f"darcy_train_{size}.pt")
    metadata = {"source_revision": REV, "warp": warp.__version__, "numpy": np.__version__,
                "torch": torch.__version__, "seed": 702341, "batch_size": 8, "batches": 80,
                "hashes_C_order": {key: hashlib.sha256(v.numpy().tobytes()).hexdigest()
                                   for key, v in [("material_uint8", x), ("pressure_float32", y)]}}
    (output / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    generate(args.source.resolve(), args.output)
