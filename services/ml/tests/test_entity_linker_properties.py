"""Property-based tests for Entity_Linker soundness (task 7.3).

Feature: rag-knowledge-pipeline, Property 19: Entity-link soundness.
Validates: Requirements 9.1

Design reference (design.md → Correctness Properties / Requirement 9.1):
    Property 19 (Entity-link soundness). For any input ``text``, every
    ``LinkedEntity`` returned by :meth:`EntityLinker.link`
      (a) carries a non-empty ``rxcui`` **or** ``cui``, and
      (b) its ``canonical_name`` or one of its ``synonyms`` occurs in the input
          text under normalized, token-aligned, case-insensitive matching
          — i.e. the linker never hallucinates a concept that is not anchored
          to an actual surface mention in the text.

The linker is exercised against a **fake** ``UmlsClient`` (no network) that
resolves a small, controlled set of drug/condition surfaces to RxNorm/UMLS
concepts and synonyms. Generated inputs interleave those known surfaces with
random filler (ascii + Vietnamese), and the soundness invariant is re-checked
with an independent reimplementation of the normalized token-alignment rule, so
the property is a true black-box check (it never calls the linker's internals).

Supporting graceful-degradation assertions (Requirement 9.4): an empty /
uninformative client yields ``[]``, a raising client never escapes as an
exception, and ``link`` is cache-idempotent (repeated calls are equal and the
second call hits no client method).
"""

from __future__ import annotations

import re
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.nlp.unicode_utils import normalize_nfc
from clara_ml.rag.normalize.entity_linker import EntityLinker, LinkedEntity

# ---------------------------------------------------------------------------
# Controlled concept fixtures (what the fake client "knows")
# ---------------------------------------------------------------------------

# Exact drugs: rxcui_for(surface) resolves directly to an RxCUI.
_EXACT_DRUGS: dict[str, str] = {
    "ibuprofen": "5640",
    "aspirin": "1191",
    "metformin": "6809",
    "paracetamol": "161",  # canonical resolves to the *generic* "acetaminophen"
}

# Fuzzy drugs: rxcui_for(surface) is None, but search_rxnorm(surface) returns a
# concept whose name equals the surface (exercises the in-text fuzzy path).
_FUZZY_DRUGS: dict[str, dict[str, str]] = {
    "naproxen": {"rxcui": "7258", "name": "naproxen", "tty": "IN", "synonym": ""},
    "omeprazole": {"rxcui": "7646", "name": "omeprazole", "tty": "IN", "synonym": ""},
}

# Conditions: only umls_cui_for(surface) resolves (to a CUI).
_CONDITIONS: dict[str, str] = {
    "hypertension": "C0020538",
    "diabetes": "C0011849",
    "asthma": "C0004096",
}

# rxcui -> brand/generic synonym variants (returned by rxcui_synonyms).
_SYNONYMS_BY_RXCUI: dict[str, list[dict[str, str]]] = {
    "5640": [
        {"name": "Advil", "lang": "en", "kind": "brand"},
        {"name": "ibuprofen", "lang": "en", "kind": "generic"},
    ],
    "1191": [
        {"name": "Bayer", "lang": "en", "kind": "brand"},
        {"name": "acetylsalicylic acid", "lang": "en", "kind": "generic"},
    ],
    "6809": [
        {"name": "Glucophage", "lang": "en", "kind": "brand"},
        {"name": "metformin", "lang": "en", "kind": "generic"},
    ],
    # paracetamol -> generic name differs from the surface mention.
    "161": [
        {"name": "acetaminophen", "lang": "en", "kind": "generic"},
        {"name": "Tylenol", "lang": "en", "kind": "brand"},
    ],
    "7258": [
        {"name": "naproxen", "lang": "en", "kind": "generic"},
        {"name": "Aleve", "lang": "en", "kind": "brand"},
    ],
    "7646": [
        {"name": "omeprazole", "lang": "en", "kind": "generic"},
        {"name": "Prilosec", "lang": "en", "kind": "brand"},
    ],
}

_EXACT_KEYS = sorted(_EXACT_DRUGS)
_FUZZY_KEYS = sorted(_FUZZY_DRUGS)
_COND_KEYS = sorted(_CONDITIONS)


# ---------------------------------------------------------------------------
# Fake UmlsClient implementations (network-free, controlled)
# ---------------------------------------------------------------------------


