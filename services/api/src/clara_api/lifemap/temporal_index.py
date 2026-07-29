"""Profile-partitioned, revision-aware temporal retrieval index."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime


class RetrievalBoundaryError(ValueError):
    pass


@dataclass(frozen=True)
class RetrievalDocument:
    document_id: str
    profile_partition: str
    revision_id: str
    source_type: str
    effective_start: datetime
    effective_end: datetime | None
    recorded_at: datetime
    episode_ids: frozenset[str]
    truth_state: str
    data_class: str
    language: str
    terms: frozenset[str]
    embedding: tuple[float, ...] | None
    graph_entities: frozenset[str]
    is_active: bool = True


@dataclass(frozen=True)
class RetrievalHit:
    document: RetrievalDocument
    lexical_score: float
    dense_score: float
    time_score: float
    graph_score: float
    total_score: float


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(v * v for v in left)) * math.sqrt(
        sum(v * v for v in right)
    )
    if not denominator:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator


class TemporalRetrievalIndex:
    """Each profile owns a separate document dictionary, not metadata alone."""

    def __init__(self) -> None:
        self._partitions: dict[str, dict[str, RetrievalDocument]] = {}

    def upsert(self, document: RetrievalDocument) -> None:
        if not document.profile_partition or not document.document_id:
            raise RetrievalBoundaryError("partition_and_document_required")
        self._partitions.setdefault(document.profile_partition, {})[
            document.document_id
        ] = document

    def search(
        self,
        *,
        profile_partition: str,
        allowed_data_classes: frozenset[str],
        query_terms: frozenset[str],
        query_embedding: tuple[float, ...] | None = None,
        episode_id: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        graph_entities: frozenset[str] = frozenset(),
        reranker: Callable[[tuple[RetrievalHit, ...]], tuple[str, ...]] | None = None,
        limit: int = 20,
    ) -> tuple[RetrievalHit, ...]:
        partition = self._partitions.get(profile_partition, {})
        candidates = [
            document
            for document in partition.values()
            if document.is_active
            and document.data_class in allowed_data_classes
            and (episode_id is None or episode_id in document.episode_ids)
            and (start_at is None or document.effective_start >= start_at)
            and (end_at is None or document.effective_start <= end_at)
        ]
        hits: list[RetrievalHit] = []
        for document in candidates:
            lexical = (
                len(query_terms & document.terms) / len(query_terms)
                if query_terms
                else 0.0
            )
            dense = (
                _cosine(query_embedding, document.embedding)
                if query_embedding is not None and document.embedding is not None
                else 0.0
            )
            time = 1.0 / (
                1.0
                + max(
                    0.0,
                    (document.recorded_at - document.effective_start).total_seconds()
                    / 86_400,
                )
            )
            graph = (
                len(graph_entities & document.graph_entities) / len(graph_entities)
                if graph_entities
                else 0.0
            )
            hits.append(
                RetrievalHit(
                    document=document,
                    lexical_score=lexical,
                    dense_score=dense,
                    time_score=time,
                    graph_score=graph,
                    total_score=0.45 * lexical + 0.30 * dense + 0.15 * time + 0.10 * graph,
                )
            )
        hits.sort(
            key=lambda hit: (
                hit.total_score,
                hit.document.effective_start,
                hit.document.document_id,
            ),
            reverse=True,
        )
        if reranker is not None:
            candidate_ids = {hit.document.document_id for hit in hits}
            ordered_ids = reranker(tuple(hits))
            if len(set(ordered_ids)) != len(ordered_ids) or not set(ordered_ids) <= candidate_ids:
                raise RetrievalBoundaryError("reranker_escaped_candidate_set")
            by_id = {hit.document.document_id: hit for hit in hits}
            hits = [by_id[document_id] for document_id in ordered_ids]
        return tuple(hits[: max(1, min(limit, 100))])
