from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clara_ml.clients.drug_sources import DrugSourceClient
from clara_ml.config import settings


@dataclass(frozen=True)
class InteractionRule:
    meds: frozenset[str]
    severity: str
    message: str


_DDI_RULES = [
    InteractionRule(
        meds=frozenset({"warfarin", "ibuprofen"}),
        severity="high",
        message="Increased bleeding risk when anticoagulant is combined with NSAID.",
    ),
    InteractionRule(
        meds=frozenset({"warfarin", "aspirin"}),
        severity="high",
        message="Dual antithrombotic effect raises major bleeding risk.",
    ),
    InteractionRule(
        meds=frozenset({"lisinopril", "ibuprofen"}),
        severity="medium",
        message="NSAID may reduce antihypertensive effect and worsen renal perfusion.",
    ),
]

_CRITICAL_SYMPTOMS = {
    "chest pain",
    "shortness of breath",
    "fainting",
    "severe bleeding",
}

_SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_SEVERITY_SCORE = {
    "low": 0,
    "medium": 1,
    "high": 3,
    "critical": 5,
}


def _normalize_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip().lower()] if value.strip() else []
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip().lower())
        return normalized
    return []


def _normalize_severity(value: object) -> str:
    severity = str(value).strip().lower()
    return severity if severity in _SEVERITY_RANK else "medium"


def _pair_key(medications: object) -> tuple[str, ...]:
    return tuple(sorted(set(_normalize_text_list(medications))))


def _parse_sources(value: object, default: str | None = None) -> set[str]:
    sources: set[str] = set()
    if isinstance(value, str):
        for item in value.split(","):
            normalized = item.strip().lower()
            if normalized:
                sources.add(normalized)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                sources.add(item.strip().lower())

    if default and not sources:
        sources.add(default)
    return sources


