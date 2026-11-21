"""Check the released pressure against the upstream interior discrete operator."""
import argparse
import hashlib
import json

import numpy as np


def audit(path):
    with np.load(path, allow_pickle=False) as fields:
        bits, pressure = fields["material"], fields["pressure"]
    assert bits.shape == pressure.shape == (640, 32, 32)
    assert bits.dtype == np.uint8 and pressure.dtype == np.float32
    assert np.array_equal(np.unique(bits), [0, 1])
    assert np.all(np.isfinite(pressure)) and np.all(pressure > 0)
    assert len({row.tobytes() for row in bits}) == 640
    k = 0.5 + 1.5 * bits
    p = pressure.astype(np.float64)
    kc, pc = k[:, 1:-1, 1:-1], p[:, 1:-1, 1:-1]
    lap = p[:, :-2, 1:-1] + p[:, 2:, 1:-1] + p[:, 1:-1, :-2] + p[:, 1:-1, 2:] - 4 * pc
    grad = ((k[:, 2:, 1:-1] - k[:, :-2, 1:-1]) * (p[:, 2:, 1:-1] - p[:, :-2, 1:-1])
            + (k[:, 1:-1, 2:] - k[:, 1:-1, :-2]) * (p[:, 1:-1, 2:] - p[:, 1:-1, :-2])) / 4
    residual = (kc * lap + grad) * 33**2 + 1
    return {"max_abs_interior_discrete_residual": float(np.abs(residual).max()),
            "rms_interior_discrete_residual": float(np.sqrt(np.mean(residual**2))),
            "n_unique_materials": 640,
            "hashes_C_order": {name: hashlib.sha256(a.tobytes()).hexdigest()
                               for name, a in [("material_uint8", bits), ("pressure_float32", pressure)]}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("fields")
    args = parser.parse_args()
    print(json.dumps(audit(args.fields), indent=2))
