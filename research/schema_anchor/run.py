"""Replay the frozen Valentine table-pair elimination experiment."""

import argparse
import hashlib
import json
import platform
import zipfile
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import pandas as pd
from valentine import valentine_match
from valentine.algorithms import Coma, Cupid


def normalize(value):
    return " ".join(str(value).lower().split())


def value_sets(frame):
    return {
        column: {s for value in frame[column].dropna() if (s := normalize(value))}
        for column in frame.columns
    }


def anchors(source, target, rare):
    left, right = value_sets(source), value_sets(target)
    ownership = [
        Counter(value for values in side.values() for value in values) for side in (left, right)
    ]
    scores = {}
    for a, values in left.items():
        for b, others in right.items():
            common = values & others
            if rare:
                common = {v for v in common if ownership[0][v] == ownership[1][v] == 1}
            if len(common) >= 3:
                scores[a, b] = len(common) / min(len(values), len(others))
    return {
        (a, b)
        for (a, b), score in scores.items()
        if score >= 0.5
        and all(
            score > other_score for (x, y), other_score in scores.items() if (x == a) != (y == b)
        )
    }


def predictions(left, right):
    arms = {"header": {(a, b) for a in left for b in right if normalize(a) == normalize(b)}}
    for name, matcher in (
        ("cupid", Cupid()),
        ("coma_schema", Coma()),
        ("coma_values", Coma(use_instances=True)),
    ):
        pairs = valentine_match([left, right], matcher, instance_sample_size=None)
        arms[name] = {(p.source_column, p.target_column) for p in pairs}
    for name, rare in (("all_values", False), ("rare_values", True)):
        arms[name] = arms["coma_values"] | anchors(left, right, rare)
    return arms


def run(path):
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "md5").hexdigest()
    if digest != "98da6d6701806538e5c685f4426b95f6":
        raise ValueError("archive fingerprint differs from published deposit")
    records = []
    with zipfile.ZipFile(path) as z:
        paths = sorted(
            p
            for p in z.namelist()
            if p.startswith(("Valentine-datasets/Magellan/", "Valentine-datasets/Wikidata/"))
            and p.endswith("_mapping.json")
        )
        for file in paths:
            prefix = file.removesuffix("_mapping.json")
            tables = []
            for suffix in ("source", "target"):
                with z.open(prefix + "_" + suffix + ".csv") as raw:
                    tables.append(pd.read_csv(raw, nrows=96))
            arms = predictions(*tables)
            gold = {
                (m["source_column"], m["target_column"])
                for m in json.loads(z.read(file))["matches"]
            }
            for a, b in gold:
                if a not in tables[0] or b not in tables[1]:
                    raise ValueError(f"unmapped gold column in {file}: {(a, b)}")
            records.append(
                dict(
                    pair=prefix,
                    rows=[len(t) for t in tables],
                    gold=sorted(gold),
                    predictions={k: sorted(v) for k, v in arms.items()},
                )
            )
    return dict(
        archive_md5=digest,
        python=platform.python_version(),
        versions={k: version(k) for k in ("pandas", "valentine", "nltk", "rapidfuzz", "numpy")},
        records=records,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.archive), indent=2) + "\n")
