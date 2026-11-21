"""Exact endpoint coding on a side-information table available at decode time."""

import argparse
import io
import json
import struct
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .benchmark import load

PREDICTORS = ("absolute", "parent", "midnight", "start", "last_parent_offset", "last_duration")
SCALES = (1, 60, 3600, 86400)
HEADER = struct.Struct("<BIB")


def residuals(side, values, method, decode=False):
    previous = {}
    for (parent, group, start), value in zip(side, values, strict=True):
        anchor = parent or 0
        if value is None:
            yield None
            continue
        if method == "absolute":
            predicted = 0
        elif method == "midnight":
            predicted = anchor // 86400 * 86400
        elif method == "parent":
            predicted = anchor
        elif method == "start":
            predicted = start
        else:
            anchor = start if method == "last_duration" else anchor
            predicted = anchor + previous.get(group, 0)
        actual = value + predicted if decode else value
        previous[group] = actual - anchor
        yield actual if decode else actual - predicted


def packet(series, method, scale, codec):
    q = [None if x is None else x // scale for x in series]
    r = [None if x is None else x % scale for x in series]
    columns = {"q": pa.array(q, type=pa.int64())}
    if any(r):
        columns["r"] = pa.array(r, type=pa.int64())
    sink = pa.BufferOutputStream()
    pq.write_table(
        pa.table(columns),
        sink,
        compression="zstd",
        compression_level=3,
        use_dictionary=codec == "dict",
        write_statistics=False,
        store_schema=False,
        column_encoding="DELTA_BINARY_PACKED" if codec == "delta" else None,
    )
    payload = sink.getvalue().to_pybytes()
    return HEADER.pack(PREDICTORS.index(method), len(payload), SCALES.index(scale)) + payload


def decode(stream, side):
    method, length, index = HEADER.unpack(stream.read(HEADER.size))
    table = pq.read_table(pa.BufferReader(stream.read(length))).to_pydict()
    remainder = table.get("r", [0] * len(table["q"]))
    values = [
        None if q is None else SCALES[index] * q + r
        for q, r in zip(table["q"], remainder, strict=True)
    ]
    return list(residuals(side, values, PREDICTORS[method], decode=True))


def train(side, values, methods):
    choices = {}
    for method in methods:
        series = list(residuals(side, values, method))
        for scale in SCALES:
            for codec in ("plain", "dict", "delta"):
                key = (method, scale, codec)
                data = packet(series, *key)
                if decode(io.BytesIO(data), side) != values:
                    raise ValueError("failed endpoint replay")
                choices[key] = len(data)
    return choices


def run(dataset, path):
    digest, rows = load(path, dataset)
    parents, groups, starts, ends = map(list, zip(*rows, strict=True))
    context = list(zip(parents, groups, [None] * len(rows), strict=True))
    first_methods = ("absolute", "parent", "midnight", "last_parent_offset")
    size_start = train(context, starts, first_methods)
    size_end = train(list(zip(parents, groups, starts, strict=True)), ends, PREDICTORS)
    ablations = {}
    for arm, allowed in {
        "no_parent": {"absolute", "start", "last_duration"},
        "basic_join": {"absolute", "start", "parent"},
        "no_history": {"absolute", "parent", "midnight", "start"},
        "candidate": set(PREDICTORS),
    }.items():
        first, last = [
            min((k for k in sizes if k[0] in allowed), key=sizes.get)
            for sizes in (size_start, size_end)
        ]
        ablations[arm] = dict(bytes=size_start[first] + size_end[last], first=first, last=last)
    # Verify the full stream without access to the source START in the second stage.
    start_spec, end_spec = (ablations["candidate"][k] for k in ("first", "last"))
    a = packet(list(residuals(context, starts, start_spec[0])), *start_spec)
    side_end = list(zip(parents, groups, starts, strict=True))
    b = packet(list(residuals(side_end, ends, end_spec[0])), *end_spec)
    stream = io.BytesIO(a + b)
    recovered = decode(stream, context)
    end_recovered = decode(stream, list(zip(parents, groups, recovered, strict=True)))
    if recovered != starts or end_recovered != ends or stream.read():
        raise ValueError("two-column replay failed")
    return dict(
        source_sha256=digest,
        rows=len(rows),
        pyarrow=pa.__version__,
        ablations=ablations,
        fits=len(size_start) + len(size_end),
        bytes_by_endpoint=[
            [[*key, size] for key, size in sizes.items()] for sizes in (size_start, size_end)
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("olist", "synthea"))
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.archive), indent=2))
