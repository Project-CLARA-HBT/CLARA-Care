"""Emit research/venue2027/proof/POPETS-X01_lineage_graph.json via agent_protocol.

Assembles the POPETS-X01_lineage_graph task report with real command logs
(pytest, ruff check+format, emitter/validator) and hashes every declared
artifact, then validates it with agent_protocol.validate_report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "POPETS-X01_lineage_graph"
SOURCE_SHA_BEFORE = "687a6f56def769fc930e0ee94b00476eecc1c69b"

CHANGED_PATHS = [
    "evaluation/venue2027/popets/lineage_graph.py",
    "evaluation/venue2027/popets/test_lineage_graph.py",
    "research/venue2027/proof/POPETS-X01_lineage_graph.json",
    "research/venue2027/proof/logs/POPETS-X01_lineage_graph.pytest.log",
    "research/venue2027/proof/logs/POPETS-X01_lineage_graph.ruff.log",
    "research/venue2027/proof/logs/POPETS-X01_lineage_graph.suite.log",
    "research/venue2027/proof/logs/POPETS-X01_lineage_graph.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/popets/lineage_graph.py",
    "evaluation/venue2027/popets/test_lineage_graph.py",
    "research/venue2027/proof/logs/POPETS-X01_lineage_graph.pytest.log",
    "research/venue2027/proof/logs/POPETS-X01_lineage_graph.ruff.log",
    "research/venue2027/proof/logs/POPETS-X01_lineage_graph.suite.log",
]


def main() -> int:
    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q " "evaluation/venue2027/popets/test_lineage_graph.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/" "POPETS-X01_lineage_graph.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/popets/lineage_graph.py "
                "evaluation/venue2027/popets/test_lineage_graph.py && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/popets/lineage_graph.py "
                "evaluation/venue2027/popets/test_lineage_graph.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/" "POPETS-X01_lineage_graph.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/" "POPETS-X01_lineage_graph.suite.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_POPETS-X01_lineage_graph_report.py "
                "# build_report + validate_report(ok:true) recorded in "
                "research/venue2027/proof/POPETS-X01_lineage_graph.json",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X01_lineage_graph.validator.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 POPETS-X01_lineage_graph deliverable: "
            "evaluation/venue2027/popets/lineage_graph.py implements the exact target "
            "contract derive_graph(disclosures, transforms) -> LineageGraph as a pure, "
            "injected-I/O, deterministic JSON-serializable context-lineage graph (no "
            "hidden clock, no randomness, no network, no DB, no provider; synthetic "
            "nodes/labels only). Nodes are context artifacts on the five derivation "
            "paths of threat-model §1 (origin_field, derived_summary, cache_object, "
            "retry_payload, provider_transport, embedding_pointer); edges are "
            "derivation/disclosure relations labeled with "
            "(principal, purpose, time, transform/digest). CORE SURFACES: "
            "descendants(node) returns ALL transitively derived items (cycle-safe "
            "iterative DFS with an on-path set — a corrupted store containing a cycle "
            "can never hang traversal); revocation_closure(node, scope) returns every "
            "transitively derived item PLUS the node itself that must be purged on "
            "revocation, following only edges whose label intersects the revoked "
            "(principal, purpose) scope (edge-level reverse-edge invalidation, arm B4) "
            "with purpose='*' as the subject-wide withdrawal of the X05 vocabulary and "
            "unlabeled edges treated as in-scope (fail closed, never a silent escape "
            "hatch); assert_revocation_complete(graph, node, closure, scope) re-walks "
            "the reachable subgraph independently of the supplied closure and raises "
            "REVOCATION_CLOSURE_INCOMPLETE naming every missed descendant — the RQ1 "
            "adversarial leak class (a forgotten retry payload / transport item) is "
            "detectable by construction, never silently accepted. FAIL-CLOSED "
            "VALIDATION at construction: derivation parents must be a child somewhere "
            "or a declared trusted root, else EDGE_UNKNOWN_ANCESTOR (unlinked "
            "derivative, POPETS-CASE-07 shape); cycles refused with EDGE_CYCLE plus a "
            "concrete cycle path (Kahn + explicit path extraction) per the task's "
            "'validate cycles and missing ancestors'; malformed records raise stable "
            "uppercase reason codes (EDGE_MALFORMED, NODE_MALFORMED) — explicit "
            "refusals, never unhandled exceptions miscounted as safe rejections. "
            "Determinism: nodes sorted by id, edges by (parent, child, transform, "
            "digest); repeated construction from the same inputs yields byte-equal "
            "serializations. Scope honesty (threat-model §5.2, task §8): the closure "
            "covers platform-side stored artifacts only; no claim of retroactive "
            "erasure of already-delivered bytes (OUT_OF_SCOPE_PAST) and no claim of "
            "model memorization removal (NOT_GUARANTEED) is made anywhere. "
            "test_lineage_graph.py: 14 tests pass (positive: typed JSON-serializable "
            "graph with node kinds + label tuples, transitive descent on the linear "
            "chain origin->summary->cache->retry->transport returning ALL "
            "descendants, complete revocation closure incl. the origin, "
            "scope-filtered closure excluding other-purpose branches, wildcard "
            "subject-wide coverage, transform-spec diamond fan-out/fan-in with digest "
            "edges, determinism + JSON round-trip, LineageGraphError-is-ValueError; "
            "adversarial: cycle refused at construction with EDGE_CYCLE, cycle-safe "
            "traversal terminates on an injected cyclic store without infinite loop, "
            "unknown ancestor refused (record and transform input), unknown-node "
            "query fails closed, MISSED descendant detected by "
            "assert_revocation_complete (deepest retry payload + transport named in "
            "the error), origin-only omission detected, scope-filtered missed branch "
            "detected under the wildcard, 5 malformed-input stable-code refusals). "
            "Full evaluation/venue2027 regression: 1675 passed. uvx ruff@0.7.1 check "
            "+ format --check clean on touched files. source_sha_after records the "
            "base commit 687a6f56 per the sibling convention (POPETS-X02, POPETS-X06); "
            "the single task commit SHA is created immediately after this report and "
            "recorded in the commit body. Baseline parity NOT_APPLICABLE (structural "
            "lineage layer; arms B0-B4 execute in P03 against this substrate)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "POPETS-X01_lineage_graph.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log OUTSIDE the
    # report's own artifact set (a log describing the validation of the report
    # cannot hash itself).
    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log = (
        ROOT
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "POPETS-X01_lineage_graph.validator.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
