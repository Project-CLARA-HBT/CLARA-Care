"""Evaluate scoped code retrieval with a purpose-only materialized projection."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path


def project(record):
    def pack(holder):
        if "authorization" not in holder:
            return None
        return [
            None
            if "coding" not in concept
            else [
                [coding.get(key) for key in ("system", "version", "code")]
                for coding in concept["coding"]
            ]
            for concept in holder["authorization"]
        ]

    return [pack(record), [pack(agent) for agent in record["agent"]]]


def full_read(db, payload):
    """Read the unprojected document through SQLite JSON1 paths at query time."""

    def concepts(path):
        kind, length = db.execute(
            "select json_type(?, ?), json_array_length(?, ?)", (payload, path, payload, path)
        ).fetchone()
        if kind is None:
            return None
        result = []
        for i in range(length):
            prefix = f"{path}[{i}].coding"
            if db.execute("select json_type(?, ?)", (payload, prefix)).fetchone()[0] is None:
                result.append(None)
                continue
            result.append(
                [
                    list(row)
                    for row in db.execute(
                        "select json_extract(value, '$.system'), json_extract(value, '$.version'), "
                        "json_extract(value, '$.code') from json_each(?, ?) order by key",
                        (payload, prefix),
                    )
                ]
            )
        return result

    agents = db.execute("select json_array_length(?, '$.agent')", (payload,)).fetchone()[0]
    return [
        concepts("$.authorization"),
        [concepts(f"$.agent[{i}].authorization") for i in range(agents)],
    ]


def known_codes(system, subset):
    base = "http://terminology.hl7.org/CodeSystem/v3-ActReason"
    assert system["url"] == base and system["content"] == "complete"
    assert subset["compose"] == {
        "include": [
            {
                "system": base,
                "filter": [{"property": "concept", "op": "is-a", "value": "PurposeOfUse"}],
            }
        ],
        "exclude": [{"system": base, "concept": [{"code": "PurposeOfUse"}]}],
    }
    members = {"PurposeOfUse"}
    while True:
        added = {
            c["code"]
            for c in system["concept"]
            if any(
                p["code"] == "subsumedBy" and p["valueCode"] in members
                for p in c.get("property", [])
            )
        }
        if added <= members:
            break
        members.update(added)
    return members - {"PurposeOfUse"}


def run(work):
    def load(name):
        return json.loads((work / name).read_bytes())

    system = load("CodeSystem-v3-ActReason.json")
    codes = known_codes(system, load("ValueSet-v3-PurposeOfUse.json"))
    db = sqlite3.connect(":memory:")
    rows = []
    groups = Counter()
    for path in sorted(work.glob("*-example*.json")):
        raw = json.loads(path.read_bytes())
        assert raw["resourceType"] == "AuditEvent"
        event, agents = project(raw)
        if [event, agents] != full_read(db, path.read_text()):
            raise ValueError(f"independent full-source query mismatch: {path.name}")
        matched = []
        counts = Counter()
        for scope, slots in (("event", [event]), ("agent", agents)):
            licensed = False
            for concepts in slots:
                if concepts is None:
                    continue
                counts[scope + "_declarations"] += len(concepts)
                for codings in concepts:
                    for sys, version, code in codings or []:
                        if (
                            sys == system["url"]
                            and version in (None, system["version"])
                            and code in codes
                        ):
                            counts[scope + "_purpose_codings"] += 1
                            licensed = True
                        else:
                            counts[scope + "_unclassified_codings"] += 1
            matched.append(licensed)
        group = ("neither", "agent_only", "event_only", "both")[matched[0] * 2 + matched[1]]
        groups[group] += 1
        semantic_bytes = json.dumps(
            [event, agents], ensure_ascii=False, separators=(",", ":")
        ).encode()
        rows.append(
            {
                "source": path.name,
                "scope_group": group,
                "projection_sha256": hashlib.sha256(semantic_bytes).hexdigest(),
                **counts,
            }
        )
    if len(rows) != 13:
        raise ValueError("incomplete dataset")
    print(
        json.dumps(
            {
                "sources": len(rows),
                "purpose_codes_in_terminology": len(codes),
                "scope_counts": dict(groups),
                "rows": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch", type=Path)
    run(parser.parse_args().scratch)
