from __future__ import annotations

import re


def _normalize_transcript(text: str) -> str:
    cleaned = text.strip()
    if cleaned:
        return cleaned
    return "Patient encounter transcript unavailable."


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[.\n!?]+", text)
    return [part.strip() for part in parts if part.strip()]


def _extract_vitals(text: str) -> dict[str, str]:
    vitals: dict[str, str] = {}

    bp_match = re.search(r"\b(?:bp|blood pressure)\s*[:=]?\s*(\d{2,3}/\d{2,3})\b", text, re.I)
    if bp_match:
        vitals["blood_pressure"] = bp_match.group(1)

    hr_match = re.search(r"\b(?:hr|heart rate|pulse)\s*[:=]?\s*(\d{2,3})\b", text, re.I)
    if hr_match:
        vitals["heart_rate"] = hr_match.group(1)

    temp_match = re.search(r"\b(?:temp|temperature)\s*[:=]?\s*(\d{2}(?:\.\d)?)\b", text, re.I)
    if temp_match:
        vitals["temperature_c"] = temp_match.group(1)

    spo2_match = re.search(r"\b(?:spo2|oxygen saturation)\s*[:=]?\s*(\d{2,3})%?\b", text, re.I)
    if spo2_match:
        vitals["spo2_percent"] = spo2_match.group(1)

    return vitals


def _subjective_block(sentences: list[str]) -> dict:
    if not sentences:
        return {
            "chief_complaint": "No complaint captured.",
            "history_of_present_illness": "Transcript did not include subjective history.",
        }

    chief = sentences[0]
    history = " ".join(sentences[:2]) if len(sentences) > 1 else chief
    return {
        "chief_complaint": chief,
        "history_of_present_illness": history,
    }


def _objective_block(text: str, sentences: list[str]) -> dict:
    vitals = _extract_vitals(text)
    findings = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(token in lowered for token in ("exam", "observed", "noted", "lab", "x-ray")):
            findings.append(sentence)

    if not findings and sentences:
        findings.append(f"General observation: {sentences[-1]}")

    return {
        "vitals": vitals,
        "findings": findings,
    }


def _assessment_block(text: str) -> dict:
    lowered = text.lower()
    problems: list[str] = []
    if "cough" in lowered:
        problems.append("Persistent cough")
    if "fever" in lowered or "temperature" in lowered or "temp" in lowered:
        problems.append("Possible febrile process")
    if "chest pain" in lowered:
        problems.append("Chest pain requires urgent exclusion of cardiac causes")
    if not problems:
        problems.append("Non-specific symptom complex")

    acuity = "high" if any("urgent" in p or "cardiac" in p for p in problems) else "moderate"
    return {
        "problems": problems,
        "acuity": acuity,
    }


def _plan_block(assessment: dict) -> dict:
    problems = assessment.get("problems", [])
    next_steps = [
        "Reconcile medication list and allergies.",
        "Provide return precautions for symptom worsening.",
    ]

    if any("cardiac" in item for item in problems):
        next_steps.insert(0, "Immediate clinician escalation and emergency triage evaluation.")
    elif any("febrile" in item.lower() for item in problems):
        next_steps.insert(0, "Consider infectious workup based on exam and local protocol.")
    else:
        next_steps.insert(0, "Continue focused diagnostic review at follow-up.")

    return {
        "next_steps": next_steps,
        "follow_up": "Follow up within 24-72h or earlier if red-flag symptoms appear.",
    }


def run_scribe_soap(transcript: str) -> dict:
    normalized = _normalize_transcript(transcript)
    sentences = _split_sentences(normalized)
    subjective = _subjective_block(sentences)
    objective = _objective_block(normalized, sentences)
    assessment = _assessment_block(normalized)
    plan = _plan_block(assessment)

    return {
        "subjective": subjective,
        "objective": objective,
        "assessment": assessment,
        "plan": plan,
        "metadata": {
            "pipeline": "p2-scribe-soap-v1",
            "fallback_used": True,
        },
    }
