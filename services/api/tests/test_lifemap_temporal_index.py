from datetime import UTC, datetime

import pytest

from clara_api.lifemap.temporal_index import (
    RetrievalBoundaryError,
    RetrievalDocument,
    TemporalRetrievalIndex,
)


def _doc(profile: str, doc: str, *, data_class: str = "lifemap"):
    return RetrievalDocument(
        document_id=doc,
        profile_partition=profile,
        revision_id=f"revision-{doc}",
        source_type="event",
        effective_start=datetime(2026, 7, 29, tzinfo=UTC),
        effective_end=None,
        recorded_at=datetime(2026, 7, 29, 1, tzinfo=UTC),
        episode_ids=frozenset({"episode-1"}),
        truth_state="confirmed",
        data_class=data_class,
        language="vi",
        terms=frozenset({"dau"}),
        embedding=(1.0, 0.0),
        graph_entities=frozenset({"headache"}),
    )


def test_profile_partition_and_data_class_filter_before_scoring() -> None:
    index = TemporalRetrievalIndex()
    index.upsert(_doc("owner", "visible"))
    index.upsert(_doc("other", "cross-profile"))
    index.upsert(_doc("owner", "withheld", data_class="medications"))
    hits = index.search(
        profile_partition="owner",
        allowed_data_classes=frozenset({"lifemap"}),
        query_terms=frozenset({"dau"}),
        query_embedding=(1.0, 0.0),
        graph_entities=frozenset({"headache"}),
    )
    assert [hit.document.document_id for hit in hits] == ["visible"]


def test_reranker_cannot_introduce_or_duplicate_document_ids() -> None:
    index = TemporalRetrievalIndex()
    index.upsert(_doc("owner", "visible"))
    with pytest.raises(RetrievalBoundaryError, match="reranker_escaped_candidate_set"):
        index.search(
            profile_partition="owner",
            allowed_data_classes=frozenset({"lifemap"}),
            query_terms=frozenset(),
            reranker=lambda _hits: ("other-profile",),
        )


def test_episode_and_time_filters_are_hard_boundaries() -> None:
    index = TemporalRetrievalIndex()
    index.upsert(_doc("owner", "visible"))
    assert (
        index.search(
            profile_partition="owner",
            allowed_data_classes=frozenset({"lifemap"}),
            query_terms=frozenset(),
            episode_id="not-authorized",
        )
        == ()
    )
