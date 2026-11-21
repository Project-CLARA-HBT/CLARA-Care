"""Score each generated XML request against the pinned conference rule truth tables."""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "coverage_fidelity"))
from replay import attributes, independent_witnesses, targets  # noqa: E402


def read_csv(path):
    with path.open() as f:
        return list(csv.reader(f))


def analyze(checkout, run):
    fixture = checkout / "src/test/resources/org/seal/policies/conference3"
    policy = fixture / "conference3.xml"
    if hashlib.sha256(policy.read_bytes()).hexdigest() != (
        "d31ecbd9c5c67f35a3e55f6089b221d5ebbd942bebfa57fc368afcc3a134de39"
    ):
        raise ValueError("policy digest")
    suite = fixture / "test_suites/conference3_MCDCCoverage"
    reference = read_csv(run / "generated/reference.csv")
    if [r[:2] for r in reference] != read_csv(suite / (suite.name + ".csv")):
        raise ValueError("reference denominator")
    rules = targets(ET.parse(policy).getroot())
    rows = {name: {} for name in rules}
    decisions = []
    normalized = set()
    binary = set()
    for name, observed in read_csv(run / "generated/generated.csv"):
        path = run / "generated" / name
        binary.add(path.read_bytes())
        values = attributes(ET.parse(path).getroot())
        normalized.add(tuple(sorted(values.items())))
        expected = "Deny"
        for rule, predicates in rules.items():
            bits = [values[key] == val if key in values else None for key, val in predicates]
            rows[rule][name] = bits
            if bits == [True, True]:
                expected = "Permit"
                break
            if False not in bits:
                expected = "IDP"
        decisions.append([name, observed, expected])
    calls = {}
    for line in (run / "generator.log").read_text().splitlines():
        if line.startswith("TALLY,"):
            _, phase, method, value = line.split(",")
            calls[f"{phase}_{method}"] = int(value)
    commands = Counter((run / "solver-calls.log").read_text().splitlines())
    return dict(
        reference=reference,
        generated=decisions,
        byte_distinct=len(binary),
        attribute_map_distinct=len(normalized),
        solver_calls=commands,
        method_entries=calls,
        rules=[
            dict(
                rule=rule,
                truths_by_request=bits,
                independent_witnesses=independent_witnesses(bits),
                error_witnesses=[name for name, b in bits.items() if None in b and False not in b],
            )
            for rule, bits in rows.items()
        ],
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkout", type=Path)
    p.add_argument("run", type=Path)
    a = p.parse_args()
    print(json.dumps(analyze(a.checkout, a.run), indent=2))
