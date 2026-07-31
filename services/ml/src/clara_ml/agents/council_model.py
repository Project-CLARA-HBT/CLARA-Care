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
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError

from clara_ml.agents.council_evidence_packet import (
    public_evidence_packet_summary,
    validated_council_evidence_packet,
)
from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.llm.model_registry import ModelTask, build_task_client

_LEGACY_TRIAGE = {"routine_follow_up", "same_day_review", "emergency_escalation"}
_TRIAGE_SUGGESTION_BY_LEGACY = {
    "routine_follow_up": "scheduled_review",
    "same_day_review": "same_day",
    "emergency_escalation": "emergency",
}
_LEGACY_TRIAGE_BY_SUGGESTION = {
    "scheduled_review": "routine_follow_up",
    "self_care_information": "routine_follow_up",
    "same_day": "same_day_review",
    "emergency": "emergency_escalation",
    "insufficient_data": "routine_follow_up",
}
_TRIAGE_SUGGESTIONS = frozenset(_LEGACY_TRIAGE_BY_SUGGESTION)
_SHADOW_CONTRACT_VERSION = "council-specialist-shadow.v4"

# Shadow specialists can suggest only a bounded operational action class, never
# free-text treatment or prescribing. The deterministic contract verifier also
# rejects an action whose severity falls below the specialist's own triage
# vote. Neither value alters the released Council result: this model path is
# shadow-only.
CouncilSafeNextActionClass = Literal[
    "collect_more_information",
    "clinician_review",
    "same_day_in_person_review",
    "emergency_evaluation",
]
_ACTION_CLASS_SEVERITY = {
    "collect_more_information": 0,
    "clinician_review": 1,
    "same_day_in_person_review": 2,
    "emergency_evaluation": 3,
}
_MIN_ACTION_SEVERITY_BY_TRIAGE = {
    "routine_follow_up": 1,
    "same_day_review": 2,
    "emergency_escalation": 3,
}


class _CaseBoundFinding(BaseModel):
    """One model claim whose evidence must be a case-packet fact ID."""

    model_config = ConfigDict(extra="ignore")

    statement: StrictStr = Field(min_length=1, max_length=600)
    evidence_ids: list[StrictStr] = Field(default_factory=list, max_length=12)


