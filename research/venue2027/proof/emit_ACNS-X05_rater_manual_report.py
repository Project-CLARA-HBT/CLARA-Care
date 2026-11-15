"""Emit the ACNS-X05_rater_manual proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-X05_rater_manual task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-X05_rater_manual"

BASE_SHA = "11a9219ce0a1d3d523400350abb959c0f56699f2"

CHANGED = [
    "research/venue2027/acns/design/rater_manual.md",
    "research/venue2027/acns/tests/test_rater_manual.py",
    "research/venue2027/proof/ACNS-X05_rater_manual.json",
    "research/venue2027/proof/emit_ACNS-X05_rater_manual_report.py",
    "research/venue2027/proof/logs/ACNS-X05_rater_manual.pytest.log",
    "research/venue2027/proof/logs/ACNS-X05_rater_manual.ruff.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/acns/tests/test_rater_manual.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X05_rater_manual.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/acns/ --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X05_rater_manual.ruff.log",
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
        artifact_paths=CHANGED[:2],
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "ACNS-X05_rater_manual (Phase P02, RQ3): pre-registered inter-rater coder "
            "manual for the SoK's evidence-boundary coding at "
            "research/venue2027/acns/design/rater_manual.md (manual_version 1.0.0, "
            "contract clara.venue2027.acns.rater-manual.v1). Defines each BND_* code "
            "from the frozen protocol rubric (BND_VALID, BND_OVERREAD, BND_UNDERREAD, "
            "BND_INDETERMINATE) with definition, derivation rule and constructed anchor "
            "examples; elaborates the C1-C8 dimensions fixed by "
            "sok_review_protocol.md section 6 (Claim extraction, Evidence class, "
            "Lattice level claimed, Lattice level demonstrated, Observer axis, Trust "
            "axis, Claim type, Ambiguity flag) with decision rules and anchors; gives "
            "the D1-D9 decision tree deriving boundary codes from C1 plus C2-C6 "
            "fields; INDETERMINATE rules IND1-IND7 (retained, never coerced; C8=AMB "
            "couples to undecidable fields; BND_INDETERMINATE is reserved for "
            "under-determined inputs, not a doubt escape hatch); stable reason codes "
            "(EXTRACT_NO_VERBATIM, EXTRACT_NO_LOCATOR, FIELD_UNDECIDABLE, "
            "BOUNDARY_REOPENED, CONFLICT_ADJUDICATION_REQUIRED, ADJ_UNAVAILABLE, "
            "MANUAL_AMENDMENT_POST_FREEZE); JSON-serializable coding record schema "
            "clara.venue2027.acns.coding-record.v1; and the inter-rater agreement "
            "protocol: two independent human coders under pseudonymous roles C1/C2 "
            "plus a third-coder adjudicator, blind allocation over the full claim set, "
            "20-source pilot revised during development only and frozen before main "
            "labels, sealed first-pass streams, kappa computed on the "
            "pre-adjudication stream with adjudicated labels reported separately, "
            "14-day adjudication window with ADJ_UNAVAILABLE retention, and all "
            "numeric thresholds delegated to rq_and_estimands.yaml/ACNS-rq_registry/"
            "ACNS-freeze. No kappa/agreement value, no rater identity and no run id "
            "is asserted anywhere: no coding run, pilot session or adjudication "
            "session has been executed; every observed statistic enters later via "
            "artifacts/venue2027/acns/<run_id>/manifest.json after ACNS-freeze. All "
            "anchor sentences are constructed teaching examples, not corpus "
            "quotations. Test driver research/venue2027/acns/tests/test_rater_manual."
            "py (stdlib-only besides pytest, 44 tests) machine-checks: manual exists "
            "and is version-stamped; all required sections; every protocol BND_* code "
            "documented with its own subsection, definition, derivation and >=2 "
            "anchors; all C1-C8 dimensions present with names matching the protocol, "
            "each with decision rules and an anchor; lattice levels L0-L4 and six "
            "evidence classes and observer positions consistent with the "
            "protocol/threat model; ordered decision tree deriving all four BND "
            "codes; INDETERMINATE section with >=5 numbered rules and no-coercion "
            "markers; required reason codes; coding-record fields; agreement-"
            "protocol markers; and negative controls - no fabricated kappa/agreement "
            "numbers (regex over kappa=0.xx style and percent patterns), no invented "
            "rater/reviewer names (pseudonymous role tokens only), no invented run "
            "ids, no placeholder text, plus execution-honesty statement. 44 passed; "
            "uvx ruff@0.7.1 check clean on research/venue2027/acns/. Deliverable path "
            "note: the task manifest names annotation_handbook.md; the orchestrator-"
            "directed path rater_manual.md delivers the same document and the manual "
            "records this mapping for downstream tasks (ACNS-X06 consumes it). "
            "baseline_parity=NOT_APPLICABLE (coding instrument, not a decision "
            "comparator; baseline arms B0-B3 enter via RQ3's executed coding sessions "
            "downstream). source_sha_after records the base commit 11a9219c per the "
            "established sibling convention; the single task commit SHA is created "
            "immediately after this report and recorded in the commit body. "
            "Downstream consumers: ACNS-X06_adjudication, ACNS-X07_witness_gallery, "
            "RQ1/RQ3 agreement statistics, ACNS-X10_sok_synthesis."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-X05_rater_manual.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
