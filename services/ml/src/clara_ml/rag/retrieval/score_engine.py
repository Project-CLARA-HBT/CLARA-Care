from __future__ import annotations

import re
from typing import Any, Sequence

from clara_ml.rag.embedder import HttpEmbeddingClient

from .domain import Document, SOURCE_SCORE_BIAS
from .text_utils import (
    analyze_query_profile,
    normalize_tags,
    query_terms,
    safe_weight,
    tag_relevance_factor,
    trust_tier_factor,
)


class DocumentScorer:
    def __init__(self, embedder: HttpEmbeddingClient | None = None) -> None:
        self.embedder = embedder or HttpEmbeddingClient()

    @staticmethod
    def _normalize_document(doc: Document, *, default_source: str = "internal") -> Document:
        metadata = dict(doc.metadata or {})
        metadata.setdefault("source", str(default_source).strip().lower() or "internal")
        metadata.setdefault("url", "")
        metadata.setdefault("score", 0.0)
        metadata["weight"] = safe_weight(metadata.get("weight", 1.0), default=1.0)
        metadata["tags"] = normalize_tags(metadata.get("tags"))
        metadata.setdefault("trust_tier", "tier_3")
        metadata.setdefault("file_type", "")
        return Document(id=doc.id, text=doc.text, metadata=metadata)

    def score_documents(
        self,
        query: str,
        documents: Sequence[Document],
        top_k: int,
        *,
        source_policies: dict[str, dict[str, float | bool]] | None = None,
        score_trace: list[dict[str, Any]] | None = None,
    ) -> list[Document]:
        if top_k <= 0:
            return []

        if score_trace is not None:
            score_trace.clear()

        normalized_docs = [self._normalize_document(doc) for doc in documents]
        if not normalized_docs:
            return []

        vectors = self.embedder.embed_batch([query] + [doc.text for doc in normalized_docs])
        if not vectors:
            return []

        query_vector = vectors[0]
        doc_vectors = vectors[1:]

        source_policies = source_policies or {}
        query_profile = analyze_query_profile(query)
        expanded_query = " ".join(query_terms(query))
        query_tokens = self._tokenize(expanded_query or query)
        scored: list[tuple[float, Document]] = []
        trace_rows: list[dict[str, Any]] = []

        for doc, doc_vector in zip(normalized_docs, doc_vectors):
            base_score = sum(a * b for a, b in zip(query_vector, doc_vector))
            lexical_overlap = self._lexical_overlap(query_tokens, doc.text)
            doc_tokens = self._tokenize(doc.text)
            primary_drug = str(query_profile.get("primary_drug") or "").strip().lower()
            has_primary_drug = bool(primary_drug) and primary_drug in doc_tokens
            has_interaction_signal = bool(
                doc_tokens.intersection(
                    {"interaction", "ddi", "bleeding", "inr", "contraindication", "adverse"}
                )
            )
            is_ddi_query = bool(query_profile.get("is_ddi_query"))

            if is_ddi_query and not has_primary_drug:
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": str(doc.metadata.get("source") or "unknown"),
                        "excluded": True,
                        "reason": "ddi_missing_primary_drug",
                        "lexical_overlap": lexical_overlap,
                    }
                )
                continue
            if is_ddi_query and lexical_overlap < 0.06 and not has_interaction_signal:
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": str(doc.metadata.get("source") or "unknown"),
                        "excluded": True,
                        "reason": "ddi_low_lexical_overlap",
                        "lexical_overlap": lexical_overlap,
                    }
                )
                continue
            source_key = str(doc.metadata.get("source") or "").strip().lower()
            policy = source_policies.get(source_key, {"enabled": True, "weight": 1.0})
            if not bool(policy.get("enabled", True)):
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": source_key or "unknown",
                        "excluded": True,
                        "reason": "source_disabled_by_policy",
                    }
                )
                continue

            policy_weight = safe_weight(policy.get("weight", 1.0), default=1.0)
            doc_weight = safe_weight(doc.metadata.get("weight", 1.0), default=1.0)
            source_bias = max(0.5, min(1.6, float(SOURCE_SCORE_BIAS.get(source_key, 1.0))))
            trust_factor = trust_tier_factor(doc.metadata.get("trust_tier"))
            tag_factor = tag_relevance_factor(query, doc.metadata.get("tags"))
            file_type = str(doc.metadata.get("file_type") or "").strip().lower()
            pdf_factor = 1.05 if file_type == "pdf" else 1.0

            semantic_component = max(float(base_score), 0.0)
            blend_score = (0.65 * semantic_component) + (0.35 * lexical_overlap)

            score = (
                blend_score
                * max(policy_weight, 0.05)
                * max(doc_weight, 0.05)
                * source_bias
                * trust_factor
                * tag_factor
                * pdf_factor
            )

            score_breakdown = {
                "base_score": float(base_score),
                "semantic_component": float(semantic_component),
                "lexical_overlap": float(lexical_overlap),
                "policy_weight": float(policy_weight),
                "doc_weight": float(doc_weight),
                "source_bias": float(source_bias),
                "trust_factor": float(trust_factor),
                "tag_factor": float(tag_factor),
                "pdf_factor": float(pdf_factor),
                "final_score": float(score),
                "ddi_query": is_ddi_query,
                "has_primary_drug": has_primary_drug,
                "has_interaction_signal": has_interaction_signal,
            }
            doc.metadata["weight"] = doc_weight
            doc.metadata["policy_weight"] = policy_weight
            doc.metadata["source_bias"] = source_bias
            doc.metadata["trust_factor"] = trust_factor
            doc.metadata["tag_factor"] = tag_factor
            doc.metadata["pdf_factor"] = pdf_factor
            doc.metadata["score"] = float(score)
            doc.metadata["score_breakdown"] = score_breakdown
            trace_rows.append(
                {
                    "doc_id": doc.id,
                    "source": source_key or "unknown",
                    "excluded": False,
                    **score_breakdown,
                }
            )
            scored.append((score, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected_docs = self._select_with_source_diversity(scored, top_k=top_k)

        if score_trace is not None:
            selected_ids = {doc.id for doc in selected_docs}
            for row in trace_rows:
                row["selected"] = row.get("doc_id") in selected_ids
            score_trace.extend(trace_rows)

        return selected_docs

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        lowered = text.lower()
        tokens = re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", lowered)
        return {token for token in tokens if token}

    @staticmethod
    def _select_with_source_diversity(
        scored: list[tuple[float, Document]],
        *,
        top_k: int,
    ) -> list[Document]:
        if top_k <= 0:
            return []
        if not scored:
            return []

        # Keep score order but prevent one source from monopolizing all slots.
        max_per_source = max(2, (top_k + 1) // 2)
        selected: list[Document] = []
        deferred: list[Document] = []
        source_counts: dict[str, int] = {}

        for _, doc in scored:
            source = str((doc.metadata or {}).get("source") or "unknown").strip().lower()
            count = source_counts.get(source, 0)
            if count < max_per_source:
                selected.append(doc)
                source_counts[source] = count + 1
            else:
                deferred.append(doc)
            if len(selected) >= top_k:
                return selected[:top_k]

        if len(selected) < top_k:
            selected.extend(deferred[: max(0, top_k - len(selected))])
        return selected[:top_k]

    @classmethod
    def _lexical_overlap(cls, query_tokens: set[str], text: str) -> float:
        if not query_tokens:
            return 0.0
        doc_tokens = cls._tokenize(text)
        if not doc_tokens:
            return 0.0
        overlap = len(query_tokens.intersection(doc_tokens))
        return float(overlap) / float(max(len(query_tokens), 1))
