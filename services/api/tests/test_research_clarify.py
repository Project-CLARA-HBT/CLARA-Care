"""Tests for the clarifying-questions endpoint (clara-research Requirement 12, task 12.1).

Covers the ``POST /research/clarify`` flag + mode gate, ambiguity detection, and the
localized clarifying-question payload. The clarifying-answer carrier on job create
(``clarifying_answers``) is exercised separately by the schema/contract tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from clara_api.api.v1.endpoints.research import (
    _build_clarifying_questions,
    _detect_query_ambiguity,
)
from clara_api.core.config import get_settings
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _enable_clarify(monkeypatch, value: bool = True) -> None:
    monkeypatch.setattr(
        get_settings(), "research_clarifying_questions_enabled", value, raising=False
    )


# --- Unit tests for the ambiguity heuristic (R12.1, R12.4) ------------------


def test_short_query_is_ambiguous() -> None:
    assert _detect_query_ambiguity("thuốc") is True
    assert _detect_query_ambiguity("điều trị bệnh") is True


def test_detailed_query_is_unambiguous() -> None:
    assert (
        _detect_query_ambiguity(
            "So sánh hiệu quả của metformin và insulin cho bệnh nhân tiểu đường type 2 cao tuổi"
        )
        is False
    )


def test_punctuation_does_not_inflate_word_count() -> None:
    # Symbols/short tokens are not content words, so this stays ambiguous.
    assert _detect_query_ambiguity("a, b? c!") is True


# --- Unit tests for question localization (R12.1) ---------------------------


def test_clarifying_questions_localized_vietnamese() -> None:
    questions = _build_clarifying_questions(ui_language="vi")
    assert [q.id for q in questions] == ["population", "scope", "outcome"]
    assert all(q.question for q in questions)


def test_clarifying_questions_localized_english() -> None:
    questions = _build_clarifying_questions(ui_language="en")
    assert [q.id for q in questions] == ["population", "scope", "outcome"]
    assert all(q.question for q in questions)


# --- Endpoint: flag + mode gate (R12.1, R12.4) ------------------------------


def test_clarify_flag_off_reports_unambiguous(monkeypatch) -> None:
    _enable_clarify(monkeypatch, value=False)
    token = _login("clarify-flagoff@example.com")
    response = client.post(
        "/api/v1/research/clarify",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "thuốc", "research_mode": "deep"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ambiguous"] is False
    assert body["questions"] == []


def test_clarify_fast_mode_not_gated(monkeypatch) -> None:
    _enable_clarify(monkeypatch)
    token = _login("clarify-fast@example.com")
    response = client.post(
        "/api/v1/research/clarify",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "thuốc", "research_mode": "fast"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ambiguous"] is False
    assert body["questions"] == []


def test_clarify_ambiguous_deep_query_returns_questions(monkeypatch) -> None:
    _enable_clarify(monkeypatch)
    token = _login("clarify-deep@example.com")
    response = client.post(
        "/api/v1/research/clarify",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "thuốc", "research_mode": "deep", "ui_language": "en"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ambiguous"] is True
    assert body["research_mode"] == "deep"
    assert [q["id"] for q in body["questions"]] == ["population", "scope", "outcome"]


def test_clarify_unambiguous_deep_query_starts_without_prompting(monkeypatch) -> None:
    _enable_clarify(monkeypatch)
    token = _login("clarify-specific@example.com")
    response = client.post(
        "/api/v1/research/clarify",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": (
                "So sánh hiệu quả của metformin và insulin cho bệnh nhân "
                "tiểu đường type 2 cao tuổi"
            ),
            "research_mode": "deep_beta",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ambiguous"] is False
    assert body["questions"] == []


def test_clarify_requires_authentication() -> None:
    response = client.post(
        "/api/v1/research/clarify",
        json={"query": "thuốc", "research_mode": "deep"},
    )
    assert response.status_code in (401, 403)
