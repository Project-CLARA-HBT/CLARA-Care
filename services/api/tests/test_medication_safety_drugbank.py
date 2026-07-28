from fastapi.testclient import TestClient

from clara_api.api.v1.endpoints import medication_safety
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> tuple[str, dict[str, str]]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def _profile_and_courses(headers: dict[str, str]) -> list[dict]:
    assert (
        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "Safety User"},
        ).status_code
        == 200
    )
    consent = client.get("/api/v1/auth/consent-status", headers=headers).json()
    assert client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={
            "accepted": True,
            "consent_version": consent["required_version"],
        },
    ).status_code == 200
    created = []
    for name, drugbank_id in (("Warfarin", "DB00682"), ("Ibuprofen", "DB01050")):
        response = client.post(
            "/api/v1/medication-courses",
            headers={**headers, "Idempotency-Key": f"course-{name}"},
            json={"medication_name": name, "drugbank_id": drugbank_id},
        )
        assert response.status_code == 201
        created.append(response.json())
    return created


def _ready() -> dict:
    return {
        "state": "ready",
        "version": "drugbank-full-2026-07",
        "pair_count": 1_000_000,
        "manifest_matches_index": True,
    }


def test_medication_course_ddi_is_drugbank_only(monkeypatch) -> None:
    _, headers = _login("drugbank-course@example.com")
    courses = _profile_and_courses(headers)
    captured: dict = {}
    monkeypatch.setattr(
        medication_safety,
        "proxy_ml_get",
        lambda *_args, **_kwargs: {"drugbank": _ready()},
    )

    def _analyze(path: str, payload: dict, **_kwargs: object) -> dict:
        captured["path"] = path
        captured["payload"] = payload
        return {
            "ddi_alerts": [
                {"type": "drug_drug", "source": "drugbank", "severity": "high"},
            ],
            "recommendation": "Contact your pharmacist.",
            "metadata": {
                "source_used": ["drugbank"],
                "fallback_used": False,
                "drugbank": {"state": "ready", "version": _ready()["version"]},
            },
        }

    monkeypatch.setattr(medication_safety, "proxy_ml_post", _analyze)
    response = client.post(
        "/api/v1/medication-courses/safety/ddi",
        headers=headers,
        json={"course_ids": [course["id"] for course in courses]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conclusion_available"] is True
    assert body["required_source"] == "drugbank"
    assert body["source_version"] == _ready()["version"]
    assert body["ddi_alerts"][0]["source"] == "drugbank"
    assert captured["path"] == "/v1/careguard/analyze"
    assert captured["payload"]["external_ddi_enabled"] is False
    assert captured["payload"]["medications"] == ["Warfarin", "Ibuprofen"]


def test_medication_course_ddi_fails_closed_when_drugbank_is_not_ready(monkeypatch) -> None:
    _, headers = _login("drugbank-down@example.com")
    _profile_and_courses(headers)
    monkeypatch.setattr(
        medication_safety,
        "proxy_ml_get",
        lambda *_args, **_kwargs: {
            "drugbank": {"state": "degraded", "version": "stale", "manifest_matches_index": False}
        },
    )
    monkeypatch.setattr(
        medication_safety,
        "proxy_ml_post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not call ML analyze")),
    )

    response = client.post("/api/v1/medication-courses/safety/ddi", headers=headers, json={})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "drugbank_required_unavailable"


def test_medication_course_ddi_rejects_local_or_fallback_result(monkeypatch) -> None:
    _, headers = _login("drugbank-fallback@example.com")
    _profile_and_courses(headers)
    monkeypatch.setattr(
        medication_safety,
        "proxy_ml_get",
        lambda *_args, **_kwargs: {"drugbank": _ready()},
    )
    monkeypatch.setattr(
        medication_safety,
        "proxy_ml_post",
        lambda *_args, **_kwargs: {
            "ddi_alerts": [{"type": "drug_drug", "source": "local_rules"}],
            "metadata": {
                "source_used": ["local_rules"],
                "fallback_used": True,
                "drugbank": {"state": "ready", "version": _ready()["version"]},
            },
        },
    )

    response = client.post("/api/v1/medication-courses/safety/ddi", headers=headers, json={})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "drugbank_required_unavailable"
