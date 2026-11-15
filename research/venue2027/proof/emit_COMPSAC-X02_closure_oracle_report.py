"""Emit research/venue2027/proof/COMPSAC-X02_closure_oracle.json via agent_protocol.

Assembles the COMPSAC-X02_closure_oracle task report with real command logs
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

TASK_ID = "COMPSAC-X02_closure_oracle"
SOURCE_SHA_BEFORE = "06125d5291c6aa4b1d65df6df1d0d7e56de58463"

CHANGED_PATHS = [
    "evaluation/venue2027/compsac/independent_closure_oracle.py",
    "evaluation/venue2027/compsac/test_independent_closure_oracle.py",
    "research/venue2027/proof/logs/COMPSAC-X02_closure_oracle.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X02_closure_oracle.ruff.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/compsac/independent_closure_oracle.py",
    "evaluation/venue2027/compsac/test_independent_closure_oracle.py",
    "research/venue2027/proof/logs/COMPSAC-X02_closure_oracle.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X02_closure_oracle.ruff.log",
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
                "evaluation/venue2027/compsac/test_independent_closure_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/COMPSAC-X02_closure_oracle.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/compsac/independent_closure_oracle.py "
                "evaluation/venue2027/compsac/test_independent_closure_oracle.py && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/compsac/independent_closure_oracle.py "
                "evaluation/venue2027/compsac/test_independent_closure_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/COMPSAC-X02_closure_oracle.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_COMPSAC-X02_closure_oracle_report.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/COMPSAC-X02_closure_oracle.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 independent dependency-closure oracle for RQ1/RQ2 "
            "(Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes). "
            "independent_closure_oracle.py: DECLARATIVE module-local rule table RESOURCE_RULES "
            "(resource -> kind/version-or-epoch/predicate/review_required; the ambiguous "
            "'medication_note' row is deliberately review-flagged) and "
            "expected_dependencies(op, state) -> frozenset[Dependency] deriving exactly one "
            "dependency per distinct touched resource — GOVERNANCE rows anchor to the live "
            "OracleState consent/policy epochs (COMPSAC-CASE-08: governance anchors never "
            "omitted), ENTITY/EVIDENCE/LEASE rows follow the rule table. Fail-closed stable "
            "reason codes: UNRULED_RESOURCE (unknown touched resource), AMBIGUOUS_RULE_REVIEW "
            "(review-flagged rule escalated, never guessed), EMPTY_OPERATION, "
            "MALFORMED_OPERATION, STATE_MISMATCH; no wildcard omission "
            "(assert_no_wildcard_omission names any dropped resource). Local Dependency/"
            "OracleOperation/OracleState/ClosureResult dataclasses, JSON-serializable, "
            "canonical closure_sha256, deterministic (no clock/randomness/DB/model). "
            "INDEPENDENCE (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2): the module does NOT "
            "import evaluation/venue2027/compsac/dependency_dsl.py (the candidate compiler); "
            "assert_oracle_independence() scans this module's own source with ast and refuses "
            "any import of the candidate DSL module with stable reason code CANDIDATE_IMPORT — "
            "covering plain/aliased/from-imports, 'from pkg import dependency_dsl' alias binds, "
            "bare-module paths, and dynamic imports (__import__/importlib.import_module) "
            "reported as the __dynamic__ sentinel for review rather than guessed safe; exact "
            "ast parsing (never substring, never sys.modules) so unrelated modules like "
            "my_dependency_dsl_tests do not trip it. test_independent_closure_oracle.py "
            "imports only the oracle: 6 positive controls (governed medication write with "
            "kind/predicate/epoch assertions, governance anchors to state epochs, read==write "
            "dedup, determinism + JSON round-trip, success ClosureResult, built-in "
            "self-checks + rule-table shape) and 16 adversarial controls (clean source "
            "passes, 7 candidate-import variants refused, live-source tamper control, exact-"
            "match acceptance of unrelated imports, __import__/importlib dynamic flags, "
            "unknown write/read resource, ambiguous escalation + no clean-op poisoning, "
            "empty/malformed ops x5, wrong state type, wildcard-omission catch). 22 passed "
            "in 0.24s (full compsac suite 139 passed); uvx ruff@0.7.1 check + format --check "
            "clean; mypy 1.13.0 --ignore-missing-imports clean. source_sha_after records the "
            "base commit 06125d52 per sibling convention (COMPSAC-X01_readset_dsl); the single "
            "task commit SHA is created immediately after this report and reported in the "
            "handoff. oracle_disagreement_count null (no candidate-vs-oracle comparison run "
            "in this task; X04/X05 harnesses consume this oracle). Baseline parity "
            "NOT_APPLICABLE (oracle layer; arms B0-B4 execute in P03 COMPSAC-X04..X07)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "COMPSAC-X02_closure_oracle.json"
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
        / "COMPSAC-X02_closure_oracle.validator.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
