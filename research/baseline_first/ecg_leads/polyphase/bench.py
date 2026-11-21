"""Measure serialized phase-prediction codecs on registered development ECG."""
import argparse
import io
import json
from pathlib import Path
import struct
import sys

import numpy as np
import soundfile as sf

PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARENT / "causal_delta"))
from measure import flac, predictors, digest

ARMS = ("average", "fixed", "lagrange", "fitted")
OFFSETS = np.array([-2, -1, 1, 2])


def neighbors(kept, phase):
    axis = np.arange(5000)
    omitted = axis[phase::5]
    retained = axis[axis % 5 != phase]
    indices = np.searchsorted(retained, omitted[:, None] + OFFSETS)
    return kept[np.clip(indices, 0, len(kept) - 1)]


def prediction(arm, features, coeff):
    if arm == "fitted":
        return (features @ coeff + 128) // 256
    if arm == "lagrange":
        return (features @ [-1, 4, 4, -1] + 3) // 6
    if arm == "fixed":
        return (features @ [-1, 9, 9, -1] + 8) // 16
    return (features[:, 1] + features[:, 2] + 1) // 2


def frame(signal):
    payload = flac(signal)
    return struct.pack("<I", len(payload)) + payload


def read_frame(stream):
    size, = struct.unpack("<I", stream.read(4))
    with sf.SoundFile(io.BytesIO(stream.read(size))) as audio:
        assert audio.samplerate == 500 and audio.channels == 1
        shift = {"PCM_16": 16, "PCM_24": 8}[audio.subtype]
        return (audio.read(dtype="int32") >> shift).astype(np.int64)


def alternatives(signal):
    best = {}
    for phase in range(5):
        retained = np.arange(len(signal)) % 5 != phase
        kept, omitted = signal[retained], signal[~retained]
        features = neighbors(kept, phase)
        fitted = np.linalg.lstsq(features, omitted, rcond=None)[0]
        coeff = np.clip(np.rint(fitted * 256), -32768, 32767).astype("<i2")
        head = bytes([phase]) + frame(kept)
        for arm in ARMS:
            model = coeff.tobytes() if arm == "fitted" else b""
            payload = head + model + frame(omitted - prediction(arm, features, coeff))
            if arm not in best or len(payload) < len(best[arm]):
                best[arm] = payload
    return best


def decode(record, arm):
    stream = io.BytesIO(record)
    adc = np.zeros((5000, 12), dtype=np.int64)
    for j in range(12):
        phase, = stream.read(1)
        if phase == 5:
            adc[:, j] = read_frame(stream)
        else:
            assert phase < 5
            kept = read_frame(stream)
            coeff = np.frombuffer(stream.read(8), "<i2") if arm == "fitted" else None
            pred = prediction(arm, neighbors(kept, phase), coeff)
            mask = np.arange(5000) % 5 != phase
            adc[mask, j] = kept
            adc[~mask, j] = read_frame(stream) + pred
        if 2 <= j < 6:
            adc[:, j] += predictors(adc, j)["limb"]
    assert not stream.read()
    return adc


def measure(ref, cache):
    filename, = cache.glob("records500/*/" + ref["record"] + ".dat")
    raw = filename.read_bytes()
    assert digest(raw) == ref["adc_sha256"]
    adc = np.frombuffer(raw, "<i2").reshape(5000, 12).astype(np.int64)
    choices = {arm: [] for arm in ARMS}
    forced = {arm: [] for arm in ARMS}
    base = []
    for j, values in enumerate(adc.T):
        if 2 <= j < 6:
            values = values - predictors(adc, j)["limb"]
        direct = bytes([5]) + frame(values)
        base.append(direct)
        for arm, split in alternatives(values).items():
            forced[arm].append(split)
            choices[arm].append(min((direct, split), key=len))
    row = {"record": ref["record"], "framed_direct": sum(map(len, base))}
    assert row["framed_direct"] == ref["baselines"]["limb"] + 60
    for arm in ARMS:
        for selection in [forced[arm], choices[arm]]:
            np.testing.assert_array_equal(decode(b"".join(selection), arm), adc)
        row[arm] = {"bytes": sum(map(len, choices[arm])),
                    "forced": sum(map(len, forced[arm])),
                    "modes": [blob[0] for blob in choices[arm]]}
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    cache = parser.parse_args().cache
    refs = json.loads((PARENT / "summary.json").read_text())["records"]
    assert len(refs) == 32
    rows = [measure(ref, cache) for ref in refs]
    totals = {arm: {key: sum(r[arm][key] for r in rows) for key in ("bytes", "forced")}
              for arm in ARMS}
    print(json.dumps({"totals": totals, "records": rows}, indent=2))
