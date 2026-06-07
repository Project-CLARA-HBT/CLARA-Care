"""Multi-template clinical note generator (task 1.6, Requirement 6).

`NoteGenerator.generate(transcript, template_id)` returns a :class:`Note` whose
``sections`` dict has EXACTLY the requested template's section keys (empty strings
allowed) — the structure is deterministic regardless of transcript content
(Requirement 6.2/6.3, Property 1). On empty/unusable input it returns the
template's sections as empty strings flagged ``insufficient_input`` rather than
fabricating clinical content (Requirement 6.4, Property 3).

An LLM completion function is injectable. When absent (or it fails) the generator
falls back to a deterministic, no-fabrication structured pass: it only ever places
text DERIVED FROM the transcript into sections and never invents drugs/allergies.
The generation prompt carries the shared assistive guardrail (no autonomous
prescribing/diagnosis — Requirement 10.2). Importing this module opens no socket.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from clara_ml.scribe.templates import DEFAULT_TEMPLATE_ID, Template, get_template

logger = logging.getLogger(__name__)

__all__ = ["Note", "NoteGenerator"]

# Injected LLM seam: prompt -> completion text (ideally JSON keyed by section).
LlmComplete = Callable[[str], str]

_GUARDRAIL = (
    "You are a clinical documentation assistant. Draft note sections strictly from "
    "the transcript. Do NOT diagnose, prescribe, or invent medications, allergies, "
    "doses, or findings not present in the transcript. A licensed clinician reviews "
    "and signs the final note."
)


@dataclass(frozen=True, slots=True)
class Note:
    """A generated note instance: exactly the template's section keys + flags."""

    template_id: str
    sections: dict[str, str]
    insufficient_input: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _is_usable(transcript: str) -> bool:
    return bool(transcript and transcript.strip() and len(transcript.strip()) >= 3)


def _empty_sections(template: Template) -> dict[str, str]:
    return {key: "" for key in template.section_keys}


def _build_prompt(template: Template, transcript: str) -> str:
    keys = ", ".join(template.section_keys)
    return (
        f"{_GUARDRAIL}\n\n"
        f"Produce a JSON object with EXACTLY these keys (and no others): [{keys}].\n"
        f"Each value is a concise clinical paragraph for that section, in the same "
        f"language as the transcript, derived only from the transcript. Leave a value "
        f'as an empty string "" if the transcript has nothing for that section.\n\n'
        f"Transcript:\n{transcript.strip()}\n\nJSON:"
    )


def _coerce_to_template(raw: Any, template: Template) -> dict[str, str]:
    """Force ``raw`` into a dict with EXACTLY the template's keys (string values).

    Unknown keys are dropped; missing keys are filled with "". This is what makes
    Property 1 (template completeness) hold regardless of LLM behavior.
    """

    parsed: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out: dict[str, str] = {}
    # Case-insensitive match of model keys to declared section keys.
    lowered = {str(k).strip().lower(): v for k, v in parsed.items()}
    for key in template.section_keys:
        value = lowered.get(key.strip().lower(), "")
        out[key] = str(value).strip() if value is not None else ""
    return out


def _extract_json(text: str) -> Any:
    if not text:
        return {}
    # Tolerate fenced/prefixed model output: grab the first {...} block.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    candidate = match.group(0) if match else text
    try:
        return json.loads(candidate)
    except (ValueError, TypeError):
        return {}


class NoteGenerator:
    """Generate a structured note for a template (LLM-assisted, structure-guaranteed)."""

    def __init__(self, llm_complete: LlmComplete | None = None) -> None:
        self._llm = llm_complete

    def generate(self, transcript: str, template_id: str | None = None) -> Note:
        template = get_template(template_id) or get_template(DEFAULT_TEMPLATE_ID)
        assert template is not None  # soap always exists

        if not _is_usable(transcript):
            return Note(
                template_id=template.id,
                sections=_empty_sections(template),
                insufficient_input=True,
                metadata={"generator": "scribe-note-v1", "reason": "insufficient_input"},
            )

        # LLM-assisted path (structure is still enforced by _coerce_to_template).
        if self._llm is not None:
            try:
                completion = self._llm(_build_prompt(template, transcript))
                sections = _coerce_to_template(_extract_json(completion), template)
                return Note(
                    template_id=template.id,
                    sections=sections,
                    insufficient_input=False,
                    metadata={"generator": "scribe-note-v1", "mode": "llm"},
                )
            except Exception as exc:  # noqa: BLE001 - degrade to deterministic fallback
                logger.warning("scribe_note_llm_failed err=%s", exc.__class__.__name__)

        # Deterministic, no-fabrication fallback: derive only from the transcript.
        sections = self._fallback_sections(template, transcript)
        return Note(
            template_id=template.id,
            sections=sections,
            insufficient_input=False,
            metadata={"generator": "scribe-note-v1", "mode": "deterministic"},
        )

    @staticmethod
    def _fallback_sections(template: Template, transcript: str) -> dict[str, str]:
        """Distribute transcript content without inventing clinical facts.

        The first declared section receives a transcript summary; the rest stay
        empty. This guarantees no fabricated drugs/allergies/findings (Req 6.5)
        while still returning exactly the template's keys.
        """

        out = _empty_sections(template)
        summary = " ".join(transcript.split()).strip()
        if template.section_keys:
            out[template.section_keys[0]] = summary
        return out
