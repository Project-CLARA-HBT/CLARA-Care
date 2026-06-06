"""Write / read adapter for the knowledge-graph tables (task 8.1).

This module is the ``Graph_Store`` persistence boundary for the biomedical
knowledge graph that ``graphrag.py`` will load from the database (task 8.2,
Requirement 10.1) instead of the static seed JSON it reads today. It owns write
and read access to two corpus tables defined in
:mod:`clara_ml.rag.store.schema`:

* ``kb_entities`` — normalized RxNorm/UMLS concepts (the graph *nodes*), with
  identity ``(cui, rxcui, canonical_name)``.
* ``kb_entity_edges`` — drug-interaction / contraindication / relationship
  *edges* between two entities, with identity
  ``(source_entity, target_entity, relation)`` and ``weight`` / ``provenance``.

Design constraints honoured here (mirroring ``document_store.py`` /
``sparse_index.py``):

* **Import-safe.** Importing this module opens no database connection and runs
  no DDL. The store is constructed with a dependency-injected session factory
  (a :class:`~sqlalchemy.orm.sessionmaker` or any zero-arg callable returning a
  :class:`~sqlalchemy.orm.Session`), so a live database is required only when a
  method actually executes. Unit/smoke tests can exercise it against an
  in-memory SQLite engine or a session double.
* **Parameterized ORM only.** Every statement goes through the SQLAlchemy ORM /
  Core expression language with bound parameters. No value is ever interpolated
  into a SQL string.
* **UPSERT with conflict handling.** :meth:`GraphStore.upsert_entity` resolves
  the ``kb_entities`` identity (reusing an existing concept by ``rxcui`` / ``cui``
  when no explicit ``canonical_name`` is given) so the entity-linker path and the
  graph-builder path converge on the same node. :meth:`GraphStore.upsert_edge`
  conflict-handles on the ``(source_entity, target_entity, relation)`` unique
  triple, updating ``weight`` / ``provenance`` in place, so re-running the graph
  builder is idempotent (Requirement 10.1).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from clara_ml.rag.store.schema import KbEntity, KbEntityEdge

__all__ = [
    "EntityInput",
    "EdgeInput",
    "EntityEdge",
    "GraphStore",
]


# ---------------------------------------------------------------------------
# Input / output dataclasses (kept here so graph_builder.py can import them)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class EntityInput:
    """A normalized concept destined for ``kb_entities`` (a graph node).

    Identity is ``(cui, rxcui, canonical_name)`` (the table's unique
    constraint). When ``canonical_name`` is omitted the store reuses an existing
    concept matched by ``rxcui`` then ``cui`` and otherwise falls back to the
    identifier itself, so an edge endpoint always resolves to a stable node id.
    """

    canonical_name: str | None = None
    entity_type: str = "drug"
    cui: str = ""
    rxcui: str = ""
    synonyms: list[dict] = field(default_factory=list)
    source_vocab: str = ""


@dataclass(slots=True)
class EdgeInput:
    """A directed relationship destined for ``kb_entity_edges`` (a graph edge).

    Identity is ``(source_entity, target_entity, relation)``; ``weight`` and
    ``provenance`` are updated in place on conflict.
    """

    source_entity: int
    target_entity: int
    relation: str
    weight: float = 0.5
    provenance: str = ""


@dataclass(slots=True)
class EntityEdge:
    """A read view of one ``kb_entity_edges`` row (returned by reads)."""

    id: int
    source_entity: int
    target_entity: int
    relation: str
    weight: float
    provenance: str


# ---------------------------------------------------------------------------
# GraphStore
# ---------------------------------------------------------------------------


class GraphStore:
    """Transactional write/UPSERT + read adapter over the ``kb_entity_*`` graph.

    Parameters
    ----------
    session_factory:
        A zero-argument callable returning a new :class:`~sqlalchemy.orm.Session`
        — typically a :class:`~sqlalchemy.orm.sessionmaker` or ``services/api``'s
        ``SessionLocal``. Injected (as in :class:`DocumentStore` /
        :class:`SparseIndex`) so the store never owns engine lifecycle and stays
        import-safe / unit-testable.

    Each write method accepts an optional ``session`` keyword. When a session is
    supplied (e.g. from :meth:`transaction`) the method participates in that
    caller-owned unit of work and does **not** commit; when omitted, the method
    opens, commits, and closes its own short transaction.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        if not callable(session_factory):
            raise TypeError(
                "session_factory must be a zero-argument callable returning a Session"
            )
        self._session_factory = session_factory

    # -- construction helpers ------------------------------------------------

    @classmethod
    def from_engine(cls, engine: Engine) -> "GraphStore":
        """Build a store from a SQLAlchemy ``Engine`` (no connection opened)."""

        factory = sessionmaker(bind=engine, expire_on_commit=False)
        return cls(factory)

    # -- session plumbing ----------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Yield a session that commits on success and rolls back on error.

        Pass the yielded session into the write methods to batch a whole
        relationship group (e.g. all edges for one ``rxcui``) into a single
        atomic unit of work.
        """

        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def _run(self, session: Session | None, work: Callable[[Session], Any]) -> Any:
        """Execute ``work`` on a supplied session or a self-managed transaction."""

        if session is not None:
            return work(session)
        with self.transaction() as managed:
            return work(managed)

    def _read(self, session: Session | None, work: Callable[[Session], Any]) -> Any:
        if session is not None:
            return work(session)
        with self._read_session() as managed:
            return work(managed)

    # -- entities ------------------------------------------------------------

    def upsert_entity(
        self,
        entity: EntityInput | None = None,
        *,
        canonical_name: str | None = None,
        entity_type: str = "drug",
        cui: str = "",
        rxcui: str = "",
        synonyms: list[dict] | None = None,
        source_vocab: str = "",
        session: Session | None = None,
    ) -> int:
        """Insert or reuse a concept in ``kb_entities``; return its ``id``.

        Accepts either an :class:`EntityInput` (first positional arg) or the
        equivalent keyword fields. Conflict handling on the
        ``(cui, rxcui, canonical_name)`` identity:

        * **Explicit ``canonical_name``** — match the full identity triple; an
          existing row is updated in place (``entity_type`` / ``synonyms`` /
          ``source_vocab``), otherwise a new row is inserted.
        * **No ``canonical_name``** — reuse an existing concept matched by
          ``rxcui`` (then ``cui``) so the graph builder converges on the node
          the entity linker created; if none exists, the identifier itself
          (``rxcui`` or ``cui``) is stored as the canonical name so the edge
          endpoint resolves to a stable id.

        Raises :class:`ValueError` when neither an identifier (``rxcui`` /
        ``cui``) nor a ``canonical_name`` is supplied (a node needs identity).
        """

        if entity is not None:
            canonical_name = entity.canonical_name
            entity_type = entity.entity_type
            cui = entity.cui
            rxcui = entity.rxcui
            synonyms = entity.synonyms
            source_vocab = entity.source_vocab

        cui_v = (cui or "").strip()
        rxcui_v = (rxcui or "").strip()
        name_v = None if canonical_name is None else str(canonical_name).strip()
        type_v = (entity_type or "drug").strip() or "drug"
        synonyms_v = list(synonyms) if synonyms else []
        vocab_v = (source_vocab or "").strip()

        if not name_v and not rxcui_v and not cui_v:
            raise ValueError("upsert_entity requires a canonical_name or an rxcui/cui identifier")

        def work(s: Session) -> int:
            existing: KbEntity | None = None

            if name_v:
                # Match the full identity triple.
                existing = s.execute(
                    select(KbEntity).where(
                        KbEntity.cui == cui_v,
                        KbEntity.rxcui == rxcui_v,
                        KbEntity.canonical_name == name_v,
                    )
                ).scalar_one_or_none()
            else:
                # No explicit name: reuse an existing concept by identifier so
                # the builder converges on the linker's node.
                if rxcui_v:
                    existing = s.execute(
                        select(KbEntity).where(KbEntity.rxcui == rxcui_v).limit(1)
                    ).scalar_one_or_none()
                if existing is None and cui_v:
                    existing = s.execute(
                        select(KbEntity).where(KbEntity.cui == cui_v).limit(1)
                    ).scalar_one_or_none()

            resolved_name = name_v or rxcui_v or cui_v

            if existing is not None:
                existing.entity_type = type_v
                if synonyms_v:
                    existing.synonyms_json = synonyms_v
                if vocab_v:
                    existing.source_vocab = vocab_v
                s.flush()
                return int(existing.id)

            row = KbEntity(
                cui=cui_v,
                rxcui=rxcui_v,
                canonical_name=resolved_name,
                entity_type=type_v,
                synonyms_json=synonyms_v,
                source_vocab=vocab_v,
            )
            s.add(row)
            s.flush()
            return int(row.id)

        return self._run(session, work)

    # -- edges ---------------------------------------------------------------

    def upsert_edge(
        self,
        source_entity: int,
        target_entity: int,
        relation: str,
        *,
        weight: float = 0.5,
        provenance: str = "",
        session: Session | None = None,
    ) -> int:
        """Insert or update one graph edge; return its ``id``.

        Conflict handling on the ``(source_entity, target_entity, relation)``
        unique triple: a matching edge has its ``weight`` / ``provenance``
        refreshed in place (idempotent re-runs), otherwise a new edge is
        inserted. ``relation`` is required and normalized (trimmed, lower-cased)
        to match the relation vocabulary used elsewhere in graphrag.
        """

        relation_v = str(relation or "").strip().lower()
        if not relation_v:
            raise ValueError("upsert_edge requires a non-empty relation")
        src = int(source_entity)
        dst = int(target_entity)
        weight_v = float(weight)
        provenance_v = str(provenance or "")

        def work(s: Session) -> int:
            existing = s.execute(
                select(KbEntityEdge).where(
                    KbEntityEdge.source_entity == src,
                    KbEntityEdge.target_entity == dst,
                    KbEntityEdge.relation == relation_v,
                )
            ).scalar_one_or_none()

            if existing is not None:
                existing.weight = weight_v
                existing.provenance = provenance_v
                s.flush()
                return int(existing.id)

            row = KbEntityEdge(
                source_entity=src,
                target_entity=dst,
                relation=relation_v,
                weight=weight_v,
                provenance=provenance_v,
            )
            s.add(row)
            s.flush()
            return int(row.id)

        return self._run(session, work)

    def upsert_edges(
        self,
        rows: Iterable[EdgeInput],
        *,
        session: Session | None = None,
    ) -> list[int]:
        """UPSERT many edges in one unit of work; return their ids in order.

        Convenience over :meth:`upsert_edge` that shares a single transaction so
        a batch of edges for one source concept commits all-or-nothing.
        """

        staged = list(rows)

        def work(s: Session) -> list[int]:
            ids: list[int] = []
            for edge in staged:
                ids.append(
                    self.upsert_edge(
                        edge.source_entity,
                        edge.target_entity,
                        edge.relation,
                        weight=edge.weight,
                        provenance=edge.provenance,
                        session=s,
                    )
                )
            return ids

        return self._run(session, work)

    def get_edges(
        self,
        *,
        source_entity: int | None = None,
        relation: str | None = None,
        session: Session | None = None,
    ) -> list[EntityEdge]:
        """Return graph edges, optionally filtered by source and/or relation.

        With no filters this returns every edge (the load path task 8.2 uses to
        hydrate graphrag from the database). ``relation`` is matched against the
        normalized (trimmed, lower-cased) stored value. Ordering is deterministic
        (``source_entity``, ``target_entity``, ``relation``).
        """

        stmt = select(KbEntityEdge)
        if source_entity is not None:
            stmt = stmt.where(KbEntityEdge.source_entity == int(source_entity))
        if relation is not None:
            stmt = stmt.where(KbEntityEdge.relation == str(relation).strip().lower())
        stmt = stmt.order_by(
            KbEntityEdge.source_entity.asc(),
            KbEntityEdge.target_entity.asc(),
            KbEntityEdge.relation.asc(),
        )

        def work(s: Session) -> list[EntityEdge]:
            rows = s.execute(stmt).scalars().all()
            return [
                EntityEdge(
                    id=int(row.id),
                    source_entity=int(row.source_entity),
                    target_entity=int(row.target_entity),
                    relation=str(row.relation),
                    weight=float(row.weight),
                    provenance=str(row.provenance or ""),
                )
                for row in rows
            ]

        return self._read(session, work)
