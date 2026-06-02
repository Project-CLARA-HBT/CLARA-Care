from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clara_ml.config import settings
from clara_ml.rag.retriever import Document


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

    def __init__(self) -> None:
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

    def _load_domain_graph(self) -> None:
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
