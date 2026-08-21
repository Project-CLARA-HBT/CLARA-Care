"""Council's bounded, deterministic CareGuard medication-safety tool.

The Council release path must not infer drug interactions from a language model
or from a specialist prompt.  This module is a deliberately narrow adapter to
the existing CareGuard/DrugBank authority: it requests a strict DrugBank check,
reduces the response to a non-identifying Council safety projection, and never
returns medication names, interaction text, source errors, or raw CareGuard
objects.  It is called only from the deterministic Council boundary and its
result is never added to an LLM case packet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

CouncilTriage = Literal[
    "routine_follow_up",
    "same_day_review",
    "emergency_escalation",
]

_ALLOWED_DRUGBANK_STATES = frozenset({"ready", "unavailable", "disabled", "unknown"})
_MAX_ALERT_IDS = 12
_MAX_VERSION_LENGTH = 160


def _run_careguard(payload: dict[str, Any]) -> dict[str, Any]:
    """Delay the CareGuard import so the Council module has no import-time I/O."""

    from clara_ml.agents.careguard import run_careguard_analyze

    return run_careguard_analyze(payload)


def _safe_drugbank_state(value: object) -> str:
    state = str(value or "unknown").strip().lower()
    return state if state in _ALLOWED_DRUGBANK_STATES else "unknown"


def _safe_drugbank_version(value: object) -> str:
    """Keep only a bounded deployment dataset version, never a file path or error."""

    if not isinstance(value, str):
        return ""
    candidate = value.strip().replace("\n", " ").replace("\r", " ")
    if not candidate or "/" in candidate or "\\" in candidate:
        return ""
    return candidate[:_MAX_VERSION_LENGTH]


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _opaque_alert_ids(value: object) -> list[str]:
    """Create run-local opaque IDs without retaining any drug or alert text."""

    if not isinstance(value, list):
        return []
    return [f"council-ddi-alert-{index}" for index, _item in enumerate(value[:_MAX_ALERT_IDS], start=1)]


def _triage_floor_for_risk(value: object) -> CouncilTriage | None:
    """Map only deterministic CareGuard severity into the Council safety floor."""

    level = str(value or "").strip().lower()
    if level == "critical":
        return "emergency_escalation"
    if level == "high":
        return "same_day_review"
    return None


def evaluate_council_medication_safety(
    medications: list[str],
    *,
    runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Run the authoritative DDI check and return a safe Council projection.

    ``drugbank_required`` is forced true and an external DDI provider is forced
    off.  A source failure or unresolved medication identity is represented as
    a human-review requirement, never as an all-clear or fabricated alert.  The
    caller is responsible for applying the returned triage floor monotonically.
    """

    normalized = [item.strip() for item in medications if isinstance(item, str) and item.strip()]
    if not normalized:
        return None

    invoke = runner or _run_careguard
    try:
        result = invoke(
            {
                "medications": normalized,
                "drugbank_required": True,
                "external_ddi_enabled": False,
                # This is an internal deterministic safety call; do not ask
                # CareGuard to generate user-facing wording for Council.
                "locale": "vi",
            }
        )
    except Exception:  # noqa: BLE001 - fail closed without emitting internal detail
        return {
            "state": "unavailable",
            "drugbank_state": "unknown",
            "drugbank_version": "",
            "alert_ids": [],
            "triage_floor": None,
            "review_required": True,
        }

    if not isinstance(result, dict):
        return {
            "state": "unavailable",
            "drugbank_state": "unknown",
            "drugbank_version": "",
            "alert_ids": [],
            "triage_floor": None,
            "review_required": True,
        }

    metadata = _as_dict(result.get("metadata"))
    drugbank = _as_dict(metadata.get("drugbank"))
    ddi_status = _as_dict(result.get("ddi_status"))
    risk = _as_dict(result.get("risk"))
    alert_ids = _opaque_alert_ids(result.get("ddi_alerts"))
    drugbank_state = _safe_drugbank_state(drugbank.get("state"))
    drugbank_version = _safe_drugbank_version(drugbank.get("version"))

    if result.get("status") == "requires_medication_clarification":
        return {
            "state": "requires_clarification",
            "drugbank_state": drugbank_state,
            "drugbank_version": drugbank_version,
            "alert_ids": [],
            "triage_floor": None,
            "review_required": True,
        }

    if ddi_status.get("conclusion_available") is False or drugbank_state != "ready":
        return {
            "state": "unavailable",
            "drugbank_state": drugbank_state,
            "drugbank_version": drugbank_version,
            "alert_ids": [],
            "triage_floor": None,
            "review_required": True,
        }

    triage_floor = _triage_floor_for_risk(risk.get("level"))
    return {
        "state": "checked",
        "drugbank_state": "ready",
        "drugbank_version": drugbank_version,
        "alert_ids": alert_ids,
        "triage_floor": triage_floor,
        "review_required": bool(alert_ids) or triage_floor is not None,
    }
