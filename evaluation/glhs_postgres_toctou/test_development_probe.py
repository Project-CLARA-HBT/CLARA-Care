from __future__ import annotations

from types import SimpleNamespace

import pytest

from evaluation.glhs_postgres_toctou.development_probe import (
    _binding_digest,
    _classify_concurrent_commit_order,
    _require_isolated_postgres,
)


def test_probe_requires_explicit_isolation_attestation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GLHS_TOCTOU_ISOLATED_RESEARCH", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="glhs_toctou_requires_isolated_research_attestation"):
        _require_isolated_postgres()


def test_probe_refuses_a_pre_binding_snapshot_contract() -> None:
    with pytest.raises(RuntimeError, match="snapshot_manifest_digest_contract_unavailable"):
        _binding_digest(SimpleNamespace(snapshot_id="legacy"))


def test_probe_accepts_only_manifest_digest_binding() -> None:
    assert _binding_digest(SimpleNamespace(manifest_digest="a" * 64)) == (
        "a" * 64,
        "manifest_digest",
    )


def test_probe_rejects_non_postgres_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLHS_TOCTOU_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    with pytest.raises(RuntimeError, match="glhs_toctou_requires_postgresql_database_url"):
        _require_isolated_postgres()


def test_concurrent_commit_classifier_does_not_hide_a_post_revoke_commit() -> None:
    assert _classify_concurrent_commit_order(
        outcome="transition_committed",
        revoke_commit_ns=10,
        commit_start_ns=11,
        commit_complete_ns=12,
    ) == ("forbidden_transition_committed_after_observed_revoke", True)


def test_concurrent_commit_classifier_keeps_overlapping_commit_indeterminate() -> None:
    assert _classify_concurrent_commit_order(
        outcome="transition_committed",
        revoke_commit_ns=12,
        commit_start_ns=10,
        commit_complete_ns=13,
    ) == ("indeterminate_ordering_transition_committed", None)
