"""Coding + medication-safety assistance for Scribe notes (task 1.7, Requirement 7).

`CodingAssistant.suggest(text)` produces ADVISORY metadata for a note:
- ICD code suggestions (each with the justifying text span) from a curated,
  pure keyword map — clearly marked as requiring clinician confirmation;
- normalized medications via the existing RAG drug lexicon / entity linker
  (lexicon-only = fast, offline, no network), degrading to surface text when
  unknown (Requirement 7.2);
- drug-drug interaction advisories via an INJECTABLE seam (defaults to a small
  curated pair set; production can inject the CareGuard/DDI path).

All output is additive metadata and never modifies the note's clinical text
(Requirement 7.4); nothing is presented as a confirmed diagnosis/prescription
(Requirement 7.5). Importing this module opens no socket.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CodeSuggestion", "MedSuggestion", "CodingResult", "CodingAssistant"]


@dataclass(frozen=True, slots=True)
class CodeSuggestion:
    code: str
    system: str  # "ICD-10"
    description: str
    span: str  # the transcript/note text that justified the suggestion
    confirmed: bool = False  # always advisory until a clinician confirms


@dataclass(frozen=True, slots=True)
class MedSuggestion:
    surface: str  # text as mentioned
    normalized_name: str = ""
    rxcui: str = ""


@dataclass(frozen=True, slots=True)
class CodingResult:
    icd: list[CodeSuggestion] = field(default_factory=list)
    medications: list[MedSuggestion] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)
    advisory: bool = True  # the whole result requires clinician confirmation

    def as_dict(self) -> dict[str, Any]:
        return {
            "icd": [vars(c) for c in self.icd],
            "medications": [vars(m) for m in self.medications],
            "interactions": list(self.interactions),
            "advisory": self.advisory,
        }


# Curated, conservative keyword -> ICD-10 map (advisory only). Kept small and
# deterministic; the LLM/clinician refines. Each entry: (keyword, code, desc).
_ICD_KEYWORDS: list[tuple[str, str, str]] = [
    ("hypertension", "I10", "Essential (primary) hypertension"),
    ("tăng huyết áp", "I10", "Essential (primary) hypertension"),
    ("type 2 diabetes", "E11.9", "Type 2 diabetes mellitus without complications"),
    ("đái tháo đường", "E11.9", "Type 2 diabetes mellitus without complications"),
    ("asthma", "J45.909", "Unspecified asthma, uncomplicated"),
    ("hen", "J45.909", "Unspecified asthma, uncomplicated"),
    ("pneumonia", "J18.9", "Pneumonia, unspecified organism"),
    ("viêm phổi", "J18.9", "Pneumonia, unspecified organism"),
    ("urinary tract infection", "N39.0", "Urinary tract infection, site not specified"),
    ("acute pharyngitis", "J02.9", "Acute pharyngitis, unspecified"),
    ("viêm họng", "J02.9", "Acute pharyngitis, unspecified"),
    ("gastritis", "K29.70", "Gastritis, unspecified, without bleeding"),
    ("viêm dạ dày", "K29.70", "Gastritis, unspecified, without bleeding"),
    ("migraine", "G43.909", "Migraine, unspecified, not intractable"),
    ("anxiety", "F41.9", "Anxiety disorder, unspecified"),
]

# Minimal curated DDI pairs (rxcui-keyed) for the default interactions seam.
_KNOWN_DDI: dict[frozenset[str], str] = {
    frozenset({"11289", "1191"}): "Warfarin + aspirin: increased bleeding risk (monitor INR).",
    frozenset({"32968", "7646"}): "Clopidogrel + omeprazole: omeprazole may reduce clopidogrel efficacy.",
    frozenset({"136411", "4917"}): "Sildenafil + nitroglycerin: severe hypotension — contraindicated.",
}

# Seam: given normalized meds (with rxcui), return interaction advisory strings.
InteractionFn = Callable[[Sequence[MedSuggestion]], list[str]]


def _default_interactions(meds: Sequence[MedSuggestion]) -> list[str]:
    rxcuis = [m.rxcui for m in meds if m.rxcui]
    out: list[str] = []
    seen: set[frozenset[str]] = set()
    for i in range(len(rxcuis)):
        for j in range(i + 1, len(rxcuis)):
            pair = frozenset({rxcuis[i], rxcuis[j]})
            if pair in _KNOWN_DDI and pair not in seen:
                seen.add(pair)
                out.append(_KNOWN_DDI[pair])
    return out


class CodingAssistant:
    """Produce advisory ICD + medication + interaction suggestions for a note."""

    def __init__(
        self,
        *,
        linker: Any | None = None,
        interaction_fn: InteractionFn | None = None,
    ) -> None:
        self._linker = linker  # injectable; built lazily (lexicon-only) if None
        self._interaction_fn = interaction_fn or _default_interactions

    def _get_linker(self) -> Any | None:
        if self._linker is not None:
            return self._linker
        try:
            from clara_ml.rag.normalize.entity_linker import EntityLinker
            from clara_ml.rag.normalize.umls_client import UmlsClient

            # Lexicon-only (no network) for fast, deterministic note-time coding.
            self._linker = EntityLinker(UmlsClient(), max_network_lookups=0)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("coding_linker_unavailable err=%s", exc.__class__.__name__)
            self._linker = None
        return self._linker

    def suggest(self, text: str, *, lang: str = "vi") -> CodingResult:
        clean = (text or "").strip()
        if not clean:
            return CodingResult()

        icd = self._suggest_icd(clean)
        meds = self._suggest_medications(clean, lang=lang)
        interactions = list(self._interaction_fn(meds))
        return CodingResult(icd=icd, medications=meds, interactions=interactions, advisory=True)

    @staticmethod
    def _suggest_icd(text: str) -> list[CodeSuggestion]:
        lowered = text.lower()
        out: list[CodeSuggestion] = []
        seen: set[str] = set()
        for keyword, code, desc in _ICD_KEYWORDS:
            if keyword in lowered and code not in seen:
                seen.add(code)
                out.append(
                    CodeSuggestion(code=code, system="ICD-10", description=desc, span=keyword)
                )
        return out

    def _suggest_medications(self, text: str, *, lang: str) -> list[MedSuggestion]:
        linker = self._get_linker()
        if linker is None:
            return []
        try:
            entities = list(linker.link(text, lang=lang) or [])
        except Exception as exc:  # noqa: BLE001 - total
            logger.warning("coding_link_failed err=%s", exc.__class__.__name__)
            return []
        out: list[MedSuggestion] = []
        seen: set[str] = set()
        for ent in entities:
            rxcui = str(getattr(ent, "rxcui", "") or "")
            name = str(getattr(ent, "canonical_name", "") or "")
            surface = name
            syns = getattr(ent, "synonyms", None) or []
            for syn in syns:
                if isinstance(syn, dict) and syn.get("kind") == "mention" and syn.get("name"):
                    surface = str(syn["name"])
                    break
            key = rxcui or name.lower()
            if key and key not in seen:
                seen.add(key)
                out.append(MedSuggestion(surface=surface, normalized_name=name, rxcui=rxcui))
        return out
