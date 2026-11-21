"""Compare reversible temporal transforms at equal Parquet settings."""

import argparse
import csv
import hashlib
import io
import json
import struct
import zipfile
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from evaluation.venue2027.aime.synthea_visit_refresh import ARCHIVE_PREFIX

BLOCK = 4096
METHODS = list(product(("absolute", "duration", "parent", "by_type"), ("plain", "dict", "delta")))
HEADER = struct.Struct("<BI")


def second(value):
    if not value:
        return None
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp())


def csv_rows(archive, name):
    with archive.open(name) as binary:
        yield from csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig"))


def load(path, dataset):
    with path.open("rb") as raw:
        digest = hashlib.file_digest(raw, "sha256").hexdigest()
    with zipfile.ZipFile(path) as archive:
        if dataset == "synthea":
            prefix = ARCHIVE_PREFIX[digest]
            parents = {
                r["Id"]: second(r["START"]) for r in csv_rows(archive, prefix + "encounters.csv")
            }
            table, fk, group, start, stop = (
                prefix + "medications.csv",
                "ENCOUNTER",
                "CODE",
                "START",
                "STOP",
            )
        else:
            parents = {
                r["order_id"]: second(r["order_purchase_timestamp"])
                for r in csv_rows(archive, "olist_orders_dataset.csv")
            }
            table, fk, group = "olist_order_reviews_dataset.csv", "order_id", "review_score"
            start, stop = "review_creation_date", "review_answer_timestamp"
        rows = [
            (parents.get(r[fk]), r[group], second(r[start]), second(r[stop]))
            for r in csv_rows(archive, table)
        ]
    return digest, rows


def transform(rows, mode, decode=False):
    """Reset predictors per independently decodable frame."""
    history = {}
    result = []
    for parent, group, first, last in rows:
        anchor = parent or 0
        offset, duration = history.get(group, (0, 0))
        first_prediction = anchor if mode in {"parent", "by_type"} else 0
        if mode == "by_type":
            first_prediction += offset
        start = first + first_prediction if decode else first
        stop_prediction = 0 if mode == "absolute" else start
        if mode == "by_type":
            stop_prediction += duration
        stop = last
        if last is not None and decode:
            stop += stop_prediction
        history[group] = (start - anchor, duration if stop is None else stop - start)
        if decode:
            result.append((start, stop))
        else:
            result.append(
                (first - first_prediction, None if last is None else last - stop_prediction)
            )
    return result


def encode(values, codec):
    first, last = zip(*values, strict=True)
    table = pa.table({k: pa.array(v, type=pa.int64()) for k, v in (("a", first), ("b", last))})
    sink = pa.BufferOutputStream()
    pq.write_table(
        table,
        sink,
        compression="zstd",
        compression_level=3,
        use_dictionary=codec == "dict",
        column_encoding="DELTA_BINARY_PACKED" if codec == "delta" else None,
        write_statistics=False,
        store_schema=False,
    )
    return sink.getvalue().to_pybytes()


def check_frame(packet, rows):
    method, size = HEADER.unpack_from(packet)
    if size != len(packet) - HEADER.size:
        raise ValueError("frame size mismatch")
    decoded = pq.read_table(pa.BufferReader(packet[HEADER.size :])).to_pydict()
    inputs = [
        (parent, group, a, b)
        for (parent, group, _, _), a, b in zip(rows, decoded["a"], decoded["b"], strict=True)
    ]
    if transform(inputs, METHODS[method][0], decode=True) != [(r[2], r[3]) for r in rows]:
        raise ValueError("timestamp pair failed to round trip")


def compare(rows):
    lengths = []
    for mode in ("absolute", "duration", "parent", "by_type"):
        values = transform(rows, mode)
        for codec in ("plain", "dict", "delta"):
            method = len(lengths)
            data = encode(values, codec)
            packet = HEADER.pack(method, len(data)) + data
            check_frame(packet, rows)
            lengths.append(len(packet))
    return lengths


def run(path, dataset):
    digest, rows = load(path, dataset)
    whole = compare(rows)
    blocks = [compare(rows[i : i + BLOCK]) for i in range(0, len(rows), BLOCK)]
    return dict(
        source_sha256=digest,
        dataset=dataset,
        rows=len(rows),
        missing_parent=sum(r[0] is None for r in rows),
        missing_end=sum(r[3] is None for r in rows),
        pyarrow=pa.__version__,
        block_size=BLOCK,
        methods=["/".join(m) for m in METHODS],
        whole_bytes=whole,
        frame_bytes=blocks,
        best_fixed_whole_bytes=min(whole),
        best_fixed_framed_bytes=min(map(sum, zip(*blocks, strict=True))),
        selected_bytes=sum(map(min, blocks)),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("synthea", "olist"))
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.archive, args.dataset), indent=2))