class FakeUmlsClient:
    """Resolves only the controlled fixtures above; everything else is empty.

    Counts every method call so the cache-idempotency property can assert that a
    repeated ``link`` is served entirely from the linker's cache.
    """

    def __init__(self) -> None:
        self.calls = 0

    @staticmethod
    def _key(name: Any) -> str:
        return normalize_nfc(str(name)).casefold().strip()

    def rxcui_for(self, name: str) -> str | None:
        self.calls += 1
        return _EXACT_DRUGS.get(self._key(name))

    def search_rxnorm(self, name: str) -> list[dict[str, str]]:
        self.calls += 1
        hit = _FUZZY_DRUGS.get(self._key(name))
        return [dict(hit)] if hit is not None else []

    def rxcui_synonyms(self, rxcui: str) -> list[dict[str, str]]:
        self.calls += 1
        return [dict(item) for item in _SYNONYMS_BY_RXCUI.get(str(rxcui).strip(), [])]

    def umls_cui_for(self, name: str) -> str | None:
        self.calls += 1
        return _CONDITIONS.get(self._key(name))


class EmptyUmlsClient:
    """Uninformative client: every lookup is empty (UTS yields nothing)."""

    def rxcui_for(self, name: str) -> str | None:  # noqa: ARG002
        return None

    def search_rxnorm(self, name: str) -> list[dict[str, str]]:  # noqa: ARG002
        return []

    def rxcui_synonyms(self, rxcui: str) -> list[dict[str, str]]:  # noqa: ARG002
        return []

    def umls_cui_for(self, name: str) -> str | None:  # noqa: ARG002
        return None


class RaisingUmlsClient:
    """Misbehaving client: every method raises (linker must stay total)."""

    def rxcui_for(self, name: str) -> str | None:  # noqa: ARG002
        raise RuntimeError("boom")

    def search_rxnorm(self, name: str) -> list[dict[str, str]]:  # noqa: ARG002
        raise RuntimeError("boom")

    def rxcui_synonyms(self, rxcui: str) -> list[dict[str, str]]:  # noqa: ARG002
        raise RuntimeError("boom")

    def umls_cui_for(self, name: str) -> str | None:  # noqa: ARG002
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Independent normalized token-alignment check (mirrors the spec wording, not
# the linker's private helpers — this is what makes the property a real check)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _norm_tokens(text: str) -> list[str]:
    if not text:
        return []
    return _TOKEN_RE.findall(normalize_nfc(str(text)).casefold())


def _phrase_in_tokens(phrase: list[str], tokens: list[str]) -> bool:
    span = len(phrase)
    if span == 0 or span > len(tokens):
        return False
    return any(tokens[i : i + span] == phrase for i in range(len(tokens) - span + 1))


def _occurs_in_text(candidate: str, text_tokens: list[str]) -> bool:
    return _phrase_in_tokens(_norm_tokens(candidate), text_tokens)


def _is_sound(entity: LinkedEntity, text_tokens: list[str]) -> bool:
    """canonical_name OR any synonym occurs (normalized, token-aligned) in text."""
    candidates = [entity.canonical_name]
    candidates.extend(str(syn.get("name", "")) for syn in entity.synonyms)
    return any(c and _occurs_in_text(c, text_tokens) for c in candidates)


# ---------------------------------------------------------------------------
# Generators: text mixing known drug surfaces with random filler
# ---------------------------------------------------------------------------

_filler_token = st.one_of(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=8),
    st.sampled_from(["đau", "bụng", "sốt", "nhức", "mỏi", "ngủ", "buồn", "nôn"]),
)

# Separators include punctuation, newlines, and stopword connectors so the
# tokenizer / n-gram surfacing is exercised across realistic boundaries.
_separator = st.sampled_from([" ", "  ", ", ", " - ", "\n", " và ", " with ", "; "])


@st.composite
def _mixed_text(draw: Any) -> tuple[list[str], str]:
    """Return (exact_drugs_present, text) with >=1 known exact drug present."""
    exact_present = draw(
        st.lists(st.sampled_from(_EXACT_KEYS), min_size=1, max_size=4, unique=True)
    )
    other_known = draw(
        st.lists(
            st.sampled_from(_FUZZY_KEYS + _COND_KEYS), max_size=3, unique=True
        )
    )
    fillers = draw(st.lists(_filler_token, max_size=8))
    parts = draw(st.permutations(exact_present + other_known + fillers))
    sep = draw(_separator)
    return exact_present, sep.join(parts)


# ---------------------------------------------------------------------------
# Property 19: Entity-link soundness (Requirement 9.1)
# ---------------------------------------------------------------------------