def _detect_ddi_alerts(medications: list[str]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    med_set = set(medications)
    for rule in _DDI_RULES:
        if rule.meds.issubset(med_set):
            alerts.append(
                {
                    "type": "drug_drug",
                    "severity": rule.severity,
                    "medications": sorted(rule.meds),
                    "message": rule.message,
                    "source": "local_rules",
                }
            )
    return alerts


def _merge_drug_alerts(
    local_alerts: list[dict[str, Any]],
    external_alerts: list[dict[str, Any]],
    openfda_evidence: dict[tuple[str, str], dict[str, int]],
) -> list[dict[str, Any]]:
    merged_by_pair: dict[tuple[str, ...], dict[str, Any]] = {}

    def ingest(alert: dict[str, Any], default_source: str) -> None:
        if alert.get("type") != "drug_drug":
            return
        key = _pair_key(alert.get("medications"))
        if len(key) < 2:
            return

        incoming_severity = _normalize_severity(alert.get("severity"))
        incoming_rank = _SEVERITY_RANK[incoming_severity]
        incoming_message = str(alert.get("message", "")).strip() or "Potential DDI detected."
        incoming_sources = _parse_sources(alert.get("source"), default=default_source)

        existing = merged_by_pair.get(key)
        if existing is None:
            merged_by_pair[key] = {
                "type": "drug_drug",
                "severity": incoming_severity,
                "medications": list(key),
                "message": incoming_message,
                "_sources": incoming_sources,
            }
            return

        existing_severity = _normalize_severity(existing.get("severity"))
        existing_rank = _SEVERITY_RANK[existing_severity]
        if incoming_rank > existing_rank:
            existing["severity"] = incoming_severity
            existing["message"] = incoming_message

        existing_sources = existing.setdefault("_sources", set())
        if isinstance(existing_sources, set):
            existing_sources.update(incoming_sources)

    for alert in local_alerts:
        ingest(alert, default_source="local_rules")
    for alert in external_alerts:
        ingest(alert, default_source="rxnav")

    for pair, evidence in openfda_evidence.items():
        key = tuple(sorted(pair))
        label_mentions = int(evidence.get("label_mentions", 0))
        event_reports = int(evidence.get("event_reports", 0))

        existing = merged_by_pair.get(key)
        if existing is None:
            severity = "medium" if label_mentions > 0 or event_reports >= 100 else "low"
            merged_by_pair[key] = {
                "type": "drug_drug",
                "severity": severity,
                "medications": list(key),
                "message": "openFDA reports label/event co-occurrence for this medication pair.",
                "evidence": {
                    "openfda_label_mentions": label_mentions,
                    "openfda_event_reports": event_reports,
                },
                "_sources": {"openfda"},
            }
            continue

        existing_sources = existing.setdefault("_sources", set())
        if isinstance(existing_sources, set):
            existing_sources.add("openfda")

        merged_evidence = existing.setdefault("evidence", {})
        if isinstance(merged_evidence, dict):
            merged_evidence["openfda_label_mentions"] = max(
                label_mentions,
                int(merged_evidence.get("openfda_label_mentions", 0)),
            )
            merged_evidence["openfda_event_reports"] = max(
                event_reports,
                int(merged_evidence.get("openfda_event_reports", 0)),
            )

    alerts: list[dict[str, Any]] = []
    for alert in merged_by_pair.values():
        sources = alert.pop("_sources", set())
        if isinstance(sources, set):
            alert["source"] = ",".join(sorted(sources)) if sources else "local_rules"
        alerts.append(alert)

    alerts.sort(
        key=lambda item: (
            -_SEVERITY_RANK[_normalize_severity(item.get("severity"))],
            tuple(item.get("medications", [])),
        )
    )
    return alerts


def _detect_allergy_conflicts(medications: list[str], allergies: list[str]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    med_set = set(medications)
    for allergy in allergies:
        if allergy in med_set:
            alerts.append(
                {
                    "type": "drug_allergy",
                    "severity": "high",
                    "medications": [allergy],
                    "message": f"Medication matches documented allergy: {allergy}.",
                    "source": "local_rules",
                }
            )
    return alerts


def _critical_symptom_hits(symptoms: list[str]) -> list[str]:
    hits: list[str] = []
    for symptom in symptoms:
        if symptom in _CRITICAL_SYMPTOMS:
            hits.append(symptom)
    return hits


def _lab_risk_flags(labs: object) -> list[str]:
    if not isinstance(labs, dict):
        return []

    flags: list[str] = []
    egfr = labs.get("egfr")
    creatinine = labs.get("creatinine")
    if isinstance(egfr, (int, float)) and egfr < 30:
        flags.append("severe_renal_impairment")
    if isinstance(creatinine, (int, float)) and creatinine > 2.0:
        flags.append("elevated_creatinine")
    return flags


def _risk_from_signals(
    ddi_alerts: list[dict[str, Any]],
    critical_symptoms: list[str],
    lab_flags: list[str],
) -> tuple[int, str]:
    score = 0
    for alert in ddi_alerts:
        severity = _normalize_severity(alert.get("severity"))
        score += _SEVERITY_SCORE[severity]

    score += len(critical_symptoms) * 2
    score += len(lab_flags)

    severe_bleeding = "severe bleeding" in critical_symptoms
    has_high_risk_ddi = any(
        alert.get("type") == "drug_drug"
        and _normalize_severity(alert.get("severity")) in {"high", "critical"}
        for alert in ddi_alerts
    )

    if severe_bleeding and has_high_risk_ddi:
        return max(score, 9), "critical"
    if score >= 9:
        return score, "critical"
    if score >= 5:
        return score, "high"
    if score >= 2:
        return score, "medium"
    return score, "low"


def _recommendation_for(
    level: str,
    ddi_alerts: list[dict[str, Any]],
    critical_symptoms: list[str],
) -> str:
    if level == "critical":
        return (
            "Treat as critical medication safety risk: urgent clinician escalation now, "
            "hold non-essential interacting drugs, and triage emergency symptoms immediately."
        )
    if level == "high":
        return (
            "Escalate urgently for clinician review; hold non-essential interacting drugs and "
            "assess emergency symptoms immediately."
        )
    if level == "medium":
        return (
            "Schedule same-day medication review, confirm dosing, and repeat key labs if symptoms "
            "or renal risk are present."
        )
    if critical_symptoms:
        return "Critical symptoms detected despite low interaction burden; seek urgent care now."
    if ddi_alerts:
        return "Interaction signals detected; monitor closely and confirm treatment intent."
    return "No major immediate risk signals detected; continue routine monitoring."


def run_careguard_analyze(payload: dict) -> dict:
    symptoms = _normalize_text_list(payload.get("symptoms"))
    medications = _normalize_text_list(payload.get("medications"))
    allergies = _normalize_text_list(payload.get("allergies"))
    labs = payload.get("labs")

    local_ddi_alerts = _detect_ddi_alerts(medications)
    source_used = ["local_rules"]
    source_errors: dict[str, list[str]] = {}
    external_ddi_alerts: list[dict[str, Any]] = []
    openfda_evidence: dict[tuple[str, str], dict[str, int]] = {}
    needs_external_lookup = len(set(medications)) >= 2

    if needs_external_lookup and settings.external_ddi_enabled:
        try:
            external = DrugSourceClient(timeout_seconds=settings.external_ddi_timeout_seconds).fetch_ddi_context(
                medications
            )
            external_ddi_alerts = external.rxnav_alerts
            openfda_evidence = external.openfda_evidence
            source_errors = external.source_errors
            for source_name in external.source_used:
                if source_name not in source_used:
                    source_used.append(source_name)
        except Exception as exc:  # pragma: no cover - defensive hard-crash guard
            source_errors["external"] = [f"unhandled_error:{exc.__class__.__name__}"]
    elif needs_external_lookup:
        source_errors["external"] = ["disabled_by_config"]

    ddi_alerts = _merge_drug_alerts(local_ddi_alerts, external_ddi_alerts, openfda_evidence)
    allergy_alerts = _detect_allergy_conflicts(medications, allergies)
    all_alerts = ddi_alerts + allergy_alerts

    critical_symptoms = _critical_symptom_hits(symptoms)
    lab_flags = _lab_risk_flags(labs)
    score, level = _risk_from_signals(all_alerts, critical_symptoms, lab_flags)

    factors = [f"critical_symptom:{s}" for s in critical_symptoms]
    factors.extend(f"lab_flag:{flag}" for flag in lab_flags)
    factors.extend(
        f"alert:{alert['type']}:{_normalize_severity(alert.get('severity'))}"
        for alert in all_alerts
    )

    external_source_used = any(source in {"rxnav", "openfda"} for source in source_used)
    fallback_used = needs_external_lookup and (not external_source_used or bool(source_errors))

    return {
        "risk": {
            "level": level,
            "score": score,
            "factors": factors,
        },
        "ddi_alerts": all_alerts,
        "recommendation": _recommendation_for(level, all_alerts, critical_symptoms),
        "metadata": {
            "pipeline": "p2-careguard-ddi-standard-v2",
            "fallback_used": fallback_used,
            "source_used": source_used,
            "source_errors": source_errors,
        },
    }
