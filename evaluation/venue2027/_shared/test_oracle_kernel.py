"""Tests for the shared independent-oracle kernel."""

from __future__ import annotations

import pathlib

import pytest

from evaluation.venue2027._shared import oracle_kernel as ok

RULES = {"clean": "ADMIT", "unsafe": "REJECT", "ambiguous": "INDETERMINATE"}


def test_adjudicate_accepts_known_family() -> None:
    result = ok.adjudicate({"case_id": "c1", "family": "clean"}, RULES, oracle_id="t")
    assert result.outcome == "ADMIT"
    assert result.reason_code == "RULE_CLEAN"


def test_adjudicate_rejects_known_unsafe() -> None:
    result = ok.adjudicate({"case_id": "c2", "family": "unsafe"}, RULES, oracle_id="t")
    assert result.outcome == "REJECT"


def test_unknown_family_is_indeterminate() -> None:
    result = ok.adjudicate({"case_id": "c3", "family": "novel"}, RULES, oracle_id="t")
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"


def test_missing_family_is_indeterminate() -> None:
    result = ok.adjudicate({"case_id": "c4"}, RULES, oracle_id="t")
    assert result.outcome == "INDETERMINATE"


def test_missing_case_id_refused() -> None:
    with pytest.raises(ok.OracleError) as exc:
        ok.adjudicate({"family": "clean"}, RULES, oracle_id="t")
    assert exc.value.reason_code == "MISSING_CASE_ID"


def test_evidence_refs_captured() -> None:
    result = ok.adjudicate(
        {"case_id": "c5", "family": "clean", "evidence": [{"uri": "a.json"}]},
        RULES,
        oracle_id="t",
    )
    assert result.evidence_refs == ("a.json",)


def test_independence_accepts_clean_oracle(tmp_path: pathlib.Path) -> None:
    oracle = tmp_path / "oracle.py"
    oracle.write_text("import json\nRULES = {}\n", encoding="utf-8")
    ok.assert_oracle_independence(str(oracle), ("dependency_dsl",))


def test_independence_refuses_candidate_import(tmp_path: pathlib.Path) -> None:
    oracle = tmp_path / "oracle.py"
    oracle.write_text("from dependency_dsl import compile_dependencies\n", encoding="utf-8")
    with pytest.raises(ok.OracleError) as exc:
        ok.assert_oracle_independence(str(oracle), ("dependency_dsl",))
    assert exc.value.reason_code == "CANDIDATE_IMPORT"


def test_independence_refuses_aliased_import(tmp_path: pathlib.Path) -> None:
    oracle = tmp_path / "oracle.py"
    oracle.write_text("import dependency_dsl as d\n", encoding="utf-8")
    with pytest.raises(ok.OracleError):
        ok.assert_oracle_independence(str(oracle), ("dependency_dsl",))


def test_independence_refuses_dynamic_import(tmp_path: pathlib.Path) -> None:
    oracle = tmp_path / "oracle.py"
    oracle.write_text("import importlib\nimportlib.import_module('dependency_dsl')\n", encoding="utf-8")
    with pytest.raises(ok.OracleError) as exc:
        ok.assert_oracle_independence(str(oracle), ("dependency_dsl",))
    assert exc.value.reason_code == "DYNAMIC_IMPORT_UNRESOLVABLE"