# Feature: rag-knowledge-pipeline, Property 19: Entity-link soundness
# Validates: Requirements 9.1
@settings(max_examples=200, deadline=None)
@given(case=_mixed_text(), lang=st.sampled_from(["en", "vi"]))
def test_property19_entity_link_soundness(case: tuple[list[str], str], lang: str) -> None:
    exact_present, text = case
    fake = FakeUmlsClient()
    linker = EntityLinker(fake)

    entities = linker.link(text, lang=lang)
    text_tokens = _norm_tokens(text)

    # SOUNDNESS: every returned entity is non-empty-identified and anchored.
    for entity in entities:
        assert entity.rxcui or entity.cui, (
            f"entity {entity!r} has neither rxcui nor cui (soundness (a))"
        )
        assert _is_sound(entity, text_tokens), (
            f"hallucinated link: neither canonical_name {entity.canonical_name!r} "
            f"nor any synonym occurs (normalized) in text {text!r}"
        )

    # NON-VACUITY: every known exact drug actually present must be linked, so
    # the soundness check above is not trivially satisfied by an empty result.
    expected_rxcuis = {_EXACT_DRUGS[name] for name in exact_present}
    returned_rxcuis = {entity.rxcui for entity in entities if entity.rxcui}
    assert expected_rxcuis.issubset(returned_rxcuis), (
        f"expected exact-drug rxcuis {expected_rxcuis} not all linked; "
        f"got {returned_rxcuis} for text {text!r}"
    )


# Feature: rag-knowledge-pipeline, Property 19: Entity-link soundness
# Validates: Requirements 9.1
@settings(max_examples=200, deadline=None)
@given(case=_mixed_text(), lang=st.sampled_from(["en", "vi"]))
def test_link_is_cache_idempotent(case: tuple[list[str], str], lang: str) -> None:
    _exact_present, text = case
    fake = FakeUmlsClient()
    linker = EntityLinker(fake)

    first = linker.link(text, lang=lang)
    calls_after_first = fake.calls
    second = linker.link(text, lang=lang)

    # Repeated calls return equal entity sets (deterministic + memoized).
    assert second == first
    # The second call is served entirely from cache: no new client calls.
    assert fake.calls == calls_after_first


# Feature: rag-knowledge-pipeline, Property 19: Entity-link soundness
# Validates: Requirements 9.1 (graceful degradation — Requirement 9.4)
@settings(max_examples=150, deadline=None)
@given(
    text=st.text(max_size=120),
    seed=st.lists(st.sampled_from(_EXACT_KEYS + _FUZZY_KEYS + _COND_KEYS), max_size=4),
)
def test_uninformative_client_returns_empty_and_never_raises(
    text: str, seed: list[str]
) -> None:
    # Mix arbitrary text with known surfaces so the client is *given* something
    # to (not) resolve; an uninformative network client must still return [].
    # The local drug lexicon is disabled here (lexicon_lookup -> None) so this
    # isolates the *network-degradation* property: with no lexicon fallback and
    # an uninformative/raising client, link() degrades to [] (recall-only).
    blended = " ".join([text, *seed])
    no_lexicon = lambda _s: None  # noqa: E731 - tiny test stub

    empty_linker = EntityLinker(EmptyUmlsClient(), lexicon_lookup=no_lexicon)
    assert empty_linker.link(blended) == []

    # A misbehaving (raising) client must never make link() raise (totality).
    raising_linker = EntityLinker(RaisingUmlsClient(), lexicon_lookup=no_lexicon)
    assert raising_linker.link(blended) == []


# Feature: rag-knowledge-pipeline, Property 19: Entity-link soundness
# Validates: Requirements 9.1
def test_known_drug_links_soundly_example() -> None:
    """Deterministic smoke example: canonical may differ from the surface but a
    synonym (the surface mention) still anchors the link in the text."""
    fake = FakeUmlsClient()
    linker = EntityLinker(fake)

    entities = linker.link("Bệnh nhân uống paracetamol và ibuprofen mỗi ngày")
    by_rxcui = {entity.rxcui: entity for entity in entities}

    # paracetamol -> rxcui 161, canonical normalized to the generic name.
    assert "161" in by_rxcui
    assert by_rxcui["161"].canonical_name == "acetaminophen"
    # ibuprofen -> rxcui 5640.
    assert "5640" in by_rxcui

    text_tokens = _norm_tokens("Bệnh nhân uống paracetamol và ibuprofen mỗi ngày")
    for entity in entities:
        assert entity.rxcui or entity.cui
        assert _is_sound(entity, text_tokens)
