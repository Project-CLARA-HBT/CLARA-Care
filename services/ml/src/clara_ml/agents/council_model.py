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
_SHADOW_CONTRACT_VERSION = "council-specialist-shadow.v2"


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


def _unique_fact_ids(value: object, valid_fact_ids: set[str], *, limit: int = 20) -> list[str]:
    """Accept only stable IDs from the immutable case packet.

    A model may describe a fact in prose, but it cannot promote that prose into
    evidence.  Every released shadow finding therefore has to point to an ID
    generated before the model call.
    """

    output: list[str] = []
    seen: set[str] = set()
    for item in _text_list(value, limit=limit):
        if item not in valid_fact_ids or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _supported_findings(
    value: object,
    *,
    valid_fact_ids: set[str],
) -> list[dict[str, Any]]:
    """Normalize only evidence-linked findings from the specialist contract.

    The prior shadow contract accepted unconstrained observations alongside a
    separate list of fact IDs.  That made it possible to emit an unsupported
    claim while still citing an unrelated fact.  v2 binds each finding to its
    own case-fact IDs and drops invalid entries rather than guessing.
    """

    if not isinstance(value, list):
        return []

    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        statement = str(item.get("statement", "")).strip()
        evidence_ids = _unique_fact_ids(item.get("evidence_ids"), valid_fact_ids, limit=12)
        if not statement or not evidence_ids:
            continue
        key = (statement, tuple(evidence_ids))
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            {
                "statement": statement[:600],
                "evidence_ids": evidence_ids,
            }
        )
        if len(findings) >= 10:
            break
    return findings


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
    abstained = raw.get("abstain", False)
    if not isinstance(abstained, bool):
        return None
    abstention_reason = str(raw.get("abstention_reason", "")).strip()[:600]
    if abstained and not abstention_reason:
        return None

    supported_findings = _supported_findings(
        raw.get("supported_findings"),
        valid_fact_ids=valid_fact_ids,
    )
    if not abstained and not supported_findings:
        return None

    supporting_ids = _unique_fact_ids(
        raw.get("supporting_case_fact_ids"), valid_fact_ids
    )
    for finding in supported_findings:
        for fact_id in finding["evidence_ids"]:
            if fact_id not in supporting_ids:
                supporting_ids.append(fact_id)
    contradicting_ids = _unique_fact_ids(
        raw.get("contradicting_case_fact_ids"), valid_fact_ids
    )
    evidence_ids = _unique_fact_ids(
        raw.get("evidence_ids", supporting_ids), valid_fact_ids
    )
    for fact_id in supporting_ids:
        if fact_id not in evidence_ids:
            evidence_ids.append(fact_id)

    uncertainties = _text_list(raw.get("uncertainties"), limit=8)
    missing_decisive_data = _text_list(raw.get("missing_decisive_data"), limit=10)
    suggested_questions = _text_list(raw.get("suggested_questions"), limit=8)
    if abstained and not (uncertainties or missing_decisive_data or suggested_questions):
        return None

    safe_next_action_class = str(raw.get("safe_next_action_class", "")).strip()[:400]
    if not safe_next_action_class:
        return None

    evidence_status = "supported_case_facts"
    if abstained:
        evidence_status = "abstained_insufficient_evidence"
    elif missing_decisive_data or uncertainties:
        evidence_status = "supported_with_uncertainties"

    return {
        "contract_version": _SHADOW_CONTRACT_VERSION,
        "specialist": specialist,
        "supported_findings": supported_findings,
        "evidence_ids": evidence_ids,
        "relevant_observations": _text_list(raw.get("relevant_observations")),
        "hypotheses": _text_list(raw.get("hypotheses"), limit=6),
        "supporting_case_fact_ids": supporting_ids,
        "contradicting_case_fact_ids": contradicting_ids,
        "missing_decisive_data": missing_decisive_data,
        "uncertainties": uncertainties,
        "suggested_questions": suggested_questions,
        "abstained": abstained,
        "abstention_reason": abstention_reason if abstained else None,
        "triage": triage,
        "safe_next_action_class": safe_next_action_class,
        "model": model,
        "evidence_scope": "case_packet_only",
        "evidence_status": evidence_status,
        # This is deliberately not an LLM self-verification result.  It only
        # records deterministic validation that evidence IDs belong to the
        # immutable case packet.  Shadow output cannot release a decision.
        "verification": {
            "method": "deterministic_case_fact_id_validation",
            "status": "passed",
            "self_verification_performed": False,
        },
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


def _shadow_adjudication(assessments: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize independent shadow opinions without synthesizing a decision.

    This is a deterministic audit projection, not an LLM adjudicator.  It keeps
    the existing rule-based Council as the only released safety path and makes
    abstentions, evidence coverage, and disagreement explicit for later human
    evaluation.
    """

    triage_counts = {item: 0 for item in sorted(_TRIAGE)}
    evidence_ids: set[str] = set()
    supported_findings = 0
    abstention_count = 0
    for assessment in assessments:
        triage = assessment.get("triage")
        if triage in triage_counts:
            triage_counts[triage] += 1
        if assessment.get("abstained"):
            abstention_count += 1
            continue
        supported_findings += len(assessment.get("supported_findings", []))
        evidence_ids.update(
            item for item in assessment.get("evidence_ids", []) if isinstance(item, str)
        )

    active_triage = [triage for triage, count in triage_counts.items() if count]
    highest_triage = max(
        active_triage,
        key=lambda value: {
            "routine_follow_up": 1,
            "same_day_review": 2,
            "emergency_escalation": 3,
        }[value],
        default="routine_follow_up",
    )
    return {
        "stage": "deterministic_shadow_adjudication",
        "status": "not_release_eligible",
        "highest_safety_triage": highest_triage,
        "triage_counts": triage_counts,
        "divergence_detected": len(active_triage) > 1,
        "supported_finding_count": supported_findings,
        "evidence_ids": sorted(evidence_ids),
        "abstention_count": abstention_count,
        "requires_human_review": True,
        "self_verification_performed": False,
        "release_effect": "none_shadow_only",
    }


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
            "facts. Return one JSON object with keys: supported_findings (list of "
            "{statement, evidence_ids}), evidence_ids (list), relevant_observations "
            "(list), hypotheses (list, uncertainty explicit), supporting_case_fact_ids "
            "(list), contradicting_case_fact_ids (list), missing_decisive_data (list), "
            "uncertainties (list), suggested_questions (list), abstain (boolean), "
            "abstention_reason (string required when abstain=true), triage "
            "(routine_follow_up|same_day_review|emergency_escalation), and "
            "safe_next_action_class (string). Do not return confidence, probability, "
            "or a diagnosis. Never invent a fact or citation.\n\n"
            f"CASE_PACKET={json.dumps(packet, ensure_ascii=False, sort_keys=True)}"
        )
        try:
            response = client.generate(
                prompt,
                system_prompt=(
                    "You are one independent specialist reviewer inside CLARA AI "
                    "Council. Return strict JSON only. Cite supplied case fact IDs for "
                    "every supported finding, abstain when evidence is insufficient, and "
                    "do not verify or adjudicate your own output."
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
    return {
        "status": status,
        "mode": "shadow",
        "independent_reviews": True,
        "assessments": assessments,
        "failures": failures,
        "case_fact_count": len(packet["facts"]),
        "adjudication": _shadow_adjudication(assessments),
    }
