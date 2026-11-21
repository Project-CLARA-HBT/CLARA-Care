"""Replay the published Cedar handwritten decision fixtures against two adapter configurations.

Supply a clone of cedar-policy/cedar-integration-tests. All inputs are read
from its pinned Git object, independent of the checkout. Match the CLI exit
code and decision text. Record every request including CLI and format errors.
The endpoint is static decision parity. Validation diagnostics and temporal
consent semantics are outside this endpoint.
"""

import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from evaluation.venue2027.sacmat.cedar_runner import CedarCli, CedarRunnerError

SOURCE = "aff4b8b99acb71aa5b288fa236295cccbb40d541"
ENGINE = "cedar-policy-cli 4.14.1"


def replay(repo):
    binary = shutil.which("cedar")
    if not binary or subprocess.check_output([binary, "--version"], text=True).strip() != ENGINE:
        raise RuntimeError("pinned_cedar_cli_required")
    cli = CedarCli(binary)
    git = ["git", "-C", str(repo)]
    files = subprocess.check_output(
        [*git, "ls-tree", "-r", "--name-only", SOURCE, "tests"], text=True
    ).splitlines()

    def read(name):
        return subprocess.check_output([*git, "show", f"{SOURCE}:{name}"], text=True)

    rows = []
    for name in files:
        if not name.endswith(".json"):
            continue
        fixture = json.loads(read(name))
        if not isinstance(fixture, dict) or "requests" not in fixture:
            continue
        policies, entities, schema = (read(fixture[k]) for k in ("policies", "entities", "schema"))
        for idx, request in enumerate(fixture["requests"]):
            payload = {"context": request["context"]}
            for key in ("principal", "action", "resource"):
                uid = request.get(key)
                if uid is not None:
                    payload[key] = uid["type"] + "::" + json.dumps(uid["id"], ensure_ascii=False)
            result = {"fixture": name, "request": idx, "expected": request["decision"].upper()}
            for arm, options in [
                ("legacy", {}),
                (
                    "source_declared",
                    dict(
                        schema_text=schema,
                        schema_format=fixture.get("schemaFormat", "cedar"),
                        policy_format=fixture.get("policyFormat", "cedar"),
                        validate_request=request.get("validateRequest", True),
                    ),
                ),
            ]:
                try:
                    code, stdout, _ = cli.authorize(
                        policies, entities, json.dumps(payload), **options
                    )
                except CedarRunnerError as exc:
                    result[arm] = exc.reason_code
                    continue
                lines = stdout.strip().splitlines()
                decision = lines[0] if lines else ""
                result[arm] = (
                    decision
                    if (code, decision) in {(0, "ALLOW"), (2, "DENY")}
                    else "EXECUTION_ERROR"
                )
            rows.append(result)
    if not rows:
        raise ValueError("no_source_requests")
    summary = {}
    for arm in ("legacy", "source_declared"):
        counts = Counter(
            "match"
            if r[arm] == r["expected"]
            else "disagreement"
            if r[arm] in {"ALLOW", "DENY"}
            else "error"
            for r in rows
        )
        summary[arm] = dict(sorted(counts.items()))
    return {
        "dataset": "cedar-policy/cedar-integration-tests",
        "commit": SOURCE,
        "cohort": "all handwritten tests/*/*.json with requests; includes format variants",
        "engine": ENGINE,
        "engine_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
        "requests": len(rows),
        "fixtures": len({r["fixture"] for r in rows}),
        "summary": summary,
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(replay(Path(sys.argv[1])), indent=2))
