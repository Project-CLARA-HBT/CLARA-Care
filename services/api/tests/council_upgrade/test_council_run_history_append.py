"""Tests for Council run-history append on run (task 3.1).

When ``COUNCIL_RUN_HISTORY_ENABLED`` is on, both the blocking
``POST /cases/{id}/run`` and the streaming ``POST /cases/{id}/run/stream``
append an immutable ``CouncilRun`` snapshot, while the case's
``result_json``/``last_run_at`` keep mirroring the latest run (Req 2.1, 2.3).
With the flag off, no history row is written and behavior is byte-equivalent to
today (Req 2.6).

These tests stub the ML proxy / ``httpx.Client`` so no live ML service is needed.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import CouncilRun
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

_RUN_PAYLOAD: dict[str, Any] = {
    "symptoms": ["polypharmacy", "fatigue"],
    "labs": {"creatinine": 1.2},
    "medications": ["warfarin"],
    "history": "htn",
    "specialist_count": 2,
    "specialists": ["pharmacology", "nephrology"],
}

_FAKE_RESULT: dict[str, Any] = {
    "final_recommendation": "review with a licensed clinician",
    "emergency_escalation": {"triggered": True, "red_flags": ["chest pain"]},
    "research": {"mode": "rule_based_council_v2"},
    "reasoning_timeline": [{"sequence": 0, "step": "intake_normalized"}],
}


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_case(token: str, request: dict[str, Any] | None = None) -> int:
    response = client.post(
        "/api/v1/council/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "history case", "request": request or _RUN_PAYLOAD},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


def _runs_for(case_id: int) -> list[CouncilRun]:
    with SessionLocal() as db:
        return list(
            db.execute(
                select(CouncilRun).where(CouncilRun.case_id == case_id)
            ).scalars().all()
        )


# ---------------------------------------------------------------------------
# Blocking /run
# ---------------------------------------------------------------------------


def test_blocking_run_appends_council_run_when_flag_on(set_flags, monkeypatch) -> None:
    set_flags(council_run_history_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    # Case still mirrors the latest run for existing consumers (Req 2.3).
    assert body["result"]["final_recommendation"] == "review with a licensed clinician"
    assert body["last_run_at"] is not None

    rows = _runs_for(case_id)
    assert len(rows) == 1
    run = rows[0]
    assert run.result_json["final_recommendation"] == "review with a licensed clinician"
    assert run.request_json["symptoms"] == ["polypharmacy", "fatigue"]
    assert run.model_version == "rule_based_council_v2"
    assert run.emergency_triggered is True


def test_blocking_run_appends_per_run_and_preserves_prior(set_flags, monkeypatch) -> None:
    set_flags(council_run_history_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    for _ in range(3):
        response = client.post(
            f"/api/v1/council/cases/{case_id}/run",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert response.status_code == 200, response.text

    rows = _runs_for(case_id)
    assert len(rows) == 3  # append-only: one immutable row per run (Req 2.1, 2.2)


def test_blocking_run_writes_no_history_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 200, response.text
    # Latest result still mirrored (today's behavior), but no history row (Req 2.6).
    assert response.json()["result"]["final_recommendation"] == (
        "review with a licensed clinician"
    )
    assert _runs_for(case_id) == []


# ---------------------------------------------------------------------------
# Streaming /run/stream
# ---------------------------------------------------------------------------


class _FakeStreamCtx:
    def __init__(self, *, status_code: int, chunks: list[bytes]) -> None:
        self.status_code = status_code
        self._chunks = chunks

    def __enter__(self) -> _FakeStreamCtx:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return b""

    def iter_raw(self):
        yield from self._chunks


class _FakeClient:
    def __init__(self, *, status_code: int, chunks: list[bytes]) -> None:
        self._status_code = status_code
        self._chunks = chunks

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def stream(self, method: str, url: str, *, json: dict[str, Any], headers: dict[str, str]):
        return _FakeStreamCtx(status_code=self._status_code, chunks=self._chunks)


def _install_fake_client(monkeypatch, *, status_code: int, chunks: list[bytes]) -> None:
    def _factory(*_args: Any, **_kwargs: Any) -> _FakeClient:
        return _FakeClient(status_code=status_code, chunks=chunks)

    monkeypatch.setattr("clara_api.api.v1.endpoints.council.httpx.Client", _factory)


def test_stream_appends_council_run_from_terminal_result(set_flags, monkeypatch) -> None:
    set_flags(council_streaming_enabled=True, council_run_history_enabled=True)
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    chunks = [
        b'event: stage\ndata: {"sequence":0,"step":"intake_normalized"}\n\n',
        (
            b'event: result\ndata: {"final_recommendation":"review with a clinician",'
            b'"emergency_escalation":{"triggered":false},'
            b'"research":{"mode":"rule_based_council_v2"}}\n\n'
        ),
    ]
    _install_fake_client(monkeypatch, status_code=200, chunks=chunks)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 200
    assert b"event: result" in response.content

    rows = _runs_for(case_id)
    assert len(rows) == 1
    run = rows[0]
    assert run.result_json["final_recommendation"] == "review with a clinician"
    assert run.model_version == "rule_based_council_v2"
    assert run.emergency_triggered is False


def test_stream_writes_no_history_on_upstream_error(set_flags, monkeypatch) -> None:
    set_flags(council_streaming_enabled=True, council_run_history_enabled=True)
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    _install_fake_client(monkeypatch, status_code=503, chunks=[])

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 200
    assert b"event: error" in response.content
    # Failed stream persists nothing (Req 1.4, 5.6).
    assert _runs_for(case_id) == []
