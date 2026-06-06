"""Document-level recall grounding via the stable ``doc_ref`` reference.

The persistent retriever returns one :class:`Document` per *chunk* (``id`` =
chunk id), but eval recall must be scored at the *document* level against the
golden ``relevant_doc_ids``. To bridge that, the retriever now surfaces a stable
``metadata["doc_ref"] = "{source}:{external_id}"`` (the provider's permanent
document identity) and the harness's id extractor prefers it.

These tests pin both halves:

* ``HybridRetriever._ranked_to_document`` emits ``doc_ref`` when the chunk meta
  carries ``source`` + ``external_id`` (and omits it otherwise);
* ``harness._doc_id`` prefers ``doc_ref`` over the chunk ``id`` and falls back
  to ``id`` when absent.
"""

from __future__ import annotations

# Import the store package first to avoid the known partially-initialized-module
# import cycle (see the import note in embedder.py).
import clara_ml.rag.store  # noqa: F401
from clara_ml.rag.eval.harness import _doc_id
from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.store.hybrid_retriever import HybridRetriever
from clara_ml.rag.store.sparse_index import RankedChunk


def _retriever() -> HybridRetriever:
    # No session_factory / dense_search needed: we only exercise the pure
    # _ranked_to_document mapping, so collaborators can be trivial stand-ins.
    return HybridRetriever(
        embedder=object(),
        sparse_index=object(),
        reranker=object(),
    )


def test_ranked_to_document_emits_doc_ref_from_source_and_external_id() -> None:
    chunk = RankedChunk(
        chunk_id=42,
        score=0.9,
        retriever="dense",
        document_id=7,
        text="warfarin label text",
        meta={"source": "dailymed", "external_id": "abc-123-setid"},
    )
    doc = _retriever()._ranked_to_document(chunk)

    assert doc.id == "42"  # provenance contract unchanged: id is still chunk id
    assert doc.metadata["doc_ref"] == "dailymed:abc-123-setid"


def test_ranked_to_document_omits_doc_ref_when_external_id_missing() -> None:
    chunk = RankedChunk(
        chunk_id=43,
        score=0.5,
        retriever="dense",
        document_id=8,
        text="legacy chunk without external id",
        meta={"source": "dailymed"},  # no external_id
    )
    doc = _retriever()._ranked_to_document(chunk)

    assert "doc_ref" not in doc.metadata


def test_doc_id_prefers_doc_ref_over_chunk_id() -> None:
    doc = Document(
        id="42",
        text="t",
        metadata={"doc_ref": "dailymed:abc-123-setid", "document_id": 7},
    )
    assert _doc_id(doc) == "dailymed:abc-123-setid"


def test_doc_id_falls_back_to_id_without_doc_ref() -> None:
    doc = Document(id="99", text="t", metadata={"document_id": 7})
    assert _doc_id(doc) == "99"
