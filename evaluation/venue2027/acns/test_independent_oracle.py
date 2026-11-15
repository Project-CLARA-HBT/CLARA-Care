"""Tests for ACNS-oracle — independent evidence-boundary truth oracle (SoK).

Positive controls prove the oracle delegates to the shared kernel and returns
the pre-registered evidence-boundary matrix (``bound_evidence`` -> ADMIT,
``attestation_downgrade`` / ``unbound_claim`` / ``replayed_receipt`` ->
REJECT) deterministically and JSON-serializably, with the SoK verdict content
carried on every verdict (granted lattice level, refused claim, pre-registered
gap code G1-G9, boundary condition).

SoK-verdict-shape controls prove the oracle expresses an *evidence-boundary
verdict* — which claim the frozen evidence supports and where the claimed
implication breaks — and NOT a mechanism outcome: no "the tool ran" /
"pipeline succeeded" outcome field exists anywhere in the verdict vocabulary,
and adversarial witnesses are labelled by the boundary their evidence breaks
(gap codes), never by whether a mechanism executed.

Adversarial controls prove independence and fail-closed semantics:

- ``verify_independence`` accepts the clean oracle source but refuses any
  source variant importing the candidate baseline module
  (``evaluation.venue2027.acns.baselines`` / any ``baselines`` module) with
  ``CANDIDATE_IMPORT`` — plain import, from-import, aliased, dotted, relative
  and injected-tamper forms — and flags unresolvable dynamic imports.
- Candidate-supplied decision fields inside a case cannot flip the verdict
  (no circular label generation): ground truth comes only from the frozen
  family rule table.
- Undeclared/unmodelled families, nested-payload families and missing case
  ids fail closed with stable kernel reason codes; ``INDETERMINATE`` is
  retained (with ``gap_code=PENDING_ADJUDICATION``), never coerced.

The test module imports only the oracle and the shared kernel (independent-
oracle rule): no candidate baseline import, no DB, no network, no clock.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027._shared.oracle_kernel import OracleError
from evaluation.venue2027.acns import independent_oracle as oracle
from evaluation.venue2027.acns.independent_oracle import (
    ACNS_EVIDENCE_BOUNDARY_RULES,
    ACNS_INDEPENDENT_ORACLE_VERSION,
    BOUNDARY_TABLE,
    ORACLE_ID,
    EvidenceBoundaryOracleVerdict,
    adjudicate,
    adjudicate_boundary,
    run_self_checks,
    scan_for_candidate_imports,
    verify_independence,
)

# ---------------------------------------------------------------------------
# Positive controls — pre-registered evidence-boundary matrix
# ---------------------------------------------------------------------------


def test_positive_bound_evidence_admits_clean_control() -> None:
    result = adjudicate(
        {
            "case_id": "ACNS-CASE-03",
            "family": "bound_evidence",
            "evidence": [{"uri": "research/venue2027/VENUES/acns/cases/schema_example.json"}],
        }
    )
    assert result.outcome == "ADMIT"
    assert result.case_id == "ACNS-CASE-03"
    assert result.oracle_id == ORACLE_ID == "acns-evidence-boundary-reference"
    assert result.reason_code == "RULE_BOUND_EVIDENCE"
    assert result.evidence_refs == ("research/venue2027/VENUES/acns/cases/schema_example.json",)
    assert result.to_dict()["kernel_version"] == oracle_kernel.ORACLE_KERNEL_VERSION


@pytest.mark.parametrize(
    ("family", "expected_outcome", "expected_reason"),
    [
        ("bound_evidence", "ADMIT", "RULE_BOUND_EVIDENCE"),
        ("attestation_downgrade", "REJECT", "RULE_ATTESTATION_DOWNGRADE"),
        ("unbound_claim", "REJECT", "RULE_UNBOUND_CLAIM"),
        ("replayed_receipt", "REJECT", "RULE_REPLAYED_RECEIPT"),
    ],
)
def test_positive_full_rule_matrix_matches_preregistration(
    family: str, expected_outcome: str, expected_reason: str
) -> None:
    result = adjudicate({"case_id": f"case-{family}", "family": family})
    assert result.outcome == expected_outcome
    assert result.reason_code == expected_reason
    assert result.oracle_id == ORACLE_ID


def test_positive_nested_payload_family_adjudicates() -> None:
    result = adjudicate({"case_id": "case-nested", "payload": {"family": "replayed_receipt"}})
    assert result.outcome == "REJECT"
    assert result.reason_code == "RULE_REPLAYED_RECEIPT"


def test_positive_boundary_verdict_carries_sok_content() -> None:
    verdict = adjudicate_boundary({"case_id": "ACNS-CASE-02", "family": "attestation_downgrade"})
    assert isinstance(verdict, EvidenceBoundaryOracleVerdict)
    assert verdict.oracle_result.outcome == "REJECT"
    assert verdict.granted_level == "L2-ACKNOWLEDGED"
    assert verdict.refused_claim == "the model executed the tool"
    assert verdict.gap_code == "G2_RECEIPT_AS_EXECUTION"
    assert "TC3" in verdict.boundary_condition
    payload = json.dumps(verdict.to_dict(), sort_keys=True)
    assert isinstance(json.loads(payload), dict)
    assert verdict.oracle_version == ACNS_INDEPENDENT_ORACLE_VERSION


def test_positive_all_boundary_rows_reference_registered_gap_codes() -> None:
    assert set(BOUNDARY_TABLE) == set(ACNS_EVIDENCE_BOUNDARY_RULES)
    for family, rule in BOUNDARY_TABLE.items():
        assert rule.gap_code in oracle.REGISTERED_GAP_CODES, family
        assert rule.granted_level and rule.refused_claim and rule.boundary_condition
        # The clean control refuses no claim beyond its stated scope.
        if family == "bound_evidence":
            assert rule.gap_code == "none"


def test_positive_deterministic_and_json_serializable() -> None:
    case = {"case_id": "case-stable", "family": "bound_evidence", "evidence": []}
    first, second = adjudicate(case), adjudicate(case)
    assert first == second
    payload = json.dumps(first.to_dict(), sort_keys=True)
    assert isinstance(json.loads(payload), dict)


def test_positive_self_checks_match_preregistered_matrix() -> None:
    verdicts = run_self_checks()
    assert [v.oracle_result.outcome for v in verdicts] == [
        "ADMIT",
        "REJECT",
        "REJECT",
        "REJECT",
        "INDETERMINATE",
    ]
    assert all(v.gap_code != "" for v in verdicts)


# ---------------------------------------------------------------------------
# SoK verdict-shape controls — evidence-boundary verdict, not mechanism outcome
# ---------------------------------------------------------------------------


def test_sok_verdicts_express_evidence_boundary_not_mechanism_outcome() -> None:
    # The whole verdict vocabulary is evidence-handling language; mechanism
    # outcomes ("tool ran", "task succeeded") are absent by construction.
    forbidden_tokens = ("tool ran", "the tool ran", "task succeeded", "pipeline succeeded")
    for family, rule in BOUNDARY_TABLE.items():
        blob = " ".join((rule.granted_level, rule.refused_claim, rule.boundary_condition)).lower()
        assert not any(token in blob for token in forbidden_tokens), family
        # Every rule names what the evidence supports (granted_level on the
        # lattice) and the claim it refuses — the boundary, not an execution.
        assert rule.granted_level.startswith("L"), family
    # Adversarial families carry pre-registered gap codes (G-codes), the SoK
    # witness vocabulary, instead of mechanism success/failure flags.
    assert BOUNDARY_TABLE["attestation_downgrade"].gap_code == "G2_RECEIPT_AS_EXECUTION"
    assert BOUNDARY_TABLE["replayed_receipt"].gap_code == "G4_SIGNATURE_AS_CONTEXT"
    assert BOUNDARY_TABLE["unbound_claim"].gap_code == "G7_LEVEL_IMPLICIT_UPGRADE"


def test_sok_downgrade_witness_rejects_implication_not_mechanism() -> None:
    # ACNS-CASE-02 (G2): the verdict names the broken implication
    # (receipt => execution), not "execution failed".
    verdict = adjudicate_boundary({"case_id": "ACNS-CASE-02", "family": "attestation_downgrade"})
    assert verdict.oracle_result.outcome == "REJECT"
    assert verdict.granted_level == "L2-ACKNOWLEDGED"  # receipt claim still holds
    assert verdict.refused_claim == "the model executed the tool"


def test_sok_independent_oracle_matches_manual_canonical_history() -> None:
    # Sentinel parity: the oracle's matrix equals the manually adjudicated
    # canonical history from the CASE_MATRIX / threat-model register.
    canonical = {
        "bound_evidence": "ADMIT",  # ACNS-CASE-03 clean control
        "attestation_downgrade": "REJECT",  # G2 witness
        "unbound_claim": "REJECT",  # G7/G9 witness
        "replayed_receipt": "REJECT",  # G4 witness
    }
    observed = {
        family: adjudicate({"case_id": f"parity-{family}", "family": family}).outcome
        for family in canonical
    }
    assert observed == canonical


# ---------------------------------------------------------------------------
# Adversarial controls — independence from candidate baselines
# ---------------------------------------------------------------------------


def test_adversarial_clean_source_passes_independence() -> None:
    verify_independence()  # live module source: must not raise
    assert scan_for_candidate_imports() == frozenset()


@pytest.mark.parametrize(
    "snippet",
    [
        "import evaluation.venue2027.acns.baselines",
        "import evaluation.venue2027.acns.baselines as b",
        "from evaluation.venue2027.acns.baselines import run_baseline",
        "from evaluation.venue2027.acns import baselines",
        "import baselines",
        "from baselines import run_baseline",
        "import acns.baselines",
        "from evaluation.venue2027.compsac import baselines",
    ],
)
def test_adversarial_candidate_import_refused(snippet: str) -> None:
    with pytest.raises(OracleError) as excinfo:
        verify_independence(f'"""doc"""\n{snippet}\n')
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"
    assert "baselines" in excinfo.value.detail


def test_adversarial_similar_names_do_not_trip_the_scan() -> None:
    # Exact component matching: modules whose names merely *contain* a
    # candidate basename are not candidate imports.
    snippet = (
        "import ast\n"
        "import my_baselines_tests\n"
        "from evaluation.venue2027.acns.independent_oracle import adjudicate\n"
        "from evaluation.venue2027._shared import oracle_kernel\n"
    )
    assert scan_for_candidate_imports(snippet) == frozenset()
    verify_independence(snippet)


def test_adversarial_dynamic_import_flagged() -> None:
    dynamic = 'm = __import__("evaluation.venue2027.acns.baselines")\n'
    assert scan_for_candidate_imports(dynamic) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        verify_independence(dynamic)
    importlib_snippet = (
        "import importlib\n" 'm = importlib.import_module("evaluation.venue2027.acns.baselines")\n'
    )
    assert scan_for_candidate_imports(importlib_snippet) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        verify_independence(importlib_snippet)


def test_adversarial_tampered_live_source_refused() -> None:
    # Tamper control: appending one candidate import to the real source must
    # flip the verdict (the scan really reads the source it is given).
    source = oracle.__file__
    assert source is not None
    live = __import__("pathlib").Path(source).read_text(encoding="utf-8")
    with pytest.raises(OracleError) as excinfo:
        verify_independence(live + "\nimport evaluation.venue2027.acns.baselines\n")
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_kernel_ast_guard_also_clean() -> None:
    # The audited kernel guard accepts this oracle's live file as well.
    source_path = oracle.__file__
    assert source_path is not None
    oracle_kernel.assert_oracle_independence(source_path, ())


# ---------------------------------------------------------------------------
# Adversarial controls — fail-closed adjudication semantics
# ---------------------------------------------------------------------------


def test_adversarial_unmodelled_family_is_indeterminate_not_reject() -> None:
    result = adjudicate({"case_id": "case-unknown", "family": "novel_attack_family"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"
    verdict = adjudicate_boundary({"case_id": "case-unknown", "family": "novel_attack_family"})
    assert verdict.gap_code == "PENDING_ADJUDICATION"
    assert verdict.granted_level == "" and verdict.refused_claim == ""


def test_adversarial_missing_family_is_indeterminate() -> None:
    result = adjudicate({"case_id": "case-nofamily"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "NO_FAMILY_DECLARED"


def test_adversarial_missing_case_id_fails_closed() -> None:
    with pytest.raises(OracleError) as excinfo:
        adjudicate({"family": "bound_evidence"})
    assert excinfo.value.reason_code == "MISSING_CASE_ID"


def test_adversarial_malformed_case_fails_closed() -> None:
    with pytest.raises(OracleError) as excinfo:
        adjudicate(["not", "a", "mapping"])  # type: ignore[arg-type]
    assert excinfo.value.reason_code == "MALFORMED_CASE"


def test_adversarial_candidate_fields_cannot_flip_the_verdict() -> None:
    # No circular label generation: candidate-supplied decision/reason fields
    # inside the case are ignored; the family rule table is the only truth.
    poisoned: dict[str, object] = {
        "case_id": "case-poisoned",
        "family": "attestation_downgrade",
        "observed_decision": "ADMIT",
        "decision": "ADMIT",
        "verdict": "ACCEPT",
        "reason_code": "OK",
        "payload": {"family": "attestation_downgrade", "expected": "ADMIT"},
    }
    assert adjudicate(poisoned).outcome == "REJECT"
    assert adjudicate_boundary(poisoned).gap_code == "G2_RECEIPT_AS_EXECUTION"
    # Symmetrically, a clean family cannot be talked into a rejection.
    poisoned_clean = {
        "case_id": "case-poisoned-clean",
        "family": "bound_evidence",
        "observed_decision": "REJECT",
        "verdict": "REJECT",
    }
    assert adjudicate(poisoned_clean).outcome == "ADMIT"


def test_adversarial_evidence_refs_survive_tampering_of_other_fields() -> None:
    case = {
        "case_id": "case-refs",
        "family": "unbound_claim",
        "evidence": [
            {"uri": "research/venue2027/acns/threat_model.md"},
            "not-a-dict",  # non-dict entries are dropped by the kernel, not fatal
            {"no_uri": True},  # kernel keeps dict entries as their (empty) uri
        ],
    }
    result = adjudicate(case)
    assert result.outcome == "REJECT"
    assert result.evidence_refs == ("research/venue2027/acns/threat_model.md", "")


def test_adversarial_no_indeterminate_coercion_into_safe_verdict() -> None:
    # INDETERMINATE is first-class: it is neither ADMIT nor REJECT, and the
    # boundary verdict marks it pending adjudication rather than counting it.
    for family in (None, "", "unmodelled"):
        case = {"case_id": "case-ind", "family": family}
        result = adjudicate(case)
        assert result.outcome == "INDETERMINATE"
        assert result.outcome not in ("ADMIT", "REJECT")
