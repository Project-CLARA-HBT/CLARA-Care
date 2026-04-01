from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from clara_ml.rag.retriever import Document


@dataclass
class GraphRagResult:
    summary: dict[str, Any]
    expansion_docs: list[Document]


class GraphRagSidecar:
    """Lightweight in-memory graph expansion for retrieved evidence."""

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

    @classmethod
    def _tokenize(cls, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{3,}", str(text or "").lower())
            if token and token not in cls._CONCEPT_STOPWORDS
        }

    def expand(
        self,
        *,
        query: str,
        documents: list[Document],
        max_neighbors: int = 8,
        expansion_docs: int = 4,
    ) -> GraphRagResult:
        if not documents:
            return GraphRagResult(
                summary={
                    "enabled": True,
                    "node_count": 0,
                    "edge_count": 0,
                    "concept_count": 0,
                    "expansion_count": 0,
                    "max_neighbors": max_neighbors,
                },
                expansion_docs=[],
            )

        safe_max_neighbors = max(1, int(max_neighbors))
        safe_expansion_docs = max(1, int(expansion_docs))
        query_tokens = self._tokenize(query)

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

        sidecar_docs: list[Document] = []
        for idx, row in enumerate(expansion_rows, start=1):
            text = (
                f"GraphRAG expansion from seed {row['seed_doc']} (source={row['source']}). "
                f"Nearest evidence neighbors: {', '.join(row['neighbors'])}. "
                f"Shared query concepts: {', '.join(row['shared_terms']) if row['shared_terms'] else 'n/a'}."
            )
            sidecar_docs.append(
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

        summary = {
            "enabled": True,
            "node_count": len(documents) + len(source_nodes) + len(concept_nodes),
            "edge_count": len(edges),
            "concept_count": len(concept_nodes),
            "expansion_count": len(sidecar_docs),
            "max_neighbors": safe_max_neighbors,
            "expansion_doc_budget": safe_expansion_docs,
            "expansion_doc_ids": [doc.id for doc in sidecar_docs],
            "expansion_rows": expansion_rows,
        }
        return GraphRagResult(summary=summary, expansion_docs=sidecar_docs)
