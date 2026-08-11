from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.commitloop import generation_probe
from evaluation.commitloop.fixtures import DeterministicFakeTransport
from evaluation.commitloop.generation_probe import run_generation_probe
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REVIEWER_MODEL,
    EvaluationClient,
    RunLimits,
)


def _clients(transport: DeterministicFakeTransport) -> dict[str, EvaluationClient]:
    return {
        model: EvaluationClient(
            base_url="https://router.invalid/v1",
            api_key="fixture-only-token",
            transport=transport,
            limits=RunLimits(max_requests=5),
        )
        for model in (GENERATOR_MODEL, REVIEWER_MODEL)
    }


def test_generation_probe_is_bounded_source_safe_and_freeze_gated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generation_probe,
        "_phase_b_preflight",
        lambda **_: ("a" * 40, "b" * 64),
    )
    transport = DeterministicFakeTransport()
    output = tmp_path / "phase-b" / "generation-probe.json"
    result = run_generation_probe(
        freeze_path=tmp_path / "phase-a" / "implementation_freeze.json",
        probe_path=tmp_path / "phase-b" / "provider-probe.json",
        output=output,
        clients=_clients(transport),
        repository_root=tmp_path,
    )
    assert result["status"] == "ACCEPTED"
    assert result["request_count"] == result["max_request_count"] == 5
    assert result["result_summary"]["stage_count"] == 5
    assert result["result_summary"]["validator_decision"] == "DETERMINISTIC_ACCEPT"
    assert "candidate" not in result["result_summary"]
    assert "synthetic_note" not in result["result_summary"]
    assert json.loads(output.read_text()) == result
    assert transport.call_count == 5


def test_generation_probe_cannot_modify_phase_a_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generation_probe,
        "_phase_b_preflight",
        lambda **_: ("a" * 40, "b" * 64),
    )
    freeze_path = tmp_path / "phase-a" / "implementation_freeze.json"
    with pytest.raises(ValueError, match="must_not_modify_phase_a_seal"):
        run_generation_probe(
            freeze_path=freeze_path,
            probe_path=tmp_path / "provider-probe.json",
            output=freeze_path.parent / "generation-probe.json",
            clients=_clients(DeterministicFakeTransport()),
            repository_root=tmp_path,
        )
