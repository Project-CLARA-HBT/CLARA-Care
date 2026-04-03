from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

from clara_ml.agents.council_neural import score_council_risk
from clara_ml.config import settings

SUPPORTED_SPECIALISTS = (
    "cardiology",
    "neurology",
    "nephrology",
    "pharmacology",
    "endocrinology",
)

_TRIAGE_SCORE = {
    "routine_follow_up": 1,
    "same_day_review": 2,
    "emergency_escalation": 3,
}

_RED_FLAG_RULES = {
    "possible_acute_coronary_syndrome": (
        "chest pain",
        "dau nguc",
    ),
    "possible_stroke": (
        "one sided weakness",
        "slurred speech",
        "facial droop",
        "sudden vision loss",
    ),
    "severe_respiratory_distress": (
        "shortness of breath",
        "kho tho",
        "cannot breathe",
    ),
    "loss_of_consciousness": (
        "loss of consciousness",
        "fainting",
        "unresponsive",
    ),
    "severe_bleeding": (
        "severe bleeding",
        "vomiting blood",
        "black stool",
    ),
}

_NEGATION_PREFIX_RE = re.compile(
    r"(?:\bno\b|\bnot\b|\bdeny\b|\bdenies\b|\bdenied\b|\bwithout\b|"
    r"\bnegative\s+for\b|\bkhong\b|\bkhông\b|\bko\b|\bchua\b|\bchưa\b)"
    r"(?:\s+\w+){0,3}\s*$",
    flags=re.IGNORECASE,
)
_NEGATION_SUFFIX_RE = re.compile(
    r"^\W*(?:none|absent|denied|negative|unlikely|ruled\s*out|resolved)\b",
    flags=re.IGNORECASE,
)
_DURATION_HINT_RE = re.compile(
    r"\b(\d+\s*(?:h|hr|hour|hours|day|days|week|weeks|month|months)|"
    r"today|yesterday|since|onset|ngay|hom nay|hom qua|tuan|thang|gio)\b",
    flags=re.IGNORECASE,
)
_SEVERITY_HINT_RE = re.compile(
    r"\b(severe|worsening|intense|sudden|acute|du doi|nang|tang dan)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class SpecialistAssessment:
    specialist: str
    reasoning_log: list[str]
    key_findings: list[str]
    triage: str
    recommendation: str


def _normalize_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        clean = value.strip().lower()
        return [clean] if clean else []
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip().lower())
        return normalized
    return []


