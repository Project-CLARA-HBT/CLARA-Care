"""Regression test: GraphRAG loads its domain graph from the database
(``kb_entity_edges`` via an injected ``GraphStore``) and NOT from the static
seed JSON file.

Background (tasks 8.1/8.2, Requirement 10.1): the GraphRAG engine
(:class:`clara_ml.rag.graphrag.GraphRagSidecar`) used to hydrate its
biomedical domain graph from a static JSON seed file. Task 8.2 replaced that
edge-load with a DB-backed path that sources drug-interaction /
contraindication edges from ``kb_entity_edges`` through
:class:`clara_ml.rag.store.graph_store.GraphStore`. This test locks that
replacement in place:

* when the DB-backed load path is active (an injected ``GraphStore`` /
  session is available and ``RAG_BIOMED_GRAPH_ENABLED`` is on), the engine
  sources edges from the store — proven with a fake ``GraphStore`` that
  returns KNOWN edges and a fake session exposing KNOWN ``kb_entities`` rows;
* those DB edges drive graph expansion (the expansion the engine emits
  reflects exactly the injected edge, not whatever the seed JSON contains);
* the static JSON file is NOT consulted on that path (the JSON loader is
  spied and asserted never to run).

Everything is injected, so no real (Postgres or SQLite) database is required.

**Validates: Requirements 10.1**
"""

from __future__ import annotations

# Import the store package before the other rag modules to avoid the known
# circular-import ordering issue between ``clara_ml.rag`` submodules.
from clara_ml.rag.store.graph_store import EntityEdge
from clara_ml.config import settings
from clara_ml.rag.graphrag import GraphRagSidecar
from clara_ml.rag.retriever import Document


# ---------------------------------------------------------------------------
# Test doubles: a fake GraphStore returning known edges + a fake session that
# exposes known kb_entities rows. No real DB is touched.
# ---------------------------------------------------------------------------


class _FakeEntityRow:
    """Minimal stand-in for a ``kb_entities`` ORM row.

    Only the attributes ``GraphRagSidecar._load_entity_rows`` reads are needed:
    ``id``, ``canonical_name``, ``entity_type`` and ``synonyms_json``.
    """

    def __init__(
        self,
        *,
        id: int,
        canonical_name: str,
        entity_type: str = "drug",
        synonyms_json: list | None = None,
    ) -> None:
        self.id = id
        self.canonical_name = canonical_name
        self.entity_type = entity_type
        self.synonyms_json = synonyms_json if synonyms_json is not None else []


class _FakeScalars:
    def __init__(self, rows: list[_FakeEntityRow]) -> None:
        self._rows = rows

    def all(self) -> list[_FakeEntityRow]:
        return list(self._rows)


