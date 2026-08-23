"""Unit and integration tests for Evaluation Hardening & Staging (EVAL-MAN-01, EVAL-ATOMIC-01)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Self

import pytest

from evaluation.model_adjudication.analyze_v2 import analyze
from evaluation.model_adjudication.reconcile_v2 import _load_run_manifest, reconcile
from evaluation.model_adjudication.run_v2 import (
    BASE_URL,
    MODELS,
    RUN_VERSION,
    run,
)


class _FakeHeaders:
    def get_content_type(self) -> str:
        return "application/json"


class _FakeResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self.headers = _FakeHeaders()
        self.status = status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def _review_payload(label: str = "PASS", rationale: str = "ok", confidence: float = 0.9) -> bytes:
    review = {
        "label": label,
        "rationale": rationale,
        "evidence_ids": ["e1", "e2"],
        "confidence": confidence,
    }
    return json.dumps({"choices": [{"message": {"content": json.dumps(review)}}]}).encode()


def _make_manifest(*, case_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "clara-model-review-manifest.v2",
        "status": "frozen",
        "study_id": "hardening-test",
        "models": list(MODELS),
        "protocols": {"safety": {"allowed_labels": ["PASS", "FAIL"]}},
        "rubric": {"dimensions": ["safety"]},
        "cases": [
            {
                "case_id": cid,
                "protocol": "safety",
                "evidence": {"e1": {"text": f"text-{cid}-1"}, "e2": {"text": f"text-{cid}-2"}},
            }
            for cid in case_ids
        ],
    }


def _make_raw_case_row(
    case_id: str, left_label: str = "PASS", right_label: str = "PASS"
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "protocol": "safety",
        "allowed_labels": ["PASS", "FAIL"],
        "evidence_ids": ["e1", "e2"],
        "prompt_sha256": "0" * 64,
        "rubric_sha256": "1" * 64,
        "router_base_url": BASE_URL,
        "decoding": {"temperature": 0, "stream": False},
        "reviews": [
            {
                "model_id": MODELS[0],
                "reviewer_id": "reviewer_a",
                "provider": {
                    "router_base_url": BASE_URL,
                    "http_status": 200,
                    "content_type": "application/json",
                    "raw_http_body_sha256": "a" * 64,
                    "parsed_review_sha256": f"sha-a-{case_id}-{left_label}",
                },
                "review": {
                    "label": left_label,
                    "rationale": "rationale a",
                    "evidence_ids": ["e1", "e2"],
                    "confidence": 0.9,
                },
            },
            {
                "model_id": MODELS[1],
                "reviewer_id": "reviewer_b",
                "provider": {
                    "router_base_url": BASE_URL,
                    "http_status": 200,
                    "content_type": "application/json",
                    "raw_http_body_sha256": "b" * 64,
                    "parsed_review_sha256": f"sha-b-{case_id}-{right_label}",
                },
                "review": {
                    "label": right_label,
                    "rationale": "rationale b",
                    "evidence_ids": ["e1", "e2"],
                    "confidence": 0.9,
                },
            },
        ],
    }


@pytest.fixture(autouse=True)
def _router_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLARA_ROUTER_API_KEY", "test-key-not-committed")


# ==============================================================================
# EVAL-MAN-01 Tests: Schema-valid run manifest enforcement & extra file ignoring
# ==============================================================================


def test_manifest_validation_accepts_valid_manifest(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    c1_row = _make_raw_case_row("c1", "PASS", "PASS")
    c1_file = raw_dir / "c1.json"
    c1_bytes = (json.dumps(c1_row, indent=2, sort_keys=True) + "\n").encode()
    c1_file.write_bytes(c1_bytes)

    manifest_data = {
        "schema_version": "clara-model-review-run.v2",
        "status": "independent_reviews_complete",
        "manifest_sha256": "m" * 64,
        "rubric_sha256": "r" * 64,
        "models": list(MODELS),
        "router_base_url": BASE_URL,
        "case_count": 1,
        "raw_outputs": ["raw/c1.json"],
        "raw_inventory": [
            {
                "case_id": "c1",
                "path": "raw/c1.json",
                "sha256": hashlib.sha256(c1_bytes).hexdigest(),
                "terminal_state": "completed",
            }
        ],
    }
    manifest_path = tmp_path / "model_review_results.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    manifest, case_paths = _load_run_manifest(manifest_path, raw_dir)
    assert manifest["schema_version"] == "clara-model-review-run.v2"
    assert len(case_paths) == 1
    assert case_paths[0].resolve() == c1_file.resolve()


def test_manifest_validation_rejects_missing_file(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    manifest_data = {
        "schema_version": "clara-model-review-run.v2",
        "status": "independent_reviews_complete",
        "case_count": 1,
        "raw_inventory": [
            {
                "case_id": "c_missing",
                "path": "raw/c_missing.json",
                "sha256": "0" * 64,
                "terminal_state": "completed",
            }
        ],
    }
    manifest_path = tmp_path / "model_review_results.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ValueError, match="model_review_manifest_file_missing"):
        _load_run_manifest(manifest_path, raw_dir)


def test_manifest_validation_rejects_sha_mismatch(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    c1_file = raw_dir / "c1.json"
    c1_file.write_text(json.dumps(_make_raw_case_row("c1")), encoding="utf-8")

    manifest_data = {
        "schema_version": "clara-model-review-run.v2",
        "status": "independent_reviews_complete",
        "case_count": 1,
        "raw_inventory": [
            {
                "case_id": "c1",
                "path": "raw/c1.json",
                "sha256": "wrong_hash_" + "0" * 53,
                "terminal_state": "completed",
            }
        ],
    }
    manifest_path = tmp_path / "model_review_results.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ValueError, match="model_review_manifest_sha_mismatch:c1"):
        _load_run_manifest(manifest_path, raw_dir)


def test_manifest_validation_rejects_non_terminal_status(tmp_path: Path) -> None:
    manifest_data = {
        "schema_version": "clara-model-review-run.v2",
        "status": "in_progress",
        "case_count": 1,
        "raw_inventory": [],
    }
    manifest_path = tmp_path / "model_review_results.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ValueError, match="model_review_manifest_not_terminal:in_progress"):
        _load_run_manifest(manifest_path, tmp_path)


def test_manifest_validation_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    manifest_data = {
        "schema_version": "clara-model-review-run.v1",
        "status": "independent_reviews_complete",
        "case_count": 1,
        "raw_inventory": [],
    }
    manifest_path = tmp_path / "model_review_results.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ValueError, match="model_review_manifest_schema_version_unsupported"):
        _load_run_manifest(manifest_path, tmp_path)


def test_reconciliation_ignores_extra_non_case_files(tmp_path: Path) -> None:
    """Extra JSON files in raw_dir (manifest, summary, random json) must not contaminate or crash reconciliation."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    out_dir = tmp_path / "reconciled"

    # Create valid case c1
    c1_row = _make_raw_case_row("c1", "PASS", "PASS")
    c1_bytes = (json.dumps(c1_row, indent=2, sort_keys=True) + "\n").encode()
    (raw_dir / "c1.json").write_bytes(c1_bytes)

    # Create extra non-case JSON files in raw_dir
    (raw_dir / "summary_report.json").write_text(
        json.dumps({"total_summary": True, "notes": "ignore me"}), encoding="utf-8"
    )
    (raw_dir / "audit_manifest.json").write_text(
        json.dumps({"version": 1, "extra": "data"}), encoding="utf-8"
    )
    (raw_dir / "arbitrary_garbage.json").write_text(
        json.dumps({"unexpected": [1, 2, 3]}), encoding="utf-8"
    )

    manifest_data = {
        "schema_version": "clara-model-review-run.v2",
        "status": "independent_reviews_complete",
        "manifest_sha256": "m" * 64,
        "rubric_sha256": "r" * 64,
        "models": list(MODELS),
        "router_base_url": BASE_URL,
        "case_count": 1,
        "raw_outputs": ["raw/c1.json"],
        "raw_inventory": [
            {
                "case_id": "c1",
                "path": "raw/c1.json",
                "sha256": hashlib.sha256(c1_bytes).hexdigest(),
                "terminal_state": "completed",
            }
        ],
    }
    manifest_path = tmp_path / "model_review_results.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    summary = reconcile(
        raw_dir=raw_dir,
        output_dir=out_dir,
        manifest_path=manifest_path,
        urlopen=lambda _req, **_kw: _FakeResponse(_review_payload("PASS")),
    )

    assert summary["case_count"] == 1
    assert summary["unresolved_count"] == 0
    assert (out_dir / "c1.json").exists()
    assert not (out_dir / "summary_report.json").exists()
    assert not (out_dir / "arbitrary_garbage.json").exists()


