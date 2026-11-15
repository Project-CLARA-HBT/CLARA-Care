"""Emit research/venue2027/proof/ACNS-X02_citation_corpus.json via agent_protocol.build_report.

Records source_sha_before/after = base commit e5f7ee3b (sibling convention: the
report's SHAs precede the single task commit that carries the report, as in
ACNS-X01_review_protocol). Validates the assembled report with validate_report.
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "research" / "venue2027" / "_shared" / "tools"))

import agent_protocol  # noqa: E402

TASK_ID = "ACNS-X02_citation_corpus"
BASE_SHA = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

REPORT_PATH = REPO / "research" / "venue2027" / "proof" / "ACNS-X02_citation_corpus.json"
ARTIFACTS = (
    "research/venue2027/acns/corpus/citation_corpus.json",
    "research/venue2027/acns/tests/test_citation_corpus.py",
)
COMMANDS = (
    {
        "argv": "python3 -m pytest -q research/venue2027/acns/tests/test_citation_corpus.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X02_citation_corpus.pytest.log",
    },
    {
        "argv": (
            "python3 -m pytest -q research/venue2027/_shared/tests/ "
            "research/venue2027/acns/tests/"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X02_citation_corpus.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/acns/tests/test_citation_corpus.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X02_citation_corpus.ruff.log",
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
            "research/venue2027/proof/ACNS-X02_citation_corpus.json",
            "research/venue2027/proof/logs/ACNS-X02_citation_corpus.pytest.log",
            "research/venue2027/proof/logs/ACNS-X02_citation_corpus.suite.log",
            "research/venue2027/proof/logs/ACNS-X02_citation_corpus.ruff.log",
        ],
        commands=list(COMMANDS),
        artifact_paths=list(ARTIFACTS),
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 ACNS SoK citation corpus (no live search executed): "
            "corpus/citation_corpus.json is a machine-readable pre-registered corpus "
            "ledger built ONLY from the real shared literature registry (24 ids); "
            "entries = the 8 registry-resolvable registered seeds of "
            "sok_review_protocol.md section 1 (rats9334 B0 attestation anchor, ct9162 "
            "transparency, macaroons14+zanzibar19 capability, agentdojo24+toolemu24+"
            "tauben25 agent-tool-use B2, fhir5 evidence-boundary B1 companion), each "
            "with role, screening_status=PLANNED, registered-seed provenance, "
            "retrieval_date=null, full_text_checked=false, and a corpus_sha256 over "
            "the canonical file bytes (placeholder-reset recompute verified by test). "
            "W3C PROV-DM is disclosed in seed_note as a registry gap (no record exists; "
            "no id invented). Honesty gates enforced by 18 stdlib tests: every id "
            "exists in the registry (no invented ids), metadata matches the registry "
            "verbatim, every doi_or_url is a real https/DOI identifier, screening "
            "statuses and roles are within declared vocabularies, counts block "
            "consistent with zero INCLUDED/EXCLUDED, no past-tense search/retrieval "
            "language anywhere, entries trace only to the registered seed channel "
            "(EXCL_NOT_TRACEABLE prevention), dedup rule checked with adversarial "
            "duplicate + invented-id + bad-URL controls, and the corpus is cross-"
            "checked against the protocol's 'NO LIVE SEARCH WAS EXECUTED' statement. "
            "The corpus asserts no corpus size and no observed per-stage count (all "
            "protocol ledger counts remain planned zeros); the executed retrieval "
            "ledger must come from the registered 5-database x 5-string search plus "
            "snowballing. Focused: 18 passed. Shared+acns suite: 351 passed. "
            "uvx ruff@0.7.1 check clean. source_sha_after records the base commit "
            "e5f7ee3b per sibling convention (ACNS-X01_review_protocol); the single "
            "task commit SHA is created immediately after this report and recorded "
            "in the commit body."
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
