from __future__ import annotations

import json

import pytest

from evaluation.commitloop import provider_probe
from evaluation.commitloop.cli import _local_fixture
from evaluation.commitloop.freeze import FreezeError
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.provider_probe import run_probe


class ProbeTransport:
    def __call__(self, path, headers, payload, timeout):
        del path, headers, timeout
        return {
            "model": REPORTED_MODEL_ID_BY_REQUESTED[payload["model"]],
            "choices": [{"message": {"content": json.dumps({"status": "ok"})}}],
            "usage": {"total_tokens": 3},
        }


def _clients() -> dict[str, EvaluationClient]:
    return {
        model: EvaluationClient(
            base_url="https://router.invalid/v1",
            api_key="fixture-only-token",
            transport=ProbeTransport(),
            limits=RunLimits(max_requests=2),
        )
        for model in (GENERATOR_MODEL, REVIEWER_MODEL)
    }


def test_probe_requires_sealed_phase_a_freeze_and_records_exact_models(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase_a = tmp_path / "phase-a"
    phase_a.mkdir()
    freeze = phase_a / "implementation_freeze.json"
    freeze.write_text(
        json.dumps(
            {
                "phase_a_status": "COMPLETE",
                "router_calls_before_freeze": 0,
                "git_sha": "synthetic-clean-sha",
            }
        )
    )
    validated: list[object] = []
    monkeypatch.setattr(provider_probe, "validate_run", validated.append)
    monkeypatch.setattr(provider_probe, "verify_live_repository_matches_freeze", lambda *_: None)
    output = tmp_path / "phase-b" / "probe.json"
    result = run_probe(freeze_path=freeze, output=output, clients=_clients())
    assert validated == [phase_a]
    assert result["requested_models"] == sorted([GENERATOR_MODEL, REVIEWER_MODEL])
    assert all(
        item["reported_model_id"] == REPORTED_MODEL_ID_BY_REQUESTED[item["requested_model_id"]]
        for item in result["results"]
    )
    assert result["schema_version"] == "commitloop-provider-probe.v2"
    assert result["fallback_allowed"] is False
    assert result["reported_model_mapping"] == REPORTED_MODEL_ID_BY_REQUESTED
    assert all(item["json_contract_supported"] is True for item in result["results"])
    assert all(item["stream_requested"] is False for item in result["results"])
    assert all(len(item["base_url_sha256"]) == 64 for item in result["results"])
    assert "fixture-only-token" not in output.read_text()
    assert "https://router.invalid" not in output.read_text()
    assert json.loads(output.read_text())["phase_a_freeze_sha"] == "synthetic-clean-sha"


def test_probe_rejects_incomplete_phase_a_freeze(tmp_path) -> None:
    freeze = tmp_path / "implementation_freeze.json"
    freeze.write_text(
        json.dumps({"phase_a_status": "IN_PROGRESS", "router_calls_before_freeze": 0})
    )
    with pytest.raises(ValueError, match="phase_a_freeze_required"):
        run_probe(
            freeze_path=freeze,
            output=tmp_path / "phase-b" / "probe.json",
            clients=_clients(),
        )


def test_probe_rejects_an_unsealed_freeze_before_transport(tmp_path) -> None:
    phase_a = tmp_path / "phase-a"
    _local_fixture(phase_a, max_requests=100)
    freeze = phase_a / "implementation_freeze.json"
    freeze.write_text(
        json.dumps(
            {
                "phase_a_status": "COMPLETE",
                "router_calls_before_freeze": 0,
                "git_sha": "synthetic-clean-sha",
            }
        )
    )
    clients = _clients()
    with pytest.raises(ValueError, match="artifact_seal_inventory_mismatch"):
        run_probe(
            freeze_path=freeze,
            output=tmp_path / "phase-b" / "probe.json",
            clients=clients,
        )
    assert all(client.request_count == 0 for client in clients.values())


def test_probe_rejects_repository_drift_before_transport(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze = tmp_path / "implementation_freeze.json"
    freeze.write_text(
        json.dumps(
            {
                "phase_a_status": "COMPLETE",
                "router_calls_before_freeze": 0,
                "git_sha": "synthetic-clean-sha",
            }
        )
    )
    monkeypatch.setattr(provider_probe, "validate_run", lambda *_: None)

    def reject_drift(*_args) -> None:
        raise FreezeError("phase_b_requires_clean_frozen_worktree")

    monkeypatch.setattr(provider_probe, "verify_live_repository_matches_freeze", reject_drift)
    clients = _clients()
    with pytest.raises(FreezeError, match="phase_b_requires_clean_frozen_worktree"):
        run_probe(
            freeze_path=freeze,
            output=tmp_path / "phase-b" / "probe.json",
            clients=clients,
        )
    assert all(client.request_count == 0 for client in clients.values())


def test_probe_refuses_to_mutate_the_sealed_phase_a_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase_a = tmp_path / "phase-a"
    phase_a.mkdir()
    freeze = phase_a / "implementation_freeze.json"
    freeze.write_text(
        json.dumps(
            {
                "phase_a_status": "COMPLETE",
                "router_calls_before_freeze": 0,
                "git_sha": "synthetic-clean-sha",
            }
        )
    )
    monkeypatch.setattr(provider_probe, "validate_run", lambda *_: None)
    monkeypatch.setattr(provider_probe, "verify_live_repository_matches_freeze", lambda *_: None)
    clients = _clients()
    with pytest.raises(ValueError, match="probe_output_must_not_modify_phase_a_seal"):
        run_probe(freeze_path=freeze, output=phase_a / "probe.json", clients=clients)
    assert all(client.request_count == 0 for client in clients.values())
