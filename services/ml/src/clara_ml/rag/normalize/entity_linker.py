"""RxNorm/UMLS entity linker (task 7.2).

The :class:`EntityLinker` maps free-text drug/condition mentions in a document
or query to normalized RxNorm/UMLS concepts (RXCUI / CUI) with attached
brand/generic and VN/EN synonyms. It is the offline-ingestion *and* online-query
entry point of the normalization layer and builds entirely on the shared,
network-resilient :class:`~clara_ml.rag.normalize.umls_client.UmlsClient`
(task 7.1).

Design contract (Requirements 9.1, 9.4; Property 19 — entity-link soundness):

* **Soundness (no hallucinated links).** Every returned :class:`LinkedEntity`
  has a non-empty ``rxcui`` *or* ``cui``, and its ``canonical_name`` or one of
  its ``synonyms`` occurs (normalized, case-insensitive, token-aligned) in the
  input ``text``. The linker never invents a concept that is not anchored to an
  actual surface mention in the text. This is enforced structurally (the matched
  surface is always attached as a synonym) and re-checked by a final soundness
  gate before any entity is returned.
* **Graceful degradation (recall-only fallback).** Every ``UmlsClient`` method
  is total and returns empty on upstream failure; the linker additionally wraps
  each call so a misbehaving client can never make :meth:`EntityLinker.link`
  raise. When UTS/RxNorm yields nothing, :meth:`link` returns ``[]`` (the query
  retains its original terms downstream — Requirement 9.4).
* **Cache-idempotent.** Linking is deterministic and memoized per
  ``(normalized text, lang)`` in an injectable, clearable cache, so repeated
  calls return the same entity set without re-hitting the network.
* **Import-safe.** Importing this module opens no socket and builds no HTTP
  client; the whole surface is verifiable with a fake/stubbed ``UmlsClient`` and
  no live network.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Any

from clara_ml.nlp.unicode_utils import normalize_nfc

logger = logging.getLogger(__name__)

__all__ = ["EntityLinker", "LinkedEntity"]


# ---------------------------------------------------------------------------
# Core type (mirrors design.md "Core Types")
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinkedEntity:
    """A normalized drug/condition concept linked to a surface mention.

    ``synonyms`` is a list of ``{"name", "lang", "kind"}`` dicts where ``kind``
    is one of ``"brand"``/``"generic"``/``"synonym"`` (from RxNorm) or
    ``"mention"`` (the exact surface that anchored the link). At least one of
    ``rxcui`` / ``cui`` is non-empty (soundness invariant).
    """

    cui: str
    rxcui: str
    canonical_name: str
    entity_type: str
    synonyms: list[dict] = field(default_factory=list)
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Tuning + tiny lexical helpers (pure, network-free)
# ---------------------------------------------------------------------------

# Longest multi-word surface considered (e.g. "amoxicillin clavulanate").
_DEFAULT_MAX_NGRAM = 3
# Single tokens shorter than this are not worth a lookup on their own.
_MIN_SINGLE_TOKEN_LEN = 3

# Confidence by match quality (deterministic).
_CONF_EXACT_RXCUI = 1.0
_CONF_FUZZY_RXNORM = 0.9
_CONF_UMLS_CUI = 0.7

# Minimal stop-word set (EN + VI) — efficiency only; soundness is unaffected.
_STOPWORDS = frozenset(
    {
        # English
        "the", "and", "or", "of", "a", "an", "to", "with", "for", "in", "on",
        "is", "are", "was", "were", "be", "by", "at", "as", "it", "this",
        "that", "you", "your", "my", "i", "he", "she", "they", "we", "do",
        "does", "did", "can", "may", "use", "used", "take", "took", "taking",
        # Vietnamese
        "và", "hoặc", "của", "tôi", "bạn", "bị", "có", "là", "khi", "cho",
        "với", "các", "những", "một", "này", "đã", "đang", "sẽ", "uống",
        "dùng", "thuốc", "không", "được",
    }
)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_HAS_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def _norm_tokens(text: str) -> list[str]:
    """Normalize (NFC + casefold) and tokenize ``text`` into word tokens."""

    if not text:
        return []
    normalized = normalize_nfc(str(text)).casefold()
    return _TOKEN_RE.findall(normalized)


def _phrase_in_tokens(phrase_tokens: list[str], text_tokens: list[str]) -> bool:
    """True if ``phrase_tokens`` appears as a contiguous sublist of tokens.

    Token-aligned matching (not raw substring) prevents partial-word false
    positives such as "ace" matching inside "acetaminophen".
    """

    span = len(phrase_tokens)
    if span == 0 or span > len(text_tokens):
        return False
    for start in range(len(text_tokens) - span + 1):
        if text_tokens[start : start + span] == phrase_tokens:
            return True
    return False


def _coerce_synonym(raw: Any) -> dict | None:
    """Coerce a raw synonym payload into ``{"name", "lang", "kind"}`` or None."""

    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    if not name:
        return None
    lang = str(raw.get("lang", "en")).strip() or "en"
    kind = str(raw.get("kind", "synonym")).strip() or "synonym"
    return {"name": name, "lang": lang, "kind": kind}


# ---------------------------------------------------------------------------
# Entity linker
# ---------------------------------------------------------------------------


class EntityLinker:
    """Link drug/condition mentions to RxNorm/UMLS concepts + synonyms.

    Constructed with an injected ``UmlsClient`` (duck-typed: any object exposing
    ``rxcui_for`` / ``search_rxnorm`` / ``rxcui_synonyms`` / ``umls_cui_for`` is
    accepted, which is what makes the linker testable with a fake client).
    """

    def __init__(
        self,
        umls_client: Any,
        *,
        max_ngram: int = _DEFAULT_MAX_NGRAM,
        cache: MutableMapping[tuple[str, str], tuple[LinkedEntity, ...]] | None = None,
    ) -> None:
        self._client = umls_client
        self._max_ngram = max(1, int(max_ngram))
        self._cache: MutableMapping[tuple[str, str], tuple[LinkedEntity, ...]] = (
            cache if cache is not None else {}
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def link(self, text: str, *, lang: str = "en") -> list[LinkedEntity]:
        """Link entities in ``text`` (see module docstring for the contract).

        Returns a deterministic, de-duplicated list of :class:`LinkedEntity`.
        Returns ``[]`` for empty text or when no sound link can be established
        (graceful, recall-only fallback — Requirement 9.4). Never raises.
        """

        raw = text or ""
        lang_norm = (lang or "en").strip().lower() or "en"
        normalized = normalize_nfc(raw)
        cache_key = (normalized.casefold(), lang_norm)

        if not normalized.strip():
            return []

        cached = self._cache.get(cache_key)
        if cached is not None:
            return [self._copy_entity(entity) for entity in cached]

        text_tokens = _norm_tokens(raw)
        if not text_tokens:
            self._cache[cache_key] = ()
            return []

        ordered = self._link_uncached(raw, lang_norm, text_tokens)
        self._cache[cache_key] = ordered
        return [self._copy_entity(entity) for entity in ordered]

    def clear_cache(self) -> None:
        """Drop all memoized link results."""

        self._cache.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _link_uncached(
        self, raw: str, lang: str, text_tokens: list[str]
    ) -> tuple[LinkedEntity, ...]:
        results: list[tuple[int, LinkedEntity]] = []
        seen: set[tuple[str, str]] = set()

        for surface, position in self._candidate_mentions(raw):
            entity = self._link_mention(surface, lang, text_tokens)
            if entity is None:
                continue
            dedupe_key = (entity.rxcui, entity.cui)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            results.append((position, entity))

        results.sort(
            key=lambda item: (
                item[0],
                item[1].canonical_name.casefold(),
                item[1].rxcui,
                item[1].cui,
            )
        )
        return tuple(entity for _, entity in results)

    def _candidate_mentions(self, raw: str) -> list[tuple[str, int]]:
        """Deterministic n-gram surface candidates with their token position."""

        spans = [match.group(0) for match in _TOKEN_RE.finditer(normalize_nfc(raw))]
        mentions: list[tuple[str, int]] = []
        seen_surfaces: set[str] = set()

        for start in range(len(spans)):
            for length in range(1, self._max_ngram + 1):
                end = start + length
                if end > len(spans):
                    break
                surface = " ".join(spans[start:end])
                norm = surface.casefold()
                if norm in seen_surfaces:
                    continue
                seen_surfaces.add(norm)
                if self._is_skippable(norm):
                    continue
                mentions.append((surface, start))
        return mentions

    @staticmethod
    def _is_skippable(norm_surface: str) -> bool:
        """Skip surfaces that cannot plausibly be a drug/condition mention."""

        tokens = norm_surface.split()
        if not tokens:
            return True
        if not _HAS_LETTER_RE.search(norm_surface):
            return True  # purely numeric / punctuation
        if all(token in _STOPWORDS for token in tokens):
            return True
        if len(tokens) == 1 and len(tokens[0]) < _MIN_SINGLE_TOKEN_LEN:
            return True
        return False

    def _link_mention(
        self, surface: str, lang: str, text_tokens: list[str]
    ) -> LinkedEntity | None:
        """Resolve a single surface mention to a sound :class:`LinkedEntity`."""

        rxcui = self._coerce_str(self._call(self._client.rxcui_for, surface, default=None))
        cui = ""
        entity_type = "drug"
        canonical = surface
        synonyms: list[dict] = []
        confidence = 0.0

        if rxcui:
            synonyms = self._fetch_synonyms(rxcui)
            canonical = self._pick_canonical(synonyms, surface)
            cui = self._coerce_str(self._call(self._client.umls_cui_for, surface, default=None))
            confidence = _CONF_EXACT_RXCUI
        else:
            chosen = self._first_in_text_concept(surface, text_tokens)
            if chosen is not None:
                rxcui = self._coerce_str(chosen.get("rxcui"))
                canonical = self._coerce_str(chosen.get("name")) or surface
                synonyms = self._fetch_synonyms(rxcui) if rxcui else []
                confidence = _CONF_FUZZY_RXNORM
            else:
                cui = self._coerce_str(
                    self._call(self._client.umls_cui_for, surface, default=None)
                )
                if cui:
                    entity_type = "condition"
                    confidence = _CONF_UMLS_CUI

        # Non-empty rxcui OR cui is mandatory (soundness invariant).
        if not rxcui and not cui:
            return None

        synonyms = self._ensure_mention_synonym(synonyms, surface, lang)
        entity = LinkedEntity(
            cui=cui,
            rxcui=rxcui,
            canonical_name=canonical,
            entity_type=entity_type,
            synonyms=synonyms,
            confidence=confidence,
        )

        # Final soundness gate (Property 19): canonical or a synonym must occur
        # token-aligned in the text. Guards against any client misbehavior.
        if not self._is_sound(entity, text_tokens):
            logger.debug("entity_link_dropped_unsound surface=%s", surface)
            return None
        return entity

    def _first_in_text_concept(
        self, surface: str, text_tokens: list[str]
    ) -> dict | None:
        """First fuzzy RxNorm concept whose name actually occurs in the text."""

        concepts = self._call(self._client.search_rxnorm, surface, default=[]) or []
        for concept in concepts:
            if not isinstance(concept, dict):
                continue
            name = self._coerce_str(concept.get("name"))
            if name and _phrase_in_tokens(_norm_tokens(name), text_tokens):
                return concept
        return None

    def _fetch_synonyms(self, rxcui: str) -> list[dict]:
        raw = self._call(self._client.rxcui_synonyms, rxcui, default=[]) or []
        synonyms: list[dict] = []
        for item in raw:
            coerced = _coerce_synonym(item)
            if coerced is not None:
                synonyms.append(coerced)
        return synonyms

    @staticmethod
    def _pick_canonical(synonyms: list[dict], surface: str) -> str:
        """Prefer a generic/ingredient name as canonical; fall back to surface."""

        generics = sorted(
            syn["name"] for syn in synonyms if syn.get("kind") == "generic" and syn.get("name")
        )
        if generics:
            return generics[0]
        return surface

    @staticmethod
    def _ensure_mention_synonym(
        synonyms: list[dict], surface: str, lang: str
    ) -> list[dict]:
        """De-dup synonyms and guarantee the matched surface is present.

        Attaching the surface mention (a contiguous token sublist of the text)
        as a synonym is what makes the soundness gate pass by construction.
        """

        deduped: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for syn in synonyms:
            name = str(syn.get("name", "")).strip()
            if not name:
                continue
            key = (name.casefold(), str(syn.get("kind", "synonym")))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(
                {
                    "name": name,
                    "lang": str(syn.get("lang", "en")) or "en",
                    "kind": str(syn.get("kind", "synonym")) or "synonym",
                }
            )

        surface_norm = surface.casefold().strip()
        if not any(syn["name"].casefold() == surface_norm for syn in deduped):
            deduped.insert(0, {"name": surface, "lang": lang, "kind": "mention"})
        return deduped

    @staticmethod
    def _is_sound(entity: LinkedEntity, text_tokens: list[str]) -> bool:
        candidates = [entity.canonical_name]
        candidates.extend(syn.get("name", "") for syn in entity.synonyms)
        for candidate in candidates:
            phrase = _norm_tokens(candidate)
            if phrase and _phrase_in_tokens(phrase, text_tokens):
                return True
        return False

    @staticmethod
    def _copy_entity(entity: LinkedEntity) -> LinkedEntity:
        """Return a defensive copy so cache contents cannot be mutated."""

        return LinkedEntity(
            cui=entity.cui,
            rxcui=entity.rxcui,
            canonical_name=entity.canonical_name,
            entity_type=entity.entity_type,
            synonyms=[dict(syn) for syn in entity.synonyms],
            confidence=entity.confidence,
        )

    @staticmethod
    def _coerce_str(value: Any) -> str:
        return "" if value is None else str(value).strip()

    @staticmethod
    def _call(fn: Callable[..., Any], *args: Any, default: Any) -> Any:
        """Call an injected client method, collapsing any error to ``default``.

        The ``UmlsClient`` contract is already total, but wrapping here keeps the
        linker total even against a misbehaving/fake client (never raises).
        """

        try:
            return fn(*args)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("entity_link_client_call_failed err=%s", type(exc).__name__)
            return default
