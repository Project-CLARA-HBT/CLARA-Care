"""Flag-toggling + decision-capture harness for guardrail preservation.

The harness has two jobs:

1. **Toggle the persistent RAG feature flags** on the live ``settings`` object
   via ``monkeypatch`` so a single test can evaluate a guardrail with the RAG
   additions OFF (legacy behavior) and ON (persistent RAG enabled).

2. **Capture each guardrail decision** in a small, hashable, comparable shape
   so "no behavioral drift" reduces to a plain equality assertion.

Capturing is intentionally network-free and deterministic. The LLM-backed NLI
path in ``clara_ml.factcheck`` is pinned off while capturing FIDES decisions so
the verdict is reproducible in CI without a DeepSeek key.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from clara_ml.agents.careguard import _SEVERITY_RANK, run_careguard_analyze
from clara_ml.clients.drug_sources import DrugSourceClient
from clara_ml.config import settings as _settings
from clara_ml.factcheck import run_fides_lite
from clara_ml.routing import P1RoleIntentRouter

# ---------------------------------------------------------------------------
# Persistent RAG feature flags (the "switches" the overhaul ships behind).
# ---------------------------------------------------------------------------

#: The persistent-RAG flags that gate the knowledge-pipeline overhaul. Flag-OFF
#: == every one False (legacy in-memory behavior). Flag-ON == every one True
#: (persistent RAG fully enabled). A guardrail decision MUST be identical in
#: both states.
PERSISTENT_RAG_FLAGS: tuple[str, ...] = (
    "rag_persistent_store_enabled",
    "rag_persistent_retrieval_enabled",
    "rag_ingestion_enabled",
    "rag_entity_normalization_enabled",
    "rag_trust_tier_ranking_enabled",
    "rag_semantic_cache_enabled",
    "rag_eval_ci_enabled",
    "rag_biomed_graph_enabled",
)

SEVERITY_RANK = dict(_SEVERITY_RANK)


def apply_flag_state(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool,
) -> None:
    """Set every persistent RAG flag on ``settings`` to ``enabled``.

    Also pins the NLI LLM path off so FIDES capture stays deterministic and
    offline regardless of ambient configuration.
    """

    for flag in PERSISTENT_RAG_FLAGS:
        monkeypatch.setattr(_settings, flag, enabled, raising=False)
    # Keep FIDES claim verification on its deterministic, offline path.
    monkeypatch.setattr(_settings, "rag_nli_llm_enabled", False, raising=False)


# ---------------------------------------------------------------------------
# Decision capture (normalised, comparable shapes)
# ---------------------------------------------------------------------------


def capture_careguard_decision(payload: dict[str, Any]) -> dict[str, Any]:
    """Capture the CareGuard guardrail decision for ``payload``.

    Returns the risk level/score plus a sorted, normalised view of every DDI
    alert so the result is order-stable and directly comparable.
    """

    result = run_careguard_analyze(payload)
    alerts = sorted(
        (
            str(alert.get("severity", "")).strip().lower(),
            tuple(sorted(alert.get("medications", []))),
            str(alert.get("type", "")),
            str(alert.get("message", "")),
        )
        for alert in result.get("ddi_alerts", [])
    )
    return {
        "risk_level": result["risk"]["level"],
        "risk_score": result["risk"]["score"],
        "alerts": alerts,
    }


def capture_openfda_severity(window: str) -> str:
    """Capture the openFDA free-text-derived severity for a label window."""

    return DrugSourceClient._infer_label_severity(window)


def capture_fides_decision(
    answer: str,
    retrieved_context: list[dict[str, Any]],
) -> dict[str, Any]:
    """Capture the FIDES verdict shape for an answer/evidence combination."""

    result = run_fides_lite(
        answer=answer,
        retrieved_context=retrieved_context,
        nli_enabled=True,
    )
    return {
        "verdict": result.verdict,
        "severity": result.severity,
        "has_contradiction": bool(result.contradiction_summary.get("has_contradiction")),
    }


_ROUTER = P1RoleIntentRouter()


def capture_emergency_route(query: str, role_hint: str | None = None) -> dict[str, Any]:
    """Capture the routing-level emergency fast-path decision for a query."""

    route = _ROUTER.route(query, role_hint=role_hint)
    return {
        "emergency": route.emergency,
        "intent": route.intent,
        "role": route.role,
    }


def capture_legal_guard(query: str, *, channel: str = "chat") -> dict[str, Any]:
    """Capture the legal/dosage guard decision for a query.

    ``clara_ml.main`` builds the FastAPI app at import time, so the import is
    kept local to this probe to avoid paying that cost for tests that only
    exercise the lighter guardrails.
    """

    from clara_ml.main import _detect_legal_guard_violation

    reason = _detect_legal_guard_violation(query, channel=channel)
    return {"blocked": reason is not None, "reason": reason}


#: Stable reason code emitted when the self-medication consent gate blocks a
#: flow, plus the HTTP status the production gate raises. These mirror the
#: ``HTTP 428 PRECONDITION_REQUIRED`` raised by
#: ``clara_api.core.consent.ensure_medical_disclaimer_consent`` when no recorded
#: medical-disclaimer consent matching the required version exists.
CONSENT_REQUIRED_REASON = "consent_required"
CONSENT_BLOCK_STATUS = 428


def capture_consent_gate(*, granted: bool) -> dict[str, Any]:
    """Capture the self-medication consent-gate decision for a consent state.

    Mirrors ``clara_api.core.consent.ensure_medical_disclaimer_consent``: a
    self-med flow is allowed only when an explicit, recorded medical-disclaimer
    consent matching the required version exists (modelled by ``granted is
    True`` on ``fixtures.ConsentState``); every other state blocks the flow with
    a 428 precondition. The decision is a pure function of consent state and
    never reads the persistent-RAG flags, so capture is deterministic and
    network-free (the API package is not importable from the ML env, and the
    real gate needs a DB session, so its decision is reproduced faithfully).
    """

    blocked = not granted
    return {
        "blocked": blocked,
        "reason": CONSENT_REQUIRED_REASON if blocked else None,
        "status_code": CONSENT_BLOCK_STATUS if blocked else None,
    }


def severity_rank(severity: str) -> int:
    """Rank a severity label (low<medium<high<critical); unknown -> medium."""

    return SEVERITY_RANK.get(str(severity).strip().lower(), SEVERITY_RANK["medium"])


# A guardrail "probe" is a zero-arg closure that returns a captured decision.
Probe = Callable[[], Any]
