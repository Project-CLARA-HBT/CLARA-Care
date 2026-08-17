"""Tests for the W7 agreement analysis (analyze_v2.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation.model_adjudication.analyze_v2 import analyze
from evaluation.model_adjudication.run_v2 import MODELS


def _review(label: str) -> dict[str, Any]:
    return {"label": label, "rationale": "r", "evidence_ids": ["e1", "e2"], "confidence": 0.9}


def _review_result(reviewer_id: str, label: str) -> dict[str, Any]:
    return {
        "model_id": MODELS[0] if reviewer_id == "reviewer_a" else MODELS[1],
        "reviewer_id": reviewer_id,
        "provider": {"parsed_review_sha256": f"parsed-{reviewer_id}-{label}" * 8},
        "review": _review(label),
    }


def _initial(a: str, b: str) -> list[dict[str, Any]]:
    return [_review_result("reviewer_a", a), _review_result("reviewer_b", b)]


def _case(*, case_id: str, status: str, initial: tuple[str, str], revised: tuple[str, str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"case_id": case_id, "status": status}
    if status == "AGREED":
        result["reviews"] = _initial(*initial)
        return result
    result["initial_reviews"] = _initial(*initial)
    result["revised_reviews"] = [_review_result("reviewer_a", revised[0]), _review_result("reviewer_b", revised[1])]
    result["reconciliation_prompts"] = {"reviewer_a": "a" * 64, "reviewer_b": "b" * 64}
    result["revised_response_hashes"] = {"reviewer_a": "ra" * 32, "reviewer_b": "rb" * 32}
    return result


def _write(data_dir: Path, results: list[dict[str, Any]]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        (data_dir / f"{result['case_id']}.json").write_text(json.dumps(result, sort_keys=True), encoding="utf-8")


def test_initial_and_post_reconciliation_stats(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            _case(case_id="c1", status="AGREED", initial=("PASS", "PASS")),
            _case(case_id="c2", status="AGREED_AFTER_RECONCILIATION", initial=("FAIL", "PASS"), revised=("PASS", "PASS")),
            _case(case_id="c3", status="UNRESOLVED", initial=("FAIL", "PASS"), revised=("FAIL", "PASS")),
        ],
    )
    result = analyze(tmp_path)
    assert result["case_count"] == 3
    assert result["initial_agreement"] == pytest.approx(1 / 3)
    assert result["disagreement_count"] == 2
    assert result["reconciliation_count"] == 2
    assert result["post_reconciliation_agreement"] == pytest.approx(2 / 3)
    assert result["unresolved_count"] == 1
    assert result["unresolved_rate"] == pytest.approx(1 / 3)
    assert "frozen_duplicate_self_consistency" not in result


def test_kappa_defined(tmp_path: Path) -> None:
    pairs = [
        _case(case_id="c1", status="AGREED", initial=("PASS", "PASS")),
        _case(case_id="c2", status="AGREED", initial=("PASS", "FAIL")),
        _case(case_id="c3", status="AGREED", initial=("FAIL", "PASS")),
    ]
    _write(tmp_path, pairs)
    result = analyze(tmp_path)
    assert result["initial_cohens_kappa"] == pytest.approx(-0.5)


def test_kappa_undefined_when_expected_is_one(tmp_path: Path) -> None:
    pairs = [
        _case(case_id="c1", status="AGREED", initial=("PASS", "PASS")),
        _case(case_id="c2", status="AGREED", initial=("PASS", "PASS")),
    ]
    _write(tmp_path, pairs)
    result = analyze(tmp_path)
    assert result["initial_cohens_kappa"] is None


def test_per_model_label_distribution(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            _case(case_id="c1", status="AGREED", initial=("PASS", "PASS")),
            _case(case_id="c2", status="AGREED", initial=("FAIL", "PASS")),
        ],
    )
    result = analyze(tmp_path)
    assert result["per_model_label_distribution"]["reviewer_a"]["model_id"] == MODELS[0]
    assert result["per_model_label_distribution"]["reviewer_a"]["labels"] == {"PASS": 1, "FAIL": 1}
    assert result["per_model_label_distribution"]["reviewer_b"]["model_id"] == MODELS[1]
    assert result["per_model_label_distribution"]["reviewer_b"]["labels"] == {"PASS": 2}


def test_raw_dir_without_reconciliation_is_handled(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            _case(case_id="c1", status="AGREED", initial=("PASS", "PASS")),
            _case(case_id="c2", status="AGREED", initial=("FAIL", "PASS")),
        ],
    )
    result = analyze(tmp_path)
    assert result["reconciliation_count"] == 0
    assert result["unresolved_count"] == 0
    assert result["post_reconciliation_agreement"] == result["initial_agreement"] == pytest.approx(0.5)


def test_frozen_duplicates_do_not_increase_n(tmp_path: Path) -> None:
    primary = [
        _case(case_id="c1", status="AGREED", initial=("PASS", "PASS")),
        _case(case_id="c2", status="AGREED_AFTER_RECONCILIATION", initial=("FAIL", "PASS"), revised=("PASS", "PASS")),
    ]
    dup = _case(case_id="c2__dup1", status="AGREED_AFTER_RECONCILIATION", initial=("FAIL", "PASS"), revised=("PASS", "PASS"))
    dup["frozen_duplicate"] = True
    dup["duplicate_of"] = "c2"
    _write(tmp_path, [*primary, dup])
    result = analyze(tmp_path)
    assert result["case_count"] == 2
    sc = result["frozen_duplicate_self_consistency"]
    assert sc["cases_with_duplicates"] == ["c2"]
    assert sc["duplicate_comparisons"] == 2
    assert sc["rate"] == pytest.approx(1.0)


def test_frozen_duplicate_self_consistency_captures_disagreement(tmp_path: Path) -> None:
    primary = [_case(case_id="c1", status="AGREED", initial=("PASS", "PASS"))]
    dup = _case(case_id="c1__dup1", status="AGREED", initial=("PASS", "FAIL"))
    dup["frozen_duplicate"] = True
    dup["duplicate_of"] = "c1"
    _write(tmp_path, [*primary, dup])
    result = analyze(tmp_path)
    assert result["case_count"] == 1
    sc = result["frozen_duplicate_self_consistency"]
    assert sc["rate"] == pytest.approx(0.5)
