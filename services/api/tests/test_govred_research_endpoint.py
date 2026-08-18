"""Contract tests for the isolated HTTP-facing synthetic GovRed primitive."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import clara_api.api.v1.endpoints.govred_research as govred_module
from clara_api.api.v1.endpoints.govred_research import (
    SyntheticCacheProbeRequest,
    SyntheticCommitProbeRequest,
    synthetic_audit_observation,
    synthetic_commit_probe,
    synthetic_disclosure_cache_probe,
)
from clara_api.core.consent import MEDICAL_CONSENT_TYPE, required_medical_disclaimer_version
from clara_api.core.security import TokenPayload
from clara_api.db.base import Base
from clara_api.db.models import PhrProfile, User, UserConsent


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="govred-http@example.test", hashed_password="x", role="normal")
        session.add(user)
        session.flush()
        session.add(PhrProfile(user_id=user.id))
        session.add(UserConsent(
            user_id=user.id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
        ))
        session.commit()
        yield session


def _configure_arm(monkeypatch: pytest.MonkeyPatch, arm: str) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", arm)
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("ENV", "development")


def _token() -> TokenPayload:
    return TokenPayload({"sub": "govred-http@example.test", "role": "normal"})


def _probe(mutation: str, sentinel: str, **kwargs) -> SyntheticCommitProbeRequest:
    return SyntheticCommitProbeRequest(mutation=mutation, sentinel_id=sentinel, **kwargs)


class _MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def available(self) -> bool:
        return True

    def set_bytes(self, key: str, value: bytes, *, ttl_seconds: int) -> bool:
        assert ttl_seconds > 0
        self.values[key] = value
        return True

    def get_bytes(self, key: str) -> bytes | None:
        return self.values.get(key)

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)


def test_state_only_http_primitive_commits_after_synthetic_consent_revoke(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "STATE_VERSION_ONLY")

    result = synthetic_commit_probe(
        _probe("consent_revoke", "sentinel01"),
        db,
        _token(),
    )

    assert result["arm"] == "STATE_VERSION_ONLY"
    assert result["outcome"] == "transition_committed"


def test_strict_http_primitive_rejects_synthetic_consent_revoke(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("consent_revoke", "sentinel02"),
            db,
            _token(),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {"code": "assertion_consent_mismatch"}


def test_state_only_http_primitive_rejects_stale_synthetic_state(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "STATE_VERSION_ONLY")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("state_advance", "sentinel03"),
            db,
            _token(),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {"code": "stale_state_version"}


def test_unbound_http_primitive_admits_stale_synthetic_state(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "UNBOUND")

    result = synthetic_commit_probe(
        _probe("state_advance", "sentinel04"),
        db,
        _token(),
    )

    assert result["arm"] == "UNBOUND"
    assert result["outcome"] == "transition_committed"


def test_every_arm_rejects_subject_cross_replay(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    for arm in ("UNBOUND", "STATE_VERSION_ONLY", "SNAPSHOT_BOUND_STATE_ONLY", "GLHS_STRICT"):
        _configure_arm(monkeypatch, arm)
        with pytest.raises(HTTPException) as raised:
            synthetic_commit_probe(
                _probe("subject_cross_replay", "sentinel07"),
                db,
                _token(),
            )
        assert raised.value.status_code == 409
        assert raised.value.detail == {"code": "assertion_scope_forbidden"}


def test_digest_tamper_attempt_rejected_by_ledger_immutability(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The unit-test store has no alembic DB triggers, so the tamper reaches the
    # storage layer and the *admission* digest revalidation rejects the commit.
    # On the real PostgreSQL boundary the persistence trigger blocks the tamper
    # before admission (``ledger_tampering_rejected``).
    _configure_arm(monkeypatch, "GLHS_STRICT")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("snapshot_digest_invalid", "sentinel08"),
            db,
            _token(),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {"code": "proposal_manifest_digest_mismatch"}


def test_digest_mutation_rejected_for_unbound_arm(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "UNBOUND")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("snapshot_digest_invalid", "sentinel09"),
            db,
            _token(),
        )

    assert raised.value.status_code == 400
    assert raised.value.detail == {"code": "mutation_not_applicable_to_arm"}


def test_snapshot_bound_state_only_commits_after_actor_switch(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The state/snapshot arm deliberately omits governance revalidation, so a
    # delegate replaying the owner's bound proposal is admitted.
    _configure_arm(monkeypatch, "SNAPSHOT_BOUND_STATE_ONLY")

    result = synthetic_commit_probe(
        _probe("actor_switch_replay", "sentinel11"),
        db,
        _token(),
    )

    assert result["outcome"] == "transition_committed"
    assert result["audit_observation"]["snapshot_linked"] is True


def test_strict_primitive_rejects_actor_switch_replay(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("actor_switch_replay", "sentinel12"),
            db,
            _token(),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {"code": "proposal_snapshot_actor_mismatch"}


def test_unbound_primitive_commits_actor_switch_without_snapshot(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "UNBOUND")

    result = synthetic_commit_probe(
        _probe("actor_switch_replay", "sentinel13"),
        db,
        _token(),
    )

    assert result["outcome"] == "transition_committed"
    assert result["audit_observation"]["snapshot_linked"] is False


def test_concurrent_writer_requires_postgres(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("concurrent_governance_writer", "sentinel14"),
            db,
            _token(),
        )

    assert raised.value.status_code == 400
    assert raised.value.detail == {"code": "mutation_requires_postgres"}


def test_two_phase_expiry_flow_rejects_expired_snapshot_under_strict(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    created = synthetic_commit_probe(
        _probe("snapshot_expired", "sentinel20", phase="create", snapshot_expires_in_seconds=1),
        db,
        _token(),
    )
    assert created["phase"] == "create"
    assert created["snapshot_public_id"] is not None

    time.sleep(1.6)

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe(
                "snapshot_expired",
                "sentinel20",
                phase="commit",
                probe_id=created["probe_id"],
            ),
            db,
            _token(),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {"code": "proposal_snapshot_expired"}


def test_two_phase_expiry_guard_rejects_not_yet_expired_snapshot(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    created = synthetic_commit_probe(
        _probe("snapshot_expired", "sentinel21", phase="create", snapshot_expires_in_seconds=300),
        db,
        _token(),
    )

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe(
                "snapshot_expired",
                "sentinel21",
                phase="commit",
                probe_id=created["probe_id"],
            ),
            db,
            _token(),
        )

    assert raised.value.status_code == 400
    assert raised.value.detail == {"code": "snapshot_not_yet_expired"}


def test_full_phase_expiry_flow_requires_two_phase(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("snapshot_expired", "sentinel22"),
            db,
            _token(),
        )

    assert raised.value.status_code == 400
    assert raised.value.detail == {"code": "mutation_requires_two_phase"}


def test_full_phase_policy_change_requires_two_phase(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("policy_version_change", "sentinel23"),
            db,
            _token(),
        )

    assert raised.value.status_code == 400
    assert raised.value.detail == {"code": "mutation_requires_two_phase"}


def test_commit_phase_requires_existing_proposal(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("none", "sentinel24", phase="commit", probe_id="missingprobeid"),
            db,
            _token(),
        )

    assert raised.value.status_code == 404
    assert raised.value.detail == {"code": "proposal_not_found"}


def test_strict_cache_probe_invalidates_after_persisted_revoke(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")
    cache = _MemoryCache()
    monkeypatch.setattr(govred_module, "_research_cache_store", lambda: cache)
    request = SyntheticCacheProbeRequest(
        phase="seed", sentinel_id="sentinel25", probe_id="cacheprobe25"
    )

    seeded = synthetic_disclosure_cache_probe(request, db, _token())
    assert seeded["cache_seeded"] is True

    owner = db.query(User).filter(User.email == "govred-http@example.test").one()
    db.add(UserConsent(
        user_id=owner.id,
        consent_type=MEDICAL_CONSENT_TYPE,
        consent_version=required_medical_disclaimer_version(),
        revoked_at=datetime.now(UTC),
    ))
    db.commit()

    observed = synthetic_disclosure_cache_probe(
        SyntheticCacheProbeRequest(
            phase="read_after_revoke", sentinel_id="sentinel25", probe_id="cacheprobe25"
        ),
        db,
        _token(),
    )
    assert observed["governance_revoked"] is True
    # Observer-only measurement: the endpoint never deletes what it measures.
    # CLARA has no production governed-content cache; the research-only Redis
    # entry remains present after revocation and is not manufactured absent.
    assert observed["cache_present_after_revoke"] is True
    assert observed["measurement_note"] == "observer_only_no_invalidation"


def test_state_only_cache_probe_retains_entry_after_revoke(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "STATE_VERSION_ONLY")
    cache = _MemoryCache()
    monkeypatch.setattr(govred_module, "_research_cache_store", lambda: cache)
    synthetic_disclosure_cache_probe(
        SyntheticCacheProbeRequest(
            phase="seed", sentinel_id="sentinel26", probe_id="cacheprobe26"
        ),
        db,
        _token(),
    )
    owner = db.query(User).filter(User.email == "govred-http@example.test").one()
    db.add(UserConsent(
        user_id=owner.id,
        consent_type=MEDICAL_CONSENT_TYPE,
        consent_version=required_medical_disclaimer_version(),
        revoked_at=datetime.now(UTC),
    ))
    db.commit()

    observed = synthetic_disclosure_cache_probe(
        SyntheticCacheProbeRequest(
            phase="read_after_revoke", sentinel_id="sentinel26", probe_id="cacheprobe26"
        ),
        db,
        _token(),
    )
    assert observed["cache_present_after_revoke"] is True


def test_audit_observer_reconstructs_committed_snapshot_bound_transition(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")
    committed = synthetic_commit_probe(_probe("none", "sentinel27"), db, _token())

    observed = synthetic_audit_observation(
        sentinel_id="sentinel27",
        probe_id=committed["probe_id"],
        db=db,
        token=_token(),
    )

    assert observed == {
        "commit_found": True,
        "transition_item_count": 1,
        "state_version_recorded": True,
        "snapshot_linkage_valid": True,
        "audit_reconstruction_complete": True,
        "reconstruction_status": "complete",
    }


def test_full_phase_purpose_switch_requires_two_phase(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe("purpose_switch_replay", "sentinel30"),
            db,
            _token(),
        )

    assert raised.value.status_code == 400
    assert raised.value.detail == {"code": "mutation_requires_two_phase"}


def test_two_phase_purpose_switch_rejects_under_strict(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")
    created = synthetic_commit_probe(
        _probe("purpose_switch_replay", "sentinel31", phase="create"),
        db,
        _token(),
    )
    assert created["phase"] == "create"
    assert created["snapshot_public_id"] is not None

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe(
                "purpose_switch_replay",
                "sentinel31",
                phase="commit",
                probe_id=created["probe_id"],
            ),
            db,
            _token(),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {"code": "proposal_snapshot_purpose_mismatch"}


def test_purpose_switch_rejection_recorded_for_audit(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")
    created = synthetic_commit_probe(
        _probe("purpose_switch_replay", "sentinel32", phase="create"),
        db,
        _token(),
    )
    try:
        synthetic_commit_probe(
            _probe(
                "purpose_switch_replay",
                "sentinel32",
                phase="commit",
                probe_id=created["probe_id"],
            ),
            db,
            _token(),
        )
    except HTTPException:
        pass

    observed = synthetic_audit_observation(
        sentinel_id="sentinel32",
        probe_id=created["probe_id"],
        db=db,
        token=_token(),
    )

    assert observed["commit_found"] is False
    assert observed["transition_item_count"] == 0
    assert observed["reconstruction_status"] == "rejected"
    assert observed["rejection_reason_code"] == "proposal_snapshot_purpose_mismatch"
    assert observed["rejection_coordinates"]["proposal_public_id"] == created["proposal_public_id"]
    assert observed["rejection_coordinates"]["snapshot_public_id"] == created["snapshot_public_id"]
    assert observed["rejection_context"]["purpose"] == "care_coordination"
    assert observed["rejection_context"]["task"] == "govred-isolated-synthetic-probe"


def test_two_phase_policy_version_change_rejects_under_strict(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "research-policy-v1")
    created = synthetic_commit_probe(
        _probe("policy_version_change", "sentinel33", phase="create"),
        db,
        _token(),
    )
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "research-policy-v2")

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe(
                "policy_version_change",
                "sentinel33",
                phase="commit",
                probe_id=created["probe_id"],
            ),
            db,
            _token(),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {"code": "assertion_policy_mismatch"}


def test_two_phase_subject_cross_replay_rejects_under_strict(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "GLHS_STRICT")
    created = synthetic_commit_probe(
        _probe("subject_cross_replay", "sentinel34", phase="create"),
        db,
        _token(),
    )

    with pytest.raises(HTTPException) as raised:
        synthetic_commit_probe(
            _probe(
                "subject_cross_replay",
                "sentinel34",
                phase="commit",
                probe_id=created["probe_id"],
            ),
            db,
            _token(),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {"code": "assertion_scope_forbidden"}

    observed = synthetic_audit_observation(
        sentinel_id="sentinel34",
        probe_id=created["probe_id"],
        db=db,
        token=_token(),
    )
    assert observed["commit_found"] is False
    assert observed["transition_item_count"] == 0
    assert observed["rejection_reason_code"] == "assertion_scope_forbidden"
    assert observed["rejection_coordinates"]["proposal_public_id"] == created["proposal_public_id"]


def test_strict_policy_override_is_isolated_attestation_gated(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Without the isolated research attestation the override is never honored:
    # the gateway returns the production POLICY_VERSION constant.
    monkeypatch.delenv("CLARA_GOVRED_ISOLATED_RESEARCH", raising=False)
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "research-policy-v1")
    from clara_api.glhs import gateway

    assert gateway._effective_policy_version() == gateway.POLICY_VERSION
