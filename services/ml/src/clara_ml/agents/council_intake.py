from __future__ import annotations

import json
import re
from typing import Any

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.llm.model_registry import ModelTask, build_asr_task_client, build_task_client

#: Sentinel ``model_used`` value for the degraded heuristic extraction path.
_HEURISTIC_FALLBACK_MODEL = "heuristic-fallback-v1"

#: User-visible degraded/fallback notice (Vietnamese-first, bilingual tail per the
#: spec's copy rule). Surfaced on the intake result when extraction falls back to
#: the heuristic path so a degraded extraction is never silently presented as a
#: primary-model result (Requirement 5.3).
_INTAKE_FALLBACK_NOTICE = (
    "Trích xuất intake đang dùng cơ chế dự phòng (heuristic) do mô hình AI "
    "không khả dụng. Kết quả có thể kém chính xác — vui lòng kiểm tra và chỉnh "
    "sửa thủ công trước khi hội chẩn. (Degraded heuristic fallback extraction — "
    "review and correct manually.)"
)


def _build_client() -> DeepSeekClient:
    # Intake extraction is a separately governed, reviewable generative-SLM
    # task. It must not borrow the specialist-shadow contract/profile.
    client, _selection = build_task_client(ModelTask.COUNCIL_INTAKE, settings)
    return client


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


def _build_intake_disclosure(model_used: str) -> dict[str, Any]:
    """Build the ``ai_disclosure`` block for an intake result.

    ``is_fallback`` is true IFF the heuristic/degraded path produced the
    extraction (``heuristic-fallback-v1``). The model_family/version split
    mirrors the compliance ``notice.model_disclosure`` helper (partition on the
    first hyphen) so Council disclosure stays consistent with the regulatory
    model-disclosure semantics (Requirement 6.6).
    """

    raw = (model_used or "").strip()
    is_fallback = raw == "heuristic-fallback-v1"
    if not raw:
        family, version = "unknown", "unknown"
    elif "-" in raw:
        head, _, tail = raw.partition("-")
        family, version = head, tail or "unknown"
    else:
        family, version = raw, "unknown"
    return {
        "model_family": family,
        "model_version": version,
        "is_fallback": is_fallback,
    }


def run_council_intake(
    *,
    transcript: str,
    audio_bytes: bytes | None = None,
    audio_filename: str = "audio.webm",
    audio_content_type: str = "audio/webm",
    disclosure_enabled: bool | None = None,
) -> dict[str, Any]:
    transcript_text = transcript.strip()
    warnings: list[str] = []

    # Text intake retains a deterministic, explicitly disclosed fallback when
    # the governed model client cannot be constructed. Audio cannot safely use
    # that fallback because there is no source text to review, so it fails
    # closed instead of fabricating an extraction.
    client: DeepSeekClient | None
    try:
        client = _build_client()
    except (TypeError, ValueError, RuntimeError) as exc:
        client = None
        warnings.append(f"governed_intake_client_unavailable:{exc.__class__.__name__}")

    if not transcript_text:
        if not audio_bytes:
            raise ValueError("Missing transcript and audio input")
        if client is None:
            raise RuntimeError("Governed Council intake model is unavailable for audio transcription")
        try:
            audio_client, audio_selection = build_asr_task_client(
                settings,
                timeout_seconds=max(
                    float(settings.deepseek_timeout_seconds),
                    float(settings.scribe_asr_timeout_seconds),
                ),
                retries_per_base=0,
            )
            transcript_text = audio_client.transcribe_audio(
                audio_bytes=audio_bytes,
                filename=audio_filename,
                content_type=audio_content_type,
                model=audio_selection.model,
                language=settings.deepseek_audio_language,
                prompt="Medical interview in Vietnamese. Return complete transcript.",
            )
        except Exception as exc:  # pragma: no cover - network and provider failures
            raise RuntimeError(
                f"DeepSeek audio transcription failed: {exc.__class__.__name__}"
            ) from exc

    extracted: dict[str, Any]
    model_used = client.model if client is not None else _HEURISTIC_FALLBACK_MODEL
    try:
        if client is None:
            raise RuntimeError("governed_intake_client_unavailable")
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
    citations = _build_intake_citations(symptoms, labs, medications, history)
    research_topics = [f"Complete missing intake section: {name}" for name in data_quality["missing_sections"]]
    if not research_topics:
        research_topics = ["Proceed to council review with current intake extraction."]

    # --- Degraded / fallback labeling (Requirement 5.3) ---------------------
    # Fallback-only + additive: when intake degrades to the heuristic path we
    # append a clear, user-visible notice to ``warnings`` (which the web intake
    # surface already renders) so a degraded extraction is never silently shown
    # as primary-model output. No model or extraction confidence is emitted: the
    # available-information state is represented by missing fields and required
    # review rather than a misleading percentage.
    is_fallback = model_used == _HEURISTIC_FALLBACK_MODEL
    if is_fallback and _INTAKE_FALLBACK_NOTICE not in warnings:
        warnings.append(_INTAKE_FALLBACK_NOTICE)

    result = {
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
        "council_payload": {
            "symptoms": symptoms,
            "labs": _labs_to_numeric_map(labs),
            "medications": medications,
            "history": history,
        },
        "needs_more_info": needs_more_info,
        "followup_questions": followup_questions,
        "data_quality_score": data_quality["score"],
        "data_quality_level": data_quality["level"],
        "analyze": {
            "needs_more_info": needs_more_info,
            "followup_questions": followup_questions,
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

    # --- Machine-readable degraded/fallback flag (Requirement 5.3) ----------
    # Fallback-only and independent of the disclosure flag: carry an explicit
    # top-level ``is_fallback`` boolean plus the user-visible ``fallback_notice``
    # so any downstream (web/mobile) can detect a degraded extraction without
    # string-matching ``model_used`` or digging into ``deepdive``. This mirrors
    # ``ai_disclosure.is_fallback`` (task 6.1) where that block is enabled. The
    # LLM-backed path adds neither key, so it is byte-identical to today and is
    # never flagged as a fallback.
    if is_fallback:
        result["is_fallback"] = True
        result["fallback_notice"] = _INTAKE_FALLBACK_NOTICE

    # --- Model & fallback disclosure (Requirement 6.1, 6.2) -----------------
    # Additive, default OFF. When COUNCIL_MODEL_DISCLOSURE_ENABLED is on
    # (explicit override via ``disclosure_enabled`` else the ML settings),
    # attach an ``ai_disclosure`` block. ``is_fallback`` is true IFF the
    # heuristic/degraded extraction path produced this intake
    # (``heuristic-fallback-v1``) so a degraded extraction is never silently
    # presented as primary-model output (design §E, Property P10). The
    # model_family/version split mirrors the compliance model-disclosure
    # semantics (Requirement 6.6). When off, the block is omitted so the
    # envelope is byte-equivalent to today (Requirement 6.5, 9.2).
    disclosure_on = (
        settings.council_model_disclosure_enabled
        if disclosure_enabled is None
        else disclosure_enabled
    )
    if disclosure_on:
        result["ai_disclosure"] = _build_intake_disclosure(model_used)

    return result
