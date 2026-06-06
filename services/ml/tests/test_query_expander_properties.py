"""Property-based tests for recall-only query expansion soundness.

Feature: rag-knowledge-pipeline, Property 18: Synonym-expansion soundness
(recall-only).

Design reference (design.md -> Correctness Properties):
    Property 18: Synonym-expansion soundness (recall-only). For any query,
    ``set(original_terms) subseteq set(expanded.terms)``; expansion never
    removes original terms and every added term traces to a linked entity or
    the curated VN<->EN lexicon.

Requirements (requirements.md -> Requirement 9, Acceptance Criteria):
    9.2 WHEN expanding a query, THE Query_Expander SHALL produce a term set that
        contains every original query term as a subset (recall-only expansion).
    9.3 WHEN expanding a query, THE Query_Expander SHALL ensure every added term
        traces to a ``LinkedEntity`` or the curated VN<->EN lexicon.
    9.4 IF the UTS API is unavailable, THEN ... otherwise return an empty
        expansion that preserves the original query terms (graceful fallback).

Target: :class:`clara_ml.rag.normalize.query_expander.QueryExpander` driven by a
FAKE, network-free entity linker (``FakeEntityLinker``) plus the curated default
VN<->EN lexicon. The fake linker maps a handful of drug surface forms to
deterministic :class:`~clara_ml.rag.normalize.entity_linker.LinkedEntity`
objects with brand/generic synonyms, so the entity-derived expansion branch is
exercised without any UTS/RxNorm call.

Three sub-properties are covered:

* RECALL-ONLY SUPERSET (9.2) -- ``set(tokenize(query)) subseteq set(terms)``;
  the original query terms are never dropped, so expansion can only raise
  recall, never lower it.
* TRACEABLE ADDITIONS (9.3) -- every term in ``terms`` that is NOT an original
  query term traces to either a fake-linker entity (its canonical name or one of
  its synonyms) or the curated lexicon; no arbitrary/hallucinated term appears.
* GRACEFUL DEGRADATION (9.4) -- a ``None`` / empty / raising linker combined
  with a lexicon that matches nothing yields ``terms == original_terms`` and
  never raises.

Validates: Requirements 9.2, 9.3.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.rag.normalize.entity_linker import LinkedEntity
from clara_ml.rag.normalize.query_expander import (
    DEFAULT_VN_EN_LEXICON,
    ExpandedQuery,
    QueryExpander,
    _dedupe,
    _entity_names,
    _normalize_phrase,
    _tokenize,
)

# Property tests run >= 100 iterations; deadline disabled because the in-process
# tokenize/expand loop timing is environment-dependent and not what we assert.
_PBT_SETTINGS = settings(max_examples=200, deadline=None)


# --------------------------------------------------------------------------- #
# Fake, network-free entity linker (deterministic surface -> LinkedEntity).
# --------------------------------------------------------------------------- #

# A drug entity is keyed by every surface token that should trigger it. Aliased
# triggers (e.g. paracetamol / acetaminophen) point at the SAME entity object so
# de-duplication by identity keeps the fake's output stable.
_ACETAMINOPHEN = LinkedEntity(
    cui="C0000970",
    rxcui="161",
    canonical_name="acetaminophen",
    entity_type="drug",
    synonyms=[
        {"name": "paracetamol", "lang": "en", "kind": "generic"},
        {"name": "Tylenol", "lang": "en", "kind": "brand"},
        {"name": "Panadol", "lang": "en", "kind": "brand"},
    ],
    confidence=1.0,
)
_ASPIRIN = LinkedEntity(
    cui="C0004057",
    rxcui="1191",
    canonical_name="aspirin",
    entity_type="drug",
    synonyms=[
        {"name": "acetylsalicylic acid", "lang": "en", "kind": "generic"},
        {"name": "Bayer", "lang": "en", "kind": "brand"},
    ],
    confidence=1.0,
)
_WARFARIN = LinkedEntity(
    cui="C0043031",
    rxcui="11289",
    canonical_name="warfarin",
    entity_type="drug",
    synonyms=[
        {"name": "Coumadin", "lang": "en", "kind": "brand"},
        {"name": "Jantoven", "lang": "en", "kind": "brand"},
    ],
    confidence=1.0,
)
_IBUPROFEN = LinkedEntity(
    cui="C0020740",
    rxcui="5640",
    canonical_name="ibuprofen",
    entity_type="drug",
    synonyms=[
        {"name": "Advil", "lang": "en", "kind": "brand"},
        {"name": "Motrin", "lang": "en", "kind": "brand"},
    ],
    confidence=1.0,
)

# Surface trigger token (already casefolded) -> entity.
_FAKE_ENTITY_DB: dict[str, LinkedEntity] = {
    "paracetamol": _ACETAMINOPHEN,
    "acetaminophen": _ACETAMINOPHEN,
    "aspirin": _ASPIRIN,
    "warfarin": _WARFARIN,
    "ibuprofen": _IBUPROFEN,
}


class FakeEntityLinker:
    """Deterministic, offline stand-in for the real ``EntityLinker``.

    Satisfies the duck-typed ``link(text, *, lang) -> list[LinkedEntity]``
    contract the expander expects. Returns one entity per distinct drug surface
    found in ``text`` (token-aligned, casefolded). Performs no I/O.
    """

    def __init__(self, db: dict[str, LinkedEntity] | None = None) -> None:
        self._db = _FAKE_ENTITY_DB if db is None else db
        self.calls = 0

    def link(self, text: str, *, lang: str = "en") -> list[LinkedEntity]:
        self.calls += 1
        tokens = set(_tokenize(text))
        out: list[LinkedEntity] = []
        seen: set[int] = set()
        for trigger, entity in self._db.items():
            if trigger in tokens and id(entity) not in seen:
                seen.add(id(entity))
                out.append(entity)
        return out


class EmptyEntityLinker:
    """A linker that always finds nothing (valid, recall-only fallback)."""

    def link(self, text: str, *, lang: str = "en") -> list[LinkedEntity]:
        return []


class RaisingEntityLinker:
    """A misbehaving linker (e.g. UTS unavailable / rate-limited)."""

    def link(self, text: str, *, lang: str = "en") -> list[LinkedEntity]:
        raise RuntimeError("UTS unavailable")


# --------------------------------------------------------------------------- #
# Query generators -- VN + EN, biased to include curated-lexicon keys/values
# and known drug surfaces so the expansion branches are genuinely exercised.
# --------------------------------------------------------------------------- #

_LEXICON_PHRASES = sorted(
    set(DEFAULT_VN_EN_LEXICON.keys())
    | {value for values in DEFAULT_VN_EN_LEXICON.values() for value in values}
)
_DRUG_PHRASES = [
    "paracetamol",
    "acetaminophen",
    "aspirin",
    "warfarin",
    "ibuprofen",
    "Tylenol",
    "Coumadin",
]
_FILLER_PHRASES = [
    "bệnh nhân",
    "uống",
    "khi",
    "với",
    "có thể",
    "cùng lúc",
    "interaction",
    "between",
    "and",
    "is it safe",
    "không",
    "trẻ em",
]

_phrase = st.sampled_from(_LEXICON_PHRASES + _DRUG_PHRASES + _FILLER_PHRASES)

# A query is a whitespace-joined mix of curated/drug/filler phrases, or free
# unicode text, or the empty string (edge case).
_query = st.one_of(
    st.lists(_phrase, min_size=0, max_size=6).map(" ".join),
    st.text(max_size=40),
    st.just(""),
    st.just("   "),
)

_lang = st.sampled_from(["vi", "en"])


# --------------------------------------------------------------------------- #
# Property tests
# --------------------------------------------------------------------------- #


@_PBT_SETTINGS
@given(query=_query, lang=_lang)
def test_expansion_is_recall_only_superset_with_traceable_additions(query: str, lang: str) -> None:
    """Property 18 (Req 9.2, 9.3): superset + traceable additions, no injection.

    For any query and any language, the expanded term set is a recall-only
    superset of the original query terms, and every added term traces to a
    fake-linker entity synonym/canonical or the curated VN<->EN lexicon.
    """

    linker = FakeEntityLinker()
    expander = QueryExpander(linker)  # default curated lexicon
    result = expander.expand(query, lang=lang)

    assert isinstance(result, ExpandedQuery)

    original_terms = set(_tokenize(query))
    expanded_terms = set(result.terms)

    # (1) Recall-only superset (Req 9.2): no original term is ever dropped.
    assert original_terms <= expanded_terms

    # Terms are unique (deterministic, de-duplicated output).
    assert len(result.terms) == len(set(result.terms))

    # (2) Provenance (Req 9.3): every ADDED term traces to a linked entity
    # (canonical name or a synonym) OR the curated lexicon (key or variant).
    # The fake linker is deterministic, so calling it again reproduces exactly
    # the entities the expander consumed internally.
    entities = linker.link(query, lang=lang)
    allowed_entity_terms = {
        _normalize_phrase(name) for entity in entities for name in _entity_names(entity)
    }
    allowed_lexicon_terms: set[str] = set(expander._lexicon.keys())
    for variants in expander._lexicon.values():
        allowed_lexicon_terms.update(variants)
    allowed = (allowed_entity_terms | allowed_lexicon_terms) - {""}

    added = expanded_terms - original_terms
    assert added <= allowed, f"untraceable added terms: {added - allowed!r}"


@_PBT_SETTINGS
@given(query=_query, lang=_lang)
def test_degraded_linker_with_no_lexicon_hits_preserves_original_terms(
    query: str, lang: str
) -> None:
    """Property 18 / Req 9.4: graceful degradation preserves original terms.

    With a lexicon that matches nothing (empty lexicon), a ``None`` / empty /
    raising linker yields ``terms == original_terms`` and never raises.
    """

    expected_terms = _dedupe(_tokenize(query))

    for linker in (None, EmptyEntityLinker(), RaisingEntityLinker()):
        expander = QueryExpander(linker, lexicon={})
        result = expander.expand(query, lang=lang)

        assert result.terms == expected_terms
        assert result.synonym_groups == []
        # Original query is retained verbatim; canonical never drops content.
        assert result.original == query


# --------------------------------------------------------------------------- #
# Anchoring examples -- guard the property tests from being vacuously true by
# pinning the curated-lexicon and entity-synonym expansions that must occur.
# --------------------------------------------------------------------------- #


def test_drug_surface_expands_via_fake_linker_synonyms() -> None:
    """A linked drug contributes its brand/generic synonyms as added terms."""

    expander = QueryExpander(FakeEntityLinker())
    result = expander.expand("can I take paracetamol with aspirin", lang="en")

    terms = set(result.terms)
    assert {"paracetamol", "aspirin"} <= terms  # originals kept
    # Entity-derived (and lexicon-corroborated) synonyms are added.
    assert {"acetaminophen", "tylenol", "panadol"} <= terms
    assert {"acetylsalicylic acid", "bayer"} <= terms


def test_vietnamese_lexicon_phrase_expands_to_english() -> None:
    """A curated multi-word VN key expands to its EN variant (recall-only)."""

    expander = QueryExpander(EmptyEntityLinker())  # lexicon-only path
    result = expander.expand("tương tác thuốc của warfarin", lang="vi")

    terms = set(result.terms)
    # Original tokens preserved.
    assert {"tương", "tác", "thuốc", "của", "warfarin"} <= terms
    # Curated VN<->EN lexicon adds the English phrase + a generic 'thuốc' map.
    assert "drug interaction" in terms
    assert {"drug", "medication", "medicine"} <= terms
