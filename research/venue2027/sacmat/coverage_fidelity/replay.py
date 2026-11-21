"""Measure strict single-condition independence on XPA's public conference fixture."""

import argparse
import csv
import hashlib
import json
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree as ET


def must(condition, message):
    if not condition:
        raise ValueError(message)


def atoms(match):
    value = match.find("{*}AttributeValue")
    attr = match.find("{*}AttributeDesignator")
    must(
        match.attrib["MatchId"].endswith(":string-equal")
        and attr is not None
        and attr.attrib["MustBePresent"] == "true"
        and value is not None
        and value.attrib["DataType"].endswith("#string")
        and attr.attrib["DataType"] == value.attrib["DataType"],
        "unsupported predicate",
    )
    return ((attr.attrib["Category"], attr.attrib["AttributeId"]), value.text)


def targets(policy):
    must(policy.attrib["RuleCombiningAlgId"].endswith(":permit-overrides"), "combiner")
    must(len(policy.find("{*}Target")) == 0, "policy target")
    result = {}
    rules = policy.findall("{*}Rule")
    must(rules[-1].attrib["Effect"] == "Deny" and len(rules[-1]) == 0, "default deny")
    for rule in rules[:-1]:
        groups = rule.findall("{*}Target/{*}AnyOf/{*}AllOf")
        must(rule.attrib["Effect"] == "Permit" and len(rule) == 1 and len(groups) == 1, "target")
        predicates = [atoms(match) for match in groups[0].findall("{*}Match")]
        must(len(predicates) == 2 and len(groups[0]) == 2, "expected binary conjunction")
        result[rule.attrib["RuleId"]] = predicates
    return result


def attributes(request):
    values = {}
    for group in request.findall("{*}Attributes"):
        for attr in group.findall("{*}Attribute"):
            key = group.attrib["Category"], attr.attrib["AttributeId"]
            items = attr.findall("{*}AttributeValue")
            must(len(items) == 1 and key not in values, "expected singleton string")
            must(items[0].attrib["DataType"].endswith("#string"), "non-string request")
            values[key] = items[0].text
    return values


def independent_witnesses(rows):
    witnesses = {}
    for (name, a), (other, b) in combinations(rows.items(), 2):
        if None in a or None in b or all(a) == all(b):
            continue
        difference = [index for index, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
        if len(difference) == 1:
            witnesses.setdefault(difference[0], [name, other])
    return witnesses


def replay(path):
    data = path / "src/test/resources/org/seal/policies/conference3"
    policy = data / "conference3.xml"
    must(
        hashlib.sha256(policy.read_bytes()).hexdigest()
        == "d31ecbd9c5c67f35a3e55f6089b221d5ebbd942bebfa57fc368afcc3a134de39",
        "pinned policy differs",
    )
    suite = data / "test_suites/conference3_MCDCCoverage"
    rules = targets(ET.parse(policy).getroot())
    rows = {rule: {} for rule in rules}
    decisions = []
    with (suite / (suite.name + ".csv")).open() as f:
        for name, label in csv.reader(f):
            values = attributes(ET.parse(suite / name).getroot())
            target_values = set()
            for rule, predicates in rules.items():
                truth = tuple(
                    None if key not in values else values[key] == val for key, val in predicates
                )
                rows[rule][name] = truth
                target_values.add(False if False in truth else None if None in truth else True)
                if True in target_values:
                    break  # An earlier permit makes later rules unreachable (Section 3.1).
            # Permit-overrides on applicable Permit rules and an unconditional Deny.
            predicted = (
                "Permit" if True in target_values else "IDP" if None in target_values else "Deny"
            )
            decisions.append(dict(request=name, published=label, replay=predicted))
    return dict(
        decisions=decisions,
        targets=[
            dict(
                rule=rule,
                rows=table,
                witnesses=independent_witnesses(table),
                errors=[name for name, bits in table.items() if None in bits and False not in bits],
            )
            for rule, table in rows.items()
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    print(json.dumps(replay(parser.parse_args().upstream), indent=2))
