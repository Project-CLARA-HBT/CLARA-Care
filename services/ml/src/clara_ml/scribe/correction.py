"""Draft-only medical ASR correction through the governed model registry.

The correction path is intentionally conservative: it returns source-spanned
*proposals* for a clinician to review, never edits the transcript, note, code,
or medication record.  When disabled or unavailable it returns an explicit
empty result rather than applying a heuristic rewrite.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from clara_ml.config import settings
from clara_ml.llm.model_registry import ModelTask, build_task_client

_MAX_TRANSCRIPT_CHARS = 20_000
_MAX_SUGGESTIONS = 12
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True, slots=True)
class CorrectionSuggestion:
    source_text: str
    replacement_text: str
    kind: str
    rationale: str
    start: int
    end: int
    status: str = "suggested_requires_clinician_review"


def _parse_json_object(value: str) -> dict[str, Any] | None:
    match = _JSON_OBJECT.search(value or "")
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _suggestions(transcript: str, value: object) -> list[CorrectionSuggestion]:
    if not isinstance(value, list):
        return []
    output: list[CorrectionSuggestion] = []
    used_spans: set[tuple[int, int]] = set()
    for raw in value:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source_text") or "").strip()
        replacement = str(raw.get("replacement_text") or "").strip()
        kind = str(raw.get("kind") or "").strip().lower()
        rationale = str(raw.get("rationale") or "").strip()
        if (
            not source
            or not replacement
            or source == replacement
            or len(source) > 160
            or len(replacement) > 160
            or len(rationale) > 400
            or kind not in {"medication_term", "clinical_term", "procedure_term"}
            # Medication/dose changes require a separate terminology workflow;
            # this correction surface may not introduce quantities.
            or any(char.isdigit() for char in replacement)
        ):
            continue
        start = transcript.find(source)
        if start < 0:
            continue
        span = (start, start + len(source))
        if span in used_spans:
            continue
        used_spans.add(span)
        output.append(
            CorrectionSuggestion(
                source_text=source,
                replacement_text=replacement,
                kind=kind,
                rationale=rationale or "Term candidate requires clinician review.",
                start=span[0],
                end=span[1],
            )
        )
        if len(output) >= _MAX_SUGGESTIONS:
            break
    return output


def propose_medical_asr_corrections(transcript: str, *, language: str) -> dict[str, Any]:
    """Return strictly validated, non-applied correction proposals.

    The feature is an explicit opt-in because transcript text can be sensitive.
    API consent enforcement remains outside this helper; callers must not use it
    for unauthorised audio/transcript processing.
    """

    text = str(transcript or "").strip()
    if not settings.scribe_medical_correction_enabled:
        return {"status": "disabled", "suggestions": [], "applied": False}
    if not text:
        return {"status": "empty_transcript", "suggestions": [], "applied": False}
    if len(text) > _MAX_TRANSCRIPT_CHARS:
        return {
            "status": "abstained_input_too_large",
            "suggestions": [],
            "applied": False,
        }
    try:
        client, selection = build_task_client(ModelTask.SCRIBE_ASR_CORRECTION, settings)
        response = client.generate(
            (
                "Review this Vietnamese medical-ASR transcript for possible term errors. "
                "Return JSON only: {\"suggestions\":[{\"source_text\":string,"
                "\"replacement_text\":string,\"kind\":\"medication_term|clinical_term|procedure_term\","
                "\"rationale\":string}]}. Every source_text must be an exact substring. "
                "Do not add or change medication dose, diagnosis, instruction, or facts. "
                "Return an empty list when uncertain.\n\nTRANSCRIPT=\n"
                + text
            ),
            system_prompt=(
                "You produce review-only source-spanned correction candidates. "
                "Never apply changes, prescribe, diagnose, or include confidence scores."
            ),
            max_tokens=900,
        )
    except Exception:  # noqa: BLE001 - fail closed without leaking upstream detail
        return {"status": "unavailable", "suggestions": [], "applied": False}
    parsed = _parse_json_object(response.content)
    suggestions = _suggestions(text, parsed.get("suggestions") if parsed else None)
    return {
        "status": "review_required",
        "suggestions": [asdict(item) for item in suggestions],
        "applied": False,
        "model": {
            "task": selection.task.value,
            "prompt_version": selection.prompt_version,
            "contract_schema_version": selection.contract_schema_version,
            "rollback_applied": selection.rollback_applied,
        },
    }
