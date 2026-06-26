"""Tests for the "never (fast && personal)" invariant (clara-research R15.2, task 15.2).

The Research_API must reject any request that sets ``personal_mode`` while the research mode is
fast. Personalization (PHR + medicine cabinet) is valid only for tier2 deep / deep_beta runs.
Enforcement lives both in the typed request schema (``ResearchTier2JobCreateRequest``) and on the
raw-dict ``/tier2`` surface via ``_enforce_never_fast_and_personal``.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from clara_api.api.v1.endpoints.research import _enforce_never_fast_and_personal
from clara_api.schemas import ResearchTier2JobCreateRequest


# --- Schema-level enforcement (covers POST /research/tier2/jobs) -------------


def test_schema_rejects_fast_with_personal_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ResearchTier2JobCreateRequest(query="q", research_mode="fast", personal_mode=True)
    assert "never (fast && personal)" in str(exc_info.value)


@pytest.mark.parametrize("mode", ["deep", "deep_beta"])
def test_schema_allows_personal_mode_in_tier2(mode: str) -> None:
    req = ResearchTier2JobCreateRequest(query="q", research_mode=mode, personal_mode=True)
    assert req.personal_mode is True
    assert req.research_mode == mode


def test_schema_allows_fast_without_personal_mode() -> None:
    req = ResearchTier2JobCreateRequest(query="q", research_mode="fast", personal_mode=False)
    assert req.research_mode == "fast"
    assert req.personal_mode is False


def test_schema_default_fast_non_personal_is_legacy_safe() -> None:
    # Legacy callers omit both fields; defaults (fast, personal_mode=False) stay valid.
    req = ResearchTier2JobCreateRequest(query="q")
    assert req.research_mode == "fast"
    assert req.personal_mode is False


# --- Raw-dict enforcement (covers POST /research/tier2) ----------------------


@pytest.mark.parametrize("personal_value", [True, 1, "true", "yes", "on"])
def test_helper_rejects_fast_with_personal(personal_value: object) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _enforce_never_fast_and_personal(
            {"research_mode": "fast", "personal_mode": personal_value}
        )
    assert exc_info.value.status_code == 422
    assert "never (fast && personal)" in exc_info.value.detail


def test_helper_rejects_fast_with_personal_via_mode_alias() -> None:
    with pytest.raises(HTTPException):
        _enforce_never_fast_and_personal({"mode": "fast", "personal_mode": True})


@pytest.mark.parametrize("mode", ["deep", "deep_beta", "deep_research", "deepbeta"])
def test_helper_allows_personal_in_tier2(mode: str) -> None:
    _enforce_never_fast_and_personal({"research_mode": mode, "personal_mode": True})


@pytest.mark.parametrize("personal_value", [False, 0, "false", "no", "", None])
def test_helper_allows_fast_without_personal(personal_value: object) -> None:
    _enforce_never_fast_and_personal({"research_mode": "fast", "personal_mode": personal_value})
