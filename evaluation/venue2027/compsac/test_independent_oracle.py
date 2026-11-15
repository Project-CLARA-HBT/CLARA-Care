"""Tests for COMPSAC-oracle — independent FORBIDDEN-COMMIT reference oracle.

Positive controls prove the oracle labels the kernel-registered COMPSAC
families exactly per the frozen FORBIDDEN-COMMIT rule table (clean -> ADMIT;
omitted_dependency / epoch_race / stale_readset -> REJECT as forbidden
commits) deterministically and JSON-serializably, and that the verdict is a
pure function of the case family — NOT of any candidate reason code.

Adversarial controls prove independence and fail-closed semantics:

- ``verify_independence`` accepts the clean oracle source but refuses any
  source variant importing a candidate module (``compsac.baselines``,
  ``baselines``, ``dependency_dsl``) with ``CANDIDATE_IMPORT`` — covering
  plain import, from-import, aliased import, dotted paths and an injected
  import appended to the real source (tamper control); dynamic imports are
  refused with ``DYNAMIC_IMPORT_UNRESOLVABLE``.
- Forbidden-commit labels are asserted to be independent of any candidate
  reason code: the same family must yield the same verdict regardless of the
  candidate-supplied ``reason_code`` / ``status`` fields attached to the case.
- Unknown, undeclared and family-less cases return ``INDETERMINATE`` (never a
  silent safe verdict); a missing ``case_id`` fails closed.

The test module imports only the oracle and the shared kernel (independent-
oracle rule): no candidate baselines import, no dependency DSL import, no DB,
no model, no clock/randomness.
"""

from __future__ import annotations

import pytest

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027.compsac import independent_oracle
from evaluation.venue2027.compsac.independent_oracle import (
    CASE_OUTCOME_RULES,
    FORBIDDEN_COMMIT_ORACLE_VERSION,
    ORACLE_ID,
    REASON_CANDIDATE_IMPORT,
    REASON_DYNAMIC_IMPORT,
    REASON_FORBIDDEN_COMMIT,
    adjudicate,
    verify_independence,
)

REJECT_FAMILIES = ("omitted_dependency", "epoch_race", "stale_readset")

#: Candidate-supplied reason codes that must never change the oracle verdict.
#: These mimic what a candidate arm (baselines / dependency DSL consumer)
#: might report; the oracle must ignore them completely.
CANDIDATE_REASON_CODES = (
    "CANDIDATE_OK",
    "CANDIDATE_FORBIDDEN_COMMIT",
    "CANDIDATE_STALE",
    "CANDIDATE_ABORT",
    "CANDIDATE_UNKNOWN",
    "",
)


def _case(family: str, case_id: str = "COMPSAC-CASE-X", **extra: object) -> dict[str, object]:
    return {"case_id": case_id, "family": family, **extra}


# ---------------------------------------------------------------------------
# Positive controls: frozen rule table, kernel delegation, provenance.
# ---------------------------------------------------------------------------


def test_clean_family_admitted() -> None:
    result = adjudicate(_case("clean", "COMPSAC-CASE-01"))
    assert result.outcome == "ADMIT"
    assert result.case_id == "COMPSAC-CASE-01"
    assert result.oracle_id == ORACLE_ID
    assert result.to_dict()["kernel_version"] == oracle_kernel.ORACLE_KERNEL_VERSION


def test_clean_family_admitted_with_evidence_refs() -> None:
    result = adjudicate(
        {
            "case_id": "COMPSAC-CASE-01b",
            "family": "clean",
            "evidence": [{"uri": "sha256:deadbeef"}, {"uri": "truth.json"}],
        }
    )
    assert result.outcome == "ADMIT"
    assert result.evidence_refs == ("sha256:deadbeef", "truth.json")


@pytest.mark.parametrize("family", REJECT_FAMILIES)
def test_forbidden_commit_families_rejected(family: str) -> None:
    result = adjudicate(_case(family))
    assert result.outcome == "REJECT"
    assert result.reason_code == REASON_FORBIDDEN_COMMIT


def test_omitted_dependency_is_forbidden_commit() -> None:
    result = adjudicate(_case("omitted_dependency", "COMPSAC-CASE-04"))
    assert result.outcome == "REJECT"
    assert result.reason_code == REASON_FORBIDDEN_COMMIT