def _normalize_labs(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, raw in value.items():
        lab_key = str(key).strip().lower()
        if not lab_key:
            continue
        if isinstance(raw, bool):
            continue
        if isinstance(raw, (int, float)):
            normalized[lab_key] = float(raw)
            continue
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                continue
            try:
                normalized[lab_key] = float(text)
            except ValueError:
                continue
    return normalized


def _normalize_history(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        clean = value.strip().lower()
        return [clean] if clean else []
    if isinstance(value, list):
        return _normalize_text_list(value)
    if isinstance(value, dict):
        chunks: list[str] = []
        for key, raw in sorted(value.items(), key=lambda item: str(item[0])):
            key_text = str(key).strip().lower()
            if key_text:
                chunks.append(key_text)
            if isinstance(raw, str):
                val = raw.strip().lower()
                if val:
                    chunks.append(val)
            elif isinstance(raw, list):
                chunks.extend(_normalize_text_list(raw))
            elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
                chunks.append(str(raw))
        return chunks
    return []


def _is_negated_span(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 52) : start].strip()
    suffix = text[end : min(len(text), end + 24)].strip()
    if _NEGATION_PREFIX_RE.search(prefix):
        return True
    if _NEGATION_SUFFIX_RE.match(suffix):
        return True
    return False


def _scan_phrase_hits(
    texts: list[str], phrases: tuple[str, ...], *, negation_aware: bool = False
) -> dict[str, list[dict[str, str]]]:
    positive: list[dict[str, str]] = []
    negated: list[dict[str, str]] = []
    seen_positive: set[tuple[str, str]] = set()
    seen_negated: set[tuple[str, str]] = set()

    for raw_text in texts:
        text = raw_text.lower()
        for phrase in phrases:
            search_from = 0
            while True:
                start = text.find(phrase, search_from)
                if start < 0:
                    break
                end = start + len(phrase)
                hit_key = (raw_text, phrase)
                if negation_aware and _is_negated_span(text, start, end):
                    if hit_key not in seen_negated:
                        seen_negated.add(hit_key)
                        negated.append({"phrase": phrase, "text": raw_text})
                else:
                    if hit_key not in seen_positive:
                        seen_positive.add(hit_key)
                        positive.append({"phrase": phrase, "text": raw_text})
                search_from = end

    return {
        "positive": positive,
        "negated": negated,
    }


def _contains_phrase(
    texts: list[str], phrases: tuple[str, ...], *, negation_aware: bool = False
) -> bool:
    hits = _scan_phrase_hits(texts, phrases, negation_aware=negation_aware)
    return bool(hits["positive"])


def _med_present(medications: list[str], keyword: str) -> bool:
    for med in medications:
        if keyword in med:
            return True
    return False


def _resolve_specialists(requested: object) -> list[str]:
    if not isinstance(requested, list):
        return list(SUPPORTED_SPECIALISTS)

    selected: list[str] = []
    for raw in requested:
        if not isinstance(raw, str):
            continue
        specialist = raw.strip().lower()
        if specialist in SUPPORTED_SPECIALISTS and specialist not in selected:
            selected.append(specialist)

    if not selected:
        selected = list(SUPPORTED_SPECIALISTS)

    if len(selected) < 2:
        for default in SUPPORTED_SPECIALISTS:
            if default not in selected:
                selected.append(default)
            if len(selected) >= 2:
                break

    if len(selected) > 5:
        selected = selected[:5]
    return selected


def _detect_red_flags(symptoms: list[str]) -> tuple[list[str], list[dict[str, str]], list[dict[str, str]]]:
    hits: list[str] = []
    positive_matches: list[dict[str, str]] = []
    negated_matches: list[dict[str, str]] = []

    for flag_name, phrases in _RED_FLAG_RULES.items():
        scan = _scan_phrase_hits(symptoms, phrases, negation_aware=True)
        for item in scan["positive"]:
            positive_matches.append({"flag": flag_name, **item})
        for item in scan["negated"]:
            negated_matches.append({"flag": flag_name, **item})
        if scan["positive"]:
            hits.append(flag_name)

    return hits, positive_matches, negated_matches


def _evaluate_cardiology(
    symptoms: list[str], labs: dict[str, float], medications: list[str], history: list[str]
) -> SpecialistAssessment:
    findings: list[str] = []
    log: list[str] = ["Reviewed cardiovascular symptoms, medications, labs, and history."]

    chest_pain = _contains_phrase(symptoms, ("chest pain", "dau nguc"), negation_aware=True)
    dyspnea = _contains_phrase(symptoms, ("shortness of breath", "kho tho"), negation_aware=True)
    palpitations = _contains_phrase(symptoms, ("palpitations", "tachycardia"), negation_aware=True)
    troponin = labs.get("troponin")
    bnp = labs.get("bnp")
    cardiac_history = _contains_phrase(
        history,
        ("coronary artery disease", "heart failure", "afib", "arrhythmia", "hypertension"),
    )
    anticoagulant = _med_present(medications, "warfarin") or _med_present(medications, "apixaban")

    if chest_pain:
        findings.append("chest_pain_reported")
        log.append("Detected chest pain symptom, which raises ACS concern.")
    if dyspnea:
        findings.append("dyspnea_reported")
        log.append("Detected shortness of breath symptom, requiring cardiac differential.")
    if palpitations:
        findings.append("palpitations_reported")
        log.append("Palpitations detected; rhythm instability is possible.")
    if isinstance(troponin, float) and troponin > 0.04:
        findings.append("troponin_elevated")
        log.append("Troponin exceeds 0.04 and supports immediate ischemic evaluation.")
    if isinstance(bnp, float) and bnp > 400:
        findings.append("bnp_elevated")
        log.append("BNP over 400 suggests possible decompensated heart failure.")
    if cardiac_history:
        findings.append("cardiac_history_present")
        log.append("Cardiac history increases baseline risk.")
    if anticoagulant:
        findings.append("on_anticoagulant")
        log.append("Anticoagulant exposure influences bleeding-vs-thrombotic risk balancing.")

    if chest_pain or (isinstance(troponin, float) and troponin > 0.04):
        triage = "emergency_escalation"
        recommendation = "Prioritize ED-level cardiac rule-out and continuous monitoring."
    elif dyspnea or palpitations or cardiac_history or (isinstance(bnp, float) and bnp > 400):
        triage = "same_day_review"
        recommendation = "Arrange same-day ECG and focused cardiology review."
    else:
        triage = "routine_follow_up"
        recommendation = "No immediate cardiac escalation signal; continue outpatient monitoring."
        log.append("No dominant high-acuity cardiovascular trigger found.")

    return SpecialistAssessment(
        specialist="cardiology",
        reasoning_log=log,
        key_findings=findings,
        triage=triage,
        recommendation=recommendation,
    )


def _evaluate_neurology(
    symptoms: list[str], labs: dict[str, float], medications: list[str], history: list[str]
) -> SpecialistAssessment:
    _ = (labs, medications)
    findings: list[str] = []
    log = ["Reviewed neurologic symptom pattern and neurologic history."]

    stroke_signs = _contains_phrase(
        symptoms,
        ("one sided weakness", "slurred speech", "facial droop", "sudden vision loss"),
        negation_aware=True,
    )
    seizure = _contains_phrase(symptoms, ("seizure", "convulsion"), negation_aware=True)
    confusion = _contains_phrase(symptoms, ("confusion", "altered mental status"), negation_aware=True)
    severe_headache = _contains_phrase(symptoms, ("severe headache", "worst headache"), negation_aware=True)
    neuro_history = _contains_phrase(history, ("stroke", "tia", "epilepsy", "migraine"))

    if stroke_signs:
        findings.append("focal_neurologic_deficit")
        log.append("Focal neurologic deficit signals possible acute stroke.")
    if seizure:
        findings.append("seizure_activity")
        log.append("Seizure activity is a high-acuity neurologic event.")
    if confusion:
        findings.append("acute_confusion")
        log.append("Acute confusion can indicate urgent neurologic or metabolic pathology.")
    if severe_headache:
        findings.append("severe_headache")
        log.append("Severe headache requires exclusion of secondary dangerous causes.")
    if neuro_history:
        findings.append("neurologic_history_present")
        log.append("Neurologic history increases risk of recurrence.")

    if stroke_signs or seizure or confusion:
        triage = "emergency_escalation"
        recommendation = "Escalate for immediate neurologic assessment and imaging."
    elif severe_headache or neuro_history:
        triage = "same_day_review"
        recommendation = "Arrange same-day neurologic exam and targeted diagnostics."
    else:
        triage = "routine_follow_up"
        recommendation = "No immediate neurologic emergency pattern identified."
        log.append("Neurologic risk signals are limited in this dataset.")

    return SpecialistAssessment(
        specialist="neurology",
        reasoning_log=log,
        key_findings=findings,
        triage=triage,
        recommendation=recommendation,
    )


def _evaluate_nephrology(
    symptoms: list[str], labs: dict[str, float], medications: list[str], history: list[str]
) -> SpecialistAssessment:
    _ = symptoms
    findings: list[str] = []
    log = ["Reviewed renal function markers, nephrotoxic exposure, and kidney history."]

    egfr = labs.get("egfr")
    creatinine = labs.get("creatinine")
    potassium = labs.get("potassium")
    ckd_history = _contains_phrase(history, ("ckd", "chronic kidney disease", "renal disease", "dialysis"))
    nsaid_exposure = any(_med_present(medications, med) for med in ("ibuprofen", "naproxen", "diclofenac"))

    if isinstance(egfr, float) and egfr < 30:
        findings.append("egfr_under_30")
        log.append("eGFR below 30 indicates advanced kidney impairment.")
    if isinstance(creatinine, float) and creatinine > 2.0:
        findings.append("creatinine_above_2")
        log.append("Creatinine above 2.0 suggests reduced renal clearance.")
    if isinstance(potassium, float) and potassium >= 6.0:
        findings.append("severe_hyperkalemia")
        log.append("Potassium >= 6.0 is a potentially life-threatening electrolyte finding.")
    if ckd_history:
        findings.append("kidney_history_present")
        log.append("Known CKD history increases sensitivity to nephrotoxic triggers.")
    if nsaid_exposure:
        findings.append("nsaid_exposure")
        log.append("NSAID exposure can worsen renal perfusion in vulnerable patients.")

    if (isinstance(egfr, float) and egfr < 15) or (isinstance(potassium, float) and potassium >= 6.0):
        triage = "emergency_escalation"
        recommendation = "Escalate immediately for acute renal/electrolyte stabilization."
    elif (
        (isinstance(egfr, float) and egfr < 30)
        or (isinstance(creatinine, float) and creatinine > 2.0)
        or (ckd_history and nsaid_exposure)
    ):
        triage = "same_day_review"
        recommendation = "Prioritize same-day nephrology review and medication adjustment."
    else:
        triage = "routine_follow_up"
        recommendation = "Renal profile does not require emergency escalation at this stage."
        log.append("No dominant severe kidney instability signal found.")

    return SpecialistAssessment(
        specialist="nephrology",
        reasoning_log=log,
        key_findings=findings,
        triage=triage,
        recommendation=recommendation,
    )


def _evaluate_pharmacology(
    symptoms: list[str], labs: dict[str, float], medications: list[str], history: list[str]
) -> SpecialistAssessment:
    _ = (labs, history)
    findings: list[str] = []
    log = ["Reviewed medication safety interactions and risk-amplifying symptom context."]

    on_warfarin = _med_present(medications, "warfarin")
    on_nsaid = any(_med_present(medications, med) for med in ("ibuprofen", "naproxen", "diclofenac"))
    on_aspirin = _med_present(medications, "aspirin")
    on_ace_or_arb = any(
        _med_present(medications, med)
        for med in ("lisinopril", "enalapril", "losartan", "valsartan", "ramipril")
    )
    on_diuretic = any(_med_present(medications, med) for med in ("furosemide", "hydrochlorothiazide"))
    bleeding_symptoms = _contains_phrase(
        symptoms,
        ("severe bleeding", "vomiting blood", "black stool"),
        negation_aware=True,
    )

    if on_warfarin and on_nsaid:
        findings.append("warfarin_nsaid_interaction")
        log.append("Warfarin + NSAID combination elevates major bleeding risk.")
    if on_warfarin and on_aspirin:
        findings.append("warfarin_aspirin_interaction")
        log.append("Warfarin + aspirin combination requires strict indication and monitoring.")
    if on_ace_or_arb and on_diuretic and on_nsaid:
        findings.append("triple_whammy_risk")
        log.append("ACE/ARB + diuretic + NSAID pattern increases AKI risk.")
    if bleeding_symptoms:
        findings.append("active_bleeding_signal")
        log.append("Bleeding symptoms elevate urgency of interaction mitigation.")

    has_high_risk_combo = any(
        key in findings
        for key in ("warfarin_nsaid_interaction", "warfarin_aspirin_interaction", "triple_whammy_risk")
    )

    if bleeding_symptoms and has_high_risk_combo:
        triage = "emergency_escalation"
        recommendation = "Escalate immediately for bleeding risk stabilization and medication hold decisions."
    elif has_high_risk_combo:
        triage = "same_day_review"
        recommendation = "Conduct same-day medication reconciliation and risk mitigation changes."
    else:
        triage = "routine_follow_up"
        recommendation = "No high-severity interaction pattern detected in current medication list."
        log.append("Medication profile is not showing major deterministic DDI triggers.")

    return SpecialistAssessment(
        specialist="pharmacology",
        reasoning_log=log,
        key_findings=findings,
        triage=triage,
        recommendation=recommendation,
    )


def _evaluate_endocrinology(
    symptoms: list[str], labs: dict[str, float], medications: list[str], history: list[str]
) -> SpecialistAssessment:
    _ = medications
    findings: list[str] = []
    log = ["Reviewed endocrine markers, glycemic range, and diabetes-related symptom burden."]

    glucose = labs.get("glucose")
    hba1c = labs.get("hba1c")
    diabetes_history = _contains_phrase(history, ("diabetes", "t2dm", "t1dm"))
    hyperglycemia_symptoms = _contains_phrase(
        symptoms,
        ("polyuria", "polydipsia", "fatigue", "unintentional weight loss"),
        negation_aware=True,
    )
    hypoglycemia_symptoms = _contains_phrase(symptoms, ("sweating", "tremor", "confusion"), negation_aware=True)

    if isinstance(glucose, float) and glucose >= 400:
        findings.append("glucose_above_400")
        log.append("Glucose >= 400 indicates severe hyperglycemia.")
    if isinstance(glucose, float) and glucose < 54:
        findings.append("glucose_below_54")
        log.append("Glucose < 54 indicates clinically significant hypoglycemia.")
    if isinstance(hba1c, float) and hba1c >= 9.0:
        findings.append("hba1c_above_9")
        log.append("HbA1c >= 9 indicates persistent poor glycemic control.")
    if diabetes_history:
        findings.append("diabetes_history_present")
        log.append("Known diabetes history contextualizes endocrine risk trajectory.")
    if hyperglycemia_symptoms:
        findings.append("hyperglycemia_symptoms")
        log.append("Symptoms align with uncontrolled glucose burden.")
    if hypoglycemia_symptoms:
        findings.append("hypoglycemia_symptoms")
        log.append("Symptoms suggest possible low-glucose episodes.")

    if (isinstance(glucose, float) and (glucose >= 400 or glucose < 54)) or (
        hypoglycemia_symptoms and isinstance(glucose, float) and glucose < 70
    ):
        triage = "emergency_escalation"
        recommendation = "Escalate urgently for acute glycemic stabilization."
    elif (
        (isinstance(glucose, float) and glucose >= 250)
        or (isinstance(hba1c, float) and hba1c >= 9.0)
        or (diabetes_history and hyperglycemia_symptoms)
    ):
        triage = "same_day_review"
        recommendation = "Schedule same-day endocrine review and treatment optimization."
    else:
        triage = "routine_follow_up"
        recommendation = "No immediate endocrine emergency trigger from available markers."
        log.append("Endocrine profile appears stable enough for routine follow-up.")

    return SpecialistAssessment(
        specialist="endocrinology",
        reasoning_log=log,
        key_findings=findings,
        triage=triage,
        recommendation=recommendation,
    )


_SPECIALIST_EVALUATORS = {
    "cardiology": _evaluate_cardiology,
    "neurology": _evaluate_neurology,
    "nephrology": _evaluate_nephrology,
    "pharmacology": _evaluate_pharmacology,
    "endocrinology": _evaluate_endocrinology,
}


def _build_conflicts(assessments: list[SpecialistAssessment]) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    for left, right in combinations(assessments, 2):
        left_score = _TRIAGE_SCORE[left.triage]
        right_score = _TRIAGE_SCORE[right.triage]
        if abs(left_score - right_score) >= 2:
            conflicts.append(
                {
                    "type": "triage_mismatch",
                    "specialists": [left.specialist, right.specialist],
                    "detail": (
                        f"{left.specialist} recommends {left.triage} while "
                        f"{right.specialist} recommends {right.triage}."
                    ),
                }
            )
    return conflicts


def _consensus_triage(assessments: list[SpecialistAssessment]) -> str:
    counts = {triage: 0 for triage in _TRIAGE_SCORE}
    for item in assessments:
        counts[item.triage] += 1
    return max(counts, key=lambda triage: (counts[triage], _TRIAGE_SCORE[triage]))


def _build_consensus_metadata(
    assessments: list[SpecialistAssessment],
    consensus_triage: str,
    conflicts: list[dict[str, object]],
) -> dict[str, Any]:
    triage_counts = {triage: 0 for triage in _TRIAGE_SCORE}
    for item in assessments:
        triage_counts[item.triage] += 1

    total = max(1, len(assessments))
    support_ratio = triage_counts[consensus_triage] / total
    disagreement_index = (total - triage_counts[consensus_triage]) / total

    strongest_dissent = ""
    strongest_dissent_votes = 0
    for triage, votes in triage_counts.items():
        if triage == consensus_triage:
            continue
        if votes > strongest_dissent_votes:
            strongest_dissent = triage
            strongest_dissent_votes = votes

    return {
        "winning_triage": consensus_triage,
        "vote_breakdown": triage_counts,
        "support_ratio": round(support_ratio, 3),
        "disagreement_index": round(disagreement_index, 3),
        "conflict_count": len(conflicts),
        "strongest_dissent": strongest_dissent,
        "strongest_dissent_votes": strongest_dissent_votes,
    }


def _consensus_summary(assessments: list[SpecialistAssessment], consensus_triage: str) -> str:
    finding_counts: dict[str, int] = {}
    for item in assessments:
        for finding in item.key_findings:
            finding_counts[finding] = finding_counts.get(finding, 0) + 1

    shared_findings = sorted([name for name, count in finding_counts.items() if count >= 2])
    if shared_findings:
        shared_text = ", ".join(shared_findings)
    else:
        shared_text = "no repeated cross-specialty finding"

    return (
        f"Council consensus triage is {consensus_triage}; shared signals: {shared_text}. "
        "Highest-acuity specialist concern remains prioritized."
    )


def _divergence_notes(
    assessments: list[SpecialistAssessment], conflicts: list[dict[str, object]]
) -> list[str]:
    distribution = {
        "emergency_escalation": 0,
        "same_day_review": 0,
        "routine_follow_up": 0,
    }
    for item in assessments:
        distribution[item.triage] += 1

    notes = [
        (
            "Triage distribution: "
            f"emergency_escalation={distribution['emergency_escalation']}, "
            f"same_day_review={distribution['same_day_review']}, "
            f"routine_follow_up={distribution['routine_follow_up']}."
        )
    ]

    if conflicts:
        notes.append("Urgency divergence detected; keep highest-acuity pathway active until reconciled.")
    else:
        notes.append("No major divergence detected across selected specialists.")
    return notes


def _score_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _compute_data_quality(
    symptoms: list[str],
    labs: dict[str, float],
    medications: list[str],
    history: list[str],
) -> dict[str, Any]:
    section_counts = {
        "symptoms": len(symptoms),
        "labs": len(labs),
        "medications": len(medications),
        "history": len(history),
    }
    non_empty_sections = sum(1 for count in section_counts.values() if count > 0)
    total_observations = sum(section_counts.values())

    symptom_detail_tokens = sum(len(item.split()) for item in symptoms)
    symptom_detail_score = min(1.0, symptom_detail_tokens / max(1, len(symptoms) * 5))

    score = (
        0.35 * (non_empty_sections / 4.0)
        + 0.35 * min(1.0, total_observations / 8.0)
        + 0.20 * symptom_detail_score
        + 0.10 * min(1.0, len(labs) / 3.0)
    )

    if section_counts["symptoms"] == 0:
        score -= 0.08
    if section_counts["medications"] == 0 and section_counts["history"] == 0:
        score -= 0.05

    score = max(0.0, min(1.0, score))
    missing_sections = [name for name, count in section_counts.items() if count == 0]

    return {
        "score": round(score, 3),
        "level": _score_level(score),
        "section_counts": section_counts,
        "non_empty_sections": non_empty_sections,
        "total_observations": total_observations,
        "missing_sections": missing_sections,
    }


def _build_followup_questions(
    symptoms: list[str],
    labs: dict[str, float],
    medications: list[str],
    history: list[str],
) -> list[str]:
    questions: list[str] = []

    if not symptoms:
        questions.append("What are the current symptoms, and which symptom is the most severe right now?")
    else:
        if not any(_DURATION_HINT_RE.search(item) for item in symptoms):
            questions.append("When did these symptoms start, and how have they changed over time?")
        if not any(_SEVERITY_HINT_RE.search(item) for item in symptoms):
            questions.append("How severe are the symptoms now on a 0-10 scale?")

    if not labs:
        questions.append("Do you have recent vitals or lab results (for example BP, HR, oxygen, glucose, creatinine)?")
    if not medications:
        questions.append("What medications and supplements are currently being used, with recent dose changes?")
    if not history:
        questions.append("What relevant medical history exists, including chronic disease, allergies, and prior events?")
    if len(symptoms) <= 1:
        questions.append("Are there associated symptoms such as chest pain, shortness of breath, neurologic changes, or bleeding?")

    deduped: list[str] = []
    seen: set[str] = set()
    for question in questions:
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(question)
        if len(deduped) >= 6:
            break

    return deduped


def _should_request_more_info(
    data_quality: dict[str, Any],
    red_flags: list[str],
) -> bool:
    if red_flags:
        return False
    score = float(data_quality["score"])
    non_empty_sections = int(data_quality["non_empty_sections"])
    total_observations = int(data_quality["total_observations"])
    return score < 0.55 or non_empty_sections < 2 or total_observations < 3


def _compute_confidence(
    *,
    data_quality_score: float,
    assessments: list[SpecialistAssessment],
    conflicts: list[dict[str, object]],
    red_flags: list[str],
    needs_more_info: bool,
) -> dict[str, Any]:
    triage_counts = {triage: 0 for triage in _TRIAGE_SCORE}
    for item in assessments:
        triage_counts[item.triage] += 1

    consensus_support = max(triage_counts.values()) / max(1, len(assessments))
    finding_density = min(
        1.0,
        sum(len(item.key_findings) for item in assessments) / max(1, len(assessments) * 4),
    )

    possible_conflicts = max(1, (len(assessments) * (len(assessments) - 1)) // 2)
    conflict_ratio = len(conflicts) / possible_conflicts

    score = (
        0.40 * data_quality_score
        + 0.30 * consensus_support
        + 0.20 * finding_density
        + 0.10 * (1.0 - min(1.0, conflict_ratio))
    )

    if red_flags:
        score = max(score, 0.82)
    if needs_more_info:
        score = min(score, 0.45)

    score = max(0.0, min(1.0, score))

    return {
        "score": round(score, 3),
        "level": _score_level(score),
        "components": {
            "data_quality": round(data_quality_score, 3),
            "consensus_support": round(consensus_support, 3),
            "finding_density": round(finding_density, 3),
            "conflict_ratio": round(conflict_ratio, 3),
        },
    }


def _build_citations(
    symptoms: list[str],
    labs: dict[str, float],
    medications: list[str],
    history: list[str],
    assessments: list[SpecialistAssessment],
    red_flag_matches: list[dict[str, str]],
    negated_red_flag_matches: list[dict[str, str]],
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []

    for index, symptom in enumerate(symptoms[:6], start=1):
        citations.append(
            {
                "source_id": f"symptom-{index}",
                "source": "patient_intake",
                "title": f"Symptom report {index}",
                "url": None,
                "relevance": "Patient-reported symptom considered in triage.",
                "snippet": symptom,
                "section": "symptoms",
                "evidence_type": "reported_symptom",
            }
        )

    for index, (lab_name, lab_value) in enumerate(sorted(labs.items())[:6], start=1):
        citations.append(
            {
                "source_id": f"lab-{index}",
                "source": "patient_intake",
                "title": f"Lab or vital: {lab_name}",
                "url": None,
                "relevance": "Quantitative marker used by specialist rules.",
                "snippet": f"{lab_name}={lab_value}",
                "section": "labs",
                "evidence_type": "numeric_observation",
            }
        )

    for index, medication in enumerate(medications[:4], start=1):
        citations.append(
            {
                "source_id": f"med-{index}",
                "source": "patient_intake",
                "title": f"Medication exposure {index}",
                "url": None,
                "relevance": "Medication exposure checked for interaction and safety risk.",
                "snippet": medication,
                "section": "medications",
                "evidence_type": "medication",
            }
        )

    for index, item in enumerate(red_flag_matches[:6], start=1):
        citations.append(
            {
                "source_id": f"red-flag-{index}",
                "source": "council_rule_engine",
                "title": f"Red-flag rule matched: {item['flag']}",
                "url": None,
                "relevance": "Safety escalation rule was positively matched.",
                "snippet": item["text"],
                "section": "safety",
                "evidence_type": "red_flag_match",
                "phrase": item["phrase"],
            }
        )

    for index, item in enumerate(negated_red_flag_matches[:4], start=1):
        citations.append(
            {
                "source_id": f"negated-red-flag-{index}",
                "source": "council_rule_engine",
                "title": f"Negated red-flag phrase: {item['flag']}",
                "url": None,
                "relevance": "Phrase ignored because local negation was detected.",
                "snippet": item["text"],
                "section": "safety",
                "evidence_type": "negated_symptom",
                "phrase": item["phrase"],
            }
        )

    for assessment in assessments:
        for index, finding in enumerate(assessment.key_findings[:2], start=1):
            citations.append(
                {
                    "source_id": f"{assessment.specialist}-finding-{index}",
                    "source": "council_rule_engine",
                    "title": f"{assessment.specialist} finding: {finding}",
                    "url": None,
                    "relevance": f"Specialist rule output supported triage {assessment.triage}.",
                    "snippet": finding,
                    "section": "specialist_assessment",
                    "evidence_type": "derived_finding",
                }
            )

    for index, item in enumerate(history[:4], start=1):
        citations.append(
            {
                "source_id": f"history-{index}",
                "source": "patient_intake",
                "title": f"Relevant history {index}",
                "url": None,
                "relevance": "History item used for baseline risk context.",
                "snippet": item,
                "section": "history",
                "evidence_type": "history",
            }
        )

    return citations


def _citation_strength(evidence_type: str) -> float:
    strength_map = {
        "red_flag_match": 0.95,
        "numeric_observation": 0.9,
        "derived_finding": 0.85,
        "medication": 0.8,
        "reported_symptom": 0.75,
        "history": 0.7,
        "negated_symptom": 0.55,
    }
    return strength_map.get(evidence_type, 0.65)


def _annotate_citation_quality(citations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not citations:
        return [], {
            "total_citations": 0,
            "average_evidence_strength": 0.0,
            "high_signal_count": 0,
            "supporting_signal_count": 0,
            "context_only_count": 0,
            "negated_context_count": 0,
        }

    annotated: list[dict[str, Any]] = []
    high_signal_count = 0
    supporting_signal_count = 0
    context_only_count = 0
    negated_context_count = 0
    strength_total = 0.0

    for item in citations:
        evidence_type = str(item.get("evidence_type") or "")
        evidence_strength = _citation_strength(evidence_type)
        strength_total += evidence_strength

        if evidence_type == "negated_symptom":
            quality_flag = "negated_context"
            negated_context_count += 1
        elif evidence_strength >= 0.85:
            quality_flag = "high_signal"
            high_signal_count += 1
        elif evidence_strength >= 0.7:
            quality_flag = "supporting_signal"
            supporting_signal_count += 1
        else:
            quality_flag = "context_only"
            context_only_count += 1

        annotated.append(
            {
                **item,
                "evidence_strength": round(evidence_strength, 3),
                "quality_flag": quality_flag,
            }
        )

    return annotated, {
        "total_citations": len(annotated),
        "average_evidence_strength": round(strength_total / len(annotated), 3),
        "high_signal_count": high_signal_count,
        "supporting_signal_count": supporting_signal_count,
        "context_only_count": context_only_count,
        "negated_context_count": negated_context_count,
    }


def _build_reasoning_timeline(
    *,
    data_quality: dict[str, Any],
    assessments: list[SpecialistAssessment],
    conflicts: list[dict[str, object]],
    consensus_metadata: dict[str, Any],
    red_flags: list[str],
    followup_questions: list[str],
    needs_more_info: bool,
    final_recommendation: str,
) -> list[dict[str, Any]]:
    return [
        {
            "sequence": 1,
            "step": "intake_normalized",
            "detail": "Input payload normalized into symptoms, labs, medications, and history.",
            "metadata": {
                "section_counts": data_quality.get("section_counts", {}),
                "data_quality_score": data_quality.get("score"),
            },
        },
        {
            "sequence": 2,
            "step": "specialist_assessment",
            "detail": "Rule-based specialist assessments completed.",
            "metadata": {
                "specialists": [item.specialist for item in assessments],
                "triage_votes": [item.triage for item in assessments],
            },
        },
        {
            "sequence": 3,
            "step": "conflict_review",
            "detail": "Cross-specialty triage conflicts evaluated.",
            "metadata": {
                "conflict_count": len(conflicts),
                "conflict_detected": bool(conflicts),
            },
        },
        {
            "sequence": 4,
            "step": "consensus_decision",
            "detail": "Council consensus score and dissent profile computed.",
            "metadata": {
                "winning_triage": consensus_metadata.get("winning_triage"),
                "support_ratio": consensus_metadata.get("support_ratio"),
                "disagreement_index": consensus_metadata.get("disagreement_index"),
            },
        },
        {
            "sequence": 5,
            "step": "safety_gate",
            "detail": "Red-flag safety gate applied before final recommendation.",
            "metadata": {
                "red_flags": red_flags,
                "triggered": bool(red_flags),
                "needs_more_info": needs_more_info,
                "followup_questions_count": len(followup_questions),
            },
        },
        {
            "sequence": 6,
            "step": "final_recommendation",
            "detail": final_recommendation,
            "metadata": {
                "needs_more_info": needs_more_info,
            },
        },
    ]


def _build_escalation_metadata(
    *,
    red_flags: list[str],
    red_flag_matches: list[dict[str, str]],
    assessments: list[SpecialistAssessment],
) -> dict[str, Any]:
    if red_flags:
        priority = "critical"
        recommended_sla_minutes = 5
        requires_human_handoff = True
    else:
        highest_score = max(_TRIAGE_SCORE[item.triage] for item in assessments)
        if highest_score >= _TRIAGE_SCORE["emergency_escalation"]:
            priority = "urgent"
            recommended_sla_minutes = 30
            requires_human_handoff = True
        elif highest_score >= _TRIAGE_SCORE["same_day_review"]:
            priority = "same_day"
            recommended_sla_minutes = 180
            requires_human_handoff = False
        else:
            priority = "routine"
            recommended_sla_minutes = 720
            requires_human_handoff = False

    created_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    trigger_evidence = [
        {
            "flag": item["flag"],
            "phrase": item["phrase"],
            "snippet": item["text"],
        }
        for item in red_flag_matches[:5]
    ]

    return {
        "priority": priority,
        "recommended_sla_minutes": recommended_sla_minutes,
        "requires_human_handoff": requires_human_handoff,
        "trigger_evidence": trigger_evidence,
        "generated_at_utc": created_at_utc,
    }


def _build_neural_feature_map(
    *,
    red_flags: list[str],
    conflicts: list[dict[str, object]],
    consensus_metadata: dict[str, Any],
    data_quality: dict[str, Any],
    confidence: dict[str, Any],
    followup_questions: list[str],
    assessments: list[SpecialistAssessment],
    medications: list[str],
) -> dict[str, float]:
    specialist_count = max(1, len(assessments))
    high_triage_votes = sum(
        1 for item in assessments if item.triage in {"same_day_review", "emergency_escalation"}
    )
    support_ratio = float(consensus_metadata.get("support_ratio", 0.0) or 0.0)
    disagreement_index = float(consensus_metadata.get("disagreement_index", 0.0) or 0.0)
    data_quality_score = float(data_quality.get("score", 0.0) or 0.0)
    confidence_score = float(confidence.get("score", 0.0) or 0.0)

    return {
        "red_flag_rate": min(1.0, len(red_flags) / 3.0),
        "conflict_rate": min(1.0, len(conflicts) / specialist_count),
        "disagreement_index": max(disagreement_index, 1.0 - support_ratio),
        "inverse_data_quality": max(0.0, 1.0 - data_quality_score),
        "inverse_confidence": max(0.0, 1.0 - confidence_score),
        "followup_density": min(1.0, len(followup_questions) / 8.0),
        "high_triage_pressure": min(1.0, high_triage_votes / specialist_count),
        "medication_burden": min(1.0, len(medications) / 8.0),
    }


def _build_neural_risk_payload(
    *,
    payload: dict,
    red_flags: list[str],
    conflicts: list[dict[str, object]],
    consensus_metadata: dict[str, Any],
    data_quality: dict[str, Any],
    confidence: dict[str, Any],
    followup_questions: list[str],
    assessments: list[SpecialistAssessment],
    medications: list[str],
) -> dict[str, Any]:
    neural_enabled = bool(payload.get("council_neural_enabled", settings.council_neural_enabled))
    shadow_mode = bool(payload.get("council_neural_shadow_mode", settings.council_neural_shadow_mode))

    if not neural_enabled:
        return {
            "enabled": False,
            "shadow_mode": shadow_mode,
            "model_version": "council-neural-shadow-v1",
        }

    feature_map = _build_neural_feature_map(
        red_flags=red_flags,
        conflicts=conflicts,
        consensus_metadata=consensus_metadata,
        data_quality=data_quality,
        confidence=confidence,
        followup_questions=followup_questions,
        assessments=assessments,
        medications=medications,
    )
    score = score_council_risk(
        feature_map,
        medium_threshold=settings.council_neural_medium_threshold,
        high_threshold=settings.council_neural_high_threshold,
    )

    recommended_triage = "routine_follow_up"
    if score.band == "high":
        recommended_triage = "emergency_escalation"
    elif score.band == "medium":
        recommended_triage = "same_day_review"

    return {
        "enabled": True,
        "shadow_mode": shadow_mode,
        "model_version": score.model_version,
        "risk_probability": score.probability,
        "risk_band": score.band,
        "recommended_triage": recommended_triage,
        "feature_map": {key: round(value, 4) for key, value in feature_map.items()},
        "top_contributors": score.top_contributors,
    }


def _build_research_topics(
    assessments: list[SpecialistAssessment],
    red_flags: list[str],
    followup_questions: list[str],
) -> list[str]:
    topics: list[str] = []

    for red_flag in red_flags:
        topics.append(f"Confirm emergency protocol pathway for {red_flag}.")

    for assessment in assessments:
        if assessment.triage != "routine_follow_up":
            topics.append(
                f"Validate {assessment.specialist} recommendation for {assessment.triage} with local protocol."
            )

    for question in followup_questions[:3]:
        topics.append(f"Resolve missing intake detail: {question}")

    if not topics:
        topics.append("Monitor symptoms and repeat structured intake if condition changes.")

    deduped: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        key = topic.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(topic)
        if len(deduped) >= 8:
            break

    return deduped


def _final_recommendation(
    consensus_triage: str,
    red_flags: list[str],
    assessments: list[SpecialistAssessment],
    needs_more_info: bool,
) -> str:
    if red_flags:
        return (
            "Emergency escalation triggered by red-flag symptoms. Direct patient to emergency "
            "services immediately while preparing rapid specialist handoff."
        )

    if needs_more_info:
        return (
            "Input data is insufficient for a reliable council conclusion. Collect targeted follow-up "
            "details before final triage decisions unless the patient acutely worsens."
        )

    highest_score = max(_TRIAGE_SCORE[item.triage] for item in assessments)
    if highest_score >= _TRIAGE_SCORE["emergency_escalation"]:
        return (
            "At least one specialist indicates emergency escalation. Route to urgent in-person "
            "evaluation and stabilize before routine workup."
        )
    if highest_score >= _TRIAGE_SCORE["same_day_review"]:
        return (
            f"Consensus trend is {consensus_triage}. Arrange same-day multidisciplinary review "
            "with medication and lab reconciliation."
        )
    return (
        "Council indicates routine follow-up. Continue monitoring with return precautions and "
        "structured outpatient reassessment."
    )


def run_council(payload: dict) -> dict:
    symptoms = _normalize_text_list(payload.get("symptoms"))
    labs = _normalize_labs(payload.get("labs"))
    medications = _normalize_text_list(payload.get("medications"))
    history = _normalize_history(payload.get("history"))
    specialists = _resolve_specialists(payload.get("specialists"))

    assessments = [
        _SPECIALIST_EVALUATORS[specialist](symptoms, labs, medications, history)
        for specialist in specialists
    ]
    assessments_payload = [asdict(item) for item in assessments]

    red_flags, red_flag_matches, negated_red_flag_matches = _detect_red_flags(symptoms)
    conflicts = _build_conflicts(assessments)
    consensus_triage = _consensus_triage(assessments)
    consensus_metadata = _build_consensus_metadata(assessments, consensus_triage, conflicts)
    consensus_summary = _consensus_summary(assessments, consensus_triage)
    divergence_notes = _divergence_notes(assessments, conflicts)

    data_quality = _compute_data_quality(symptoms, labs, medications, history)
    followup_questions = _build_followup_questions(symptoms, labs, medications, history)
    needs_more_info = _should_request_more_info(data_quality, red_flags)

    confidence = _compute_confidence(
        data_quality_score=float(data_quality["score"]),
        assessments=assessments,
        conflicts=conflicts,
        red_flags=red_flags,
        needs_more_info=needs_more_info,
    )

    final_recommendation = _final_recommendation(
        consensus_triage,
        red_flags,
        assessments,
        needs_more_info,
    )

    citations = _build_citations(
        symptoms,
        labs,
        medications,
        history,
        assessments,
        red_flag_matches,
        negated_red_flag_matches,
    )
    citations, citation_quality = _annotate_citation_quality(citations)

    escalation_metadata = _build_escalation_metadata(
        red_flags=red_flags,
        red_flag_matches=red_flag_matches,
        assessments=assessments,
    )

    if red_flags:
        estimated_duration_minutes = 5
    elif needs_more_info:
        estimated_duration_minutes = 10 + min(8, len(followup_questions) * 2)
    else:
        estimated_duration_minutes = 12 + (len(assessments) * 8) + (len(conflicts) * 6)

    research_topics = _build_research_topics(assessments, red_flags, followup_questions)
    reasoning_timeline = _build_reasoning_timeline(
        data_quality=data_quality,
        assessments=assessments,
        conflicts=conflicts,
        consensus_metadata=consensus_metadata,
        red_flags=red_flags,
        followup_questions=followup_questions,
        needs_more_info=needs_more_info,
        final_recommendation=final_recommendation,
    )
    neural_risk = _build_neural_risk_payload(
        payload=payload,
        red_flags=red_flags,
        conflicts=conflicts,
        consensus_metadata=consensus_metadata,
        data_quality=data_quality,
        confidence=confidence,
        followup_questions=followup_questions,
        assessments=assessments,
        medications=medications,
    )

    return {
        "requested_specialists": specialists,
        "per_specialist_reasoning_logs": assessments_payload,
        "conflict_list": conflicts,
        "council_consensus": consensus_metadata,
        "consensus_summary": consensus_summary,
        "divergence_notes": divergence_notes,
        "final_recommendation": final_recommendation,
        "estimated_duration_minutes": estimated_duration_minutes,
        "emergency_escalation": {
            "triggered": bool(red_flags),
            "red_flags": red_flags,
            "action": (
                "immediate_emergency_referral"
                if red_flags
                else "standard_multidisciplinary_pathway"
            ),
            "negated_red_flags": negated_red_flag_matches,
            "metadata": escalation_metadata,
        },
        "needs_more_info": needs_more_info,
        "followup_questions": followup_questions,
        "confidence_score": confidence["score"],
        "confidence_level": confidence["level"],
        "data_quality_score": data_quality["score"],
        "data_quality_level": data_quality["level"],
        "analyze": {
            "consensus_triage": consensus_triage,
            "emergency_triggered": bool(red_flags),
            "needs_more_info": needs_more_info,
            "followup_questions": followup_questions,
            "confidence": confidence,
            "data_quality": data_quality,
            "final_recommendation": final_recommendation,
        },
        "details": {
            "requested_specialists": specialists,
            "specialist_assessments": assessments_payload,
            "conflicts": conflicts,
            "red_flag_matches": red_flag_matches,
            "negated_red_flag_matches": negated_red_flag_matches,
            "consensus": consensus_metadata,
            "consensus_summary": consensus_summary,
            "divergence_notes": divergence_notes,
        },
        "citations": citations,
        "citation_quality": citation_quality,
        "reasoning_timeline": reasoning_timeline,
        "neural_risk": neural_risk,
        "research": {
            "mode": "rule_based_council_v2",
            "topics": research_topics,
            "followup_questions": followup_questions,
            "confidence_components": confidence["components"],
            "data_gaps": data_quality["missing_sections"],
        },
        "deepdive": {
            "cross_specialty": {
                "consensus_triage": consensus_triage,
                "conflict_count": len(conflicts),
                "red_flag_count": len(red_flags),
                "highest_triage_score": max(_TRIAGE_SCORE[item.triage] for item in assessments),
            },
            "specialist_sections": [
                {
                    "specialist": item.specialist,
                    "triage": item.triage,
                    "key_findings": item.key_findings,
                    "reasoning_log": item.reasoning_log,
                    "recommendation": item.recommendation,
                }
                for item in assessments
            ],
        },
    }
