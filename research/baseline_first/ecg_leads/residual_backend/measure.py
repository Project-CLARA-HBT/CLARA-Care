"""Replay only the previously registered development records on little-endian x86."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

parent = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(parent))
from screen import digest, encode, predictors

cache = Path(sys.argv[1])
codec = sys.argv[2]
records = json.loads((parent / "summary.json").read_text())["records"]
assert len(records) == 32
rows = []
for record in records:
    path, = cache.glob("records500/*/" + record["record"] + ".dat")
    raw = path.read_bytes()
    assert digest(raw) == record["adc_sha256"]
    x = np.frombuffer(raw, "<i2").reshape(5000, 12).astype(np.int32)
    residual = x.copy()
    for j in range(2, 6):
        residual[:, j] -= predictors(x, j)["limb"]
    control = sum(encode(channel[:, None])[0] for channel in residual.T)
    assert control == record["baselines"]["limb"]
    row = {"record": record["record"], "flac": control}
    for tag, (name, data) in enumerate([("direct", x), ("limb", residual)]):
        # Store low 16 bits. Modular addition also reverses wrapped residuals.
        payload = subprocess.check_output([codec, "encode"], input=data.astype("<u2").tobytes())
        stream = bytes([tag]) + payload
        decoded = subprocess.check_output([codec, "decode"], input=stream[1:])
        restored = np.frombuffer(decoded, "<i2").reshape(5000, 12).astype(np.int32)
        if stream[0] == 1:
            for j in range(2, 6):
                restored[:, j] += predictors(restored, j)["limb"]
        assert restored.astype("<i2").tobytes() == raw
        row[name] = len(stream)
    rows.append(row)
totals = {k: sum(row[k] for row in rows) for k in ("flac", "direct", "limb")}
assert totals["flac"] == 870339
print(json.dumps({"totals": totals, "records": rows}, indent=2))
