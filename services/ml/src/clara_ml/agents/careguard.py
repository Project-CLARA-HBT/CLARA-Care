from __future__ import annotations

from dataclasses import dataclass


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


def _detect_ddi_alerts(medications: list[str]) -> list[dict]:
    alerts: list[dict] = []
    med_set = set(medications)
    for rule in _DDI_RULES:
        if rule.meds.issubset(med_set):
            alerts.append(
                {
                    "type": "drug_drug",
                    "severity": rule.severity,
                    "medications": sorted(rule.meds),
                    "message": rule.message,
                }
            )
    return alerts


def _detect_allergy_conflicts(medications: list[str], allergies: list[str]) -> list[dict]:
    alerts: list[dict] = []
    med_set = set(medications)
    for allergy in allergies:
        if allergy in med_set:
            alerts.append(
                {
                    "type": "drug_allergy",
                    "severity": "high",
                    "medications": [allergy],
                    "message": f"Medication matches documented allergy: {allergy}.",
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
    ddi_alerts: list[dict],
    critical_symptoms: list[str],
    lab_flags: list[str],
) -> tuple[int, str]:
    score = 0
    for alert in ddi_alerts:
        if alert["severity"] == "high":
            score += 3
        elif alert["severity"] == "medium":
            score += 1
    score += len(critical_symptoms) * 2
    score += len(lab_flags)

    if score >= 5:
        return score, "high"
    if score >= 2:
        return score, "medium"
    return score, "low"


def _recommendation_for(level: str, ddi_alerts: list[dict], critical_symptoms: list[str]) -> str:
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

    ddi_alerts = _detect_ddi_alerts(medications)
    allergy_alerts = _detect_allergy_conflicts(medications, allergies)
    all_alerts = ddi_alerts + allergy_alerts

    critical_symptoms = _critical_symptom_hits(symptoms)
    lab_flags = _lab_risk_flags(labs)
    score, level = _risk_from_signals(all_alerts, critical_symptoms, lab_flags)

    factors = [f"critical_symptom:{s}" for s in critical_symptoms]
    factors.extend(f"lab_flag:{flag}" for flag in lab_flags)
    factors.extend(f"alert:{alert['type']}:{alert['severity']}" for alert in all_alerts)

    return {
        "risk": {
            "level": level,
            "score": score,
            "factors": factors,
        },
        "ddi_alerts": all_alerts,
        "recommendation": _recommendation_for(level, all_alerts, critical_symptoms),
        "metadata": {
            "pipeline": "p2-careguard-skeleton-v1",
            "fallback_used": True,
        },
    }
