from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.governance_adversarial import isolated_boundary_adapter as adapter


def _case(family: str = "stale_thss_replay") -> dict[str, object]:
    return {"case_id": "case-1", "family": family, "oracle": {"sentinel_token": "RIVF_SENTINEL_001"}}


def _arm() -> dict[str, object]:
    return {"name": "GLHS_STRICT", "bind_snapshot": True, "revalidate_state": True, "revalidate_governance": True, "research_only": True}


def _configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-test")
    monkeypatch.setenv("GOVRED_RESEARCH_BASE_URL", "http://isolated")
    monkeypatch.setenv("GOVRED_POSTGRES_CONTAINER", "clara-rivf-test-postgres-1")
    monkeypatch.setenv("GOVRED_REDIS_CONTAINER", "clara-rivf-test-redis-1")
    monkeypatch.setenv("GOVRED_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setenv("GOVRED_IMPLEMENTATION_REVISION", "a" * 40)
    monkeypatch.setenv("ENV", "development")


def test_adapter_refuses_production_and_nonisolated_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError, match="forbidden_in_production"):
        adapter._config()
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-app")
    with pytest.raises(RuntimeError, match="project_attestation_invalid"):
        adapter._config()


def test_adapter_runs_http_commit_and_writes_sanitized_hash_bound_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    calls: list[tuple[str, str]] = []

    def request(_config, path, *, method="GET", body=None, token=None):
        calls.append((method, path))
        if path.endswith("/arm"):
            return 200, json.dumps({"arm": "GLHS_STRICT", "bind_snapshot": True, "revalidate_state": True, "revalidate_governance": True}).encode(), False
        if path.endswith("/register"):
            return 200, b"{}", False
        if path.endswith("/login"):
            return 200, b'{"access_token":"token"}', False
        if path.endswith("/consent-status"):
            return 200, b'{"required_version":"2026-04-v1"}', False
        if path.endswith("/consent"):
            return 200, b'{"consent_version":"2026-04-v1"}', False
        if "synthetic-audit-observation" in path:
            return 200, b'{"audit_reconstruction_complete":true}', False
        return 409, b'{"detail":{"code":"stale_state_version"}}', False

    monkeypatch.setattr(adapter, "_request", request)
    monkeypatch.setattr(adapter, "_snapshot", lambda _: {"postgres_sha256": "b" * 64, "redis_sha256": "c" * 64, "audit_sha256": "d" * 64})
    result = adapter.adapter(case=_case(), arm=_arm())

    assert result["normalized_outcome"] == "rejected"
    assert ("POST", "/api/v1/govred-research/synthetic-commit-probe") in calls
    observation = tmp_path / result["observation_artifact_ref"]
    artifact = json.loads(observation.read_text())
    assert artifact["raw_response_persisted"] is False
    assert "response_body" not in artifact["observation"]
    assert (tmp_path / result["arm_implementation_attestation"]["implementation_artifact_ref"]).is_file()


def test_adapter_uses_valid_synthetic_email_domain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    registered: list[dict[str, object]] = []

    def request(_config, path, *, method="GET", body=None, token=None):
        if path.endswith("/register"):
            assert body is not None and isinstance(body.get("email"), str)
            registered.append(body)
            return 200, b"{}", False
        if path.endswith("/login"):
            return 200, b'{"access_token":"token"}', False
        if path.endswith("/consent-status"):
            return 200, b'{"required_version":"2026-04-v1"}', False
        if path.endswith("/consent"):
            return 200, b'{"consent_version":"2026-04-v1"}', False
        if path.endswith("/arm"):
            return 200, json.dumps({"arm": "GLHS_STRICT", "bind_snapshot": True, "revalidate_state": True, "revalidate_governance": True}).encode(), False
        if "synthetic-audit-observation" in path:
            return 200, b'{"audit_reconstruction_complete":true}', False
        return 409, b'{"detail":{"code":"stale_state_version"}}', False

    monkeypatch.setattr(adapter, "_request", request)
    monkeypatch.setattr(adapter, "_snapshot", lambda _: {"postgres_sha256": "b" * 64, "redis_sha256": "c" * 64, "audit_sha256": "d" * 64})
    adapter.adapter(case=_case(), arm=_arm())
    email = str(registered[0]["email"])
    assert email.endswith("@example.org")


