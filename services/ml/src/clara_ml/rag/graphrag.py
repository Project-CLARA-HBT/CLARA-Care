from __future__ import annotations

import json
import logging
import re
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any

from clara_ml.config import settings
from clara_ml.rag.retriever import Document

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime import cost
    from sqlalchemy.engine import Engine

    from clara_ml.rag.store.graph_store import GraphStore

logger = logging.getLogger(__name__)


@dataclass
class GraphRagResult:
    summary: dict[str, Any]
    expansion_docs: list[Document]


class GraphRagSidecar:
    """GraphRAG sidecar: lexical graph + biomedical domain graph expansion."""

    _CONCEPT_STOPWORDS = {
        "with",
        "from",
        "that",
        "this",
        "into",
        "about",
        "drug",
        "drugs",
        "thuoc",
        "risk",
        "nhung",
        "cua",
        "cho",
        "the",
    }
    _DDI_TERMS = {
        "interaction",
        "ddi",
        "contraindication",
        "bleeding",
        "hemorrhage",
        "adverse",
        "warning",
        "xuat",
        "huyet",
        "chong",
        "chi",
        "dinh",
    }
    _DEFAULT_DOMAIN_GRAPH = (
        Path(__file__).resolve().parents[1] / "nlp" / "seed_data" / "biomed_domain_graph.v1.json"
    )

    @dataclass
    class _DomainEntity:
        entity_id: str
        label: str
        entity_type: str
        aliases: list[str]

    @dataclass
    class _DomainEdge:
        source: str
        target: str
        relation: str
        weight: float

    def __init__(
        self,
        *,
        engine: Engine | None = None,
        graph_store: GraphStore | None = None,
    ) -> None:
        # DB-backed graph wiring (task 8.2, Requirement 10.1). Both are optional
        # and injectable for DI/tests; when neither is supplied the engine is
        # lazily resolved via ``rag.store.health.resolve_default_engine`` at load
        # time. Production never silently substitutes a static graph after a DB
        # failure: a stale graph is less safe than no graph expansion.
        self._engine = engine
        self._graph_store = graph_store
        # Provenance of the currently loaded domain graph: "database",
        # "static_json", or "none". Useful for diagnostics / regression tests.
        self._graph_source = "none"
        self._graph_load_reason = "not_attempted"
        self._last_db_attempt_at = 0.0
        self._load_lock = threading.RLock()
        self._domain_graph_loaded = False
        self._domain_entities: dict[str, GraphRagSidecar._DomainEntity] = {}
        self._domain_edges: list[GraphRagSidecar._DomainEdge] = []
        self._alias_index: dict[str, set[str]] = defaultdict(set)
        self._load_domain_graph()

    @classmethod
    def _tokenize(cls, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{3,}", str(text or "").lower())
            if token and token not in cls._CONCEPT_STOPWORDS
        }

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(re.findall(r"[0-9a-zA-ZÀ-ỹ]+", str(text or "").lower()))

    @staticmethod
    def _normalize_phrase(text: str) -> str:
        return " ".join(re.findall(r"[0-9a-zA-ZÀ-ỹ]+", str(text or "").lower()))

    def _reset_graph_state(self) -> None:
        """Clear all in-memory domain-graph state (entities, edges, aliases)."""

        self._domain_graph_loaded = False
        self._domain_entities.clear()
        self._domain_edges.clear()
        self._alias_index.clear()

    def _static_json_fallback_allowed(self) -> bool:
        """Return whether an explicitly requested non-production seed is safe.

        The static graph exists for local development and isolated fixtures.  It
        is not a production source of authority: a database schema/query error
        must remain observable and retryable rather than silently producing an
        out-of-date expansion.  This guard remains local to the sidecar so an
        injected test store cannot accidentally weaken the deployed policy.
        """

        return bool(
            getattr(settings, "rag_biomed_graph_static_fallback_enabled", False)
            and str(getattr(settings, "environment", "")).strip().lower()
            not in {"prod", "production"}
        )

    def _load_domain_graph(self) -> None:
        """Load the biomedical domain graph from the authoritative store.

        Requirement 10.1: the GraphRAG engine SHALL load drug-interaction and
        contraindication edges from ``kb_entity_edges`` rather than from a static
        JSON file. When ``settings.rag_biomed_graph_enabled`` is on AND a database
        engine/``GraphStore`` is available, edges are hydrated from the database
        via :meth:`GraphStore.get_edges`. A missing table, empty edge set or DB
        failure leaves the graph unavailable and the caller continues with base
        evidence. Static JSON can be enabled only for non-production local
        fixtures through ``RAG_BIOMED_GRAPH_STATIC_FALLBACK_ENABLED=true``.
        """

        with self._load_lock:
            self._reset_graph_state()
            self._graph_source = "none"
            self._graph_load_reason = "static_only"

            if settings.rag_biomed_graph_enabled:
                self._last_db_attempt_at = monotonic()
                try:
                    if self._load_domain_graph_from_db():
                        self._graph_source = "database"
                        self._graph_load_reason = "database_loaded"
                        return
                    self._graph_load_reason = "database_unavailable_or_empty"
                except Exception as exc:  # noqa: BLE001 - defensive: never crash on DB
                    self._graph_load_reason = f"database_error:{exc.__class__.__name__}"
                    logger.debug("graphrag DB edge-load unavailable (%s: %s)", exc.__class__.__name__, exc)
                    self._reset_graph_state()

            if self._static_json_fallback_allowed():
                self._load_domain_graph_from_json()
                if self._domain_graph_loaded:
                    self._graph_source = "static_json"
                    self._graph_load_reason = "static_json_explicit_non_production"

    def _maybe_retry_database_graph(self) -> None:
        """Recover from a transient DB graph failure without retrying per request."""

        if not settings.rag_biomed_graph_enabled or self._graph_source == "database":
            return
        retry_seconds = max(30, int(getattr(settings, "rag_biomed_graph_retry_seconds", 300)))
        if monotonic() - self._last_db_attempt_at >= retry_seconds:
            self._load_domain_graph()

    # -- DB-backed edge load (task 8.2) --------------------------------------

    def _resolve_db_access(self) -> tuple[GraphStore | None, Any]:
        """Resolve a ``(GraphStore, session_factory)`` pair for the DB load path.

        An explicitly injected ``GraphStore`` wins (DI/tests). Otherwise an engine
        is used — the injected one when present, else lazily resolved via
        ``rag.store.health.resolve_default_engine`` (which returns ``None`` when no
        database URL is configured). Returns ``(None, None)`` when no database
        access is available, signalling the caller to fall back to static JSON.
        """

        if self._graph_store is not None:
            return self._graph_store, getattr(self._graph_store, "_session_factory", None)

        engine = self._engine
        if engine is None:
            from clara_ml.rag.store.health import resolve_default_engine

            engine = resolve_default_engine(settings)
        if engine is None:
            return None, None

        from sqlalchemy.orm import sessionmaker

        from clara_ml.rag.store.graph_store import GraphStore

        store = GraphStore.from_engine(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        return store, session_factory

    def _load_entity_rows(self, session_factory: Any, entity_ids: set[int]) -> dict[int, dict[str, Any]]:
        """Read the ``kb_entities`` rows referenced by graph edges.

        Returns a mapping ``entity_id -> {canonical_name, entity_type,
        synonyms_json}`` used to build the alias index that matches query/document
        text against graph nodes. Returns an empty mapping when no session factory
        is available (e.g. an injected store without one).
        """

        if session_factory is None or not entity_ids:
            return {}

        from sqlalchemy import select

        from clara_ml.rag.store.schema import KbEntity

        session = session_factory()
        try:
            rows = (
                session.execute(select(KbEntity).where(KbEntity.id.in_(sorted(entity_ids))))
                .scalars()
                .all()
            )
            return {
                int(row.id): {
                    "canonical_name": str(row.canonical_name or ""),
                    "entity_type": str(row.entity_type or "concept"),
                    "synonyms_json": (
                        row.synonyms_json if isinstance(row.synonyms_json, list) else []
                    ),
                }
                for row in rows
            }
        finally:
            session.close()

    def _load_domain_graph_from_db(self) -> bool:
        """Hydrate the domain graph from ``kb_entity_edges`` (and ``kb_entities``).

        Returns ``True`` only when the database yielded a usable graph (at least
        one entity and one edge); ``False`` otherwise so the caller falls back to
        the static JSON. Never mutates partial state on a ``False`` return path in
        a way that survives (the dispatcher resets state on fallback).
        """

        store, session_factory = self._resolve_db_access()
        if store is None:
            return False

        edges = store.get_edges()
        if not edges:
            return False

        referenced_ids: set[int] = set()
        for edge in edges:
            referenced_ids.add(int(edge.source_entity))
            referenced_ids.add(int(edge.target_entity))

        entity_rows = self._load_entity_rows(session_factory, referenced_ids)
        if not entity_rows:
            return False

        for entity_id, row in entity_rows.items():
            node_id = str(entity_id)
            label = str(row.get("canonical_name") or node_id).strip() or node_id
            entity_type = str(row.get("entity_type") or "concept").strip().lower()
            aliases: list[str] = []
            synonyms = row.get("synonyms_json")
            if isinstance(synonyms, list):
                for synonym in synonyms:
                    name = synonym.get("name") if isinstance(synonym, dict) else synonym
                    normalized = self._normalize_phrase(name) if name else ""
                    if normalized:
                        aliases.append(normalized)
            aliases.append(self._normalize_phrase(label))
            aliases = sorted({alias for alias in aliases if alias})
            entity = self._DomainEntity(
                entity_id=node_id,
                label=label,
                entity_type=entity_type,
                aliases=aliases,
            )
            self._domain_entities[node_id] = entity
            for alias in aliases:
                self._alias_index[alias].add(node_id)

        for edge in edges:
            source = str(int(edge.source_entity))
            target = str(int(edge.target_entity))
            if source not in self._domain_entities or target not in self._domain_entities:
                continue
            relation = str(edge.relation or "related_to").strip().lower()
            try:
                weight = float(edge.weight)
            except (TypeError, ValueError):
                weight = 0.5
            self._domain_edges.append(
                self._DomainEdge(
                    source=source,
                    target=target,
                    relation=relation,
                    weight=max(0.0, min(weight, 1.0)),
                )
            )

        self._domain_graph_loaded = bool(self._domain_entities and self._domain_edges)
        return self._domain_graph_loaded

    def _load_domain_graph_from_json(self) -> None:
        self._domain_graph_loaded = False
        self._domain_entities.clear()
        self._domain_edges.clear()
        self._alias_index.clear()

        raw_path = str(settings.rag_biomed_graph_path or "").strip()
        candidate = Path(raw_path) if raw_path else self._DEFAULT_DOMAIN_GRAPH
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            return

        entities = payload.get("entities")
        edges = payload.get("edges")
        if not isinstance(entities, list) or not isinstance(edges, list):
            return

        for row in entities:
            if not isinstance(row, dict):
                continue
            entity_id = str(row.get("id") or "").strip()
            if not entity_id:
                continue
            label = str(row.get("label") or entity_id).strip()
            entity_type = str(row.get("type") or "concept").strip().lower()
            aliases_raw = row.get("aliases")
            aliases: list[str] = []
            if isinstance(aliases_raw, list):
                aliases = [self._normalize_phrase(alias) for alias in aliases_raw if str(alias).strip()]
            aliases.append(self._normalize_phrase(label))
            aliases = sorted({alias for alias in aliases if alias})
            entity = self._DomainEntity(
                entity_id=entity_id,
                label=label,
                entity_type=entity_type,
                aliases=aliases,
            )
            self._domain_entities[entity_id] = entity
            for alias in aliases:
                self._alias_index[alias].add(entity_id)

        for row in edges:
            if not isinstance(row, dict):
                continue
            source = str(row.get("source") or "").strip()
            target = str(row.get("target") or "").strip()
            if source not in self._domain_entities or target not in self._domain_entities:
                continue
            relation = str(row.get("relation") or "related_to").strip().lower()
            try:
                weight = float(row.get("weight") or 0.5)
            except (TypeError, ValueError):
                weight = 0.5
            self._domain_edges.append(
                self._DomainEdge(
                    source=source,
                    target=target,
                    relation=relation,
                    weight=max(0.0, min(weight, 1.0)),
                )
            )
        self._domain_graph_loaded = bool(self._domain_entities and self._domain_edges)

    def _match_domain_entities(self, text: str) -> set[str]:
        if not text or not self._domain_graph_loaded:
            return set()
        normalized_text = self._normalize_text(text)
        matched: set[str] = set()
        for alias, entity_ids in self._alias_index.items():
            if not alias:
                continue
            if alias in normalized_text:
                matched.update(entity_ids)
        return matched

    def _build_domain_expansion(
        self,
        *,
        query: str,
        documents: list[Document],
        budget: int,
    ) -> tuple[dict[str, Any], list[Document]]:
        if budget <= 0:
            return (
                {
                    "domain_graph_enabled": bool(settings.rag_biomed_graph_enabled),
                    "domain_graph_loaded": self._domain_graph_loaded,
                    "domain_entity_matches": [],
                    "domain_entity_match_count": 0,
                    "domain_edge_hit_count": 0,
                    "domain_edge_hits": [],
                },
                [],
            )
        if not settings.rag_biomed_graph_enabled or not self._domain_graph_loaded:
            return (
                {
                    "domain_graph_enabled": bool(settings.rag_biomed_graph_enabled),
                    "domain_graph_loaded": self._domain_graph_loaded,
                    "domain_entity_matches": [],
                    "domain_entity_match_count": 0,
                    "domain_edge_hit_count": 0,
                    "domain_edge_hits": [],
                },
                [],
            )

        corpus_segments = [query]
        for doc in documents:
            corpus_segments.append(doc.text)
            metadata = doc.metadata if isinstance(doc.metadata, dict) else {}
            corpus_segments.append(str(metadata.get("title") or ""))
            corpus_segments.append(str(metadata.get("url") or ""))
        matched_entities = self._match_domain_entities(" ".join(corpus_segments))
        if not matched_entities:
            return (
                {
                    "domain_graph_enabled": True,
                    "domain_graph_loaded": True,
                    "domain_entity_matches": [],
                    "domain_entity_match_count": 0,
                    "domain_edge_hit_count": 0,
                    "domain_edge_hits": [],
                },
                [],
            )

        relation_priority = {
            "contraindicated_with_class": 6,
            "contraindicated_with_drug": 6,
            "major_interaction_with": 6,
            "raises_risk": 5,
            "has_risk": 4,
            "belongs_to": 3,
            "related_to": 1,
        }
        scored_edges: list[tuple[float, GraphRagSidecar._DomainEdge, bool]] = []
        for edge in self._domain_edges:
            src_hit = edge.source in matched_entities
            dst_hit = edge.target in matched_entities
            if not src_hit and not dst_hit:
                continue
            dual_hit = src_hit and dst_hit
            relation_rank = relation_priority.get(edge.relation, 1)
            score = edge.weight + relation_rank / 10.0 + (0.35 if dual_hit else 0.0)
            scored_edges.append((score, edge, dual_hit))

        scored_edges.sort(key=lambda row: row[0], reverse=True)
        max_edges = min(int(settings.rag_biomed_graph_max_edges), budget)
        selected = scored_edges[:max_edges]

        edge_hits: list[dict[str, Any]] = []
        expansion_docs: list[Document] = []
        for index, (score, edge, dual_hit) in enumerate(selected, start=1):
            source_entity = self._domain_entities.get(edge.source)
            target_entity = self._domain_entities.get(edge.target)
            if source_entity is None or target_entity is None:
                continue
            edge_hits.append(
                {
                    "source": source_entity.label,
                    "target": target_entity.label,
                    "source_id": source_entity.entity_id,
                    "target_id": target_entity.entity_id,
                    "relation": edge.relation,
                    "weight": round(edge.weight, 4),
                    "score": round(score, 4),
                    "dual_hit": dual_hit,
                }
            )
            text = (
                f"Biomedical graph signal: {source_entity.label} -> {target_entity.label} "
                f"({edge.relation}). Clinical weight={edge.weight:.2f}. "
                f"Entity types: {source_entity.entity_type}/{target_entity.entity_type}."
            )
            expansion_docs.append(
                Document(
                    id=f"graphrag-domain-{index}",
                    text=text,
                    metadata={
                        "source": "graphrag_domain",
                        "url": "",
                        "score": score,
                        "weight": edge.weight,
                        "graph_relation": edge.relation,
                        "graph_source_id": source_entity.entity_id,
                        "graph_target_id": target_entity.entity_id,
                    },
                )
            )

        summary = {
            "domain_graph_enabled": True,
            "domain_graph_loaded": True,
            "domain_entity_matches": sorted(matched_entities),
            "domain_entity_match_count": len(matched_entities),
            "domain_edge_hit_count": len(edge_hits),
            "domain_edge_hits": edge_hits,
        }
        return summary, expansion_docs

    def expand(
        self,
        *,
        query: str,
        documents: list[Document],
        max_neighbors: int = 8,
        expansion_docs: int = 4,
    ) -> GraphRagResult:
        self._maybe_retry_database_graph()
        safe_max_neighbors = max(1, int(max_neighbors))
        safe_expansion_docs = max(1, int(expansion_docs))
        query_tokens = self._tokenize(query)

        if not documents:
            domain_summary, domain_docs = self._build_domain_expansion(
                query=query,
                documents=[],
                budget=safe_expansion_docs,
            )
            return GraphRagResult(
                summary={
                    "enabled": True,
                    "node_count": len(query_tokens),
                    "edge_count": 0,
                    "concept_count": len(query_tokens),
                    "expansion_count": len(domain_docs),
                    "max_neighbors": safe_max_neighbors,
                    "expansion_doc_budget": safe_expansion_docs,
                    "expansion_doc_ids": [doc.id for doc in domain_docs],
                    "expansion_rows": [],
                    **domain_summary,
                },
                expansion_docs=domain_docs,
            )

        doc_tokens: dict[str, set[str]] = {}
        source_nodes: set[str] = set()
        concept_nodes: set[str] = set(query_tokens)
        source_to_docs: dict[str, list[Document]] = {}

        for doc in documents:
            source = str((doc.metadata or {}).get("source") or "unknown").strip().lower()
            source_nodes.add(source)
            source_to_docs.setdefault(source, []).append(doc)
            tokens = self._tokenize(
                " ".join(
                    [
                        doc.text,
                        str((doc.metadata or {}).get("title") or ""),
                        str((doc.metadata or {}).get("url") or ""),
                    ]
                )
            )
            doc_tokens[doc.id] = tokens
            concept_nodes.update(tokens.intersection(query_tokens))

        edges: set[tuple[str, str, str]] = set()
        doc_ids = [doc.id for doc in documents]
        for doc in documents:
            source = str((doc.metadata or {}).get("source") or "unknown").strip().lower()
            edges.add((f"doc:{doc.id}", f"source:{source}", "same_source"))

        for idx, left_id in enumerate(doc_ids):
            left_tokens = doc_tokens.get(left_id, set())
            for right_id in doc_ids[idx + 1 :]:
                right_tokens = doc_tokens.get(right_id, set())
                shared = left_tokens.intersection(right_tokens)
                if not shared:
                    continue
                relation = "shares_concept"
                if shared.intersection(self._DDI_TERMS):
                    relation = "ddi_signal"
                edges.add((f"doc:{left_id}", f"doc:{right_id}", relation))

        expansion_rows: list[dict[str, Any]] = []
        for seed_doc in documents[: min(4, len(documents))]:
            seed_id = seed_doc.id
            seed_source = str((seed_doc.metadata or {}).get("source") or "unknown").strip().lower()
            seed_tokens = doc_tokens.get(seed_id, set())
            neighbor_candidates: list[tuple[int, str]] = []

            for candidate in source_to_docs.get(seed_source, []):
                if candidate.id == seed_id:
                    continue
                overlap = len(seed_tokens.intersection(doc_tokens.get(candidate.id, set())))
                neighbor_candidates.append((max(overlap, 0), candidate.id))

            for candidate in documents:
                if candidate.id == seed_id:
                    continue
                overlap = len(seed_tokens.intersection(doc_tokens.get(candidate.id, set())))
                if overlap <= 0:
                    continue
                neighbor_candidates.append((overlap, candidate.id))

            ranked: list[str] = []
            seen: set[str] = set()
            for overlap, candidate_id in sorted(neighbor_candidates, key=lambda row: row[0], reverse=True):
                if candidate_id in seen:
                    continue
                seen.add(candidate_id)
                if overlap <= 0 and len(ranked) >= safe_max_neighbors:
                    break
                ranked.append(candidate_id)
                if len(ranked) >= safe_max_neighbors:
                    break

            if not ranked:
                continue

            shared_terms = sorted(list(seed_tokens.intersection(query_tokens)))[:6]
            row = {
                "seed_doc": seed_id,
                "source": seed_source,
                "neighbors": ranked,
                "shared_terms": shared_terms,
            }
            expansion_rows.append(row)
            if len(expansion_rows) >= safe_expansion_docs:
                break

        lexical_docs: list[Document] = []
        for idx, row in enumerate(expansion_rows, start=1):
            text = (
                f"GraphRAG expansion from seed {row['seed_doc']} (source={row['source']}). "
                f"Nearest evidence neighbors: {', '.join(row['neighbors'])}. "
                f"Shared query concepts: {', '.join(row['shared_terms']) if row['shared_terms'] else 'n/a'}."
            )
            lexical_docs.append(
                Document(
                    id=f"graphrag-expansion-{idx}",
                    text=text,
                    metadata={
                        "source": "graphrag",
                        "url": "",
                        "score": 0.0,
                        "weight": 1.0,
                        "graph_seed_doc": row["seed_doc"],
                    },
                )
            )

        domain_summary, domain_docs = self._build_domain_expansion(
            query=query,
            documents=documents,
            budget=safe_expansion_docs,
        )

        merged_docs: list[Document] = []
        for item in [*domain_docs, *lexical_docs]:
            if any(existing.id == item.id for existing in merged_docs):
                continue
            merged_docs.append(item)
            if len(merged_docs) >= safe_expansion_docs:
                break

        summary = {
            "enabled": True,
            "node_count": len(documents) + len(source_nodes) + len(concept_nodes),
            "edge_count": len(edges),
            "concept_count": len(concept_nodes),
            "expansion_count": len(merged_docs),
            "max_neighbors": safe_max_neighbors,
            "expansion_doc_budget": safe_expansion_docs,
            "expansion_doc_ids": [doc.id for doc in merged_docs],
            "expansion_rows": expansion_rows,
            **domain_summary,
        }
        return GraphRagResult(summary=summary, expansion_docs=merged_docs)
