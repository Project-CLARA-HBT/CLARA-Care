"""Recall-only medical query expansion (task 7.4).

``QueryExpander`` widens a user query for retrieval **without ever changing its
clinical intent**. It is the online-plane counterpart of the entity linker: the
linker (task 7.2) maps drug/condition mentions to RxNorm/UMLS concepts with
brand/generic and VN/EN synonyms; the expander turns those concepts — plus a
small curated VN↔EN medical lexicon — into extra retrieval terms.

Design contract (Requirements 9.2, 9.3, 9.4 — Property 18):

* **Recall-only superset (Req 9.2).** ``set(original_terms) ⊆ set(result.terms)``.
  Expansion is strictly additive: it NEVER removes an original query term, so it
  can only *raise* recall, never lower it.
* **Term provenance (Req 9.3).** Every term that is *added* on top of the
  original query traces to either a :class:`LinkedEntity` returned by the
  injected entity linker (its canonical name or one of its rxcui/cui synonyms)
  or to the curated VN↔EN lexicon. No arbitrary/hallucinated term is injected.
* **Intent-preserving canonical.** ``canonical`` retains every original mention
  (e.g. a drug-drug-interaction query keeps *both* drugs); it only normalizes
  whitespace, it does not drop content.
* **Graceful degradation (Req 9.4).** If the linker returns nothing, is ``None``,
  or raises (e.g. UTS unavailable / rate-limited) and the lexicon matches
  nothing, :meth:`QueryExpander.expand` returns an :class:`ExpandedQuery` whose
  ``terms`` equal the original query terms. ``expand`` never raises.

* **Import-safe.** Importing this module performs no network I/O, constructs no
  HTTP client, and does not require :mod:`clara_ml.rag.normalize.entity_linker`
  to exist yet — the linker is duck-typed at runtime and only referenced for
  type checking. The whole surface is verifiable with a fake linker offline.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from clara_ml.rag.normalize.entity_linker import LinkedEntity

logger = logging.getLogger(__name__)

__all__ = ["ExpandedQuery", "QueryExpander", "DEFAULT_VN_EN_LEXICON"]


# ---------------------------------------------------------------------------
# Curated VN<->EN medical lexicon (default; replaceable via constructor)
# ---------------------------------------------------------------------------
#
# A deliberately small, high-precision seed mapping. Keys/values are matched
# case-insensitively as whole-word phrases against the query. The mapping is
# turned into a *symmetric* one-hop adjacency at construction time, so a hit on
# either side of a pair contributes the other side (Vietnamese ↔ English).
# Multi-word phrases (e.g. "tương tác thuốc") are supported.
DEFAULT_VN_EN_LEXICON: dict[str, list[str]] = {
    # Drug name variants (international vs. US-adopted spelling)
    "paracetamol": ["acetaminophen"],
    "acetaminophen": ["paracetamol"],
    "aspirin": ["acetylsalicylic acid", "axit acetylsalicylic"],
    "adrenaline": ["epinephrine"],
    "epinephrine": ["adrenaline"],
    # Clinical concept VN <-> EN
    "thuốc": ["drug", "medication", "medicine"],
    "tương tác thuốc": ["drug interaction"],
    "chống chỉ định": ["contraindication", "contraindications"],
    "tác dụng phụ": ["side effect", "adverse effect"],
    "liều": ["dose", "dosage"],
    "liều dùng": ["dose", "dosage"],
    "quá liều": ["overdose"],
    "huyết áp": ["blood pressure"],
    "tăng huyết áp": ["hypertension", "high blood pressure"],
    "tiểu đường": ["diabetes", "đái tháo đường"],
    "đái tháo đường": ["diabetes", "tiểu đường"],
    "kháng sinh": ["antibiotic", "antibiotics"],
    "giảm đau": ["analgesic", "painkiller"],
    "hạ sốt": ["antipyretic"],
    "thuốc chống đông": ["anticoagulant"],
    "đau đầu": ["headache"],
    "sốt": ["fever"],
    "ho": ["cough"],
    "dị ứng": ["allergy", "allergic"],
    "mang thai": ["pregnancy", "pregnant"],
}


# ---------------------------------------------------------------------------
# Core type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpandedQuery:
    """Result of expanding a query (design Core Types).

    Attributes:
        original: The query exactly as supplied by the caller.
        canonical: An intent-preserving, whitespace-normalized form of the
            query (retains every original mention — never drops a drug).
        terms: A recall-only **superset** of the original query terms; always
            contains every original term and, additionally, any traceable
            synonym/translation terms.
        synonym_groups: Groups of mutually equivalent terms. Each group is
            anchored by an original/lexicon/entity term and lists its variants.
    """

    original: str
    canonical: str
    terms: list[str] = field(default_factory=list)
    synonym_groups: list[list[str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Linker interface (duck-typed at runtime; structural for documentation)
# ---------------------------------------------------------------------------


@runtime_checkable
class _EntityLinkerLike(Protocol):
    """Structural type for the injected entity linker.

    Only :meth:`link` is used. A real ``EntityLinker`` (task 7.2) satisfies this,
    and so does any fake exposing ``link(text, *, lang) -> list[LinkedEntity]``.
    """

    def link(self, text: str, *, lang: str) -> list[LinkedEntity]: ...


# ---------------------------------------------------------------------------
# Network-free text helpers
# ---------------------------------------------------------------------------

# Unicode-aware word tokenizer. ``\w`` matches Vietnamese letters (they are
# Unicode word characters) so diacritics are preserved.
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _tokenize(text: str) -> list[str]:
    """Split ``text`` into casefolded, diacritic-preserving word tokens."""

    if not text:
        return []
    return [match.group(0).casefold() for match in _WORD_RE.finditer(text)]


def _normalize_phrase(text: str) -> str:
    """Normalize a term/phrase to a space-joined sequence of word tokens."""

    return " ".join(_tokenize(text))


def _dedupe(items: Iterable[str]) -> list[str]:
    """Order-preserving de-duplication, dropping empty strings."""

    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _entity_names(entity: Any) -> list[str]:
    """Extract the canonical name + synonym names from a ``LinkedEntity``.

    Tolerates both the dataclass shape (``synonyms`` = ``list[dict]`` with a
    ``name`` key, per design) and plain objects, so a fake linker is enough to
    exercise the expander offline.
    """

    names: list[str] = []
    canonical = getattr(entity, "canonical_name", None)
    if isinstance(canonical, str):
        names.append(canonical)

    synonyms = getattr(entity, "synonyms", None) or []
    if isinstance(synonyms, (list, tuple)):
        for syn in synonyms:
            name = syn.get("name") if isinstance(syn, dict) else getattr(syn, "name", None)
            if isinstance(name, str):
                names.append(name)
    return names


# ---------------------------------------------------------------------------
# QueryExpander
# ---------------------------------------------------------------------------


class QueryExpander:
    """Recall-only synonym / VN↔EN query expander.

    Constructed with an injected entity linker (``rag.normalize.entity_linker``)
    and, optionally, a curated VN↔EN medical lexicon (defaults to
    :data:`DEFAULT_VN_EN_LEXICON`, fully replaceable).

    The single public method :meth:`expand` is **total**: it never raises and,
    in the worst case (no linker results, no lexicon hits, linker error), yields
    an :class:`ExpandedQuery` whose ``terms`` equal the original query terms
    (Requirement 9.4).
    """

    def __init__(
        self,
        linker: _EntityLinkerLike | None,
        *,
        lexicon: dict[str, list[str]] | None = None,
    ) -> None:
        self._linker = linker
        source = DEFAULT_VN_EN_LEXICON if lexicon is None else lexicon
        # Build a symmetric, one-hop adjacency keyed by normalized phrase so a
        # hit on either language contributes the other (no transitive merging
        # of unrelated concepts). Keys are normalized for whole-word matching.
        adjacency: dict[str, set[str]] = {}
        for raw_key, raw_values in source.items():
            key = _normalize_phrase(raw_key)
            if not key:
                continue
            for raw_value in raw_values or []:
                value = _normalize_phrase(raw_value)
                if not value or value == key:
                    continue
                adjacency.setdefault(key, set()).add(value)
                adjacency.setdefault(value, set()).add(key)
        self._lexicon: dict[str, list[str]] = {
            term: sorted(variants) for term, variants in adjacency.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def expand(self, query: str, *, lang: str = "vi") -> ExpandedQuery:
        """Expand ``query`` into a recall-only :class:`ExpandedQuery`.

        Postconditions (design / Property 18):
          * ``set(original_terms) ⊆ set(result.terms)`` (recall-only superset).
          * Every *added* term traces to a linked entity or the curated lexicon.
          * ``canonical`` preserves clinical intent (keeps every original mention).
          * Never raises; degrades to ``terms == original_terms`` when nothing
            can be added (Req 9.4).
        """

        text = query or ""
        canonical = _WS_RE.sub(" ", text).strip()
        original_terms = _dedupe(_tokenize(text))

        # Base result always starts from the original terms (recall-only floor).
        terms: list[str] = list(original_terms)
        seen: set[str] = set(terms)
        synonym_groups: list[list[str]] = []

        def _add_group(anchor: str, variants: list[str]) -> None:
            """Add a synonym group + its terms, never dropping originals."""

            group = _dedupe([anchor, *variants])
            additions = [t for t in group if t not in seen]
            if not additions:
                return
            for term in additions:
                seen.add(term)
                terms.append(term)
            if len(group) >= 2:
                synonym_groups.append(group)

        # 1) Entity-derived synonyms (brand/generic, VN/EN) from the linker.
        for entity in self._safe_link(text, lang=lang):
            names = _dedupe(_normalize_phrase(name) for name in _entity_names(entity))
            if len(names) >= 2:
                # First name (canonical) anchors the group; rest are variants.
                _add_group(names[0], names[1:])
            elif names:
                # Single name: still a valid added term if not already present.
                _add_group(names[0], [])

        # 2) Curated VN<->EN lexicon hits (whole-word phrase matches).
        for key, variants in self._lexicon_matches(original_terms):
            _add_group(key, variants)

        return ExpandedQuery(
            original=text,
            canonical=canonical,
            terms=terms,
            synonym_groups=synonym_groups,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _safe_link(self, text: str, *, lang: str) -> list[Any]:
        """Call the injected linker, swallowing any failure (Req 9.4)."""

        if self._linker is None or not text.strip():
            return []
        try:
            result = self._linker.link(text, lang=lang)
        except Exception as exc:  # UTS unavailable / rate-limited / bug → recall-only
            logger.debug("query_expander_link_failed err=%s", type(exc).__name__)
            return []
        return list(result) if isinstance(result, (list, tuple)) else []

    def _lexicon_matches(self, original_terms: list[str]) -> list[tuple[str, list[str]]]:
        """Return ``(key, variants)`` lexicon hits found in the query terms.

        A key matches when it appears as a whole-word phrase in the query token
        stream, so multi-word keys (e.g. ``"tương tác thuốc"``) are supported
        without matching across unrelated word boundaries.
        """

        if not original_terms or not self._lexicon:
            return []
        padded = f" {' '.join(original_terms)} "
        matches: list[tuple[str, list[str]]] = []
        for key, variants in self._lexicon.items():
            if f" {key} " in padded:
                matches.append((key, list(variants)))
        return matches
