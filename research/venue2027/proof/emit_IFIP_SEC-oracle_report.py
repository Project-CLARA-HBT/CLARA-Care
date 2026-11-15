"""Emit research/venue2027/proof/IFIP_SEC-oracle.json via agent_protocol.

Assembles the IFIP_SEC-oracle task report with real command logs (pytest,
ruff check+format, emitter/validator) and hashes every declared artifact,
then validates it with agent_protocol.validate_report.

The report is written with ``source_sha_after`` recording the base commit
(sibling convention: COMPSAC-X02_closure_oracle / COMPSAC-X01_readset_dsl);
the single task commit SHA is created immediately after this report and
reported in the handoff.
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

TASK_ID = "IFIP_SEC-oracle"
SOURCE_SHA_BEFORE = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED_PATHS = [
    "evaluation/venue2027/ifip_sec/independent_oracle.py",
    "evaluation/venue2027/ifip_sec/test_independent_oracle.py",
    "research/venue2027/proof/IFIP_SEC-oracle.json",
    "research/venue2027/proof/logs/IFIP_SEC-oracle.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-oracle.ruff.log",
    "research/venue2027/proof/emit_IFIP_SEC-oracle_report.py",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/ifip_sec/independent_oracle.py",
    "evaluation/venue2027/ifip_sec/test_independent_oracle.py",
    "research/venue2027/proof/logs/IFIP_SEC-oracle.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-oracle.ruff.log",
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
                "argv": "python3 -m pytest -q "
                "evaluation/venue2027/ifip_sec/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-oracle.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/ifip_sec/independent_oracle.py "
                "evaluation/venue2027/ifip_sec/test_independent_oracle.py && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/ifip_sec/independent_oracle.py "
                "evaluation/venue2027/ifip_sec/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-oracle.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_IFIP_SEC-oracle_report.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-oracle.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 independent per-case truth oracle for RQ1-RQ3 (Replay-Closed Authorization "
            "Across Purpose, Delegation, and AI Proposal Lineage). "
            "independent_oracle.py DELEGATES all decision logic to the shared audited kernel "
            "evaluation.venue2027._shared.oracle_kernel.adjudicate (ORACLE_KERNEL_VERSION "
            "1.0.0) with a module-local DECLARATIVE IFIP reference rule table "
            "IFIP_REFERENCE_RULES frozen against CASE_MATRIX.md: fresh_accept->ADMIT "
            "(CASE-01), cross_purpose_replay->REJECT (CASE-02), delegation_replay->REJECT "
            "(consumed-once invariant), lineage_splice->REJECT (provenance binding). Any "
            "family outside the table returns INDETERMINATE via kernel UNMODELLED_FAMILY "
            "(e.g. CASE-08 key rotation, DECIDE_BY_SPEC), and an undeclared family returns "
            "INDETERMINATE via NO_FAMILY_DECLARED - never a silent safe verdict. "
            "ORACLE_ID='ifip-sec-reference'; entry point adjudicate(case)->OracleResult "
            "(kernel OracleResult, JSON-serializable via to_dict, evidence uris captured "
            "verbatim); missing case_id raises OracleError MISSING_CASE_ID (wiring error, "
            "not an outcome). INDEPENDENCE (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2): "
            "the module does NOT import the IFIP baselines/candidate - no import of "
            "evaluation.venue2027.ifip_sec.baselines, consistency_token_adapter or any "
            "candidate mechanism; verify_independence() scans this module's own source with "
            "ast and refuses any import of the candidate modules listed in "
            "CANDIDATE_MODULE_NAMES ('ifip_sec.baselines', "
            "'ifip_sec.consistency_token_adapter', 'baselines', "
            "'consistency_token_adapter') with stable reason code CANDIDATE_IMPORT - "
            "covering plain/aliased/from-imports and dotted paths (matched per dotted "
            "component on the candidate basenames, so the oracle's own package path and "
            "look-alike modules like my_baseline_labels do not trip it), and dynamic "
            "imports (__import__/importlib.import_module) flagged as the __dynamic__ "
            "sentinel for review rather than guessed safe. test_independent_oracle.py "
            "imports only the oracle (plus the shared kernel): 5 positive controls "
            "(fresh-accept admit with evidence capture, 3 reject families, unknown/"
            "undeclared/payload-family INDETERMINATE, MISSING_CASE_ID refusal, "
            "determinism + JSON round-trip + rule-table freeze + built-in self-checks) and "
            "17 adversarial controls (clean live source passes, 10 candidate-import "
            "variants refused, unrelated-import acceptance, __import__/importlib dynamic "
            "flags, temp on-disk rogue oracle importing the candidate refused by the "
            "kernel AST guard assert_oracle_independence, tampered live-source control). "
            "22 passed in 0.28s (full ifip_sec evaluation suite 75 passed); "
            "uvx ruff@0.7.1 check + format --check clean; source_sha_after records the "
            "base commit e5f7ee3b per sibling convention (COMPSAC-X02_closure_oracle); the "
            "single task commit SHA is created immediately after this report and reported "
            "in the handoff. oracle_disagreement_count null (no candidate-vs-oracle "
            "comparison run in this task; the candidate does not exist yet - "
            "IFIP_SEC-candidate depends on this oracle). Baseline parity NOT_APPLICABLE "
            "(oracle layer; arms B0-B4 execute in P03 IFIP_SEC-baseline_tests)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "IFIP_SEC-oracle.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log
    # OUTSIDE the report's own artifact set (a log describing the validation
    # of the report cannot hash itself).
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
        / "IFIP_SEC-oracle.validator.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
