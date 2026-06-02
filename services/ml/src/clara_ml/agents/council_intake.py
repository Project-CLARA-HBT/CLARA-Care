from __future__ import annotations

import json
import re
from typing import Any

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient


def _build_client() -> DeepSeekClient:
    return DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout_seconds=settings.deepseek_timeout_seconds,
        max_concurrency=settings.llm_global_max_concurrency,
        min_interval_seconds=settings.llm_global_min_interval_seconds,
        request_jitter_seconds=settings.llm_global_jitter_seconds,
    )


def _strip_code_fence(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _normalize_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            candidate = _as_text(item.get("name") or item.get("value") or item.get("text"))
        else:
            candidate = _as_text(item)
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(candidate)
    return normalized


def _normalize_labs(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    if isinstance(value, dict):
        for key, raw in value.items():
            name = _as_text(key)
            val = _as_text(raw)
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "value": val,
                    "unit": "",
                    "raw": f"{name}={val}" if val else name,
                }
            )
        return rows

    if not isinstance(value, list):
        return rows

    for item in value:
        if isinstance(item, dict):
            name = _as_text(item.get("name") or item.get("key") or item.get("lab"))
            val = _as_text(item.get("value") or item.get("result"))
            unit = _as_text(item.get("unit"))
            raw = _as_text(item.get("raw"))
            if not name and not raw:
                continue
            if not raw:
                raw = f"{name}={val} {unit}".strip()
            rows.append(
                {
                    "name": name,
                    "value": val,
                    "unit": unit,
                    "raw": raw,
                }
            )
            continue

        raw_line = _as_text(item)
        if not raw_line:
            continue
        key_match = re.match(r"^([A-Za-zÀ-ỹ0-9_/-]+)\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)\s*(.*)$", raw_line)
        if key_match:
            rows.append(
                {
                    "name": key_match.group(1).strip(),
                    "value": key_match.group(2).strip(),
                    "unit": key_match.group(3).strip(),
                    "raw": raw_line,
                }
            )
        else:
            rows.append({"name": "", "value": "", "unit": "", "raw": raw_line})

    return rows


