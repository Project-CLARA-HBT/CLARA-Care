"""Local, network-free drug lexicon for fast entity normalization (task 7.2+).

The :class:`~clara_ml.rag.normalize.entity_linker.EntityLinker` originally
resolved every candidate surface through the RxNorm REST API. On a full document
(thousands of n-gram candidates) or even a short query, that meant dozens-to-
thousands of synchronous HTTP round-trips, making ingestion hang and adding
several seconds to every online retrieval (query expansion).

This module ships a small, curated, in-memory lexicon of the high-value drug
concepts the corpus + golden eval set actually exercise, mapping common
generic/brand/Vietnamese aliases to their stable RxNorm ingredient ``rxcui`` and
canonical name. Lexicon resolution is O(1) and opens no socket, so the common
case (a known drug) is resolved instantly offline; the linker falls back to a
*bounded* number of RxNorm REST lookups only for surfaces the lexicon does not
cover.

The ``rxcui`` values are RxNorm ingredient identifiers and match the
``expected_rxcui`` used by the golden Q&A set (``rag.eval.golden_set``).

Pure data + pure functions: importing this module opens no socket and touches no
database.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from clara_ml.nlp.unicode_utils import normalize_nfc

__all__ = ["LexEntry", "lookup", "DRUG_LEXICON"]


@dataclass(frozen=True)
class LexEntry:
    """A resolved lexicon concept: canonical name + rxcui + alias synonyms."""

    rxcui: str
    canonical_name: str
    synonyms: list[dict] = field(default_factory=list)


def _entry(rxcui: str, canonical: str, *aliases: tuple[str, str, str]) -> LexEntry:
    """Build a :class:`LexEntry`. ``aliases`` are ``(name, lang, kind)`` tuples."""

    syns = [{"name": canonical, "lang": "en", "kind": "generic"}]
    syns.extend({"name": n, "lang": lang, "kind": kind} for n, lang, kind in aliases)
    return LexEntry(rxcui=rxcui, canonical_name=canonical, synonyms=syns)


# Curated lexicon. Keys (and alias names) are matched case-insensitively after
# NFC normalization. ``rxcui`` = RxNorm ingredient CUI (matches golden set).
_ENTRIES: list[LexEntry] = [
    _entry("11289", "warfarin", ("coumadin", "en", "brand"), ("jantoven", "en", "brand")),
    _entry("1191", "aspirin", ("acetylsalicylic acid", "en", "synonym"), ("aspirin", "vi", "synonym")),
    _entry("32968", "clopidogrel", ("plavix", "en", "brand")),
    _entry("7646", "omeprazole", ("prilosec", "en", "brand"), ("losec", "en", "brand")),
    _entry("29046", "lisinopril", ("prinivil", "en", "brand"), ("zestril", "en", "brand")),
    _entry("136411", "sildenafil", ("viagra", "en", "brand"), ("revatio", "en", "brand")),
    _entry("4917", "nitroglycerin", ("glyceryl trinitrate", "en", "synonym"), ("nitroglycerine", "en", "synonym")),
    _entry("6809", "metformin", ("glucophage", "en", "brand")),
    _entry("723", "amoxicillin", ("amoxil", "en", "brand"), ("amoxicilin", "vi", "synonym")),
    _entry("5640", "ibuprofen", ("advil", "en", "brand"), ("motrin", "en", "brand")),
    _entry("36567", "simvastatin", ("zocor", "en", "brand")),
    _entry(
        "161", "acetaminophen",
        ("paracetamol", "en", "synonym"), ("paracetamol", "vi", "synonym"),
        ("tylenol", "en", "brand"), ("panadol", "en", "brand"),
    ),
    _entry("83367", "atorvastatin", ("lipitor", "en", "brand")),
    _entry("52175", "losartan", ("cozaar", "en", "brand")),
    _entry("7258", "naproxen", ("aleve", "en", "brand"), ("naprosyn", "en", "brand")),
    _entry("4815", "furosemide", ("lasix", "en", "brand")),
    _entry("8123", "prednisone"),
    _entry("2670", "ciprofloxacin", ("cipro", "en", "brand")),
    _entry("18631", "azithromycin", ("zithromax", "en", "brand")),
    _entry("3616", "diclofenac", ("voltaren", "en", "brand")),
    _entry("6915", "metoprolol", ("lopressor", "en", "brand"), ("toprol", "en", "brand")),
]


def _build_index() -> dict[str, LexEntry]:
    """Map every canonical + alias surface (normalized) to its :class:`LexEntry`."""

    index: dict[str, LexEntry] = {}
    for entry in _ENTRIES:
        index[_key(entry.canonical_name)] = entry
        for syn in entry.synonyms:
            name = syn.get("name", "")
            if name:
                index.setdefault(_key(name), entry)
    return index


def _key(text: str) -> str:
    return normalize_nfc(str(text or "")).casefold().strip()


# Public, immutable view of the lexicon index (built once at import).
DRUG_LEXICON: dict[str, LexEntry] = _build_index()


def lookup(surface: str) -> LexEntry | None:
    """Return the :class:`LexEntry` for an exact (normalized) surface, or ``None``."""

    if not surface:
        return None
    return DRUG_LEXICON.get(_key(surface))