class CouncilSpecialistOpinionContract(BaseModel):
    """Strict, versioned input contract for an independent shadow specialist.

    This object is deliberately internal: a valid model parse is still not a
    verified clinical assertion.  ``_normalize_assessment`` additionally binds
    every finding to immutable case facts and the shadow adjudicator has no
    authority to release or alter the deterministic Council result.
    """

    model_config = ConfigDict(extra="ignore")

    supported_findings: list[_CaseBoundFinding] = Field(default_factory=list, max_length=10)
    evidence_ids: list[StrictStr] = Field(default_factory=list, max_length=20)
    red_flags: list[StrictStr] = Field(default_factory=list, max_length=8)
    supporting_case_fact_ids: list[StrictStr] = Field(default_factory=list, max_length=20)
    contradicting_case_fact_ids: list[StrictStr] = Field(default_factory=list, max_length=20)
    missing_information: list[StrictStr] = Field(
        default_factory=list,
        max_length=10,
        validation_alias=AliasChoices("missing_information", "missing_decisive_data"),
    )
    uncertainties: list[StrictStr] = Field(default_factory=list, max_length=8)
    suggested_questions: list[StrictStr] = Field(default_factory=list, max_length=8)
    abstain: StrictBool = False
    abstention_reason: StrictStr = ""
    triage_suggestion: StrictStr = Field(
        validation_alias=AliasChoices("triage_suggestion", "triage"),
    )
    safe_next_action_class: CouncilSafeNextActionClass


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
    try:
        # Parse first so malformed/extra model output cannot drift the shadow
        # contract.  ``Strict*`` fields reject coerced booleans/numbers; this is
        # an input boundary, not an LLM self-check.
        raw = CouncilSpecialistOpinionContract.model_validate(raw).model_dump()
    except ValidationError:
        return None

    raw_triage = str(raw.get("triage_suggestion", raw.get("triage", ""))).strip().lower()
    if raw_triage in _LEGACY_TRIAGE:
        triage = raw_triage
        triage_suggestion = _TRIAGE_SUGGESTION_BY_LEGACY[triage]
    elif raw_triage in _TRIAGE_SUGGESTIONS:
        triage_suggestion = raw_triage
        triage = _LEGACY_TRIAGE_BY_SUGGESTION[triage_suggestion]
    else:
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
    missing_decisive_data = _text_list(raw.get("missing_information"), limit=10)
    suggested_questions = _text_list(raw.get("suggested_questions"), limit=8)
    if abstained and not (uncertainties or missing_decisive_data or suggested_questions):
        return None

    safe_next_action_class = raw.get("safe_next_action_class")
    if safe_next_action_class not in _ACTION_CLASS_SEVERITY:
        return None
    if _ACTION_CLASS_SEVERITY[safe_next_action_class] < _MIN_ACTION_SEVERITY_BY_TRIAGE[triage]:
        return None

    evidence_status = "supported_case_facts"
    if abstained:
        evidence_status = "abstained_insufficient_evidence"
    elif missing_decisive_data or uncertainties:
        evidence_status = "supported_with_uncertainties"

    # ``specialist_opinion`` is the canonical minimum Council specialist
    # contract.  The richer compatibility fields below retain per-finding case
    # fact bindings, which are stronger than a bare prose list.  Candidates for
    # red flags are deliberately not released from a model response: only the
    # deterministic emergency tools can raise an emergency floor.
    specialist_opinion = {
        "specialty": specialist,
        "supported_findings": [item["statement"] for item in supported_findings],
        "evidence_ids": evidence_ids,
        "red_flags": [],
        "missing_information": missing_decisive_data,
        "uncertainties": uncertainties,
        "suggested_questions": suggested_questions,
        "triage_suggestion": triage_suggestion,
        "abstained": abstained,
    }

    return {
        "contract_version": _SHADOW_CONTRACT_VERSION,
        "specialist": specialist,
        "specialist_opinion": specialist_opinion,
        "supported_findings": supported_findings,
        "evidence_ids": evidence_ids,
        "supporting_case_fact_ids": supporting_ids,
        "contradicting_case_fact_ids": contradicting_ids,
        "missing_decisive_data": missing_decisive_data,
        "uncertainties": uncertainties,
        "suggested_questions": suggested_questions,
        "abstained": abstained,
        "abstention_reason": abstention_reason if abstained else None,
        "triage": triage,
        "triage_suggestion": triage_suggestion,
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

    triage_counts = {item: 0 for item in sorted(_LEGACY_TRIAGE)}
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
    missing_source_claim_count = 0
    verified_claim_count = 0
    verified_specialists: list[str] = []
    for assessment in assessments:
        findings = assessment.get("supported_findings", [])
        if not isinstance(findings, list):
            continue
        specialist_verified = True
        for finding in findings:
            if not isinstance(finding, dict) or not finding.get("evidence_ids"):
                missing_source_claim_count += 1
                specialist_verified = False
            else:
                verified_claim_count += 1
        if specialist_verified and findings:
            specialist = assessment.get("specialist")
            if isinstance(specialist, str):
                verified_specialists.append(specialist)

    return {
        "stage": "deterministic_shadow_adjudication",
        "status": "not_release_eligible",
        "highest_safety_triage": highest_triage,
        "triage_counts": triage_counts,
        "divergence_detected": len(active_triage) > 1,
        "supported_finding_count": supported_findings,
        "evidence_ids": sorted(evidence_ids),
        "abstention_count": abstention_count,
        "claim_verification": {
            "method": "per_finding_case_fact_id_validation",
            "verified_claim_count": verified_claim_count,
            "missing_source_claim_count": missing_source_claim_count,
            "verified_specialists": sorted(verified_specialists),
            "self_verification_performed": False,
        },
        "adjudicator_scope": {
            "may": ["detect_consensus", "detect_disagreement", "identify_missing_sources"],
            "may_not": ["make_release_decision", "override_safety_policy", "confirm_facts"],
        },
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

    # An evidence snapshot is deliberately optional and may only be supplied by
    # the explicitly enabled Council boundary.  The validator strips/rejects
    # all content-bearing fields before the registry-bound specialist request;
    # specialists can see opaque IDs/categories only and must not use them as
    # factual support for a finding.
    has_evidence_packet = "council_evidence_packet" in payload
    evidence_packet = validated_council_evidence_packet(
        payload.get("council_evidence_packet")
    )
    evidence_summary = public_evidence_packet_summary(evidence_packet)
    if has_evidence_packet and evidence_packet is None:
        evidence_summary = {"status": "rejected", "evidence_count": 0, "categories": []}

    assessments: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    valid_fact_ids = {str(item["id"]) for item in packet["facts"]}
    for specialist in specialists:
        prompt = (
            f"Specialty: {specialist}. Independently review the case packet below. "
            "This is decision support, not diagnosis or prescribing. Use only supplied "
            "facts. Return one JSON object with keys: supported_findings (list of "
            "{statement, evidence_ids}), evidence_ids (list), supporting_case_fact_ids "
            "(list), contradicting_case_fact_ids (list), missing_information (list), "
            "red_flags (list), uncertainties (list), suggested_questions (list), "
            "abstain (boolean), abstention_reason (string required when abstain=true), "
            "triage_suggestion "
            "(emergency|same_day|scheduled_review|self_care_information|insufficient_data), and "
            "safe_next_action_class (one of collect_more_information, clinician_review, "
            "same_day_in_person_review, emergency_evaluation). Do not return confidence, "
            "probability, a diagnosis, treatment instruction, or medication-dose change. "
            "Never invent a fact or citation. A separate evidence-availability packet, when "
            "present, contains only opaque retrieval IDs and categories. It is not evidence "
            "content: do not use it to support a finding, diagnose, prescribe, or alter triage. "
            "Only supplied CASE_PACKET fact IDs can support a finding.\n\n"
            f"CASE_PACKET={json.dumps(packet, ensure_ascii=False, sort_keys=True)}"
        )
        if evidence_packet is not None:
            prompt += (
                "\n\nVALIDATED_EVIDENCE_AVAILABILITY="
                f"{json.dumps(evidence_packet, ensure_ascii=False, sort_keys=True)}"
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
    result = {
        "status": status,
        "mode": "shadow",
        "independent_reviews": True,
        "assessments": assessments,
        "failures": failures,
        "case_fact_count": len(packet["facts"]),
        "adjudication": _shadow_adjudication(assessments),
    }
    if has_evidence_packet:
        result["evidence_packet"] = evidence_summary
    return result
