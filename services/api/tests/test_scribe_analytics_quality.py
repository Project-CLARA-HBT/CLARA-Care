"""Quality-metrics analytics endpoint tests (Requirement 15).

``GET /scribe/analytics/quality`` exposes the wave-7 note-quality + efficiency
metrics (edit-rate, time-saved, degraded-ASR rate, grounded-claim rate, PDQI-9
structural proxy) derived purely from persisted non-PII session metadata. These
tests assert:

- flag ON returns metrics derived from seeded note versions / grounding / ASR
  metadata, including the grounded-claim rate (from ``grounding_json``) and the
  structural proxy (Req 15.2);
- flag OFF returns 404 so the surface is fully retracted (Req 15.1) and the
  flags-off regression gate stays green;
- a non-doctor account is rejected with 403 (RBAC), even with the flag on;
- the output contains NO seeded transcript substring / patient identifier
  (PII-free, Req 15.3);
- metrics are omitted when their input is unavailable (omit-on-missing, Req 15.6);
- the legacy ``/analytics/summary`` and ``/analytics/derived`` payloads are
  unchanged (additive).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeNoteVersion, ScribeSession, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

# Seeded "PII" tokens that must never leak into the analytics payload.
_PII_TOKENS = ("Nguyen", "0901234567", "warfarin", "secret-history-text")


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    status = client.get(
        "/api/v1/auth/consent-status", headers={"Authorization": f"Bearer {token}"}
    )
    version = status.json()["required_version"]
    client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": version, "accepted": True},
    )
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _enable(monkeypatch, value: bool = True) -> None:
    settings = get_settings()
    monkeypatch.setattr(
        settings, "rag_scribe_quality_metrics_enabled", value, raising=False
    )


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        return user.id


def _seed_session(
    *,
    email: str,
    transcript: str,
    note_versions: list[dict] | None = None,
    asr_meta: dict | None = None,
) -> int:
    """Insert a ScribeSession (+ optional note versions / asr_meta) directly.

    Each ``note_versions`` entry is ``{"sections": ..., "grounding": ...}`` where
    ``grounding`` is optional (mirrors the persisted ``grounding_json`` column).
    """

    uid = _user_id(email)
    with SessionLocal() as db:
        item = ScribeSession(
            user_id=uid,
            title="visit",
            status="draft",
            transcript=transcript,
            asr_meta_json=asr_meta,
        )
        db.add(item)
        db.flush()
        for idx, entry in enumerate(note_versions or [], start=1):
            db.add(
                ScribeNoteVersion(
                    session_id=item.id,
                    version_no=idx,
                    template_id="soap",
                    sections_json=entry.get("sections"),
                    grounding_json=entry.get("grounding"),
                    created_by=uid,
                )
            )
        db.commit()
        return item.id


def test_quality_flag_off_returns_404(monkeypatch) -> None:
    # Req 15.1: with the flag off the enterprise quality surface is retracted (404).
    _enable(monkeypatch, value=False)
    token = _login("dr.quality.flagoff@doctor.clara")
    resp = client.get("/api/v1/scribe/analytics/quality", headers=_auth(token))
    assert resp.status_code == 404, resp.text


def test_quality_rbac_rejects_non_doctor(monkeypatch) -> None:
    # RBAC runs as a dependency before the flag check -> 403 even with flag on.
    _enable(monkeypatch, value=True)
    token = _login("plain.user.quality@example.com")  # non-doctor account
    resp = client.get("/api/v1/scribe/analytics/quality", headers=_auth(token))
    assert resp.status_code == 403, resp.text


def test_quality_metrics_computed_from_seeded_metadata(monkeypatch) -> None:
    _enable(monkeypatch, value=True)
    email = "dr.quality.calc@doctor.clara"
    token = _login(email)
    _seed_session(
        email=email,
        transcript=f"{_PII_TOKENS[0]} {_PII_TOKENS[1]} {_PII_TOKENS[2]}",
        note_versions=[
            {"sections": {"subjective": "patient reports a cough", "plan": "rest"}},
            {
                "sections": {
                    "subjective": "patient reports a dry cough",
                    "objective": "afebrile",
                    "assessment": "URI",
                    "plan": "rest and fluids",
                },
                "grounding": {
                    "enabled": True,
                    "grounded_claim_rate": 0.8,
                    "total_significant": 5,
                },
            },
        ],
        asr_meta={
            "provider": "whisper",
            "language": "vi",
            "segments": [
                {"text": "seg one", "degraded": True},
                {"text": "seg two", "degraded": False},
                {"text": "seg three", "degraded": False},
                {"text": "seg four", "degraded": False},
            ],
        },
    )

    resp = client.get("/api/v1/scribe/analytics/quality", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["encounters"]) == 1
    enc = body["encounters"][0]
    assert 0.0 < enc["edit_rate"] <= 1.0
    assert enc["time_saved_minutes"] >= 0.0
    assert enc["degraded_rate"] == 0.25
    # Grounded-claim rate sourced from the finalized note's grounding_json.
    assert enc["grounded_claim_rate"] == 0.8
    # Finalized note populates all 4 sections -> structural proxy 1.0.
    assert enc["pdqi9_structural_proxy"] == 1.0

    agg = body["aggregate"]
    assert agg["degraded_rate"] == 0.25
    assert agg["grounded_claim_rate"] == 0.8
    assert agg["pdqi9_structural_proxy"] == 1.0
    assert "edit_rate" in agg


def test_quality_output_is_pii_free(monkeypatch) -> None:
    _enable(monkeypatch, value=True)
    email = "dr.quality.pii@doctor.clara"
    token = _login(email)
    _seed_session(
        email=email,
        transcript=" ".join(_PII_TOKENS),
        note_versions=[
            {
                "sections": {
                    "S": f"{_PII_TOKENS[0]} prescribed {_PII_TOKENS[2]}",
                    "P": _PII_TOKENS[3],
                }
            },
            {
                "sections": {
                    "S": f"{_PII_TOKENS[0]} prescribed {_PII_TOKENS[2]} daily",
                    "P": _PII_TOKENS[3],
                },
                "grounding": {"enabled": True, "grounded_claim_rate": 0.5, "total_significant": 2},
            },
        ],
        asr_meta={"segments": [{"text": _PII_TOKENS[3], "degraded": True}]},
    )

    resp = client.get("/api/v1/scribe/analytics/quality", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    serialized = json.dumps(resp.json())
    for pii in _PII_TOKENS:
        assert pii not in serialized
    for enc in resp.json()["encounters"]:
        for key, value in enc.items():
            if key == "session_id":
                continue
            assert value is None or isinstance(value, (int, float))


def test_quality_omits_grounded_rate_when_grounding_absent(monkeypatch) -> None:
    _enable(monkeypatch, value=True)
    email = "dr.quality.omit@doctor.clara"
    token = _login(email)
    # Note versions but NO grounding metadata and NO asr_meta -> grounded_claim_rate
    # and degraded_rate omitted (null); edit/time + structural proxy still present.
    _seed_session(
        email=email,
        transcript="some transcript",
        note_versions=[
            {"sections": {"S": "generated"}},
            {"sections": {"S": "generated edited", "P": "rest"}},
        ],
        asr_meta=None,
    )

    resp = client.get("/api/v1/scribe/analytics/quality", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    encounters = resp.json()["encounters"]
    assert len(encounters) == 1
    enc = encounters[0]
    assert enc["grounded_claim_rate"] is None
    assert enc["degraded_rate"] is None
    assert enc["edit_rate"] is not None
    assert enc["time_saved_minutes"] is not None
    assert enc["pdqi9_structural_proxy"] is not None


def test_legacy_summary_and_derived_payloads_unchanged(monkeypatch) -> None:
    # Additive guarantee: the existing analytics surfaces keep their field sets even
    # when the quality flag is on.
    _enable(monkeypatch, value=True)
    token = _login("dr.quality.legacy@doctor.clara")

    summary = client.get("/api/v1/scribe/analytics/summary", headers=_auth(token))
    assert summary.status_code == 200, summary.text
    assert set(summary.json().keys()) == {
        "total_sessions",
        "completed_sessions",
        "draft_sessions",
        "sessions_today",
        "avg_transcript_chars",
    }

    derived = client.get("/api/v1/scribe/analytics/derived", headers=_auth(token))
    assert derived.status_code == 200, derived.text
    assert set(derived.json().keys()) == {"encounters", "aggregate"}
