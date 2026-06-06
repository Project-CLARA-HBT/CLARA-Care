"""Knowledge-graph builder: materialize ``kb_entity_edges`` (task 8.1).

The :class:`GraphBuilder` populates the biomedical knowledge graph that
``graphrag.py`` will load from the database (task 8.2, Requirement 10.1) instead
of the static seed JSON it reads today. It turns two sources of relationship
signal into normalized ``(source, relation, target)`` edges persisted via the
injected :class:`~clara_ml.rag.store.graph_store.GraphStore`:

1. **RxNorm relationships** — :meth:`GraphBuilder.build_edges_for_rxcui` walks
   the RxNorm ``rela`` graph through the shared, network-resilient
   :class:`~clara_ml.rag.normalize.umls_client.UmlsClient` (task 7.1) for the
   curated relation set (``has_tradename`` / ``tradename_of`` / ``consists_of``
   / ``ingredient_of``) and upserts an entity node per endpoint plus an edge
   carrying ``relation`` / ``weight`` / ``provenance``.
2. **Drug-label signals** — :meth:`GraphBuilder.build_from_label_signals` is a
   documented seam that maps DDI / contraindication signals extracted from a
   drug label into edges with label-sourced provenance. A clean stand-in
   extractor is provided so the seam is exercisable today; the real
   label-section parser lands with the ingestion connectors.

Design contract:

* **Dependency-injected + import-safe.** The builder is constructed with an
  injected ``UmlsClient`` and ``GraphStore``; importing this module opens no
  socket and no database connection. The whole surface is verifiable with a
  fake client and an in-memory fake store.
* **Idempotent.** Edge identity is ``(source_entity, target_entity, relation)``
  and node identity is reused by ``rxcui``; re-running the builder updates rows
  in place rather than duplicating them (Requirement 10.1).
* **Graceful.** ``UmlsClient`` methods are total and return empty on upstream
  failure; the builder additionally treats an empty client result as "no edges"
  and never raises for a missing/unknown ``rxcui``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["GraphBuilder", "BuiltEdge", "LabelSignal"]


# ---------------------------------------------------------------------------
# RxNorm relation configuration
# ---------------------------------------------------------------------------

# Curated RxNorm ``rela`` relations the builder materializes, each with a
# default edge weight (clinical salience proxy). brand<->generic links
# (tradename) are informative but low-risk; composition links (ingredient)
# carry slightly more weight as they drive ingredient-level DDI reasoning.
_RXNORM_RELATIONS: dict[str, float] = {
    "has_tradename": 0.4,
    "tradename_of": 0.4,
    "consists_of": 0.5,
    "ingredient_of": 0.6,
}

# Provenance namespace for RxNorm-derived edges (source_key + endpoint).
_RXNORM_PROVENANCE = "rxnorm:related_rxcui"


@dataclass(slots=True)
class BuiltEdge:
    """A read-friendly summary of one edge the builder upserted.

    Returned by the build methods so callers (and tests) can assert the
    ``relation`` / ``weight`` / ``provenance`` carried by each edge without a
    second database read.
    """

    edge_id: int
    source_entity: int
    target_entity: int
    relation: str
    weight: float
    provenance: str


@dataclass(slots=True)
class LabelSignal:
    """A normalized drug-label relationship signal (the label-derived seam).

    ``subject``/``object`` are drug/concept surface names or RxCUIs;
    ``relation`` is a graph relation (e.g. ``"major_interaction_with"`` or
    ``"contraindicated_with_drug"``); ``weight`` is a clinical-salience proxy
    and ``source`` identifies the asserting label for provenance.
    """

    subject: str
    object: str
    relation: str
    weight: float = 0.5
    source: str = "drug_label"


# ---------------------------------------------------------------------------
# GraphBuilder
# ---------------------------------------------------------------------------


class GraphBuilder:
    """Build ``kb_entity_edges`` from RxNorm relationships + label signals.

    Parameters
    ----------
    umls_client:
        An injected :class:`UmlsClient` (duck-typed: any object exposing
        ``related_rxcui(rxcui, relation) -> list[str]`` is accepted, which is
        what makes the builder testable with a fake client).
    graph_store:
        An injected :class:`~clara_ml.rag.store.graph_store.GraphStore` (or any
        object exposing ``upsert_entity`` / ``upsert_edge``), the persistence
        boundary for nodes and edges.
    relations:
        Optional override of the RxNorm relation->weight map (defaults to the
        curated :data:`_RXNORM_RELATIONS`).
    """

    def __init__(
        self,
        umls_client: Any,
        graph_store: Any,
        *,
        relations: dict[str, float] | None = None,
    ) -> None:
        self._client = umls_client
        self._store = graph_store
        self._relations = dict(relations) if relations else dict(_RXNORM_RELATIONS)

    # ------------------------------------------------------------------
    # RxNorm relationship edges
    # ------------------------------------------------------------------

    def build_edges_for_rxcui(self, rxcui: str) -> list[BuiltEdge]:
        """Materialize RxNorm relationship edges for a single ``rxcui``.

        For each curated relation, asks the client for related RxCUIs and, for
        every target, upserts the source and target entity nodes and an edge
        carrying ``relation`` / ``weight`` / ``provenance``. Returns the list of
        :class:`BuiltEdge` summaries (empty when the client yields nothing).

        Idempotent (node reuse by ``rxcui``; edge conflict on the
        ``(source, target, relation)`` triple) and graceful (an empty / failing
        client produces no edges and never raises).
        """

        source_rxcui = str(rxcui or "").strip()
        if not source_rxcui:
            return []

        built: list[BuiltEdge] = []
        source_id: int | None = None  # resolved lazily, only if there are targets
        entity_ids: dict[str, int] = {}

        for relation, weight in self._relations.items():
            targets = self._related(source_rxcui, relation)
            for target_rxcui in targets:
                target_rxcui = str(target_rxcui or "").strip()
                if not target_rxcui or target_rxcui == source_rxcui:
                    continue

                if source_id is None:
                    source_id = self._entity_for_rxcui(source_rxcui, entity_ids)
                target_id = self._entity_for_rxcui(target_rxcui, entity_ids)

                provenance = f"{_RXNORM_PROVENANCE}?rxcui={source_rxcui}&rela={relation}"
                edge_id = self._store.upsert_edge(
                    source_id,
                    target_id,
                    relation,
                    weight=weight,
                    provenance=provenance,
                )
                built.append(
                    BuiltEdge(
                        edge_id=int(edge_id),
                        source_entity=int(source_id),
                        target_entity=int(target_id),
                        relation=relation,
                        weight=float(weight),
                        provenance=provenance,
                    )
                )

        return built

    # ------------------------------------------------------------------
    # Label-derived signal edges (documented seam)
    # ------------------------------------------------------------------

    def build_from_label_signals(
        self, drug_label_text_or_signals: str | Iterable[LabelSignal]
    ) -> list[BuiltEdge]:
        """Map DDI / contraindication label signals into graph edges (seam).

        Accepts either:

        * an iterable of pre-extracted :class:`LabelSignal` objects (the shape
          the real label-section parser will emit), or
        * raw drug-label text, which the clean stand-in
          :meth:`extract_label_signals` turns into :class:`LabelSignal` objects.

        Each signal upserts its subject/object entity nodes (by name) and an
        edge carrying the signal ``relation`` / ``weight`` and label-sourced
        ``provenance``. Returns the :class:`BuiltEdge` summaries (empty when no
        signals are found). Idempotent and graceful (never raises on empty
        input).
        """

        if isinstance(drug_label_text_or_signals, str):
            signals = self.extract_label_signals(drug_label_text_or_signals)
        else:
            signals = [s for s in drug_label_text_or_signals if isinstance(s, LabelSignal)]

        built: list[BuiltEdge] = []
        entity_ids: dict[str, int] = {}
        for signal in signals:
            subject = str(signal.subject or "").strip()
            obj = str(signal.object or "").strip()
            relation = str(signal.relation or "").strip().lower()
            if not subject or not obj or not relation:
                continue

            source_id = self._entity_for_name(subject, entity_ids)
            target_id = self._entity_for_name(obj, entity_ids)
            provenance = f"label:{signal.source}" if signal.source else "label"
            edge_id = self._store.upsert_edge(
                source_id,
                target_id,
                relation,
                weight=float(signal.weight),
                provenance=provenance,
            )
            built.append(
                BuiltEdge(
                    edge_id=int(edge_id),
                    source_entity=int(source_id),
                    target_entity=int(target_id),
                    relation=relation,
                    weight=float(signal.weight),
                    provenance=provenance,
                )
            )
        return built

    @staticmethod
    def extract_label_signals(label_text: str) -> list[LabelSignal]:
        """Clean stand-in extractor: pull DDI/contraindication signals from text.

        This is intentionally a simple, deterministic stand-in for the real
        label-section parser (which lands with the DailyMed/openFDA connectors).
        It recognizes two cue patterns per line and emits a :class:`LabelSignal`:

        * ``"<drug> interacts with <drug>"`` -> ``major_interaction_with``
        * ``"<drug> contraindicated with <drug>"`` -> ``contraindicated_with_drug``

        Returns ``[]`` for empty / unrecognized text (graceful). The real parser
        will replace this with structured section extraction; the edge-writing
        contract (relation/weight/provenance) stays the same.
        """

        text = str(label_text or "")
        if not text.strip():
            return []

        patterns = [
            (re.compile(r"(.+?)\s+contraindicated\s+with\s+(.+)", re.IGNORECASE),
             "contraindicated_with_drug", 0.9),
            (re.compile(r"(.+?)\s+interacts?\s+with\s+(.+)", re.IGNORECASE),
             "major_interaction_with", 0.7),
        ]

        signals: list[LabelSignal] = []
        for raw_line in text.splitlines():
            line = raw_line.strip().rstrip(".")
            if not line:
                continue
            for pattern, relation, weight in patterns:
                match = pattern.search(line)
                if not match:
                    continue
                subject = match.group(1).strip(" .,-")
                obj = match.group(2).strip(" .,-")
                if subject and obj:
                    signals.append(
                        LabelSignal(
                            subject=subject,
                            object=obj,
                            relation=relation,
                            weight=weight,
                            source="drug_label",
                        )
                    )
                break  # first matching cue per line wins
        return signals

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _related(self, rxcui: str, relation: str) -> list[str]:
        """Call the client's ``related_rxcui``, collapsing any error to ``[]``."""

        try:
            result = self._client.related_rxcui(rxcui, relation)
        except Exception as exc:  # pragma: no cover - defensive; client is total
            logger.debug("graph_builder_related_failed err=%s", type(exc).__name__)
            return []
        return list(result or [])

    def _entity_for_rxcui(self, rxcui: str, cache: dict[str, int]) -> int:
        """Resolve (and cache within a build) the node id for an ``rxcui``."""

        key = f"rxcui:{rxcui}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        entity_id = int(
            self._store.upsert_entity(
                rxcui=rxcui,
                entity_type="drug",
                source_vocab="RXNORM",
            )
        )
        cache[key] = entity_id
        return entity_id

    def _entity_for_name(self, name: str, cache: dict[str, int]) -> int:
        """Resolve (and cache within a build) the node id for a concept name."""

        key = f"name:{name.casefold()}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        entity_id = int(
            self._store.upsert_entity(
                canonical_name=name,
                entity_type="drug",
                source_vocab="label",
            )
        )
        cache[key] = entity_id
        return entity_id
