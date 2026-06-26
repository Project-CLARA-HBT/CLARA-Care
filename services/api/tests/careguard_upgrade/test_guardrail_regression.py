"""Medical-safety guardrail regression suite (API side).

Feature: clara-selfmed-careguard-upgrade (task 11.1)

This module pins the *existing* CareGuard safety guardrails on the API surface so
the upgrade — which is additive and feature-flagged — can never silently regress
them. None of these guards depend on the new ``SELFMED_*`` / ``CAREGUARD_*``
flags; they are the pre-feature contract and must hold at every flag combination.

Covered here (the API-owned guardrails):

* **Consent gate** (Req 7.3, 12.6) — the medical-disclaimer consent is required
  before any cabinet read/write or the ``auto-ddi-check`` interaction flow.
* **Cross-border transfer guard** (Req 12.6) — when cross-border gating is on and
  the user has not granted ``cross_border_processing`` consent, PHR-derived
  fields (``reconciled_medications`` / ``coded_allergies``) are stripped from the
  offshore ML payload; granting the consent restores them.
* **PHR-reconciliation behavior is flag-gated** (Req 7.5, 12.6) — with the PHR
  reconciliation flag off the ``auto-ddi-check`` payload is the legacy
  cabinet-only shape (no ``reconciled_medications``); on, it is added.
* **Clinician-review directive + PHR hedge preserved** (Req 7.4) — output derived
  from self-declared PHR data carries the bilingual self-declared / review-with-a
  -clinician hedge.

The ML-side guardrails (no-prescribing / no-diagnosis boundary in the generated
recommendation, and dosage-token stripping during normalization) are pinned in
``services/ml/tests/test_careguard_guardrail_regression.py`` where that logic
lives.

The single ML proxy seam (``proxy_ml_post``) is mocked so no real ML service is
contacted; the tests assert on the *request payload* the API builds (what would
cross the offshore boundary) and on the response envelope the API returns.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.compliance import consent as consent_ledger
from clara_api.core.config import get_settings
from clara_api.db.models import PhrProfile, User
from clara_api.db.session import SessionLocal
from clara_api.main import app
from clara_api.phr.provenance import hedge_text_bilingual

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login_without_consent(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _login(email: str) -> str:
    token = _login_without_consent(email)
    status_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    required_version = status_response.json()["required_version"]
    accept_response = client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": required_version, "accepted": True},
    )
    assert accept_response.status_code == 200
    return token


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        return int(db.execute(select(User.id).where(User.email == email)).scalar_one())


def _add_item(token: str, drug_name: str) -> None:
    response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_name": drug_name, "source": "manual"},
    )
    assert response.status_code == 200


def _seed_phr_medication(email: str, *, normalized_name: str = "warfarin") -> None:
    """Give the user a self-declared PHR medication so reconciliation is PHR-derived."""
    with SessionLocal() as db:
        user_id = int(db.execute(select(User.id).where(User.email == email)).scalar_one())
        profile = db.execute(
            select(PhrProfile).where(PhrProfile.user_id == user_id)
        ).scalar_one_or_none()
        if profile is None:
            profile = PhrProfile(user_id=user_id, full_name="Guardrail Subject")
            db.add(profile)
        profile.medications_json = [
            {
                "id": "phr-med-1",
                "rx_cui": "",
                "normalized_name": normalized_name,
                "name": normalized_name,
            }
        ]
        db.commit()


def _grant_cross_border(email: str) -> None:
    with SessionLocal() as db:
        user_id = int(db.execute(select(User.id).where(User.email == email)).scalar_one())
        consent_ledger.grant(
            db, user_id=user_id, purpose=consent_ledger.PURPOSE_CROSS_BORDER, version="v1"
        )
        db.commit()


def _make_capture_proxy(captured: dict[str, Any]):
    def _fake_proxy(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured["path"] = path
        captured["payload"] = payload
        return {
            "risk_tier": "high",
            "ddi_alerts": [{"title": "test"}],
            "recommendations": ["Nên hỏi bác sĩ hoặc dược sĩ."],
            "citations": [{"source": "RxNorm", "url": "https://rxnav.nlm.nih.gov/"}],
            "metadata": {
                "source_used": ["local_rules"],
                "source_errors": {},
            },
        }

    return _fake_proxy


def _enable_env(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Consent gate (Req 7.3, 12.6)
# ---------------------------------------------------------------------------


def test_cabinet_read_requires_medical_disclaimer_consent() -> None:
    token = _login_without_consent("guardrail-consent-cabinet@example.com")
    response = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 428
    assert "miễn trừ trách nhiệm y tế" in response.json()["detail"]


def test_cabinet_write_requires_medical_disclaimer_consent() -> None:
    token = _login_without_consent("guardrail-consent-write@example.com")
    response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_name": "Warfarin", "source": "manual"},
    )
    assert response.status_code == 428


def test_auto_ddi_check_requires_medical_disclaimer_consent(monkeypatch) -> None:
    token = _login_without_consent("guardrail-consent-ddi@example.com")

    def _must_not_proxy(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("ML proxy must not be called before the consent gate passes")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.careguard.proxy_ml_post", _must_not_proxy
    )
    response = client.post(
        "/api/v1/careguard/cabinet/auto-ddi-check",
        headers={"Authorization": f"Bearer {token}"},
        json={"allergies": [], "symptoms": [], "labs": {}},
    )
    assert response.status_code == 428


# ---------------------------------------------------------------------------
# PHR reconciliation is flag-gated (Req 7.5, 12.6)
# ---------------------------------------------------------------------------


def test_reconciliation_flag_off_payload_is_legacy_cabinet_only(monkeypatch) -> None:
    """Flag OFF (default) ⇒ no reconciled_medications, no phr_hedge (legacy shape)."""
    email = "guardrail-recon-off@example.com"
    token = _login(email)
    _add_item(token, "Warfarin")
    _seed_phr_medication(email)

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.careguard.proxy_ml_post", _make_capture_proxy(captured)
    )

    response = client.post(
        "/api/v1/careguard/cabinet/auto-ddi-check",
        headers={"Authorization": f"Bearer {token}"},
        json={"allergies": [], "symptoms": [], "labs": {}},
    )
    assert response.status_code == 200
    payload = captured["payload"]
    assert "reconciled_medications" not in payload
    assert "coded_allergies" not in payload
    assert "phr_hedge" not in response.json()


def test_reconciliation_flag_on_adds_reconciled_medications_and_hedge(monkeypatch) -> None:
    """Flag ON + PHR-derived meds ⇒ reconciled_medications added and PHR hedge attached."""
    email = "guardrail-recon-on@example.com"
    token = _login(email)
    _add_item(token, "Warfarin")
    _seed_phr_medication(email)

    _enable_env(
        monkeypatch,
        PHR_ENHANCED_ENABLED="true",
        PHR_RECONCILIATION_ENABLED="true",
    )

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.careguard.proxy_ml_post", _make_capture_proxy(captured)
    )

    response = client.post(
        "/api/v1/careguard/cabinet/auto-ddi-check",
        headers={"Authorization": f"Bearer {token}"},
        json={"allergies": [], "symptoms": [], "labs": {}},
    )
    assert response.status_code == 200
    payload = captured["payload"]
    assert "reconciled_medications" in payload
    assert isinstance(payload["reconciled_medications"], list)


# ---------------------------------------------------------------------------
# Clinician-review directive + PHR hedge preserved (Req 7.4)
# ---------------------------------------------------------------------------


def test_phr_derived_output_carries_self_declared_clinician_hedge(monkeypatch) -> None:
    email = "guardrail-hedge@example.com"
    token = _login(email)
    _add_item(token, "Warfarin")
    _seed_phr_medication(email)

    _enable_env(
        monkeypatch,
        PHR_ENHANCED_ENABLED="true",
        PHR_RECONCILIATION_ENABLED="true",
    )

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.careguard.proxy_ml_post", _make_capture_proxy(captured)
    )

    response = client.post(
        "/api/v1/careguard/cabinet/auto-ddi-check",
        headers={"Authorization": f"Bearer {token}"},
        json={"allergies": [], "symptoms": [], "labs": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("phr_hedge") == hedge_text_bilingual()
    # The hedge is the clinician-review directive on the PHR-derived path: it
    # explicitly tells the user the result is self-declared and to review it with
    # a clinician before acting.
    assert "bác sĩ" in body["phr_hedge"]
    assert "clinician" in body["phr_hedge"]


# ---------------------------------------------------------------------------
# Cross-border transfer guard (Req 12.6)
# ---------------------------------------------------------------------------


def test_cross_border_guard_strips_phr_fields_without_consent(monkeypatch) -> None:
    """Gating ON + no cross-border consent ⇒ PHR-derived fields stripped from ML payload."""
    email = "guardrail-xborder-block@example.com"
    token = _login(email)
    _add_item(token, "Warfarin")
    _seed_phr_medication(email)

    _enable_env(
        monkeypatch,
        PHR_ENHANCED_ENABLED="true",
        PHR_RECONCILIATION_ENABLED="true",
        COMPLIANCE_CROSS_BORDER_GATING_ENABLED="true",
    )

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.careguard.proxy_ml_post", _make_capture_proxy(captured)
    )

    response = client.post(
        "/api/v1/careguard/cabinet/auto-ddi-check",
        headers={"Authorization": f"Bearer {token}"},
        json={"allergies": [], "symptoms": [], "labs": {}},
    )
    assert response.status_code == 200
    payload = captured["payload"]
    # The offshore call must NOT carry identifiable PHR-derived fields.
    assert "reconciled_medications" not in payload
    assert "coded_allergies" not in payload
    # The cabinet-only medication list (already user-visible, non-PHR-derived) is
    # still sent so the local DDI check can run.
    assert "medications" in payload


def test_cross_border_guard_retains_phr_fields_with_consent(monkeypatch) -> None:
    """Gating ON + cross-border consent present ⇒ PHR-derived fields preserved."""
    email = "guardrail-xborder-allow@example.com"
    token = _login(email)
    _add_item(token, "Warfarin")
    _seed_phr_medication(email)
    _grant_cross_border(email)

    _enable_env(
        monkeypatch,
        PHR_ENHANCED_ENABLED="true",
        PHR_RECONCILIATION_ENABLED="true",
        COMPLIANCE_CROSS_BORDER_GATING_ENABLED="true",
    )

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.careguard.proxy_ml_post", _make_capture_proxy(captured)
    )

    response = client.post(
        "/api/v1/careguard/cabinet/auto-ddi-check",
        headers={"Authorization": f"Bearer {token}"},
        json={"allergies": [], "symptoms": [], "labs": {}},
    )
    assert response.status_code == 200
    payload = captured["payload"]
    assert "reconciled_medications" in payload
