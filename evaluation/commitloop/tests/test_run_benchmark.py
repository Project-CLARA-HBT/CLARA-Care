from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from evaluation.commitloop import run_benchmark
from evaluation.commitloop.fixtures import DeterministicFakeTransport, synthetic_bundle
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.run_benchmark import run_phase_b_benchmark
from evaluation.commitloop.validate import validate_run


def _clients(transport, limits: RunLimits) -> dict[str, EvaluationClient]:
    return {
        model: EvaluationClient(
            base_url="https://router.invalid/v1",
            api_key="phase-b-fixture-token",
            transport=transport,
            limits=limits,
        )
        for model in (GENERATOR_MODEL, REVIEWER_MODEL)
    }


def _probe(path, freeze_sha: str) -> None:
    results = []
    for model in (GENERATOR_MODEL, REVIEWER_MODEL):
        results.append(
            {
                "requested_model_id": model,
                "reported_model_id": REPORTED_MODEL_ID_BY_REQUESTED[model],
                "json_contract_supported": True,
                "stream_requested": False,
                "streaming_behavior": "non_streaming_response",
                "base_url_sha256": "a" * 64,
            }
        )
    path.write_text(
        json.dumps(
            {
                "schema_version": "commitloop-provider-probe.v2",
                "phase_a_freeze_sha": freeze_sha,
                "requested_models": sorted([GENERATOR_MODEL, REVIEWER_MODEL]),
                "exact_model_policy": "reported_must_match_declared_mapping",
                "reported_model_mapping": REPORTED_MODEL_ID_BY_REQUESTED,
                "fallback_allowed": False,
                "results": results,
            }
        )
    )


def test_phase_b_runner_is_freeze_and_probe_bound_with_fake_transport(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze_sha = "b" * 40
    freeze_dir = tmp_path / "phase-a"
    freeze_dir.mkdir()
    freeze_path = freeze_dir / "implementation_freeze.json"
    freeze_path.write_text("{}")
    probe_path = tmp_path / "probe.json"
    _probe(probe_path, freeze_sha)
    monkeypatch.setattr(
        run_benchmark,
        "_freeze",
        lambda *_args, **_kwargs: {"git_sha": freeze_sha},
    )
    limits = RunLimits(max_subjects=2, max_cases=20, max_requests=500, checkpoint_every=3)
    transport = DeterministicFakeTransport()
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    output = tmp_path / "phase-b"

    manifest = run_phase_b_benchmark(
        freeze_path=freeze_path,
        probe_path=probe_path,
        output_dir=output,
        bundles=[
            (synthetic_bundle("synthetic-a", "a"), "R4"),
            (synthetic_bundle("synthetic-b", "b"), "R4"),
        ],
        clients=_clients(transport, limits),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
        repository_root=tmp_path,
    )

    assert manifest["execution_mode"] == "phase_b_router"
    assert manifest["phase_a_freeze_sha"] == freeze_sha
    assert manifest["provider_probe_sha256"] == hashlib.sha256(probe_path.read_bytes()).hexdigest()
    assert manifest["source_case_count"] == 2
    assert manifest["variant_case_count"] == 18
    assert manifest["request_count"] == 364
    assert transport.call_count == 364
    assert (
        json.loads((output / "validation_report.json").read_text())["external_calls"]
        == "ROUTER_PHASE_B"
    )
    assert "post-freeze evaluation router" in (output / "report.md").read_text()
    validate_run(output)


def test_phase_b_runner_rejects_probe_mismatch_before_transport(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze_sha = "c" * 40
    freeze_dir = tmp_path / "phase-a"
    freeze_dir.mkdir()
    freeze_path = freeze_dir / "implementation_freeze.json"
    freeze_path.write_text("{}")
    probe_path = tmp_path / "probe.json"
    _probe(probe_path, "d" * 40)
    monkeypatch.setattr(
        run_benchmark,
        "_freeze",
        lambda *_args, **_kwargs: {"git_sha": freeze_sha},
    )
    limits = RunLimits(max_subjects=1, max_cases=1, max_requests=20)
    transport = DeterministicFakeTransport()
    with pytest.raises(ValueError, match="phase_b_probe_freeze_mismatch"):
        run_phase_b_benchmark(
            freeze_path=freeze_path,
            probe_path=probe_path,
            output_dir=tmp_path / "phase-b",
            bundles=[(synthetic_bundle("synthetic-a", "a"), "R4")],
            clients=_clients(transport, limits),
            valid_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
            known_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
            limits=limits,
            repository_root=tmp_path,
        )
    assert transport.call_count == 0


def test_phase_b_runner_refuses_to_modify_phase_a_seal(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze_sha = "e" * 40
    freeze_dir = tmp_path / "phase-a"
    freeze_dir.mkdir()
    freeze_path = freeze_dir / "implementation_freeze.json"
    freeze_path.write_text("{}")
    probe_path = tmp_path / "probe.json"
    _probe(probe_path, freeze_sha)
    monkeypatch.setattr(
        run_benchmark,
        "_freeze",
        lambda *_args, **_kwargs: {"git_sha": freeze_sha},
    )
    limits = RunLimits(max_subjects=1, max_cases=1, max_requests=20)
    transport = DeterministicFakeTransport()
    with pytest.raises(ValueError, match="phase_b_output_must_not_modify_phase_a_seal"):
        run_phase_b_benchmark(
            freeze_path=freeze_path,
            probe_path=probe_path,
            output_dir=freeze_dir / "phase-b",
            bundles=[(synthetic_bundle("synthetic-a", "a"), "R4")],
            clients=_clients(transport, limits),
            valid_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
            known_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
            limits=limits,
            repository_root=tmp_path,
        )
    assert transport.call_count == 0