class _FakeExecuteResult:
    def __init__(self, rows: list[_FakeEntityRow]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    """A fake SQLAlchemy session that ignores the statement and returns the
    pre-seeded ``kb_entities`` rows. Tracks whether it was closed."""

    def __init__(self, rows: list[_FakeEntityRow]) -> None:
        self._rows = rows
        self.closed = False

    def execute(self, _stmt):  # noqa: ANN001 - statement is intentionally ignored
        return _FakeExecuteResult(self._rows)

    def close(self) -> None:
        self.closed = True


class _FakeGraphStore:
    """A fake ``GraphStore`` whose ``get_edges`` returns KNOWN edges and whose
    ``_session_factory`` yields a fake session over KNOWN ``kb_entities`` rows.

    Mirrors the real ``GraphStore`` surface the sidecar relies on:
    ``get_edges()`` and the ``_session_factory`` attribute resolved by
    ``GraphRagSidecar._resolve_db_access``.
    """

    def __init__(self, edges: list[EntityEdge], entity_rows: list[_FakeEntityRow]) -> None:
        self._edges = list(edges)
        self._entity_rows = list(entity_rows)
        self.get_edges_calls = 0
        self.sessions: list[_FakeSession] = []

    def _session_factory(self) -> _FakeSession:
        session = _FakeSession(self._entity_rows)
        self.sessions.append(session)
        return session

    def get_edges(self, **_kwargs) -> list[EntityEdge]:
        self.get_edges_calls += 1
        return list(self._edges)


def _build_fake_store() -> _FakeGraphStore:
    """A two-node, one-edge graph: warfarin --major_interaction_with--> aspirin.

    The node ids (1, 2), labels and relation are intentionally specific so the
    assertions can verify the expansion is driven by THESE injected DB edges and
    not by the contents of the static seed JSON.
    """

    edges = [
        EntityEdge(
            id=1,
            source_entity=1,
            target_entity=2,
            relation="major_interaction_with",
            weight=0.9,
            provenance="dailymed:spl/warfarin",
        ),
    ]
    entity_rows = [
        _FakeEntityRow(
            id=1,
            canonical_name="warfarin",
            entity_type="ingredient",
            synonyms_json=[{"name": "Coumadin", "lang": "en", "kind": "brand"}],
        ),
        _FakeEntityRow(
            id=2,
            canonical_name="aspirin",
            entity_type="ingredient",
            synonyms_json=[{"name": "acetylsalicylic acid", "lang": "en", "kind": "generic"}],
        ),
    ]
    return _FakeGraphStore(edges, entity_rows)


def test_graphrag_loads_edges_from_db_not_static_json(monkeypatch):
    """When a GraphStore is injected, edges come from ``kb_entity_edges`` and the
    static JSON seed file is never read."""

    monkeypatch.setattr(settings, "rag_biomed_graph_enabled", True)

    # Spy the static-JSON loader: it must NOT be called on the DB-backed path.
    json_loads = {"count": 0}

    def _spy_load_json(self) -> None:  # noqa: ANN001
        json_loads["count"] += 1

    monkeypatch.setattr(GraphRagSidecar, "_load_domain_graph_from_json", _spy_load_json)

    fake_store = _build_fake_store()
    sidecar = GraphRagSidecar(graph_store=fake_store)

    # The graph was sourced from the database via the injected store...
    assert sidecar._graph_source == "database"
    assert sidecar._domain_graph_loaded is True
    assert fake_store.get_edges_calls == 1
    # ...the kb_entities session was opened and closed.
    assert fake_store.sessions and all(session.closed for session in fake_store.sessions)

    # ...and the static JSON seed file was never consulted on this path.
    assert json_loads["count"] == 0

    # The loaded nodes/edges are exactly the injected DB rows.
    assert set(sidecar._domain_entities.keys()) == {"1", "2"}
    assert sidecar._domain_entities["1"].label == "warfarin"
    assert sidecar._domain_entities["2"].label == "aspirin"
    assert len(sidecar._domain_edges) == 1
    loaded_edge = sidecar._domain_edges[0]
    assert (loaded_edge.source, loaded_edge.target) == ("1", "2")
    assert loaded_edge.relation == "major_interaction_with"
    assert loaded_edge.weight == 0.9


def test_graphrag_db_edges_drive_expansion(monkeypatch):
    """The edges loaded from the DB (not the JSON) drive graph expansion: a query
    mentioning the injected entities surfaces the injected interaction edge."""

    monkeypatch.setattr(settings, "rag_biomed_graph_enabled", True)

    json_loads = {"count": 0}

    def _spy_load_json(self) -> None:  # noqa: ANN001
        json_loads["count"] += 1

    monkeypatch.setattr(GraphRagSidecar, "_load_domain_graph_from_json", _spy_load_json)

    fake_store = _build_fake_store()
    sidecar = GraphRagSidecar(graph_store=fake_store)
    assert sidecar._graph_source == "database"
    assert json_loads["count"] == 0

    result = sidecar.expand(
        query="Tương tác giữa warfarin và aspirin có nguy hiểm không?",
        documents=[
            Document(
                id="doc-1",
                text="Warfarin and aspirin co-administration increases bleeding risk.",
                metadata={"source": "dailymed", "url": ""},
            ),
        ],
        expansion_docs=4,
    )

    summary = result.summary
    assert summary["domain_graph_enabled"] is True
    assert summary["domain_graph_loaded"] is True
    # Both injected entities matched, and the injected edge produced a hit.
    assert summary["domain_entity_match_count"] >= 2
    assert summary["domain_edge_hit_count"] >= 1

    edge_hits = summary["domain_edge_hits"]
    interaction_hits = [
        hit
        for hit in edge_hits
        if hit["source"] == "warfarin"
        and hit["target"] == "aspirin"
        and hit["relation"] == "major_interaction_with"
    ]
    assert interaction_hits, f"expected the injected DB edge to drive expansion, got {edge_hits}"

    # The expansion documents reflect the DB-sourced edge.
    domain_docs = [
        doc for doc in result.expansion_docs if doc.metadata.get("source") == "graphrag_domain"
    ]
    assert domain_docs, "expected at least one graphrag_domain expansion doc from the DB edge"
    assert any(
        doc.metadata.get("graph_relation") == "major_interaction_with"
        and doc.metadata.get("graph_source_id") == "1"
        and doc.metadata.get("graph_target_id") == "2"
        for doc in domain_docs
    )
