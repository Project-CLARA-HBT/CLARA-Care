"""Emit research/venue2027/proof/ACNS-X04_claim_extractor.json via agent_protocol.build_report.

Records source_sha_before/after = base commit 687a6f56 (sibling convention: the
report's SHAs precede the single task commit that carries the report, as in
ACNS-X01_review_protocol / ACNS-X02_citation_corpus). Validates the assembled
report with validate_report.
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "research" / "venue2027" / "_shared" / "tools"))

import agent_protocol  # noqa: E402

TASK_ID = "ACNS-X04_claim_extractor"
BASE_SHA = "687a6f56def769fc930e0ee94b00476eecc1c69b"

REPORT_PATH = REPO / "research" / "venue2027" / "proof" / "ACNS-X04_claim_extractor.json"
ARTIFACTS = (
    "evaluation/venue2027/acns/claim_extractor.py",
    "research/venue2027/acns/tests/test_claim_extractor.py",
)
COMMANDS = (
    {
        "argv": "python3 -m pytest -q research/venue2027/acns/tests/test_claim_extractor.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X04_claim_extractor.pytest.log",
    },
    {
        "argv": (
            "python3 -m pytest -q research/venue2027/_shared/tests/ "
            "research/venue2027/acns/tests/ evaluation/venue2027/_shared/ "
            "evaluation/venue2027/acns/"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X04_claim_extractor.suite.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/acns/claim_extractor.py "
            "research/venue2027/acns/tests/test_claim_extractor.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X04_claim_extractor.ruff.log",
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
            "research/venue2027/proof/ACNS-X04_claim_extractor.json",
            "research/venue2027/proof/logs/ACNS-X04_claim_extractor.pytest.log",
            "research/venue2027/proof/logs/ACNS-X04_claim_extractor.suite.log",
            "research/venue2027/proof/logs/ACNS-X04_claim_extractor.ruff.log",
        ],
        commands=list(COMMANDS),
        artifact_paths=list(ARTIFACTS),
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 ACNS SoK claim extractor (RQ1, deterministic, NO LLM): "
            "evaluation/venue2027/acns/claim_extractor.py implements the task "
            "contract extract_claims(record) -> list[Claim] (the manifest's "
            "extract(paper)->list[Claim] with the orchestrator-directed name) "
            "plus the fail-closed gate assert_no_unsupported_claim(claims). "
            "Claim carries the five contract fields (claim_kind existence/"
            "boundary/performance per protocol section 6 C7, subject, "
            "evidence_boundary, asserted_guarantee, scope universal/existential/"
            "unscoped) plus traceability: text pointer (char span), verbatim "
            "quote (C1), evidence_class (six-class lattice), gap_codes (G1-G9 "
            "register restated from threat_model.md section 6), ambiguity flag "
            "(C8) and confidence. Each claim maps to the evidence-boundary "
            "taxonomy of sok_review_protocol.md section 8.2 / rater_manual.md "
            "section 3: BND_VALID (claimed level <= demonstrated ceiling), "
            "BND_OVERREAD with the specific gap (G1 transport-ack-as-processing, "
            "G2 receipt-as-execution, G3 execution-as-consumption, residual G7), "
            "BND_UNDERREAD (coverage insight), BND_INDETERMINATE (hedged/"
            "undecidable wording retained, never coerced, rater manual section 5 "
            "IND); evidence_boundary=None marks a guarantee with no disclosed "
            "evidence (G9 shape) for the fail-closed gate. Deterministic rules "
            "only: ordered sentence segmentation, caption (Figure N:) and "
            "ablation footnotes skipped (task negative vector), negated-proof "
            "sentences coded as boundary claims not positive ones (anchor "
            "C7-A2), performance sentences context-only, hedges -> INDETERMINATE"
            "/low-confidence, marketing-only records (>=2 promotional markers, "
            "no disclosed evidence artifact) yield no confident claim per the "
            "protocol's EXCL_NOT_PEER_REVIEWED channel; demonstrated level (C4) "
            "derives from the record-level D3 evidence inventory with the "
            "class-to-level ceiling and strongest-evidence priority (rater "
            "manual section 2 C2/C4). Fail-closed semantics with stable reason "
            "codes: MALFORMED_RECORD, EMPTY_TEXT, MALFORMED_CLAIM_LIST, "
            "MALFORMED_CLAIM, UNSUPPORTED_CLAIM_NO_EVIDENCE_BOUNDARY (raised by "
            "assert_no_unsupported_claim when a claim asserts a guarantee with "
            "no evidence boundary - never a silent pass). No LLM, no network, "
            "no clock, no randomness, no PHI/PII (synthetic-acns-2027-style "
            "inline fixtures only). Test driver research/venue2027/acns/tests/"
            "test_claim_extractor.py (11 tests, positive + adversarial): P1 "
            "receipt-scope claim BND_VALID/L2 deterministic, P2 receipt-as-"
            "execution BND_OVERREAD+G2, P3 negated-proof boundary claim, P4 "
            "determinism (byte-identical to_dict), P5 schema vocabularies + "
            "JSON-serializable, A1 unsupported claim refused by the gate (stable "
            "code) while supported claims pass, A2 marketing-only record yields "
            "no confident claim, A3 captions/ablations not claims, A4 malformed "
            "input fails closed with stable codes, A5 hedged wording retained "
            "INDETERMINATE (never coerced), A6 underread coverage insight. "
            "Focused: 11 passed. Regression suite (research shared+acns tests, "
            "evaluation shared+acns): 664 passed. uvx ruff@0.7.1 check clean on "
            "both files. source_sha_after records the base commit 687a6f56 per "
            "sibling convention (ACNS-X01_review_protocol, "
            "ACNS-X02_citation_corpus); the single task commit SHA is created "
            "immediately after this report and recorded in the commit body."
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
