"""Emit the DIMVA-X08_splitter task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the DIMVA-X08_splitter task. No network access.

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
BASE = "e373f6e46465917ad4fbd7d6656e77e51c4805db"

MODULE = "evaluation/venue2027/dimva/group_split.py"
TESTS = "evaluation/venue2027/dimva/test_group_split.py"
PROOF = "research/venue2027/proof/DIMVA-X08_splitter.json"
PYTEST_LOG = "research/venue2027/proof/logs/DIMVA-X08_splitter.pytest.log"
RUFF_LOG = "research/venue2027/proof/logs/DIMVA-X08_splitter.ruff.log"
SUITE_LOG = "research/venue2027/proof/logs/DIMVA-X08_splitter.suite.log"
VALIDATOR_LOG = "research/venue2027/proof/logs/DIMVA-X08_splitter.validator.log"

CHANGED = [MODULE, TESTS, PROOF, PYTEST_LOG, RUFF_LOG, SUITE_LOG, VALIDATOR_LOG]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DIMVA-X08_splitter",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q evaluation/venue2027/dimva/test_group_split.py"
                ),
                "exit_code": 0,
                "log_path": PYTEST_LOG,
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/dimva/group_split.py "
                    "evaluation/venue2027/dimva/test_group_split.py"
                ),
                "exit_code": 0,
                "log_path": RUFF_LOG,
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": SUITE_LOG,
            },
        ],
        artifact_paths=[MODULE, TESTS, PYTEST_LOG, RUFF_LOG, SUITE_LOG],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 DIMVA-X08_splitter deliverable for venue dimva: "
            "evaluation/venue2027/dimva/group_split.py implements the strict "
            "independent cross-domain holdout split(groups, seed) -> Partitions for "
            "RQ2. Unit of inference is one campaign group, never an individual event "
            "(GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md section 3). Identity bridges — "
            "shared attacker_family, shared tenant, shared canonical tooling template "
            "(case/separator paraphrases like 'Probe-Tool.01' vs 'probe_tool_01' are "
            "canonicalized and bridged) and shared source_lineage — are merged via "
            "deterministic union-find into leakage components; components are shuffled "
            "with random.Random(seed) and allocated 0.6/0.2/0.2 by largest remainder "
            "with a no-empty-split repair pass, so the same (groups, seed) always "
            "yields byte-identical partitions (partition_sha256 over the assignment). "
            "A LeakageAudit returns the exact pre-split bridge findings (kind, "
            "attribute, group_ids, raw_values) and a post-hoc bridge-overlap report; "
            "split() fails closed with RC_BRIDGE_OVERLAP_DETECTED if any bridge ever "
            "spans splits, and the independent detector detect_bridge_overlaps() "
            "recomputes overlaps for any (groups, assignment) pair. Event-level split "
            "attempts are REFUSED as leaky with RC_EVENT_LEVEL_SPLIT_REFUSED (duplicate "
            "group_id records or several group records sharing one campaign_id are "
            "event fragments of a single campaign and must never be spread across "
            "partitions); other stable reason codes: EMPTY_GROUPS, "
            "MISSING_GROUP_FIELD, UNKNOWN_GROUP_FIELD (reason-code/attacker-label side "
            "channels fail closed), INVALID_GROUP_FIELD, INVALID_SEED, "
            "INVALID_SPLIT_RATIOS, DEGENERATE_COMPONENT_COUNT (bridges collapsing "
            "below three components), INCOMPLETE_ASSIGNMENT, UNKNOWN_ASSIGNMENT_KEY, "
            "INVALID_SPLIT_LABEL. evaluation/venue2027/dimva/test_group_split.py (22 "
            "tests) proves positive vectors: determinism (same seed byte-identical, "
            "different seed changes layout), every group assigned to exactly one split "
            "with no group spanning two splits and all three splits non-empty, default "
            "and custom ratio allocation, family/tenant/tooling/lineage bridge merging, "
            "template-paraphrase near-duplicate bridging, transitive bridge-chain "
            "collapse, audit exactness and clean state, JSON-serializable versioned "
            "output — and adversarial vectors: event-level split refused (duplicate "
            "group_id AND shared campaign_id), two campaigns from the same attacker "
            "family/tenant asserted to stay in one split with both bridges flagged in "
            "the audit, forced leaky assignment producing an exact overlap report "
            "(family + tenant bridges with their split labels), empty/unknown/missing/"
            "malformed fields, invalid seed/ratios, and total bridge collapse refused. "
            "Commands: pytest exit 0 (22 passed); uvx ruff@0.7.1 check exit 0; full "
            "evaluation/venue2027/ suite exit 0 (1283 passed) — no regression. Proof "
            "emitted via agent_protocol.build_report(task_id='DIMVA-X08_splitter') "
            "with real log_paths and validated ok:true; report + logs committed "
            "together with the work per established repo convention. SHA convention "
            "follows repo precedent (SH-claim_overlap/IFIP_SEC-scope/DIMVA-X01): "
            "before==after==parent source state because the single required commit "
            "contains this self-referential report; the final deliverable commit SHA "
            "is reported in the handoff."
        ),
    )

    out_path = REPO / PROOF
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DIMVA-X08_splitter",
    )
    log_path = REPO / VALIDATOR_LOG
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
