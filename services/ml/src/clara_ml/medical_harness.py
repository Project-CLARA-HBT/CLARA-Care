"""Internal stage orchestrator for CLARA's medical answer pipeline.

This is intentionally a deterministic pre/post processor around the existing
router, CareGuard, RAG and FIDES components.  It never accepts provider keys or
clinical facts from the client beyond the existing structured context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clara_ml.agents.careguard import run_careguard_analyze
from clara_ml.medical_answer_v2 import detect_emergency_red_flags
from clara_ml.nlp.pii_filter import PiiResult, redact_pii
from clara_ml.routing import P1RoleIntentRouter, RouteResult


@dataclass
class HarnessPreflight:
    pii: PiiResult
    route: RouteResult
    red_flags: list[str]
    missing_information: list[dict[str, str]]
    careguard: dict[str, Any] | None
    stages: list[dict[str, Any]]


def _missing_information(context: dict[str, Any], intent: str) -> list[dict[str, str]]:
    fields = (
        ("age", "Age can change risk thresholds and treatment choices."),
        ("conditions", "Relevant conditions can change contraindications and urgency."),
        ("medications", "Current medicines are needed for interaction and duplication checks."),
        ("allergies", "Medication allergies must be confirmed before medication guidance."),
    )
    if intent == "evidence_review":
        fields = (("population", "The target population determines evidence applicability."),)
    return [
        {"field": key, "why_it_matters": reason} for key, reason in fields if not context.get(key)
    ]


def preflight_harness(
    *,
    query: str,
    role_hint: str | None,
    clinical_context: dict[str, Any] | None,
    router: P1RoleIntentRouter,
) -> HarnessPreflight:
    """Run all deterministic gates that must precede retrieval and generation."""

    stages: list[dict[str, Any]] = []
    pii = redact_pii(query)
    stages.append({"stage": "normalize_redact", "status": "completed", "pii_flags": pii.flags})
    route = router.route(pii.redacted_text, role_hint=role_hint)
    stages.append(
        {
            "stage": "intent_acuity",
            "status": "completed",
            "intent": route.intent,
            "role": route.role,
            "confidence": route.confidence,
        }
    )
    red_flags = detect_emergency_red_flags(pii.redacted_text)
    if red_flags and not route.emergency:
        route.intent = "emergency_triage"
        route.emergency = True
        route.confidence = max(route.confidence, 0.995)
    stages.append(
        {
            "stage": "emergency_gate",
            "status": "escalate" if route.emergency else "clear",
            "red_flags": red_flags,
            "retrieval_bypassed": route.emergency,
        }
    )
    context = clinical_context or {}
    missing = _missing_information(context, route.intent)
    stages.append(
        {
            "stage": "missing_information",
            "status": "needs_context" if missing else "sufficient",
            "fields": [item["field"] for item in missing],
        }
    )
    careguard: dict[str, Any] | None = None
    if not route.emergency and context.get("medications"):
        try:
            careguard = run_careguard_analyze(
                {
                    "medications": context.get("medications", []),
                    "allergies": context.get("allergies", []),
                    "symptoms": context.get("symptoms", []),
                    "labs": context.get("labs", {}),
                    "external_ddi_enabled": False,
                }
            )
            careguard_status = str(
                (careguard.get("metadata") or {}).get("rules_unavailable")
                and "unavailable"
                or "checked"
            )
        except Exception as exc:  # noqa: BLE001 - medication gate fails closed
            careguard_status = "error"
            stages.append(
                {
                    "stage": "medication_safety",
                    "status": "not_checked",
                    "error": exc.__class__.__name__,
                }
            )
        else:
            stages.append({"stage": "medication_safety", "status": careguard_status})
    else:
        stages.append(
            {
                "stage": "medication_safety",
                "status": "bypassed_emergency" if route.emergency else "not_applicable",
            }
        )
    return HarnessPreflight(pii, route, red_flags, missing, careguard, stages)


def postprocess_stages(
    *,
    preflight: HarnessPreflight,
    evidence_count: int,
    factcheck_verdict: str,
    degraded: bool,
) -> list[dict[str, Any]]:
    """Describe evidence, repair/abstain and postprocess stages for the artifact."""

    stages = list(preflight.stages)
    stages.append(
        {
            "stage": "evidence_claim_verification",
            "status": "completed"
            if evidence_count and factcheck_verdict in {"pass", "supported"}
            else "uncertain",
            "evidence_count": evidence_count,
            "factcheck_verdict": factcheck_verdict,
        }
    )
    stages.append(
        {
            "stage": "repair_abstain",
            "status": "abstain_or_warn" if degraded or not evidence_count else "pass",
        }
    )
    stages.append({"stage": "postprocess", "status": "completed"})
    return stages
