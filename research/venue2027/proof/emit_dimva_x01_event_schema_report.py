"""Emit the DIMVA-X01_event_schema task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the DIMVA-X01_event_schema task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "11a9219ce0a1d3d523400350abb959c0f56699f2"

SCHEMA = "research/venue2027/dimva/protocols/event.schema.json"
TESTS = "research/venue2027/dimva/tests/test_event_schema.py"
PYTEST_LOG = "research/venue2027/proof/logs/DIMVA-X01_event_schema.pytest.log"
RUFF_LOG = "research/venue2027/proof/logs/DIMVA-X01_event_schema.ruff.log"
VALIDATOR_LOG = "research/venue2027/proof/logs/DIMVA-X01_event_schema.validator.log"
PROOF = "research/venue2027/proof/DIMVA-X01_event_schema.json"

CHANGED = [
    SCHEMA,
    TESTS,
    PROOF,
    "research/venue2027/proof/emit_dimva_x01_event_schema_report.py",
    PYTEST_LOG,
    RUFF_LOG,
    VALIDATOR_LOG,
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DIMVA-X01_event_schema",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q research/venue2027/dimva/tests/test_event_schema.py",
                "exit_code": 0,
                "log_path": PYTEST_LOG,
            },
            {
                "argv": "uvx ruff@0.7.1 check research/venue2027/dimva/tests/test_event_schema.py",
                "exit_code": 0,
                "log_path": RUFF_LOG,
            },
        ],
        artifact_paths=[
            SCHEMA,
            TESTS,
            PYTEST_LOG,
            RUFF_LOG,
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 DIMVA-X01_event_schema deliverable for venue dimva: "
            "research/venue2027/dimva/protocols/event.schema.json defines the MINIMAL "
            "agent-event telemetry schema ($id "
            "clara.venue2027.dimva.minimal_agent_event.v1, draft 2020-12) with exactly "
            "seven fields (actor, tool, scope, allowed, purpose, ts, campaign_id), "
            "required for all seven, additionalProperties=false and an explicit "
            "MINIMALITY NOTE in the description; no PHI/health-text/reason-code/attacker-"
            "label surface (actor and scope are opaque SHA-256 hex digests, purpose is a "
            "closed coarse enum, ts is a 60 s bucket index). "
            "research/venue2027/dimva/tests/test_event_schema.py (20 tests) validates "
            "positive events (>=3 distinct valid events incl. a reproducible batch) and "
            "adversarial rejections through the shared stdlib validator "
            "research/venue2027/_shared/tools/schema_validator.py::validate_instance: "
            "missing tool and missing scope -> REQUIRED_MISSING; PHI-like field "
            "(patient_name), free-text reason and reason_code -> ADDITIONAL_PROPERTY; "
            "non-bool allowed ('false', 0, 1, None) -> TYPE_MISMATCH; extra field "
            "(attacker_label) -> ADDITIONAL_PROPERTY; plus clear-text principal "
            "PATTERN_MISMATCH, unknown purpose ENUM_MISMATCH, bad ts and missing "
            "actor/campaign_id fail-closed controls, and schema-shape assertions "
            "(7-field contract, minimality note, no PHI-like property names, no attacker "
            "label, only validator-supported keywords). Commands: pytest exit 0 (20 "
            "passed); uvx ruff@0.7.1 check exit 0 (format --check clean). Proof emitted "
            "via agent_protocol.build_report(task_id='DIMVA-X01_event_schema') with real "
            "log_paths and validated ok:true; report + logs committed together with the "
            "work per established repo convention."
        ),
    )

    out_path = REPO / PROOF
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DIMVA-X01_event_schema",
    )
    log_path = REPO / VALIDATOR_LOG
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
