"""Emit research/venue2027/proof/ACNS-X01_review_protocol.json via agent_protocol.build_report.

Records source_sha_before/after = base commit 9b6be889 (sibling convention: the
report's SHAs precede the single task commit that carries the report, as in
ACNS-scope/ACNS-prior). Validates the assembled report with validate_report.
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "research" / "venue2027" / "_shared" / "tools"))

import agent_protocol  # noqa: E402

TASK_ID = "ACNS-X01_review_protocol"
BASE_SHA = "9b6be889db89c2228c6ea1ac599f0000d03c63a4"

REPORT_PATH = REPO / "research" / "venue2027" / "proof" / "ACNS-X01_review_protocol.json"
ARTIFACTS = (
    "research/venue2027/acns/design/sok_review_protocol.md",
    "research/venue2027/acns/tests/test_review_protocol.py",
)
COMMANDS = (
    {
        "argv": ("python3 -m pytest -q research/venue2027/acns/tests/test_review_protocol.py"),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X01_review_protocol.pytest.log",
    },
    {
        "argv": (
            "python3 -m pytest -q research/venue2027/_shared/tests/ "
            "research/venue2027/acns/tests/"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X01_review_protocol.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/acns/tests/test_review_protocol.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X01_review_protocol.ruff.log",
    },
)


def main() -> int:
    report = agent_protocol.build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=[
            *ARTIFACTS,
            "research/venue2027/proof/ACNS-X01_review_protocol.json",
            "research/venue2027/proof/logs/ACNS-X01_review_protocol.pytest.log",
            "research/venue2027/proof/logs/ACNS-X01_review_protocol.suite.log",
            "research/venue2027/proof/logs/ACNS-X01_review_protocol.ruff.log",
        ],
        commands=list(COMMANDS),
        artifact_paths=list(ARTIFACTS),
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P01 ACNS SoK review-selection protocol (no live search executed): "
            "sok_review_protocol.md pre-registers population/unit (2019-01-01..2026-12-31 "
            "window, cutoff 2026-12-31), 5 inclusion criteria (I1 peer-reviewed "
            "attestation incl. SDO standards, I2 window, I3 provenance topic, I4 agent "
            "tool-use/receipt claims, I5 retrievable full text with retrieval date), 8 "
            "exclusion reason codes (marketing/white papers/blogs/preprints excluded via "
            "EXCL_NOT_PEER_REVIEWED), 5 databases (ACM DL, IEEE Xplore, Scopus, DBLP, "
            "USENIX) with 5 frozen search strings S1-S5, backward/forward snowballing "
            "with saturation rule, S0-S6 screening-stage ledger with per-stage counts "
            "ALL ZERO and labeled 'planned, not executed' (no invented counts; the doc "
            "states NO LIVE SEARCH WAS EXECUTED), C1-C8 coding scheme, third-coder "
            "conflict adjudication within 14 days with conservative-inclusion rule and "
            "append-only adjudication ledger, RB1-RB5 risk-of-bias + BND_* "
            "evidence-boundary rubric with UNKNOWN retained, own-paper anti-bias rule "
            "(CLARA papers may not dominate: hard cap 3 records + <=5% of corpus, "
            "with-and-without sensitivity reporting, no sole-CLARA anchor for any "
            "evidence class), convenience-only sampling prohibited via registered "
            "channel traceability (EXCL_NOT_TRACEABLE), and the E15-E22/IFIP/DIMVA "
            "cross-study firewall. Tests: 30 structural + adversarial checks pass "
            "(required sections, >=2 databases, explicit cutoff date, screening ledger "
            "with counts, coding+conflict rules, own-paper prohibition, no "
            "TBD/TODO/FIXME placeholders, no fabricated empirics). Suite: 259 passed "
            "(shared + acns). uvx ruff@0.7.1 check clean. source_sha_after records the "
            "base commit 9b6be889 per sibling convention (ACNS-scope/ACNS-prior); the "
            "single task commit SHA is created immediately after this report and "
            "recorded in the commit body."
        ),
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = agent_protocol.validate_report(
        report,
        repo=REPO,
        expected_task_id=TASK_ID,
        verify_artifacts=True,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
