"""Encode and decode the registered PTB-XL development records."""
import argparse
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARENT))
from screen import digest, predictors

ARMS = ("limb", "delta", "linear", "gated")
BLOCK = 250


def flac(signal):
    sixteen = signal.min() >= -32768 and signal.max() <= 32767
    assert signal.min() >= -(1 << 23) and signal.max() < (1 << 23)
    pcm = signal.astype("int16") if sixteen else (signal << 8).astype("int32")
    subtype = "PCM_16" if sixteen else "PCM_24"
    file = io.BytesIO()
    sf.write(file, pcm, 500, format="FLAC", subtype=subtype, compression_level=1.0)
    return file.getvalue()


def gain(source, target):
    den = int(source @ source)
    if den == 0:
        return 0
    num = int(source @ target) * 8
    # Round a tie toward positive infinity on both sides of zero.
    return max(-16, min(16, (2 * num + den) // (2 * den)))


def predict(history, previous, current, gated):
    lowest = int(history @ history)
    prediction = np.zeros(len(current), dtype=np.int64)
    for old, new in zip(previous.T, current.T, strict=True):
        limit = np.median(abs(old)) if gated else 0
        high = abs(old) > limit if gated else np.zeros(len(old), dtype=bool)
        lo_gain = gain(old[~high], history[~high])
        hi_gain = gain(old[high], history[high])
        residual = history - (np.where(high, hi_gain, lo_gain) * old + 4) // 8
        loss = int(residual @ residual)
        if loss < lowest:
            lowest = loss
            new_gain = np.where(abs(new) > limit, hi_gain, lo_gain) if gated else lo_gain
            prediction = (new * new_gain + 4) // 8
    return prediction


def chest(signal, decoded_sources, arm, inverse):
    source_delta = np.diff(decoded_sources, axis=0, prepend=0)
    values = signal if inverse else np.diff(signal, prepend=0)
    result = values.copy()
    if arm in ("linear", "gated"):
        for start in range(BLOCK, len(signal), BLOCK):
            past = slice(start - BLOCK, start)
            now = slice(start, start + BLOCK)
            history = result[past] if inverse else values[past]
            pred = predict(history, source_delta[past], source_delta[now], arm == "gated")
            result[now] = values[now] + pred if inverse else values[now] - pred
    return result.cumsum() if inverse else result


def transform(signal, available, j, arm, inverse):
    if 2 <= j < 6:
        pred = predictors(available, j)["limb"]
        return signal + pred if inverse else signal - pred
    if j >= 6 and arm != "limb":
        sources = available[:, [0, 1, *range(6, j)]]
        return chest(signal, sources, arm, inverse)
    return signal


def encode(raw, arm):
    record = io.BytesIO()
    for j, signal in enumerate(raw.T):
        payload = flac(transform(signal, raw, j, arm, inverse=False))
        record.write(struct.pack("<I", len(payload)))
        record.write(payload)
    return record.getvalue()


def decode(record, arm):
    stream = io.BytesIO(record)
    output = np.zeros((5000, 12), dtype=np.int64)
    for j in range(12):
        length, = struct.unpack("<I", stream.read(4))
        with sf.SoundFile(io.BytesIO(stream.read(length))) as audio:
            assert audio.channels == 1 and audio.samplerate == 500
            shift = {"PCM_16": 16, "PCM_24": 8}[audio.subtype]
            signal = (audio.read(dtype="int32") >> shift).astype(np.int64)
        output[:, j] = transform(signal, output, j, arm, inverse=True)
    assert not stream.read()
    return output


def main(cache):
    rows = []
    for ref in json.loads((PARENT / "summary.json").read_text())["records"]:
        filename, = cache.glob("records500/*/" + ref["record"] + ".dat")
        blob = filename.read_bytes()
        assert digest(blob) == ref["adc_sha256"]
        raw = np.frombuffer(blob, "<i2").reshape(5000, 12).astype(np.int64)
        row = {"record": ref["record"]}
        for arm in ARMS:
            payload = encode(raw, arm)
            np.testing.assert_array_equal(decode(payload, arm), raw)
            row[arm] = len(payload)
        assert row["limb"] == ref["baselines"]["limb"] + 48
        rows.append(row)
    assert len(rows) == 32
    totals = {arm: sum(row[arm] for row in rows) for arm in ARMS}
    print(json.dumps({"totals": totals, "records": rows}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    main(parser.parse_args().cache)
