from __future__ import annotations

import json
import subprocess

import pytest

from evaluation.governance_adversarial import development_boundary_probe as probe


def test_probe_records_sanitized_before_after_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe, "_identity", lambda *_: ("token", "profile"))
    monkeypatch.setattr(probe, "_request", lambda *_args, **_kwargs: (404, {"detail": {"code": "scope_forbidden"}}))
    snapshots = iter(
        (
            {"postgres_sha256": "a" * 64, "redis_sha256": "b" * 64, "audit_sha256": "c" * 64},
            {"postgres_sha256": "a" * 64, "redis_sha256": "b" * 64, "audit_sha256": "c" * 64},
        )
    )
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, json.dumps(next(snapshots))),
    )

    result = probe.run(base_url="http://isolated", observer_command=["observer"])

    assert result["cross_subject_scope_denied"] is True
    assert result["observer_before"] == result["observer_after"]


def test_observer_rejects_non_sanitized_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, '{"postgres_sha256":"raw"}'),
    )
    with pytest.raises(RuntimeError, match="govred_observer_shape_invalid"):
        probe._snapshot(["observer"])
