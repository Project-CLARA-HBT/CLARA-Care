"""Structured clinical answer contract layered on top of the existing RAG pipeline.

This module does not generate medical facts. It packages the answer, evidence,
verification state, uncertainty, and next actions already produced by the real
retrieval/safety pipeline so clients can render a clinical workbench instead of
an opaque chat bubble.
"""

from __future__ import annotations

from typing import Any

_URGENT_INTENTS = {"emergency_triage"}
_MEDICAL_INTENTS = {
    "symptom_triage",
    "medication_safety",
    "doctor_case_review",
    "evidence_review",
    "emergency_triage",
}


def _text(value: Any, max_length: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:max_length]


def _evidence(context: Any) -> list[dict[str, Any]]:
    if not isinstance(context, list):
        return []
    output: list[dict[str, Any]] = []
    for index, raw_item in enumerate(context[:12], start=1):
        if not isinstance(raw_item, dict):
            continue
        raw: dict[str, Any] = raw_item
        raw_meta = raw.get("metadata")
        metadata: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        source = _text(raw.get("source") or metadata.get("source") or raw.get("id"), 200)
        url = _text(raw.get("url") or metadata.get("url"), 1000)
        title = _text(raw.get("title") or metadata.get("title") or source, 300)
        excerpt = _text(raw.get("text") or raw.get("content"), 700)
        record: dict[str, Any] = {
            "evidence_id": f"E{index}",
            "source": source,
            "title": title,
            "excerpt": excerpt,
        }
        if url:
            record["url"] = url
        trust_tier = raw.get("trust_tier") or metadata.get("trust_tier")
        if trust_tier is not None:
            record["trust_tier"] = trust_tier
        effective_date = raw.get("effective_date") or metadata.get("effective_date")
        if effective_date is not None:
            record["effective_date"] = str(effective_date)
        output.append(record)
    return output


def _missing_context(context: dict[str, Any] | None, intent: str) -> list[dict[str, str]]:
    context = context or {}
    suggestions: list[tuple[str, str]] = [
        ("age", "Tuổi/nhóm tuổi có thể thay đổi ngưỡng nguy cơ và lựa chọn điều trị."),
        ("conditions", "Bệnh nền giúp đánh giá chống chỉ định và mức độ khẩn."),
        ("medications", "Danh sách thuốc hiện dùng cần cho kiểm tra tương tác và trùng hoạt chất."),
        ("allergies", "Dị ứng thuốc cần được xác nhận trước mọi khuyến nghị dùng thuốc."),
    ]
    if intent == "evidence_review":
        suggestions = [("population", "Xác định quần thể/PICO giúp giới hạn bằng chứng phù hợp.")]
    return [
        {"field": field, "why_it_matters": reason}
        for field, reason in suggestions
        if not context.get(field)
    ]


def build_clinical_answer_package(
    *,
    answer: str,
    intent: str,
    emergency: bool,
    policy_action: str,
    model_used: str,
    retrieved_context: Any,
    factcheck: Any,
    clinical_context: dict[str, Any] | None = None,
    protocol: str = "clinical_answer",
) -> dict[str, Any] | None:
    """Return a transparent answer package for medical intents; otherwise ``None``."""

    if intent not in _MEDICAL_INTENTS and protocol == "chat":
        return None

    evidence = _evidence(retrieved_context)
    fact = factcheck if isinstance(factcheck, dict) else {}
    verdict = _text(fact.get("verdict"), 24) or "not_run"
    severity = _text(fact.get("severity"), 24) or "unknown"
    fallback = model_used.startswith(("local-synth", "api-safe", "api-local"))
    if emergency or intent in _URGENT_INTENTS:
        triage_level = "emergency"
    elif policy_action in {"block", "escalate"} or severity == "high":
        triage_level = "urgent_review"
    elif intent == "symptom_triage":
        triage_level = "clinical_review"
    else:
        triage_level = "routine"

    evidence_ids = [item["evidence_id"] for item in evidence]
    support_status = "supported"
    if not evidence:
        support_status = "insufficient_evidence"
    elif verdict in {"warn", "fail"}:
        support_status = "partially_supported"
    if fallback:
        support_status = "degraded"

    uncertainty_reasons: list[str] = []
    if not evidence:
        uncertainty_reasons.append("No retrievable evidence was available for this answer.")
    if verdict in {"warn", "fail"}:
        uncertainty_reasons.append("Automated claim verification did not fully pass.")
    if fallback:
        uncertainty_reasons.append("The primary model path was unavailable; degraded output was used.")

    return {
        "schema_version": "1.0",
        "protocol": protocol,
        "triage": {
            "level": triage_level,
            "emergency": bool(emergency),
            "policy_action": policy_action,
        },
        "answer": answer,
        "claim_support": {
            "claim_id": "C1",
            "claim_scope": "complete_generated_answer",
            "status": support_status,
            "evidence_ids": evidence_ids,
            "verification": {"verdict": verdict, "severity": severity},
        },
        "evidence_ledger": evidence,
        "uncertainty": {
            "level": "high" if support_status in {"insufficient_evidence", "degraded"} else severity,
            "reasons": uncertainty_reasons,
        },
        "missing_information": _missing_context(clinical_context, intent),
        "next_actions": [
            {
                "action": "Seek emergency care now",
                "priority": "immediate",
            }
        ]
        if triage_level == "emergency"
        else [
            {
                "action": "Review the evidence ledger and supply missing case context before acting",
                "priority": "before_clinical_decision",
            }
        ],
        "provenance": {
            "model_used": model_used,
            "evidence_count": len(evidence),
            "fallback_used": fallback,
        },
    }
