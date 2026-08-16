"""Contract tests for the isolated HTTP-facing synthetic GovRed primitive."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.govred_research import (
    SyntheticCommitProbeRequest,
    synthetic_commit_probe,
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


def test_state_only_http_primitive_commits_after_synthetic_consent_revoke(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "STATE_VERSION_ONLY")

    result = synthetic_commit_probe(
        SyntheticCommitProbeRequest(mutation="consent_revoke", sentinel_id="sentinel01"),
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
            SyntheticCommitProbeRequest(mutation="consent_revoke", sentinel_id="sentinel02"),
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
            SyntheticCommitProbeRequest(mutation="state_advance", sentinel_id="sentinel03"),
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
        SyntheticCommitProbeRequest(mutation="state_advance", sentinel_id="sentinel04"),
        db,
        _token(),
    )

    assert result["arm"] == "UNBOUND"
    assert result["outcome"] == "transition_committed"