def test_adapter_grants_medical_consent_after_login(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    consent_calls: list[dict[str, object]] = []

    def request(_config, path, *, method="GET", body=None, token=None):
        if path.endswith("/register"):
            return 200, b"{}", False
        if path.endswith("/login"):
            return 200, b'{"access_token":"token"}', False
        if path.endswith("/consent-status"):
            return 200, b'{"required_version":"2026-04-v1"}', False
        if path.endswith("/consent"):
            consent_calls.append({"body": body, "method": method})
            return 200, b'{"consent_version":"2026-04-v1"}', False
        if path.endswith("/arm"):
            return 200, json.dumps({"arm": "GLHS_STRICT", "bind_snapshot": True, "revalidate_state": True, "revalidate_governance": True}).encode(), False
        if "synthetic-audit-observation" in path:
            return 200, b'{"audit_reconstruction_complete":true}', False
        return 409, b'{"detail":{"code":"stale_state_version"}}', False

    monkeypatch.setattr(adapter, "_request", request)
    monkeypatch.setattr(adapter, "_snapshot", lambda _: {"postgres_sha256": "b" * 64, "redis_sha256": "c" * 64, "audit_sha256": "d" * 64})
    adapter.adapter(case=_case(), arm=_arm())
    assert consent_calls
    assert consent_calls[0]["method"] == "POST"
    body = consent_calls[0]["body"]
    assert isinstance(body, dict) and body.get("accepted") is True
    assert body.get("consent_version") == "2026-04-v1"


def test_adapter_marks_unsupported_cross_subject_read_as_not_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    assert adapter.adapter(case=_case("cross_subject_retrieval"), arm=_arm()) == {"run_status": "NOT_RUN"}


def test_adapter_observes_service_owned_cache_reuse_around_revocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch, tmp_path)
    calls: list[tuple[str, str, str | None]] = []

    def request(_config, path, *, method="GET", body=None, token=None):
        phase = body.get("phase") if body else None
        calls.append((method, path, phase))
        if path.endswith("/register"):
            return 200, b"{}", False
        if path.endswith("/login"):
            return 200, b'{"access_token":"token"}', False
        if path.endswith("/consent-status"):
            return 200, b'{"required_version":"2026-04-v1"}', False
        if path.endswith("/consent"):
            return 200, b'{"consent_version":"2026-04-v1"}', False
        if path.endswith("/arm"):
            return 200, json.dumps({"arm": "GLHS_STRICT", "bind_snapshot": True, "revalidate_state": True, "revalidate_governance": True}).encode(), False
        if "synthetic-disclosure-cache-probe" in path and phase == "seed":
            return 200, b'{"cache_seeded":true}', False
        if path.endswith("/synthetic-commit-probe"):
            return 409, b'{"detail":{"code":"assertion_consent_mismatch"}}', False
        if "synthetic-audit-observation" in path:
            return 200, b'{"audit_reconstruction_complete":false}', False
        if "synthetic-disclosure-cache-probe" in path and phase == "read_after_revoke":
            return 200, b'{"cache_present_after_revoke":false}', False
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_request", request)
    monkeypatch.setattr(adapter, "_snapshot", lambda _: {"postgres_sha256": "b" * 64, "redis_sha256": "c" * 64, "audit_sha256": "d" * 64})

    result = adapter.adapter(case=_case("revoked_consent_cache_index_reuse"), arm=_arm())

    cache_calls = [call for call in calls if "synthetic-disclosure-cache-probe" in call[1]]
    commit_index = next(index for index, call in enumerate(calls) if call[1].endswith("/synthetic-commit-probe"))
    assert [call[2] for call in cache_calls] == ["seed", "read_after_revoke"]
    assert calls.index(cache_calls[0]) < commit_index < calls.index(cache_calls[1])
    assert result["observation"].cache_index_revocation_failure is False
    assert result["observation"].audit_reconstruction_complete is False
