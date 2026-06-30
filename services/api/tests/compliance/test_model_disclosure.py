"""Unit tests for response-envelope model disclosure (task 3.2).

Covers the ``ComplianceService.model_disclosure`` facade and the
``notice.model_disclosure`` helper that build the response-envelope
``ai_disclosure`` field from ``model_used``:

- Flag OFF ⇒ disclosure omitted (``None``) so the envelope is byte-equivalent
  to today (Property P6 / Requirement 8.1, 8.2).
- Flag ON ⇒ disclosure carries ``model_family``/``model_version``/``is_fallback``.
- ``is_fallback`` is true **iff** the answer came from ``local-synth-*``
  (Correctness Property P8 / Requirements 1.3, 1.4).

**Validates: Requirements 1.3, 1.4**
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from clara_api.compliance.notice import model_disclosure as build_model_disclosure
from clara_api.compliance.service import ComplianceService
from clara_api.core.config import Settings, get_settings
from clara_api.db.session import SessionLocal


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Facade flag-awareness (Property P6 at the disclosure seam)
# ---------------------------------------------------------------------------


class TestModelDisclosureFlagAware:
    def test_returns_none_when_flag_off(self, db) -> None:
        """Flag off ⇒ no ai_disclosure field (legacy envelope preserved)."""
        service = ComplianceService(db, settings=Settings())  # flags default OFF
        assert service.model_disclosure("deepseek-v3.2") is None
        assert service.model_disclosure("local-synth-v1") is None
        assert service.model_disclosure(None) is None

    def test_returns_disclosure_when_flag_on(self, db, monkeypatch) -> None:
        monkeypatch.setenv("COMPLIANCE_MODEL_DISCLOSURE_ENABLED", "true")
        get_settings.cache_clear()
        service = ComplianceService(db, settings=get_settings())

        disclosure = service.model_disclosure("deepseek-v3.2")
        assert disclosure == {
            "model_family": "deepseek",
            "model_version": "v3.2",
            "is_fallback": False,
        }


# ---------------------------------------------------------------------------
# Property P8 — is_fallback iff local-synth-* (helper level)
# ---------------------------------------------------------------------------


class TestDisclosureCorrectnessP8:
    @pytest.mark.parametrize(
        "model_used",
        ["local-synth-v1", "local-synth-v2", "LOCAL-SYNTH-X", "local-synth"],
    )
    def test_is_fallback_true_for_local_synth(self, model_used: str) -> None:
        assert build_model_disclosure(model_used)["is_fallback"] is True

    @pytest.mark.parametrize(
        "model_used",
        ["deepseek-v3.2", "deepseek-v4-pro", "api-safe-fallback-v1", "gpt-5.3", "", None],
    )
    def test_is_fallback_false_for_non_local_synth(self, model_used: str | None) -> None:
        # api-safe-* / api-local-synth-guard-* are API guard sentinels, NOT the
        # ML local deterministic synthesiser, so they are NOT P8 fallbacks.
        assert build_model_disclosure(model_used)["is_fallback"] is False

    def test_family_and_version_split_on_first_hyphen(self) -> None:
        disclosure = build_model_disclosure("deepseek-v4-pro")
        assert disclosure["model_family"] == "deepseek"
        assert disclosure["model_version"] == "v4-pro"

    def test_unknown_when_blank(self) -> None:
        disclosure = build_model_disclosure("")
        assert disclosure["model_family"] == "unknown"
        assert disclosure["model_version"] == "unknown"
        assert disclosure["is_fallback"] is False
