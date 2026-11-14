"""Structural tests for the ACNS novelty contract (task ACNS-scope).

Purpose
-------
Validate that ``research/venue2027/acns/novelty_contract.md`` is a structurally
complete scope register: SoK declaration (no new mechanism), claim-to-prior-work
falsification matrix with real registry prior-work ids, exactly three RQs each
carrying endpoint / baseline / oracle / test / falsification, refusal of the
frozen E15-E22 archive, explicit differentiation from IFIP SEC and DIMVA, and a
GO / NO-GO decision.

Allowed input: the contract markdown file, read-only.
Failure semantics: AssertionError with a stable message per violated section.
Version: clara.venue2027.acns.test-novelty-contract.v1
"""

from __future__ import annotations

import pathlib
import re

CONTRACT_PATH = pathlib.Path(__file__).resolve().parents[1] / "novelty_contract.md"

RQ_SECTIONS = ("RQ1", "RQ2", "RQ3")

REQUIRED_RQ_FIELDS = (
    "primary endpoint",
    "strongest competing baseline",
    "independent oracle",
    "statistical test",
    "falsification condition",
)

REQUIRED_PRIOR_WORK_IDS = (
    "rats9334",
    "agentdojo24",
    "toolemu24",
    "fhir5",
    "tauben25",
    "ct9162",
)

FORBIDDEN_ARCHIVE_ID = "E15"

SIBLING_STUDIES = ("IFIP SEC", "DIMVA")


def _contract_text() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_contract_exists_and_has_title_and_reader() -> None:
    text = _contract_text()
    assert CONTRACT_PATH.is_file(), "novelty_contract.md missing"
    assert "SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems" in text
    assert "Target reader" in text, "target reader section missing"


def test_declares_sok_and_not_a_new_mechanism() -> None:
    text = _contract_text()
    assert "Systematization of Knowledge" in text, "SoK class not declared"
    assert (
        "does NOT claim a new mechanism" in text
    ), "contract must explicitly disclaim a new mechanism"
    assert (
        "evidence-boundary taxonomy" in text and "coverage matrix" in text
    ), "SoK contribution must be named as taxonomy + coverage matrix"


def test_falsification_matrix_present_with_real_prior_work_ids() -> None:
    text = _contract_text()
    matrix_rows = re.findall(r"^\|\s*F\d+\s*\|", text, flags=re.MULTILINE)
    assert (
        len(matrix_rows) >= 5
    ), f"claim-to-prior-work falsification matrix too small: {len(matrix_rows)} rows"
    for pid in REQUIRED_PRIOR_WORK_IDS:
        assert pid in text, f"prior-work registry id {pid!r} absent from matrix"


def test_exactly_three_rqs_with_required_fields() -> None:
    text = _contract_text()
    rq_headers = re.findall(r"^###\s+(RQ\d)\s+[—-]", text, flags=re.MULTILINE)
    assert rq_headers == list(
        RQ_SECTIONS
    ), f"expected exactly RQ1/RQ2/RQ3 sections, got {rq_headers}"
    for rq in RQ_SECTIONS:
        section = re.search(rf"^###\s+{rq}\b.*?(?=^###\s|\Z)", text, flags=re.MULTILINE | re.DOTALL)
        assert section is not None, f"RQ section {rq} not found"
        section_text = section.group(0).lower()
        for field in REQUIRED_RQ_FIELDS:
            assert field in section_text, f"{rq}: missing {field!r}"


def test_blueprints_baselines_named_as_competing_explanations() -> None:
    text = _contract_text()
    for baseline in (
        "RFC 9334",
        "W3C PROV",
        "AgentDojo",
        "two independent human-coded",
    ):
        assert baseline in text, f"blueprint baseline {baseline!r} not used"


def test_refuses_frozen_e15_e22_archive() -> None:
    text = _contract_text()
    assert "refuses" in text.lower(), "explicit refusal language missing"
    assert "E15" in text and "E22" in text, "frozen E15-E22 archive not addressed"
    assert (
        "reuses_archive: []" in text or "reuses_archive" in text
    ), "shared overlap registry declaration not referenced"
    refusal_section = re.search(
        r"Refusal of frozen E15.E22 archive.*?(?=^##\s|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert refusal_section is not None, "archive refusal section missing"


def test_explicitly_differentiates_from_ifip_sec_and_dimva() -> None:
    text = _contract_text()
    for sibling, distinct_from in (
        ("IFIP SEC", "mechanism"),
        ("DIMVA", "detection"),
    ):
        assert sibling in text, f"{sibling} differentiation missing"
        idx = text.index(sibling)
        window = text[idx : idx + 2000]
        assert (
            distinct_from.lower() in window.lower()
        ), f"{sibling} must be distinguished as {distinct_from!r}"


def test_scope_paragraph_names_truly_distinct_contribution() -> None:
    text = _contract_text()
    assert "truly distinct" in text.lower(), "scope must name the truly distinct contribution"
    scope_section = re.search(r"^##\s+4\..*?(?=^##\s|\Z)", text, flags=re.MULTILINE | re.DOTALL)
    assert scope_section is not None, "one-paragraph scope section missing"
    assert "taxonomy" in scope_section.group(0).lower()


def test_decision_is_explicit_go_or_no_go() -> None:
    text = _contract_text()
    assert re.search(
        r"Decision:\s*(GO|NO-GO)", text
    ), "explicit 'Decision: GO' or 'Decision: NO-GO' required"


def test_no_invented_empirical_numbers() -> None:
    text = _contract_text()
    assert (
        "artifacts/venue2027/acns/<run_id>/manifest.json" in text
    ), "empirical values must be routed through the run manifest"
    kappa_claims = re.findall(r"[Kk]appa[^\n]*?(\d+\.\d+)", text)
    assert not kappa_claims, f"contract must not assert kappa values: {kappa_claims}"
