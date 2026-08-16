from __future__ import annotations

import hashlib

import pytest

from evaluation.governance_adversarial import remote_store_observer as observer


def test_observer_hashes_store_outputs_without_returning_them(monkeypatch) -> None:
    calls: list[list[str]] = []

    def capture(command: list[str]) -> bytes:
        calls.append(command)
        return b"synthetic-store-state"

    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setattr(observer, "_capture", capture)
    result = observer.observe(
        postgres_container="clara-rivf-dev-postgres-1",
        redis_container="clara-rivf-dev-redis-1",
        redis_pattern="govred-run:*",
    )

    assert set(result) == {"postgres_sha256", "redis_sha256", "audit_sha256"}
    assert all(len(value) == 64 for value in result.values())
    assert all("clara-rivf-dev" in " ".join(call) for call in calls)


def test_observer_postgres_signature_covers_glhs_commit_and_assertion_tables(monkeypatch) -> None:
    commands: list[list[str]] = []

    def capture(command: list[str]) -> bytes:
        commands.append(command)
        return b"synthetic-store-state"

    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setattr(observer, "_capture", capture)
    observer.observe(
        postgres_container="clara-rivf-dev-postgres-1",
        redis_container="clara-rivf-dev-redis-1",
        redis_pattern="govred-run:*",
    )
    postgres_command = " ".join(commands[0])
    for table in (
        "glhs_assertions",
        "glhs_transitions",
        "glhs_snapshot_manifests",
        "glhs_clinical_commitment_proposals",
        "glhs_clinical_commitment_versions",
        "glhs_clinical_commitment_transitions",
    ):
        assert table in postgres_command


def test_observer_requires_explicit_isolated_research_attestation() -> None:
    with pytest.raises(RuntimeError, match="requires_isolated_research_attestation"):
        observer.observe(
            postgres_container="clara-rivf-dev-postgres-1",
            redis_container="clara-rivf-dev-redis-1",
            redis_pattern="govred-run:*",
        )


def test_observer_rejects_container_outside_isolated_project(monkeypatch) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")

    with pytest.raises(RuntimeError, match="container_outside_isolated_project"):
        observer.observe(
            postgres_container="clara-app-postgres-1",
            redis_container="clara-rivf-dev-redis-1",
            redis_pattern="govred-run:*",
        )


def test_observer_canonicalizes_redis_scan_order(monkeypatch) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")

    def capture(command: list[str]) -> bytes:
        if "redis-cli" in command:
            return b"govred-run:z\ngovred-run:a\n"
        return b"synthetic-postgres"

    monkeypatch.setattr(observer, "_capture", capture)
    result = observer.observe(
        postgres_container="clara-rivf-dev-postgres-1",
        redis_container="clara-rivf-dev-redis-1",
        redis_pattern="govred-run:*",
    )

    assert result["redis_sha256"] == hashlib.sha256(b"govred-run:a\ngovred-run:z").hexdigest()
