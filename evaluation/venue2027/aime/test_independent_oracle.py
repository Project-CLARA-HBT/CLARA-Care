"""Tests for the AIME independent per-case truth oracle.

Positive controls: every AIME rule-table row routes to its frozen outcome via
the shared kernel; blinded adjudication records resolve INDETERMINATE cases.
Adversarial controls: candidate imports refused, dynamic imports refused,
INDETERMINATE never coerced, PII/unblinded/malformed adjudication records
refused, and the live module source passes the independence scan with zero
model/LLM imports. Synthetic cases only — no real PHI, no network, no
provider/model call.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027.aime import independent_oracle as oracle


def _case(family: str, case_id: str = "AIME-CASE-01") -> dict[str, object]:
    return {
        "case_id": case_id,
        "family": family,
        "evidence": [{"uri": "synthetic/case.json"}],
    }


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_rule_table_matches_frozen_design() -> None:
    assert oracle.AIME_RULES == {
        "stable_history": "ADMIT",
        "consent_change": "REJECT",
        "medication_withdrawal": "REJECT",
        "allergy_update": "REJECT",
        "reconciliation": "INDETERMINATE",
    }


def test_stable_history_admits() -> None:
    result = oracle.adjudicate(_case("stable_history"))
    assert result.outcome == "ADMIT"
    assert result.reason_code == "RULE_STABLE_HISTORY"
    assert result.oracle_id == "aime-clinical-reference"


def test_consent_change_rejects() -> None:
    result = oracle.adjudicate(_case("consent_change", "AIME-CASE-03"))
    assert result.outcome == "REJECT"
    assert result.reason_code == "RULE_CONSENT_CHANGE"


def test_medication_withdrawal_rejects() -> None:
    result = oracle.adjudicate(_case("medication_withdrawal", "AIME-CASE-02"))
    assert result.outcome == "REJECT"
    assert result.reason_code == "RULE_MEDICATION_WITHDRAWAL"


def test_allergy_update_rejects() -> None:
    result = oracle.adjudicate(_case("allergy_update", "AIME-CASE-02"))
    assert result.outcome == "REJECT"
    assert result.reason_code == "RULE_ALLERGY_UPDATE"


def test_reconciliation_is_indeterminate() -> None:
    result = oracle.adjudicate(_case("reconciliation", "AIME-CASE-04"))
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "RULE_RECONCILIATION"


def test_family_read_from_dataset_payload() -> None:
    case = {
        "case_id": "AIME-CASE-03",
        "payload": {"family": "consent_change", "update_family": "consent_change"},
    }
    result = oracle.adjudicate(case)
    assert result.outcome == "REJECT"


def test_evidence_refs_captured_from_case() -> None:
    result = oracle.adjudicate(_case("stable_history"))
    assert result.evidence_refs == ("synthetic/case.json",)


def test_to_dict_is_json_serializable() -> None:
    import json

    payload = oracle.adjudicate(_case("reconciliation", "AIME-CASE-05")).to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["outcome"] == "INDETERMINATE"
    assert payload["kernel_version"] == oracle_kernel.ORACLE_KERNEL_VERSION


def test_requires_human_review_true_only_for_indeterminate() -> None:
    assert oracle.requires_human_review(_case("reconciliation")) is True
    assert oracle.requires_human_review(_case("stable_history")) is False
    assert oracle.requires_human_review(_case("consent_change")) is False


def test_blinded_adjudication_record_round_trip() -> None:
    record = oracle.BlindedAdjudication(
        case_id="AIME-CASE-05",
        reviewer_pseudonym="clinician-07",
        blinded=True,
        adjudicated_at="2027-01-01T00:00:00Z",
        verdict="REJECT",
        reason_code="CLINICIAN_REVIEW_REJECT",
    )
    payload = record.to_dict()
    assert payload["blinded"] is True
    assert payload["oracle_id"] == "aime-clinical-reference"
    rebuilt = oracle.BlindedAdjudication(**payload)
    assert rebuilt == record


def test_blinded_adjudication_accepts_plus_offset_utc() -> None:
    record = oracle.BlindedAdjudication(
        case_id="AIME-CASE-04",
        reviewer_pseudonym="clinician-07",
        blinded=True,
        adjudicated_at="2027-01-01T00:00:00+00:00",
        verdict="ADMIT",
        reason_code="CLINICIAN_REVIEW_ADMIT",
    )
    assert record.verdict == "ADMIT"


def test_self_scan_reports_clean_and_zero_llm() -> None:
    audit = oracle.self_scan()
    assert audit["independence"]["ok"] is True
    assert audit["rule_table"] == oracle.AIME_RULES
    assert audit["llm_calls"] == 0
    assert audit["model_imports"] == 0
    assert audit["oracle_id"] == "aime-clinical-reference"


def test_determinism_same_input_same_result() -> None:
    first = oracle.adjudicate(_case("reconciliation"))
    second = oracle.adjudicate(_case("reconciliation"))
    assert dataclasses.astuple(first) == dataclasses.astuple(second)


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_missing_case_id_refused_fail_closed() -> None:
    with pytest.raises(oracle_kernel.OracleError) as exc:
        oracle.adjudicate({"family": "stable_history"})
    assert exc.value.reason_code == "MISSING_CASE_ID"


def test_missing_family_is_indeterminate() -> None:
    result = oracle.adjudicate({"case_id": "AIME-CASE-XX"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "NO_FAMILY_DECLARED"
    assert oracle.requires_human_review({"case_id": "AIME-CASE-XX"}) is True


def test_unmodelled_family_is_indeterminate_not_safe() -> None:
    result = oracle.adjudicate(_case("novel_unregistered_family", "AIME-CASE-XX"))
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"


def test_unknown_family_routes_to_human_review() -> None:
    assert oracle.requires_human_review(_case("novel_unregistered_family")) is True


def test_indeterminate_never_coerced_to_safe_verdict() -> None:
    for family in ("reconciliation", "novel_unregistered_family"):
        outcome = oracle.adjudicate(_case(family)).outcome
        assert outcome == "INDETERMINATE"
        assert outcome not in ("ADMIT", "REJECT")


def test_adjudication_refuses_unblinded_reviewer() -> None:
    with pytest.raises(oracle_kernel.OracleError) as exc:
        oracle.BlindedAdjudication(
            case_id="AIME-CASE-05",
            reviewer_pseudonym="clinician-07",
            blinded=False,
            adjudicated_at="2027-01-01T00:00:00Z",
            verdict="REJECT",
            reason_code="CLINICIAN_REVIEW_REJECT",
        )
    assert exc.value.reason_code == "REVIEWER_NOT_BLINDED"


def test_adjudication_refuses_pii_in_pseudonym() -> None:
    with pytest.raises(oracle_kernel.OracleError) as exc:
        oracle.BlindedAdjudication(
            case_id="AIME-CASE-05",
            reviewer_pseudonym="dr.exampe@hospital.org",
            blinded=True,
            adjudicated_at="2027-01-01T00:00:00Z",
            verdict="ADMIT",
            reason_code="CLINICIAN_REVIEW_ADMIT",
        )
    assert exc.value.reason_code == "ADJUDICATOR_PII"


def test_adjudication_refuses_invalid_verdict_and_timestamp() -> None:
    with pytest.raises(oracle_kernel.OracleError) as verdict_exc:
        oracle.BlindedAdjudication(
            case_id="AIME-CASE-05",
            reviewer_pseudonym="clinician-07",
            blinded=True,
            adjudicated_at="2027-01-01T00:00:00Z",
            verdict="MAYBE",
            reason_code="CLINICIAN_REVIEW_MAYBE",
        )
    assert verdict_exc.value.reason_code == "ADJUDICATED_VERDICT_INVALID"
    with pytest.raises(oracle_kernel.OracleError) as ts_exc:
        oracle.BlindedAdjudication(
            case_id="AIME-CASE-05",
            reviewer_pseudonym="clinician-07",
            blinded=True,
            adjudicated_at="not-a-timestamp",
            verdict="ADMIT",
            reason_code="CLINICIAN_REVIEW_ADMIT",
        )
    assert ts_exc.value.reason_code == "ADJUDICATION_TIMESTAMP_INVALID"


def test_adjudication_refuses_non_utc_timestamp() -> None:
    with pytest.raises(oracle_kernel.OracleError) as exc:
        oracle.BlindedAdjudication(
            case_id="AIME-CASE-05",
            reviewer_pseudonym="clinician-07",
            blinded=True,
            adjudicated_at="2027-01-01T07:00:00+07:00",
            verdict="ADMIT",
            reason_code="CLINICIAN_REVIEW_ADMIT",
        )
    assert exc.value.reason_code == "ADJUDICATION_TIMESTAMP_INVALID"


def test_self_scan_refuses_rule_table_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oracle, "AIME_RULES", {**oracle.AIME_RULES, "rogue_family": "ADMIT"})
    with pytest.raises(oracle_kernel.OracleError) as exc:
        oracle.self_scan()
    assert exc.value.reason_code == "RULE_TABLE_DRIFT"


def test_live_module_passes_kernel_independence_scan() -> None:
    source = pathlib.Path(oracle.__file__).resolve()
    oracle_kernel.assert_oracle_independence(str(source), oracle.CANDIDATE_MODULE_BASENAMES)


def test_live_module_imports_no_model_or_llm_library() -> None:
    tree = ast.parse(
        pathlib.Path(oracle.__file__).read_text(encoding="utf-8"),
        filename=str(oracle.__file__),
    )
    forbidden_roots = {
        "openai",
        "anthropic",
        "transformers",
        "torch",
        "tensorflow",
        "litellm",
        "requests",
        "httpx",
        "urllib3",
        "services",
        "evaluation",
    }
    allowed_evaluation_prefix = "evaluation.venue2027._shared"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden_roots and not alias.name.startswith(allowed_evaluation_prefix):
                    pytest.fail(f"oracle imports forbidden module: {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in forbidden_roots and not node.module.startswith(allowed_evaluation_prefix):
                pytest.fail(f"oracle imports from forbidden module: {node.module}")


def test_oracle_independence_refuses_rogue_candidate_import(
    tmp_path: pathlib.Path,
) -> None:
    rogue = tmp_path / "rogue_oracle.py"
    rogue.write_text(
        "import baselines\n",
        encoding="utf-8",
    )
    with pytest.raises(oracle_kernel.OracleError) as exc:
        oracle_kernel.assert_oracle_independence(str(rogue), oracle.CANDIDATE_MODULE_BASENAMES)
    assert exc.value.reason_code == "CANDIDATE_IMPORT"


def test_oracle_independence_refuses_dynamic_import(tmp_path: pathlib.Path) -> None:
    rogue = tmp_path / "rogue_dynamic.py"
    rogue.write_text(
        "import importlib\nimportlib.import_module('baselines')\n",
        encoding="utf-8",
    )
    with pytest.raises(oracle_kernel.OracleError) as exc:
        oracle_kernel.assert_oracle_independence(str(rogue), oracle.CANDIDATE_MODULE_BASENAMES)
    assert exc.value.reason_code == "DYNAMIC_IMPORT_UNRESOLVABLE"


def test_synthetic_only_fixture_no_real_phi() -> None:
    case = _case("stable_history", "AIME-CASE-01")
    blob = repr(case).lower()
    for marker in ("@hospital", "mrn", "national_id", "passport", "insurance_id"):
        assert marker not in blob