def test_epoch_race_and_stale_readset_rejected() -> None:
    assert adjudicate(_case("epoch_race", "COMPSAC-CASE-03")).outcome == "REJECT"
    assert adjudicate(_case("stale_readset", "COMPSAC-CASE-02")).outcome == "REJECT"


def test_family_via_payload_is_honoured() -> None:
    result = adjudicate({"case_id": "c-payload", "payload": {"family": "clean"}})
    assert result.outcome == "ADMIT"


def test_rule_table_is_exactly_the_frozen_compsac_table() -> None:
    assert CASE_OUTCOME_RULES == {
        "clean": "ADMIT",
        "omitted_dependency": "REJECT",
        "epoch_race": "REJECT",
        "stale_readset": "REJECT",
    }


def test_result_is_json_serializable() -> None:
    import json

    payload = adjudicate(_case("clean")).to_dict()
    assert json.loads(json.dumps(payload)) == payload


def test_self_checks_pass_and_match_rule_table() -> None:
    results = independent_oracle.run_self_checks()
    assert {r.case_id.removeprefix("selfcheck-"): r.outcome for r in results} == dict(
        CASE_OUTCOME_RULES
    )


def test_version_and_oracle_id_stable() -> None:
    assert ORACLE_ID == "compsac-forbidden-commit-reference"
    assert FORBIDDEN_COMMIT_ORACLE_VERSION == "clara.compsac.forbidden-commit-oracle-v1"


# ---------------------------------------------------------------------------
# Adversarial controls: independence from candidate reason codes.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", ["clean", *REJECT_FAMILIES])
@pytest.mark.parametrize("candidate_reason", CANDIDATE_REASON_CODES)
def test_verdict_ignores_candidate_reason_code(family: str, candidate_reason: str) -> None:
    """Same family => same verdict, whatever the candidate arm reports."""

    labelled = _case(family, candidate_reason_code=candidate_reason, candidate_status="FAILED")
    bare = _case(family)
    left = adjudicate(labelled)
    right = adjudicate(bare)
    assert (left.outcome, left.reason_code) == (right.outcome, right.reason_code)


@pytest.mark.parametrize("candidate_reason", CANDIDATE_REASON_CODES)
def test_forbidden_commit_label_independent_of_candidate_reason(candidate_reason: str) -> None:
    """The forbidden-commit REJECT must not flip based on candidate output."""

    for family in REJECT_FAMILIES:
        result = adjudicate(
            {
                "case_id": "COMPSAC-CASE-ADV",
                "family": family,
                "observed": {"reason_code": candidate_reason, "status": "COMMITTED"},
                "candidate_reason_code": candidate_reason,
            }
        )
        assert result.outcome == "REJECT"
        assert result.reason_code == REASON_FORBIDDEN_COMMIT


def test_candidate_claiming_clean_does_not_admit_forbidden_family() -> None:
    result = adjudicate(
        {
            "case_id": "COMPSAC-CASE-ADV2",
            "family": "omitted_dependency",
            "observed": {"reason_code": "ALL_DEPENDENCIES_VERIFIED", "status": "COMMITTED"},
        }
    )
    assert result.outcome == "REJECT"


def test_candidate_claiming_forbidden_does_not_reject_clean_family() -> None:
    result = adjudicate(
        {
            "case_id": "COMPSAC-CASE-ADV3",
            "family": "clean",
            "observed": {"reason_code": "FORBIDDEN_COMMIT_DETECTED", "status": "ABORTED"},
        }
    )
    assert result.outcome == "ADMIT"


# ---------------------------------------------------------------------------
# Adversarial controls: INDETERMINATE / fail-closed semantics.
# ---------------------------------------------------------------------------


def test_unknown_family_is_indeterminate() -> None:
    result = adjudicate(_case("novel_write_skew"))
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"


