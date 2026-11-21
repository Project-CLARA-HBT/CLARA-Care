"""Serialized per-record ECG codecs with residual alphabets and parity contexts."""
import argparse
import io
import json
import lzma
from pathlib import Path
import struct
import sys
import zlib

import constriction
import numpy as np

PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARENT/"causal_delta"))
sys.path.insert(0, str(PARENT/"polyphase"))
from measure import digest, predictors, flac
from bench import read_frame

KEEP = [0,1,6,7,8,9,10,11]
ARMS = ("flac", "marginal", "marginal_parity", "joint", "joint_parity", "lzma", "lzma_parity")


def frame(payload):
    return struct.pack("<I",len(payload)) + payload


def take(stream):
    size, = struct.unpack("<I",stream.read(4))
    payload = stream.read(size)
    assert len(payload) == size
    return payload


def ans_dist(counts):
    return constriction.stream.model.Categorical(counts.astype(np.float64),perfect=False)


def residual_block(values, context, use_lzma):
    vocab, ids = np.unique(values, axis=0,return_inverse=True)
    ids = ids.ravel().astype(np.int32)
    out = io.BytesIO()
    out.write(frame(zlib.compress(vocab.astype("<i4").tobytes(),9)))
    if use_lzma:
        order = np.argsort(context,kind="stable")
        dtype = "u1" if len(vocab) <= 256 else "<u2"
        out.write(frame(lzma.compress(ids[order].astype(dtype).tobytes())))
    else:
        for group in np.unique(context):
            symbols = ids[context == group]
            counts = np.bincount(symbols,minlength=len(vocab)).astype("<u2")
            out.write(frame(zlib.compress(counts.tobytes(),9)))
            if len(vocab) > 1:
                coder = constriction.stream.stack.AnsCoder()
                coder.encode_reverse(symbols,ans_dist(counts))
                out.write(frame(coder.get_compressed().astype("<u4").tobytes()))
    return out.getvalue()


def recover_block(stream, width, context, use_lzma):
    vocab = np.frombuffer(zlib.decompress(take(stream)), "<i4").reshape(-1,width)
    ids = np.zeros(len(context), dtype=np.int32)
    if use_lzma:
        dtype = "u1" if len(vocab) <= 256 else "<u2"
        ids[np.argsort(context,kind="stable")] = np.frombuffer(lzma.decompress(take(stream)),dtype)
    else:
        for group in np.unique(context):
            selected = context == group
            counts = np.frombuffer(zlib.decompress(take(stream)),"<u2")
            assert len(counts) == len(vocab) and counts.sum() == selected.sum()
            if len(vocab) > 1:
                raw = np.frombuffer(take(stream),"<u4").astype(np.uint32)
                coder = constriction.stream.stack.AnsCoder(raw)
                ids[selected] = coder.decode(ans_dist(counts),int(selected.sum()))
                assert coder.is_empty()
    return vocab[ids]


def contexts(signal, arm):
    if arm.endswith("_parity"):
        return signal[:,0] % 2 + 2 * (signal[:,1] % 2)
    return np.zeros(len(signal),int)


def encode(adc, arm):
    out = io.BytesIO()
    out.write(bytes([ARMS.index(arm)]))
    for j in KEEP:
        out.write(frame(flac(adc[:,j])))
    res = np.column_stack([adc[:,j]-predictors(adc,j)["limb"] for j in range(2,6)])
    if arm == "flac":
        for col in res.T:
            out.write(frame(flac(col)))
    else:
        blocks = np.hsplit(res,4) if arm.startswith("marginal") else [res]
        for block in blocks:
            out.write(residual_block(block,contexts(adc,arm),arm.startswith("lzma")))
    return out.getvalue()


def decode(payload):
    stream = io.BytesIO(payload)
    mode, = stream.read(1)
    arm = ARMS[mode]
    leads = [read_frame(stream) for _ in KEEP]
    adc = np.zeros((len(leads[0]),12),dtype=np.int64)
    for j, lead in zip(KEEP, leads, strict=True):
        adc[:,j] = lead
    if arm == "flac":
        res = np.column_stack([read_frame(stream) for _ in range(4)])
    else:
        widths = [1]*4 if arm.startswith("marginal") else [4]
        res = np.column_stack([recover_block(stream,width,contexts(adc,arm),arm.startswith("lzma"))
                               for width in widths])
    for j in range(2,6):
        adc[:,j] = res[:,j-2]+predictors(adc,j)["limb"]
    assert stream.read() == b""
    return adc


def main(cache):
    refs = json.loads((PARENT/"summary.json").read_text())["records"]
    rows = []
    for ref in refs:
        filename, = cache.glob("records500/*/"+ref["record"]+".dat")
        data = filename.read_bytes()
        assert digest(data) == ref["adc_sha256"]
        adc = np.frombuffer(data,"<i2").reshape(5000,12).astype(np.int64)
        row = {"record":ref["record"]}
        for arm in ARMS:
            payload = encode(adc,arm)
            np.testing.assert_array_equal(decode(payload),adc)
            row[arm] = len(payload)
        assert row["flac"] == ref["baselines"]["limb"]+49
        rows.append(row)
    totals = {arm:sum(r[arm] for r in rows) for arm in ARMS}
    print(json.dumps({"totals":totals,"records":rows},indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cache",type=Path)
    main(p.parse_args().cache)
