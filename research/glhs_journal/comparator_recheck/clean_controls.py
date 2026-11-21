"""Reconcile E17 clean controls with sealed decisions and the pinned call sites."""

import ast
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / "research/glhs_journal/q4_r4/evidence/E17_current_state_insufficiency"


def audit():
    records = BUNDLE / "raw/runs.jsonl"
    hashes = dict(
        entry.split(maxsplit=1)[::-1]
        for entry in (BUNDLE / "checksums.sha256").read_text().splitlines()
    )
    if hashlib.sha256(records.read_bytes()).hexdigest() != hashes["raw/runs.jsonl"]:
        raise ValueError("E17 raw-record seal mismatch")
    summary = json.loads((BUNDLE / "derived/summary.json").read_text())
    revision = summary["provenance"]["system_under_test_sha"]
    source = subprocess.check_output(
        ["git", "show", revision + ":evaluation/glhs_r4_eval/run_e17.py"], cwd=ROOT, text=True
    )
    inputs = {}
    for stmt in ast.walk(ast.parse(source)):
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
        ):
            if stmt.targets[0].id in {"res_c3_good", "res_c4_good"} and isinstance(
                stmt.value, ast.Call
            ):
                keywords = [arg.arg for arg in stmt.value.keywords]
                inputs[stmt.targets[0].id] = "observed_model_visible_projection" in keywords
    if set(inputs) != {"res_c3_good", "res_c4_good"}:
        raise ValueError("missing clean-control call")
    by_case = defaultdict(dict)
    for line in records.read_text().splitlines():
        row = json.loads(line)
        variants = by_case[row["scenario_id"]]
        if row["variant"] in variants:
            raise ValueError("duplicate case variant")
        variants[row["variant"]] = row
    if any(set(v) != {"P_good", "P_substituted"} for v in by_case.values()):
        raise ValueError("unpaired E17 case")
    controls = [variants["P_good"] for variants in by_case.values()]
    all_admitted = {
        arm: sum(row[arm + "_admitted"] for row in controls) for arm in ("c0", "c1", "c3", "c4")
    }
    return dict(
        sealed_revision=revision,
        paired_cases=len(controls),
        clean_admitted=all_admitted,
        clean_supplied_observed_projection=inputs,
        raw_control_rows_record_c3_reason=any("c3_reasons" in row for row in controls),
    )


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