def test_missing_family_is_indeterminate() -> None:
    result = adjudicate({"case_id": "c-nofamily"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "NO_FAMILY_DECLARED"


def test_empty_family_string_is_indeterminate() -> None:
    result = adjudicate(_case(""))
    assert result.outcome == "INDETERMINATE"


def test_missing_case_id_fails_closed() -> None:
    with pytest.raises(oracle_kernel.OracleError) as exc:
        adjudicate({"family": "clean"})
    assert exc.value.reason_code == "MISSING_CASE_ID"


def test_indeterminate_is_never_coerced_to_safe_verdict() -> None:
    for family in (None, "", "unmodelled"):
        case = {"case_id": "c-x"}
        if family is not None:
            case["family"] = family
        result = adjudicate(case)
        assert result.outcome == "INDETERMINATE"


# ---------------------------------------------------------------------------
# Adversarial controls: source-level independence (verify_independence).
# ---------------------------------------------------------------------------


def test_verify_independence_accepts_clean_oracle(tmp_path, monkeypatch) -> None:
    """The real oracle source must pass its own independence scan."""

    verify_independence()


def test_verify_independence_refuses_plain_baselines_import(tmp_path) -> None:
    source = "import baselines\nRULES = {}\n"
    oracle = tmp_path / "oracle.py"
    oracle.write_text(source, encoding="utf-8")
    with pytest.raises(oracle_kernel.OracleError) as exc:
        verify_independence(source, str(oracle))
    assert exc.value.reason_code == REASON_CANDIDATE_IMPORT


def test_verify_independence_refuses_dotted_baselines_import(tmp_path) -> None:
    source = "from compsac.baselines import arm_b1\n"
    oracle = tmp_path / "oracle.py"
    oracle.write_text(source, encoding="utf-8")
    with pytest.raises(oracle_kernel.OracleError) as exc:
        verify_independence(source, str(oracle))
    assert exc.value.reason_code == REASON_CANDIDATE_IMPORT


def test_verify_independence_refuses_dependency_dsl_from_import(tmp_path) -> None:
    source = "from evaluation.venue2027.compsac.dependency_dsl import compile\n"
    oracle = tmp_path / "oracle.py"
    oracle.write_text(source, encoding="utf-8")
    with pytest.raises(oracle_kernel.OracleError) as exc:
        verify_independence(source, str(oracle))
    assert exc.value.reason_code == REASON_CANDIDATE_IMPORT


def test_verify_independence_refuses_aliased_import(tmp_path) -> None:
    source = "import dependency_dsl as dsl\n"
    oracle = tmp_path / "oracle.py"
    oracle.write_text(source, encoding="utf-8")
    with pytest.raises(oracle_kernel.OracleError) as exc:
        verify_independence(source, str(oracle))
    assert exc.value.reason_code == REASON_CANDIDATE_IMPORT


def test_verify_independence_refuses_import_injected_into_real_source(tmp_path) -> None:
    """Tamper control: appending a candidate import to the live source fails."""

    real = independent_oracle.__file__
    assert real is not None
    with open(real, encoding="utf-8") as fh:
        source = fh.read()
    source += "\nimport baselines\n"
    oracle = tmp_path / "tampered_oracle.py"
    oracle.write_text(source, encoding="utf-8")
    with pytest.raises(oracle_kernel.OracleError) as exc:
        verify_independence(source, str(oracle))
    assert exc.value.reason_code == REASON_CANDIDATE_IMPORT


def test_verify_independence_refuses_dynamic_import(tmp_path) -> None:
    source = "importlib.import_module('compsac.baselines')\n"
    oracle = tmp_path / "oracle.py"
    oracle.write_text(source, encoding="utf-8")
    with pytest.raises(oracle_kernel.OracleError) as exc:
        verify_independence(source, str(oracle))
    assert exc.value.reason_code == REASON_DYNAMIC_IMPORT


def test_verify_independence_refuses_builtin_dynamic_import(tmp_path) -> None:
    source = "__import__('baselines')\n"
    oracle = tmp_path / "oracle.py"
    oracle.write_text(source, encoding="utf-8")
    with pytest.raises(oracle_kernel.OracleError) as exc:
        verify_independence(source, str(oracle))
    assert exc.value.reason_code == REASON_DYNAMIC_IMPORT


def test_oracle_module_does_not_import_candidates_at_source_level() -> None:
    """Direct AST scan of the shipped oracle file finds zero candidate imports."""

    import ast
    from pathlib import Path

    source = Path(independent_oracle.__file__).read_text(encoding="utf-8")
    targets: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.append(node.module)
    forbidden = {"compsac.baselines", "baselines", "dependency_dsl"}
    offending = [t for t in targets if any(part in forbidden for part in t.split("."))]
    assert offending == []
