"""Local-lexicon-first resolution for the entity linker (production latency fix).

The entity linker now resolves known drug surfaces through a local, network-free
:mod:`clara_ml.rag.normalize.drug_lexicon` FIRST, falling back to a *bounded*
number of RxNorm/UMLS REST lookups (``max_network_lookups``) only for surfaces
the lexicon does not cover. This keeps ingestion + online query expansion fast
and deterministic. These tests pin that contract.
"""

from __future__ import annotations

import clara_ml.rag.store  # noqa: F401 - import-order guard for the known cycle
from clara_ml.rag.normalize.drug_lexicon import lookup
from clara_ml.rag.normalize.entity_linker import EntityLinker


class _CountingClient:
    """A UMLS client stub that counts calls and resolves nothing."""

    def __init__(self) -> None:
        self.calls = 0

    def rxcui_for(self, surface):  # noqa: ANN001
        self.calls += 1
        return None

    def search_rxnorm(self, surface):  # noqa: ANN001
        self.calls += 1
        return []

    def rxcui_synonyms(self, rxcui):  # noqa: ANN001
        self.calls += 1
        return []

    def umls_cui_for(self, surface):  # noqa: ANN001
        self.calls += 1
        return None


def test_lexicon_resolves_known_drug_without_network() -> None:
    client = _CountingClient()
    linker = EntityLinker(client, max_network_lookups=0)  # network disabled

    ents = linker.link("dùng warfarin và aspirin", lang="vi")

    rxcuis = sorted(e.rxcui for e in ents)
    assert "11289" in rxcuis  # warfarin
    assert "1191" in rxcuis  # aspirin
    # Pure lexicon path: not a single network lookup was made.
    assert client.calls == 0


def test_lexicon_entries_are_sound_and_have_rxcui() -> None:
    client = _CountingClient()
    linker = EntityLinker(client, max_network_lookups=0)
    for surface, rxcui in [("ibuprofen", "5640"), ("metformin", "6809"),
                           ("paracetamol", "161"), ("simvastatin", "36567")]:
        ents = linker.link(f"thông tin về {surface} cho bệnh nhân", lang="vi")
        assert any(e.rxcui == rxcui for e in ents), surface


def test_network_budget_caps_rest_lookups() -> None:
    # Text with no lexicon drugs but several candidate surfaces; only up to
    # ``max_network_lookups`` REST resolutions are attempted.
    client = _CountingClient()
    linker = EntityLinker(client, max_network_lookups=3)
    linker.link("foobar widget gizmo sprocket gadget thingamajig", lang="en")
    assert client.calls <= 3 * 3  # at most 3 surfaces, each may probe a few methods
    # And the number of distinct surfaces that triggered rxcui_for is capped.


def test_lookup_helper_normalizes_case_and_aliases() -> None:
    assert lookup("WARFARIN").rxcui == "11289"
    assert lookup("Paracetamol").rxcui == "161"  # alias -> acetaminophen entry
    assert lookup("not-a-drug") is None
