"""Exercise the v1 verifier using offline synthetic harness runs and tampered copies."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from evaluation.venue2027._shared.harness import Campaign, execute
from scripts.research.venue2027.freeze_protocol import FreezeConfig, freeze
from scripts.research.venue2027.verify_release import render_figure, verify


def put(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(root):
    files = ["freeze.json", "plan.json", "raw.jsonl", "analysis.json", "claims.csv", "counts.svg"]
    manifest = {
        "schema_version": "harness-release.v1",
        "freeze": "freeze.json",
        "plan": "plan.json",
        "raw": "raw.jsonl",
        "analysis": "analysis.json",
        "figure": "counts.svg",
        "ledger": "claims.csv",
        "sha256": {name: digest(root / name) for name in files},
    }
    put(root / "manifest.json", manifest)
    return digest(root / "manifest.json")


def build_example(root, source_sha):
    """Run an engineering fixture. Synthetic outcomes exercise accounting categories."""
    campaign = Campaign(
        "release-dev", ("unit-1", "unit-2"), ("local", "unavailable"), (8, 8), source_sha
    )
    claims = [
        {"claim_id": "local-completions", "arm_id": "local", "metric": "completed"},
        {"claim_id": "unavailable-external", "arm_id": "unavailable", "metric": "not_run_external"},
    ]
    put(
        root / "plan.json",
        {"campaign": asdict(campaign), "analysis_id": "harness-counts.v1", "claims": claims},
    )
    stamp = lambda: datetime.now(UTC).isoformat()  # noqa: E731
    frozen = freeze(FreezeConfig(campaign.campaign_id, "development", root, ["plan.json"], stamp))
    put(root / "freeze.json", frozen.to_dict())
    arms = {
        "local": lambda case, _: "REJECT" if case["case_id"] == "unit-1" else "TIMEOUT",
        "unavailable": lambda *_: "NOT_RUN_EXTERNAL",
    }
    bundle = execute(campaign, arms, lambda *_: {"decision": "INDETERMINATE"})
    (root / "raw.jsonl").write_text(bundle.to_jsonl(), encoding="utf-8")
    shared = dict(
        planned=2,
        recorded=2,
        attempted=0,
        completed=0,
        error=0,
        missing=0,
        admit=0,
        reject=0,
        timeout=0,
        execution_error=0,
        invalid_result=0,
        indeterminate=0,
        not_run_external=0,
    )
    counts = {
        "local": dict(shared, attempted=2, completed=1, error=1, reject=1, timeout=1),
        "unavailable": dict(shared, not_run_external=2),
    }
    put(root / "analysis.json", counts)
    (root / "counts.svg").write_bytes(render_figure(counts))
    with (root / "claims.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["claim_id", "arm_id", "metric", "value"])
        writer.writeheader()
        for claim in claims:
            writer.writerow({**claim, "value": counts[claim["arm_id"]][claim["metric"]]})
    return seal(root)


@pytest.fixture
def release(tmp_path):
    pin = build_example(tmp_path, "a" * 40)
    return tmp_path, pin


def test_offline_replay_counts_and_is_repeatable(release):
    root, pin = release
    result = verify(root / "manifest.json", pin)
    assert result.ok, result
    assert result == verify(root / "manifest.json", pin)
    assert result.denominators["local"]["error"] == 1
    assert result.denominators["unavailable"]["attempted"] == 0
    assert result.denominators["unavailable"]["not_run_external"] == 2
    assert result.claims_verified == 2


@pytest.mark.parametrize(
    "filename", ["claims.csv", "counts.svg", "analysis.json", "plan.json", "raw.jsonl"]
)
def test_changed_file_rejected_by_original_pin(release, filename):
    root, pin = release
    path = root / filename
    path.write_bytes(path.read_bytes() + b" ")
    assert verify(root / "manifest.json", pin).reason_code == "CHECKSUM_MISMATCH"


@pytest.mark.parametrize(
    "mutation, code",
    [
        ("deleted", "DENOMINATOR_MISMATCH"),
        ("duplicate", "PAIR_INVALID"),
        ("source", "PAIR_INVALID"),
        ("falsified", "PAIR_INVALID"),
        ("retroactive", "FREEZE_CHRONOLOGY"),
        ("forged_summary", "ANALYSIS_MISMATCH"),
        ("hidden_claim", "LEDGER_MISMATCH"),
        ("wrong_claim", "LEDGER_MISMATCH"),
        ("figure", "FIGURE_MISMATCH"),
        ("plan", "FREEZE_DRIFT"),
        ("bad_total", "DENOMINATOR_MISMATCH"),
    ],
)
def test_resealed_copy_still_requires_valid_replay(release, mutation, code):
    root, _ = release
    path = root / "raw.jsonl"
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    if mutation == "deleted":
        lines.pop(0)
    elif mutation == "duplicate":
        lines[0] = lines[1]
    elif mutation == "source":
        lines[0]["source_commit"] = "b" * 40
    elif mutation == "falsified":
        lines[0]["outcome"]["observed_outcome"] = "ADMIT"
    elif mutation == "retroactive":
        lines[0]["recorded_at"] = 0
    elif mutation == "bad_total":
        lines[-1]["missing_pairs"] = 1
    elif mutation == "forged_summary":
        counts = json.loads((root / "analysis.json").read_text())
        counts["local"]["error"] = True
        put(root / "analysis.json", counts)
    elif mutation == "plan":
        with (root / "plan.json").open("a") as f:
            f.write(" ")
    elif mutation in {"hidden_claim", "wrong_claim"}:
        ledger = root / "claims.csv"
        rows = ledger.read_text().splitlines()
        if mutation == "hidden_claim":
            rows.pop()
        else:
            rows[-1] = rows[-1][:-1] + "0"
        ledger.write_text("\n".join(rows) + "\n")
    else:
        (root / "counts.svg").write_text("<svg/>")
    path.write_text("".join(json.dumps(row) + "\n" for row in lines))
    result = verify(root / "manifest.json", seal(root))
    if mutation == "deleted":
        assert result.denominators["local"]["missing"] == 1
    assert result.reason_code == code
    assert not result.ok and result.claims_verified == 0


def test_requires_manifest_pin_and_confines_paths(release):
    root, _ = release
    path = root / "manifest.json"
    assert verify(path, "0" * 64).reason_code == "MANIFEST_DIGEST_MISMATCH"
    data = json.loads(path.read_text())
    data["raw"] = "../raw.jsonl"
    data["sha256"]["../raw.jsonl"] = data["sha256"].pop("raw.jsonl")
    put(path, data)
    assert verify(path, digest(path)).reason_code == "PATH_INVALID"
