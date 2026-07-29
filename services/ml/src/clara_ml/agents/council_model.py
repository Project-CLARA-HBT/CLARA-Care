"""Independent model-backed Council assessments in governed shadow mode.

This module does not role-play a conversation between agents. Each selected
specialty receives the same immutable, normalized case packet independently and
returns a strict structured assessment. The rule engine remains the release
safety baseline until the model path passes clinical evaluation; failures return
an explicit unavailable record and never synthetic clinical content.
"""

from __future__ import annotations

import json
import re
from typing import Any

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.llm.model_registry import ModelTask, build_task_client

_TRIAGE = {"routine_follow_up", "same_day_review", "emergency_escalation"}


def _client() -> DeepSeekClient:
    client, _selection = build_task_client(ModelTask.COUNCIL_SHADOW, settings)
    return client


def _json_object(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text or "", flags=re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _text_list(value: object, *, limit: int = 10) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            output.append(text[:600])
        if len(output) >= limit:
            break
    return output


def _normalize_assessment(
    raw: dict[str, Any],
    *,
    specialist: str,
    model: str,
    valid_fact_ids: set[str],
) -> dict[str, Any] | None:
    triage = str(raw.get("triage", "")).strip().lower()
    if triage not in _TRIAGE:
        return None
    confidence_raw = raw.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence_raw)))
    except (TypeError, ValueError):
        confidence = 0.0
    supporting_ids = [
        item
        for item in _text_list(raw.get("supporting_case_fact_ids"), limit=20)
        if item in valid_fact_ids
    ]
    contradicting_ids = [
        item
        for item in _text_list(raw.get("contradicting_case_fact_ids"), limit=20)
        if item in valid_fact_ids
    ]
    return {
        "specialist": specialist,
        "relevant_observations": _text_list(raw.get("relevant_observations")),
        "hypotheses": _text_list(raw.get("hypotheses"), limit=6),
        "supporting_case_fact_ids": supporting_ids,
        "contradicting_case_fact_ids": contradicting_ids,
        "missing_decisive_data": _text_list(raw.get("missing_decisive_data")),
        "triage": triage,
        "confidence": round(confidence, 3),
        "safe_next_action_class": str(
            raw.get("safe_next_action_class", "")
        ).strip()[:400],
        "model": model,
        "evidence_scope": "case_packet_only",
    }


def _case_packet(payload: dict[str, Any]) -> dict[str, Any]:
    """Create stable fact IDs so assessments cite supplied facts, not prose memory."""

    facts: list[dict[str, Any]] = []
    for section in ("symptoms", "medications", "history"):
        value = payload.get(section)
        items = value if isinstance(value, list) else ([value] if value else [])
        for index, item in enumerate(items, start=1):
            facts.append({"id": f"{section}-{index}", "section": section, "value": item})
    labs = payload.get("labs")
    if isinstance(labs, dict):
        for index, (name, value) in enumerate(sorted(labs.items()), start=1):
            facts.append(
                {
                    "id": f"lab-{index}",
                    "section": "labs",
                    "name": name,
                    "value": value,
                }
            )
    return {"facts": facts}


def run_model_council_shadow(
    payload: dict[str, Any],
    specialists: list[str],
) -> dict[str, Any]:
    if not settings.council_llm_shadow_enabled:
        return {"status": "disabled", "assessments": [], "failures": []}

    packet = _case_packet(payload)
    if not packet["facts"]:
        return {
            "status": "insufficient_input",
            "assessments": [],
            "failures": [],
        }

    try:
        client = _client()
    except (TypeError, ValueError, RuntimeError) as exc:
        return {
            "status": "unavailable",
            "assessments": [],
            "failures": [{"stage": "client", "code": exc.__class__.__name__}],
        }

    assessments: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    valid_fact_ids = {str(item["id"]) for item in packet["facts"]}
    for specialist in specialists:
        prompt = (
            f"Specialty: {specialist}. Independently review the case packet below. "
            "This is decision support, not diagnosis or prescribing. Use only supplied "
            "facts. Return one JSON object with keys: relevant_observations (list), "
            "hypotheses (list, uncertainty explicit), supporting_case_fact_ids (list), "
            "contradicting_case_fact_ids (list), missing_decisive_data (list), triage "
            "(routine_follow_up|same_day_review|emergency_escalation), confidence (0..1), "
            "safe_next_action_class (string). Never invent a fact or citation.\n\n"
            f"CASE_PACKET={json.dumps(packet, ensure_ascii=False, sort_keys=True)}"
        )
        try:
            response = client.generate(
                prompt,
                system_prompt=(
                    "You are one independent specialist reviewer inside CLARA AI "
                    "Council. Return strict JSON only and cite supplied case fact IDs."
                ),
                max_tokens=settings.council_llm_max_tokens,
            )
            parsed = _json_object(response.content)
            normalized = (
                _normalize_assessment(
                    parsed,
                    specialist=specialist,
                    model=response.model,
                    valid_fact_ids=valid_fact_ids,
                )
                if parsed is not None
                else None
            )
            if normalized is None:
                failures.append({"specialist": specialist, "code": "invalid_schema"})
            else:
                assessments.append(normalized)
        except Exception as exc:  # noqa: BLE001 - explicit unavailable record
            failures.append({"specialist": specialist, "code": exc.__class__.__name__})

    if assessments and not failures:
        status = "complete"
    elif assessments:
        status = "partial"
    else:
        status = "unavailable"
    triage_counts = {item: 0 for item in sorted(_TRIAGE)}
    for assessment in assessments:
        triage_counts[assessment["triage"]] += 1
    highest_triage = max(
        (item["triage"] for item in assessments),
        key=lambda value: {
            "routine_follow_up": 1,
            "same_day_review": 2,
            "emergency_escalation": 3,
        }[value],
        default="routine_follow_up",
    )
    triage_values = {item["triage"] for item in assessments}
    return {
        "status": status,
        "mode": "shadow",
        "independent_reviews": True,
        "assessments": assessments,
        "failures": failures,
        "case_fact_count": len(packet["facts"]),
        "adjudication": {
            "highest_safety_triage": highest_triage,
            "triage_counts": triage_counts,
            "divergence_detected": len(triage_values) > 1,
            "release_effect": "none_shadow_only",
        },
    }
