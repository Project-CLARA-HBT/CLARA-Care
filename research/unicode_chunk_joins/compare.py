"""Exhaustive two-chunk experiment on the explicitly labeled UCD 15.1 cases."""

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import icu74 as icu

DIGEST = "871238e37e3be0696ec2bd0891119a041b052da1a84485eda05a5438724b223e"
TARGETS = {"NFC": (1, 1, 1, 3, 3), "NFD": (2, 2, 2, 4, 4), "NFKC": (3,) * 5, "NFKD": (4,) * 5}


def hexes(s):
    return " ".join(f"{ord(c):04X}" for c in s)


def read_cases(path):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != DIGEST:
        raise ValueError("Unexpected corpus digest")
    cases = {form: {} for form in TARGETS}
    rows = 0
    for line in data.decode().splitlines():
        record = line.partition("#")[0].strip()
        if not record or record.startswith("@"):
            continue
        fields = record.rstrip(";").split(";")
        cols = ["".join(chr(int(cp, 16)) for cp in col.split()) for col in fields]
        if len(cols) != 5:
            raise ValueError(record)
        rows += 1
        for form, targets in TARGETS.items():
            for i, (s, target) in enumerate(zip(cols, targets, strict=True)):
                label, source = cases[form].get(s, (cols[target], False))
                if label != cols[target]:
                    raise ValueError("Inconsistent oracle")
                cases[form][s] = label, source or i == 0
    return rows, cases


def boundary(form, a, b):
    return icu.after(icu.instance(form), ord(a)) or icu.before(icu.instance(form), ord(b))


def window(form, left, right, k):
    i, j = len(left) - 1, 1
    while i > 0 and not boundary(form, left[i - 1], left[i]):
        if len(left) - i == k:
            return False, False
        i -= 1
    while j < len(right) and not boundary(form, right[j - 1], right[j]):
        if j == k:
            return False, False
        j += 1
    return icu.is_normal(form, left[i:] + right[:j]), i == 0 and j == len(right)


def decisions(form, left, right):
    a, b = left[-1], right[0]
    seam = bool(boundary(form, a, b))
    results = {
        "repair": False,
        "direct": True,
        "starter": icu.ccc(ord(b)) == 0,
        "pair": icu.is_normal(form, a + b),
        "before": bool(icu.before(icu.instance(form), ord(b))),
        "either": seam,
        "full": icu.is_normal(form, left + right),
    }
    whole_checks = set()
    for k in (1, 2, 4):
        policy = f"window{k}"
        if seam:
            results[policy] = True
        else:
            results[policy], whole = window(form, left, right, k)
            if whole:
                whole_checks.add(policy)
    return results, whole_checks


def run(path, out):
    rows, cases = read_cases(path)
    stats = defaultdict(Counter)
    examples = {}
    counts = {}
    for form, inputs in cases.items():
        counts[form] = {"distinct_inputs": len(inputs), "splittable": 0}
        for s, (expected, source) in inputs.items():
            if icu.normalize(form, s) != expected:
                raise ValueError("Whole-input control failed")
            counts[form]["splittable"] += len(s) > 1
            groups = ["all"]
            if source:
                groups.append("source")
            elif all(0x1100 <= ord(cp) <= 0x11FF for cp in s):
                groups.append("derived_only_jamo")
            if len(s) > 8:
                groups.append("longer_than_eight")
            for cut in range(1, len(s)):
                left = icu.normalize(form, s[:cut])
                right = icu.normalize(form, s[cut:])
                joined = left + right
                if icu.normalize(form, joined) != expected:
                    raise ValueError("Repair control failed")
                safe = joined == expected
                predictions, checked = decisions(form, left, right)
                if predictions["full"] != safe:
                    raise ValueError("Full check disagrees with oracle")
                for policy, accept in predictions.items():
                    for group in groups:
                        cell = stats[group, form, policy]
                        cell["splits"] += 1
                        cell["direct"] += accept
                        cell["incorrect"] += accept and not safe
                        cell["unnecessary_repairs"] += safe and not accept
                        cell["whole_window_checks"] += policy in checked
                        cell["whole_window_direct"] += accept and policy in checked
                    if accept and not safe and policy in ("starter", "pair"):
                        key = f"{form}_{policy}"
                        rank = (len(s), s, cut)
                        if key not in examples or rank < examples[key][0]:
                            examples[key] = (
                                rank,
                                dict(
                                    left=hexes(left),
                                    right=hexes(right),
                                    expected=hexes(expected),
                                    input=hexes(s),
                                    cut=cut,
                                ),
                            )
    out.mkdir(parents=True, exist_ok=True)
    with (out / "counts.csv").open("w") as f:
        writer = csv.writer(f, lineterminator="\n")
        keys = [
            "splits",
            "direct",
            "incorrect",
            "unnecessary_repairs",
            "whole_window_checks",
            "whole_window_direct",
        ]
        writer.writerow(["group", "form", "policy", *keys])
        for group_key, cell in sorted(stats.items()):
            writer.writerow([*group_key, *(cell[k] for k in keys)])
    manifest = dict(
        explicit_rows=rows,
        counts=counts,
        corpus_sha256=DIGEST,
        examples={k: v[1] for k, v in examples.items()},
    )
    (out / "audit.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.corpus, args.output)
