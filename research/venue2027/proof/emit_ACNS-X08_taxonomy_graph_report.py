"""Emit the ACNS-X08_taxonomy_graph proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-X08_taxonomy_graph task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-X08_taxonomy_graph"
BASE_SHA = "01705809bd25101ffb3bd74ec74db769626f234b"

CHANGED = [
    "evaluation/venue2027/acns/taxonomy_graph.py",
    "evaluation/venue2027/acns/test_taxonomy_graph.py",
    "research/venue2027/proof/ACNS-X08_taxonomy_graph.json",
    "research/venue2027/proof/emit_ACNS-X08_taxonomy_graph_report.py",
    "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.pytest.log",
    "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.ruff.log",
    "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.suite.log",
    "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.validator.log",
]

ARTIFACTS = [
    "evaluation/venue2027/acns/taxonomy_graph.py",
    "evaluation/venue2027/acns/test_taxonomy_graph.py",
    "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.pytest.log",
    "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.ruff.log",
    "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.suite.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/test_taxonomy_graph.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/acns/taxonomy_graph.py "
            "evaluation/venue2027/acns/test_taxonomy_graph.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X08_taxonomy_graph.suite.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        unresolved=[],
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "ACNS-X08_taxonomy_graph (Phase P05, venue acns; SoK: Evidence Boundaries of "
            "Attestation in Tool-Using AI Systems, RQ2): delivers evaluation/venue2027/acns/"
            "taxonomy_graph.py implementing graph representation of the evidence taxonomy "
            "where edges are annotated with extra assumptions, counterexample IDs, and threat "
            "model failure families. Avoids directional implication without evidence: "
            "validate_evidence_path(graph, from_node, to_node) -> PathValidityResult verifies "
            "whether a path of valid evidence transitions exists; unsupported level jumps, "
            "unbridged transitions (e.g. bare transport ACK E03, receipt-to-execution E04, "
            "execution-to-committed E05, transport-to-inference E06, hash-only token E07), "
            "and reverse directional implications fail closed and report concrete counterexample "
            "IDs (dispatched-not-acknowledged, acknowledged-not-executed, executed-not-committed, "
            "assembled-not-sent, NC1_hash_only_token_miscalled_hardware_attestation, "
            "NC2_transport_ack_implies_inference), missing trust assumptions, and gap codes (G1, "
            "G2, G3, G7). Functions build_taxonomy_graph(yaml_path) -> TaxonomyGraph, "
            "validate_evidence_path, export_graph() -> dict, render_graph(evidence_types, edges) "
            "-> SVG string, and emit_taxonomy_graph(run_id) -> Path. Adversarial controls: "
            "cycles detected via DFS recursion stack and assert_acyclic(), unsupported jumps "
            "rejected with reason_code UNSUPPORTED_JUMP, invalid node IDs raise stable "
            "reason-coded TaxonomyGraphError(INVALID_NODE_ID), malformed taxonomy YAML raises "
            "TaxonomyGraphError(MALFORMED_TAXONOMY). Machine-readable JSON artifact emitted at "
            "artifacts/venue2027/acns/acns-x08-taxonomy-graph-1.0.0/taxonomy_graph.json. "
            "Tests: 12 passed in evaluation/venue2027/acns/test_taxonomy_graph.py (positive + "
            "adversarial); 174 passed across full evaluation/venue2027/acns/ regression. "
            "uvx ruff@0.7.1 check and format clean on touched files. source_sha_after = base SHA "
            "per established repo convention."
        ),
    )

    out = REPO / "research" / "venue2027" / "proof" / "ACNS-X08_taxonomy_graph.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    validation = ap.validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    val_log = (
        REPO / "research" / "venue2027" / "proof" / "logs" / "ACNS-X08_taxonomy_graph.validator.log"
    )
    val_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