# ==============================================================================
# EVAL-ATOMIC-01 Tests: Staging directory, atomic promotion, crash-resume
# ==============================================================================


def test_run_v2_staging_and_atomic_promotion(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_make_manifest(case_ids=["case_1", "case_2"])))
    out_dir = tmp_path / "run_out"

    fake_resp = _FakeResponse(_review_payload("PASS"))
    summary = run(
        manifest_path=manifest_path,
        output_dir=out_dir,
        urlopen=lambda _req, **_kw: fake_resp,
    )

    assert summary["case_count"] == 2
    assert summary["status"] == "independent_reviews_complete"
    assert out_dir.exists()
    assert not (tmp_path / "run_out.staging").exists()
    assert (out_dir / "raw" / "case_1.json").exists()
    assert (out_dir / "raw" / "case_2.json").exists()
    assert (out_dir / "model_review_results.json").exists()

    results = json.loads((out_dir / "model_review_results.json").read_text())
    assert len(results["raw_inventory"]) == 2
    for item in results["raw_inventory"]:
        assert item["terminal_state"] == "completed"
        assert item["sha256"]


def test_run_v2_resumes_from_journal_producing_same_sealed_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kill process after case k, resume once, obtain same sealed digest as uninterrupted run."""
    manifest_data = _make_manifest(case_ids=["case_a", "case_b", "case_c"])
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data))

    # Provide deterministic _call behavior across runs
    called_cases: list[str] = []

    def deterministic_call(
        *,
        model: str,
        prompt: str,
        allowed_labels: tuple[str, ...],
        available_evidence_ids: list[str],
        retries: int = 2,
        urlopen: Any = None,
    ) -> dict[str, Any]:
        for cid in ("case_a", "case_b", "case_c"):
            if f"text-{cid}" in prompt:
                called_cases.append(cid)
        return {
            "model_id": model,
            "timestamp_utc": "2026-08-23T00:00:00Z",
            "attempts": 1,
            "latency_ms": 10.0,
            "decoding": {"temperature": 0, "stream": False},
            "provider": {
                "router_base_url": BASE_URL,
                "http_status": 200,
                "content_type": "application/json",
                "raw_http_body_sha256": "0" * 64,
                "parsed_review_sha256": "1" * 64,
            },
            "review": {
                "label": "PASS",
                "rationale": "deterministic rationale",
                "evidence_ids": available_evidence_ids,
                "confidence": 0.95,
            },
        }

    monkeypatch.setattr(
        "evaluation.model_adjudication.run_v2._call", deterministic_call
    )

    # 1. Produce golden uninterrupted run
    golden_dir = tmp_path / "golden_run"
    golden_summary = run(
        manifest_path=manifest_path,
        output_dir=golden_dir,
    )

    golden_results_file = golden_dir / "model_review_results.json"
    golden_results_bytes = golden_results_file.read_bytes()
    golden_digest = hashlib.sha256(golden_results_bytes).hexdigest()

    # 2. Simulate partial run by creating a staging dir with only 1 case completed in journal
    resumed_dir = tmp_path / "resumed_run"
    staging_dir = tmp_path / "resumed_run.staging"
    staging_raw = staging_dir / "raw"
    staging_raw.mkdir(parents=True)

    # Read case_a row from golden run to simulate pre-existing completed case_a
    case_a_golden_text = (golden_dir / "raw" / "case_a.json").read_text()
    case_a_row = json.loads(case_a_golden_text)
    (staging_raw / "case_a.json").write_text(case_a_golden_text)

    journal_path = staging_dir / "journal.jsonl"
    journal_entry = (
        json.dumps({"case_id": "case_a", "record": case_a_row}, sort_keys=True) + "\n"
    )
    journal_path.write_text(journal_entry)

    called_cases.clear()

    resumed_summary = run(
        manifest_path=manifest_path,
        output_dir=resumed_dir,
    )

    # case_a was skipped due to journal resumption; case_b and case_c were called
    assert "case_a" not in called_cases
    assert "case_b" in called_cases
    assert "case_c" in called_cases

    # Verify identical output digest
    resumed_results_file = resumed_dir / "model_review_results.json"
    resumed_results_bytes = resumed_results_file.read_bytes()
    resumed_digest = hashlib.sha256(resumed_results_bytes).hexdigest()

    assert resumed_digest == golden_digest
    assert resumed_summary["case_count"] == golden_summary["case_count"]


def test_reconcile_v2_staging_and_resumption(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    out_dir = tmp_path / "reconciled"

    c1_row = _make_raw_case_row("c1", "PASS", "PASS")
    c2_row = _make_raw_case_row("c2", "PASS", "FAIL")

    (raw_dir / "c1.json").write_text(json.dumps(c1_row, indent=2, sort_keys=True) + "\n")
    (raw_dir / "c2.json").write_text(json.dumps(c2_row, indent=2, sort_keys=True) + "\n")

    summary = reconcile(
        raw_dir=raw_dir,
        output_dir=out_dir,
        urlopen=lambda _req, **_kw: _FakeResponse(_review_payload("PASS")),
    )

    assert summary["case_count"] == 2
    assert summary["unresolved_count"] == 0
    assert out_dir.exists()
    assert not (tmp_path / "reconciled.staging").exists()
    assert (out_dir / "c1.json").exists()
    assert (out_dir / "c2.json").exists()


def test_analyze_v2_ignores_non_case_files(tmp_path: Path) -> None:
    """analyze_v2 must filter out summaries, manifests, and non-case files safely."""
    # Write valid cases
    (tmp_path / "c1.json").write_text(
        json.dumps(
            {
                "case_id": "c1",
                "status": "AGREED",
                "reviews": [
                    {"review": {"label": "PASS"}},
                    {"review": {"label": "PASS"}},
                ],
            }
        )
    )
    (tmp_path / "c2.json").write_text(
        json.dumps(
            {
                "case_id": "c2",
                "status": "AGREED",
                "reviews": [
                    {"review": {"label": "FAIL"}},
                    {"review": {"label": "FAIL"}},
                ],
            }
        )
    )
    # Write non-case json files
    (tmp_path / "model_review_results.json").write_text(
        json.dumps({"schema_version": RUN_VERSION, "status": "completed"})
    )
    (tmp_path / "reconcile_summary.json").write_text(
        json.dumps({"schema_version": "clara-model-reconcile.v2", "case_count": 2})
    )

    result = analyze(tmp_path)
    assert result["case_count"] == 2
    assert result["initial_agreement"] == 1.0