def _format_labs_input(labs: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for item in labs:
        name = _as_text(item.get("name"))
        value = _as_text(item.get("value"))
        unit = _as_text(item.get("unit"))
        raw = _as_text(item.get("raw"))
        if name and value:
            line = f"{name}={value}"
            if unit:
                line = f"{line} {unit}"
            lines.append(line)
            continue
        if raw:
            lines.append(raw)
    return "\n".join(lines)


def _labs_to_numeric_map(labs: list[dict[str, str]]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for item in labs:
        name = _as_text(item.get("name")).lower()
        value = _as_text(item.get("value")).replace(",", ".")
        if not name or not value:
            continue
        try:
            normalized[name] = float(value)
        except ValueError:
            continue
    return normalized


def _score_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _compute_intake_data_quality(
    transcript: str,
    symptoms: list[str],
    labs: list[dict[str, str]],
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

    transcript_tokens = len([token for token in re.split(r"\s+", transcript.strip()) if token])
    transcript_detail = min(1.0, transcript_tokens / 60.0)

    score = (
        0.45 * (non_empty_sections / 4.0)
        + 0.35 * min(1.0, total_observations / 8.0)
        + 0.20 * transcript_detail
    )
    if section_counts["symptoms"] == 0:
        score -= 0.08
    if section_counts["labs"] == 0:
        score -= 0.04

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


def _build_intake_followup_questions(
    symptoms: list[str],
    labs: list[dict[str, str]],
    medications: list[str],
    history: list[str],
) -> list[str]:
    questions: list[str] = []
    if not symptoms:
        questions.append("What are the current symptoms and their severity right now?")
    else:
        questions.append("When did the symptoms start, and are they getting better or worse?")
    if not labs:
        questions.append("Do you have recent vitals or test results to include?")
    if not medications:
        questions.append("Which medications or supplements are currently being used?")
    if not history:
        questions.append("What chronic conditions, allergies, or relevant history should be added?")
    if len(symptoms) <= 1:
        questions.append("Are there associated symptoms such as chest pain, dyspnea, neurologic changes, or bleeding?")
    return questions[:6]


def _compute_intake_confidence(
    *,
    data_quality_score: float,
    model_used: str,
    warnings: list[str],
    needs_more_info: bool,
) -> dict[str, Any]:
    model_score = 0.92 if model_used != "heuristic-fallback-v1" else 0.72
    warning_penalty = min(0.2, 0.08 * len(warnings))
    score = (0.75 * data_quality_score) + (0.25 * model_score) - warning_penalty
    if needs_more_info:
        score = min(score, 0.48)
    score = max(0.0, min(1.0, score))
    return {
        "score": round(score, 3),
        "level": _score_level(score),
        "components": {
            "data_quality": round(data_quality_score, 3),
            "model_reliability": round(model_score, 3),
            "warning_penalty": round(warning_penalty, 3),
        },
    }


def _build_intake_citations(
    symptoms: list[str],
    labs: list[dict[str, str]],
    medications: list[str],
    history: list[str],
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for index, symptom in enumerate(symptoms[:6], start=1):
        citations.append(
            {
                "source_id": f"intake-symptom-{index}",
                "source": "transcript_extraction",
                "title": f"Symptom extract {index}",
                "url": None,
                "relevance": "Symptom text captured from intake transcript.",
                "snippet": symptom,
                "section": "symptoms",
                "evidence_type": "extracted_text",
            }
        )
    for index, lab in enumerate(labs[:6], start=1):
        raw = _as_text(lab.get("raw")) or f"{_as_text(lab.get('name'))}={_as_text(lab.get('value'))}"
        citations.append(
            {
                "source_id": f"intake-lab-{index}",
                "source": "transcript_extraction",
                "title": f"Lab extract {index}",
                "url": None,
                "relevance": "Numeric marker extracted for downstream council scoring.",
                "snippet": raw,
                "section": "labs",
                "evidence_type": "numeric_extract",
            }
        )
    for index, medication in enumerate(medications[:4], start=1):
        citations.append(
            {
                "source_id": f"intake-med-{index}",
                "source": "transcript_extraction",
                "title": f"Medication extract {index}",
                "url": None,
                "relevance": "Medication exposure extracted from transcript.",
                "snippet": medication,
                "section": "medications",
                "evidence_type": "medication_extract",
            }
        )
    for index, item in enumerate(history[:4], start=1):
        citations.append(
            {
                "source_id": f"intake-history-{index}",
                "source": "transcript_extraction",
                "title": f"History extract {index}",
                "url": None,
                "relevance": "History context extracted from transcript.",
                "snippet": item,
                "section": "history",
                "evidence_type": "history_extract",
            }
        )
    return citations


def _heuristic_intake(transcript: str) -> dict[str, Any]:
    lines = [line.strip(" -\t") for line in transcript.splitlines() if line.strip()]
    if not lines:
        lines = [chunk.strip() for chunk in re.split(r"[.;]", transcript) if chunk.strip()]

    lab_rows: list[dict[str, str]] = []
    symptoms: list[str] = []
    medications: list[str] = []
    history: list[str] = []

    med_pattern = re.compile(
        r"\b(metformin|warfarin|aspirin|clopidogrel|insulin|atorvastatin|rosuvastatin|ibuprofen|naproxen|paracetamol|amoxicillin)\b",
        flags=re.IGNORECASE,
    )
    symptom_hint = re.compile(
        r"(đau|dau|sốt|sot|khó thở|kho tho|ho|mệt|met|chóng mặt|chong mat|buồn nôn|buon non|đau đầu|dau dau)",
        flags=re.IGNORECASE,
    )
    history_hint = re.compile(
        r"(tiền sử|tien su|history|bệnh nền|benh nen|tăng huyết áp|tang huyet ap|đái tháo đường|dai thao duong|ckd|suy thận|suy tim)",
        flags=re.IGNORECASE,
    )

    for line in lines:
        lab_match = re.search(r"([A-Za-zÀ-ỹ0-9_/-]+)\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)\s*([A-Za-z%/0-9]*)", line)
        if lab_match:
            lab_rows.append(
                {
                    "name": lab_match.group(1).strip(),
                    "value": lab_match.group(2).strip(),
                    "unit": lab_match.group(3).strip(),
                    "raw": line,
                }
            )

        for med in med_pattern.findall(line):
            cleaned = med.strip()
            if cleaned and cleaned.lower() not in {item.lower() for item in medications}:
                medications.append(cleaned)

        if symptom_hint.search(line):
            symptoms.append(line)

        if history_hint.search(line):
            history.append(line)

    symptoms = _normalize_text_list(symptoms)
    medications = _normalize_text_list(medications)
    history = _normalize_text_list(history)

    return {
        "symptoms": symptoms,
        "labs": lab_rows,
        "medications": medications,
        "history": history,
    }


def _extract_with_deepseek(client: DeepSeekClient, transcript: str) -> dict[str, Any]:
    system_prompt = (
        "Bạn là trợ lý chuẩn hóa intake lâm sàng cho hội chẩn. "
        "Nhiệm vụ: trích xuất chính xác 4 phần từ transcript: symptoms, labs, medications, history. "
        "Chỉ trả về JSON hợp lệ, không markdown, không giải thích."
    )
    prompt = (
        "Hãy trích xuất dữ liệu từ transcript dưới đây và trả về JSON với đúng schema:\n"
        "{\n"
        '  "symptoms": ["..."],\n'
        '  "labs": [{"name": "", "value": "", "unit": "", "raw": ""}],\n'
        '  "medications": ["..."],\n'
        '  "history": ["..."]\n'
        "}\n"
        "Quy tắc:\n"
        "- symptoms: triệu chứng hiện tại, dấu hiệu cấp tính.\n"
        "- labs: chỉ số xét nghiệm hoặc sinh hiệu có giá trị định lượng.\n"
        "- medications: thuốc đang dùng hoặc mới dùng gần đây.\n"
        "- history: bệnh sử, bệnh nền, tiền sử liên quan.\n"
        "- Không chắc chắn thì để rỗng thay vì bịa.\n\n"
        f"Transcript:\n{transcript}"
    )

    response = client.generate(prompt=prompt, system_prompt=system_prompt)
    cleaned = _strip_code_fence(response.content)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("DeepSeek intake output is not a JSON object")
    payload["_model_used"] = response.model
    return payload


def run_council_intake(
    *,
    transcript: str,
    audio_bytes: bytes | None = None,
    audio_filename: str = "audio.webm",
    audio_content_type: str = "audio/webm",
) -> dict[str, Any]:
    transcript_text = transcript.strip()
    warnings: list[str] = []

    client = _build_client()

    if not transcript_text:
        if not audio_bytes:
            raise ValueError("Missing transcript and audio input")
        try:
            transcript_text = client.transcribe_audio(
                audio_bytes=audio_bytes,
                filename=audio_filename,
                content_type=audio_content_type,
                model=settings.deepseek_audio_model,
                language=settings.deepseek_audio_language,
                prompt="Medical interview in Vietnamese. Return complete transcript.",
            )
        except Exception as exc:  # pragma: no cover - network and provider failures
            raise RuntimeError(
                f"DeepSeek audio transcription failed: {exc.__class__.__name__}"
            ) from exc

    extracted: dict[str, Any]
    model_used = client.model
    try:
        extracted = _extract_with_deepseek(client, transcript_text)
        model_used = _as_text(extracted.get("_model_used")) or client.model
    except Exception as exc:  # pragma: no cover - defensive fallback
        warnings.append(f"deepseek_extract_fallback:{exc.__class__.__name__}")
        extracted = _heuristic_intake(transcript_text)
        model_used = "heuristic-fallback-v1"

    symptoms = _normalize_text_list(extracted.get("symptoms"))
    labs = _normalize_labs(extracted.get("labs"))
    medications = _normalize_text_list(extracted.get("medications"))
    history = _normalize_text_list(extracted.get("history"))
    data_quality = _compute_intake_data_quality(
        transcript_text,
        symptoms,
        labs,
        medications,
        history,
    )
    followup_questions = _build_intake_followup_questions(symptoms, labs, medications, history)
    needs_more_info = (
        data_quality["score"] < 0.55
        or data_quality["non_empty_sections"] < 2
        or data_quality["total_observations"] < 3
    )
    confidence = _compute_intake_confidence(
        data_quality_score=float(data_quality["score"]),
        model_used=model_used,
        warnings=warnings,
        needs_more_info=needs_more_info,
    )
    citations = _build_intake_citations(symptoms, labs, medications, history)
    research_topics = [f"Complete missing intake section: {name}" for name in data_quality["missing_sections"]]
    if not research_topics:
        research_topics = ["Proceed to council review with current intake extraction."]

    return {
        "transcript": transcript_text,
        "symptoms": symptoms,
        "labs": labs,
        "medications": medications,
        "history": history,
        "text_fields": {
            "symptoms_input": "\n".join(symptoms),
            "labs_input": _format_labs_input(labs),
            "medications_input": "\n".join(medications),
            "history_input": "\n".join(history),
        },
        "warnings": warnings,
        "model_used": model_used,
        "missing_fields": list(data_quality["missing_sections"]),
        "field_confidence": {
            "symptoms": round(1.0 if symptoms else 0.25, 3),
            "labs": round(1.0 if labs else 0.3, 3),
            "medications": round(1.0 if medications else 0.35, 3),
            "history": round(1.0 if history else 0.35, 3),
        },
        "council_payload": {
            "symptoms": symptoms,
            "labs": _labs_to_numeric_map(labs),
            "medications": medications,
            "history": history,
        },
        "needs_more_info": needs_more_info,
        "followup_questions": followup_questions,
        "confidence_score": confidence["score"],
        "confidence_level": confidence["level"],
        "data_quality_score": data_quality["score"],
        "data_quality_level": data_quality["level"],
        "analyze": {
            "needs_more_info": needs_more_info,
            "followup_questions": followup_questions,
            "confidence": confidence,
            "data_quality": data_quality,
        },
        "details": {
            "section_counts": data_quality["section_counts"],
            "warnings": warnings,
            "model_used": model_used,
        },
        "citations": citations,
        "research": {
            "mode": "intake_extraction_v2",
            "topics": research_topics,
            "followup_questions": followup_questions,
            "data_gaps": data_quality["missing_sections"],
        },
        "deepdive": {
            "extraction": {
                "model_used": model_used,
                "fallback_used": model_used == "heuristic-fallback-v1",
                "warnings": warnings,
            },
            "normalized_fields": {
                "symptoms_count": len(symptoms),
                "labs_count": len(labs),
                "medications_count": len(medications),
                "history_count": len(history),
            },
        },
    }
