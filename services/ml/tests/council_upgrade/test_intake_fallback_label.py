"""Degraded / fallback labeling of Council intake (ML side, task 5.2).

Covers Requirement 5.3 (design §D "Resilience wrapper" / Error Handling
"Degraded labeling"): when ``run_council_intake`` falls back to the heuristic
extractor (``heuristic-fallback-v1`` — no LLM / model unavailable), the result
must carry the degraded state in BOTH a machine-readable form
(``is_fallback`` / ``model_used`` / ``ai_disclosure.is_fallback``) and a
user-visible form (a notice surfaced through the already-rendered ``warnings``
list and a dedicated ``fallback_notice`` string). An LLM-backed extraction is
never flagged as a fallback, and the happy path stays byte-equivalent to today.

Everything here is deterministic and network-free: the DeepSeek client build and
the extraction call are monkeypatched so no provider or socket is touched.
"""

from __future__ import annotations

import pytest

import clara_ml.agents.council_intake as ci

from .harness import council_flags

_TRANSCRIPT = "Bệnh nhân đau ngực nhiều, khó thở. glucose=110 mg/dL. Đang dùng aspirin."


class _StubClient:
    """Minimal stand-in for ``DeepSeekClient`` (only ``model`` is read here)."""

    model = "deepseek-stub"


def _force_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the DeepSeek extraction raise so intake degrades to the heuristic path."""

    def _boom(_client: object, _transcript: str) -> dict[str, object]:
        raise RuntimeError("deepseek unavailable")

    monkeypatch.setattr(ci, "_build_client", lambda: _StubClient())
    monkeypatch.setattr(ci, "_extract_with_deepseek", _boom)


def _force_llm(monkeypatch: pytest.MonkeyPatch, model: str = "deepseek-v3.2") -> None:
    """Make the DeepSeek extraction succeed with a real model id (no fallback)."""

    def _ok(_client: object, _transcript: str) -> dict[str, object]:
        return {
            "symptoms": ["đau ngực"],
            "labs": [{"name": "glucose", "value": "110", "unit": "mg/dL", "raw": "glucose=110 mg/dL"}],
            "medications": ["aspirin"],
            "history": [],
            "_model_used": model,
        }

    monkeypatch.setattr(ci, "_build_client", lambda: _StubClient())
    monkeypatch.setattr(ci, "_extract_with_deepseek", _ok)


class TestHeuristicFallbackLabeling:
    def test_machine_readable_flags_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fallback ⇒ top-level is_fallback True + heuristic model_used + deepdive flag."""
        _force_fallback(monkeypatch)
        result = ci.run_council_intake(transcript=_TRANSCRIPT)

        assert result["is_fallback"] is True
        assert result["model_used"] == "heuristic-fallback-v1"
        assert result["deepdive"]["extraction"]["fallback_used"] is True

    def test_user_visible_notice_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fallback ⇒ a human-readable notice in fallback_notice AND the warnings list."""
        _force_fallback(monkeypatch)
        result = ci.run_council_intake(transcript=_TRANSCRIPT)

        notice = result["fallback_notice"]
        assert isinstance(notice, str) and notice.strip()
        # The notice is surfaced through the warnings list the web intake renders.
        assert notice in result["warnings"]
        # The technical fallback reason is retained alongside the friendly notice.
        assert any(w.startswith("deepseek_extract_fallback:") for w in result["warnings"])

    def test_confidence_math_is_byte_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The user-visible notice is appended AFTER confidence, so the penalty is unchanged.

        Only the single technical warning counts toward the confidence
        warning-penalty (0.08), proving the labeling did not perturb the
        existing confidence computation (back-compatibility).
        """
        _force_fallback(monkeypatch)
        result = ci.run_council_intake(transcript=_TRANSCRIPT)

        assert result["analyze"]["confidence"]["components"]["warning_penalty"] == 0.08

    def test_consistent_with_ai_disclosure_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When disclosure is on, ai_disclosure.is_fallback agrees with the top-level flag."""
        _force_fallback(monkeypatch)
        with council_flags(council_model_disclosure_enabled=True):
            result = ci.run_council_intake(transcript=_TRANSCRIPT)

        assert result["is_fallback"] is True
        assert result["ai_disclosure"]["is_fallback"] is True


class TestLlmBackedIntakeNotFlagged:
    def test_no_fallback_keys_on_llm_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM-backed extraction ⇒ no is_fallback/fallback_notice keys (byte-equivalent)."""
        _force_llm(monkeypatch)
        result = ci.run_council_intake(transcript=_TRANSCRIPT)

        assert result["model_used"] == "deepseek-v3.2"
        assert "is_fallback" not in result
        assert "fallback_notice" not in result
        assert result["deepdive"]["extraction"]["fallback_used"] is False

    def test_no_fallback_notice_in_warnings_on_llm_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM-backed extraction ⇒ no degraded notice leaks into warnings."""
        _force_llm(monkeypatch)
        result = ci.run_council_intake(transcript=_TRANSCRIPT)

        assert ci._INTAKE_FALLBACK_NOTICE not in result["warnings"]

    def test_disclosure_not_fallback_on_llm_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With disclosure on, an LLM-backed intake discloses is_fallback False."""
        _force_llm(monkeypatch)
        with council_flags(council_model_disclosure_enabled=True):
            result = ci.run_council_intake(transcript=_TRANSCRIPT)

        assert result["ai_disclosure"]["is_fallback"] is False
        assert "is_fallback" not in result
