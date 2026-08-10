"""Regression: flag-off reproduces the legacy in-memory retrieval path.

Task 5.12 — locks the backward-compatibility contract of the P2 cutover so that
turning ``RAG_PERSISTENT_RETRIEVAL_ENABLED`` off keeps the pre-change behaviour
byte-for-byte and never mixes the two embedding regimes.

Validates:
    * Requirement 3.1 — WHERE ``RAG_PERSISTENT_RETRIEVAL_ENABLED`` is false, THE
      Knowledge_Pipeline SHALL use the legacy in-memory retriever (live fetch)
      and produce behaviour equivalent to the pre-change system.
    * Requirement 3.3 — WHEN handling a single query, THE Knowledge_Pipeline
      SHALL select exactly one retrieval path and SHALL NOT combine
      embed-every-document and embed-query-only behaviour within that query.

These tests complement (and do not modify) the existing legacy suite in
``test_rag_pipeline.py``. They assert three things the legacy suite does not:

1. With the flag off the resolved retrieval path is exactly ``legacy_in_memory``.
2. The persistent ``HybridRetriever`` is never *built* (no engine resolution,
   no construction) and never *consulted* (even when one is injected) — so the
   embed-query-only path is provably not taken.
3. Exactly one embedding-semantics path runs per query: the legacy embed-all
   retriever is consulted while the persistent embed-query path is not.
"""

from __future__ import annotations

import contextlib
from typing import Any

import clara_ml.rag.store.hybrid_retriever as hybrid_retriever_mod
from clara_ml.config import settings
from clara_ml.rag.pipeline import RagPipelineP0
from clara_ml.rag.retriever import Document
from clara_ml.rag.store import health

# A query that resolves entirely against the static seed corpus (no live
# connectors), mirroring the offline determinism the legacy suite relies on.
_LEGACY_QUERY = "canh bao tuong tac warfarin va nsaid nguy co xuat huyet"


@contextlib.contextmanager
def _persistent_flags_off(monkeypatch):
    """Force the persistent flags off and clear any resolved self-check state.

    Both persistent flags are pinned off, and ``get_resolved_persistent_flags``
    is made to report "not resolved" so the pipeline reads the raw (off) setting
    deterministically regardless of whether a prior test ran the startup
    self-check (the resolved-flags holder is module-level global state).
    """

    monkeypatch.setattr(settings, "rag_persistent_retrieval_enabled", False, raising=False)
    monkeypatch.setattr(settings, "rag_persistent_store_enabled", False, raising=False)
    monkeypatch.setattr(health, "get_resolved_persistent_flags", lambda: None)
    yield


class _TrackingHybridRetriever:
    """Persistent retriever stub that records whether it was ever consulted.

    Its ``retrieve`` is the embed-query-only path. If the flag-off pipeline ever
    calls it, ``retrieve_calls`` becomes non-empty and the regression fails. The
    sentinel document id would also leak into the result, giving a second signal
    that the persistent path was (wrongly) mixed in.
    """

    _SENTINEL_ID = "persistent-should-not-appear"

    def __init__(self) -> None:
        self.retrieve_calls: list[tuple[Any, ...]] = []

    def retrieve(self, query: str, *args: Any, **kwargs: Any) -> list[Document]:
        self.retrieve_calls.append((query, args, kwargs))
        return [
            Document(
                id=self._SENTINEL_ID,
                text="persistent path output that must never appear when flag is off",
                metadata={"source": "persistent", "trust_tier": 1},
            )
        ]


def _retrieval_path(result: Any) -> str:
    trace = result.context_debug.get("retrieval_trace", {})
    assert isinstance(trace, dict)
    return trace.get("retrieval_path")


def test_persistent_retrieval_active_is_false_when_flag_off(monkeypatch):
    """The routing predicate resolves to the legacy path with the flag off."""

    with _persistent_flags_off(monkeypatch):
        pipe = RagPipelineP0(deepseek_api_key="")
        assert pipe._persistent_retrieval_active() is False


def test_flag_off_retrieval_path_is_legacy_in_memory(monkeypatch):
    """Req 3.1: the resolved retrieval path is exactly ``legacy_in_memory``."""

    with _persistent_flags_off(monkeypatch):
        pipe = RagPipelineP0(deepseek_api_key="")
        result = pipe.run(_LEGACY_QUERY, deepseek_fallback_enabled=True)

    trace = result.context_debug.get("retrieval_trace", {})
    assert trace.get("retrieval_path") == "legacy_in_memory"
    # No persistent path and no semantic-cache short-circuit were taken.
    assert trace.get("semantic_cache_hit") is False
    # Behaviour-equivalent to the pre-change system: seed corpus + local synth.
    assert len(result.retrieved_ids) > 0
    assert result.model_used == "local-synth-v1"


def test_flag_off_never_builds_persistent_retriever(monkeypatch):
    """Req 3.1/3.3: no persistent retriever is constructed when the flag is off.

    Asserts the build seam is never entered: ``_get_hybrid_retriever`` and
    ``_persistent_retrieve`` are never called, and the ``HybridRetriever``
    construction entrypoint (``from_engine``) is never reached. (The lower-level
    ``resolve_default_engine`` helper is deliberately *not* asserted on here — it
    is shared with the GraphRAG DB-edge loader and may run independently of the
    retrieval flag; ``from_engine`` is the precise persistent-build signal.)
    """

    probes = {"from_engine": 0, "hybrid_calls": 0, "persistent_calls": 0}

    def _record_from_engine(*_args: Any, **_kwargs: Any):
        probes["from_engine"] += 1
        raise AssertionError("HybridRetriever.from_engine must not run with flag off")

    monkeypatch.setattr(hybrid_retriever_mod.HybridRetriever, "from_engine", _record_from_engine)

    with _persistent_flags_off(monkeypatch):
        pipe = RagPipelineP0(deepseek_api_key="")

        orig_get = pipe._get_hybrid_retriever
        orig_persistent = pipe._persistent_retrieve

        def _get_wrapper(*args: Any, **kwargs: Any):
            probes["hybrid_calls"] += 1
            return orig_get(*args, **kwargs)

        def _persistent_wrapper(*args: Any, **kwargs: Any):
            probes["persistent_calls"] += 1
            return orig_persistent(*args, **kwargs)

        monkeypatch.setattr(pipe, "_get_hybrid_retriever", _get_wrapper)
        monkeypatch.setattr(pipe, "_persistent_retrieve", _persistent_wrapper)

        result = pipe.run(_LEGACY_QUERY, deepseek_fallback_enabled=True)

    assert probes["persistent_calls"] == 0
    assert probes["hybrid_calls"] == 0
    assert probes["from_engine"] == 0
    assert _retrieval_path(result) == "legacy_in_memory"


def test_flag_off_does_not_consult_injected_persistent_retriever(monkeypatch):
    """Req 3.3: an injected persistent retriever is never consulted (no mixing).

    Even when a fully-built persistent retriever exists on the pipeline, the
    flag-off path must not touch it, and its output must never leak into the
    result alongside legacy documents.
    """

    tracker = _TrackingHybridRetriever()

    with _persistent_flags_off(monkeypatch):
        pipe = RagPipelineP0(deepseek_api_key="", hybrid_retriever=tracker)
        result = pipe.run(_LEGACY_QUERY, deepseek_fallback_enabled=True)

    assert tracker.retrieve_calls == []
    assert _retrieval_path(result) == "legacy_in_memory"
    assert tracker._SENTINEL_ID not in result.retrieved_ids
    assert all(
        (doc or {}).get("source") != "persistent"
        for doc in result.retrieved_context
        if isinstance(doc, dict)
    )


def test_flag_off_runs_single_legacy_embed_all_path(monkeypatch):
    """Req 3.3: exactly one embedding regime runs — legacy embed-all, not both.

    The legacy in-memory retriever (``retrieve_internal``, the embed-every-doc
    regime) is consulted, while the injected persistent retriever (the
    embed-query-only regime) is not — proving the query never mixes the two.
    """

    tracker = _TrackingHybridRetriever()

    with _persistent_flags_off(monkeypatch):
        pipe = RagPipelineP0(deepseek_api_key="", hybrid_retriever=tracker)

        calls = {"internal": 0}
        orig_internal = pipe.retriever.retrieve_internal

        def _internal_wrapper(*args: Any, **kwargs: Any):
            calls["internal"] += 1
            return orig_internal(*args, **kwargs)

        monkeypatch.setattr(pipe.retriever, "retrieve_internal", _internal_wrapper)

        result = pipe.run(_LEGACY_QUERY, deepseek_fallback_enabled=True)

    # Legacy embed-all path consulted exactly once for primary retrieval.
    assert calls["internal"] == 1
    # Persistent embed-query path not consulted at all.
    assert tracker.retrieve_calls == []
    assert _retrieval_path(result) == "legacy_in_memory"


def test_flag_off_is_deterministic_and_reproduces_legacy_results(monkeypatch):
    """Req 3.1: repeated flag-off runs reproduce the same legacy retrieval.

    Backward-compatibility means the flag-off path is stable: the resolved path,
    retrieved ids, and synthesis model are identical across runs of the same
    query, with no persistent semantics leaking in.
    """

    with _persistent_flags_off(monkeypatch):
        pipe = RagPipelineP0(deepseek_api_key="")
        first = pipe.run(_LEGACY_QUERY, deepseek_fallback_enabled=True)
        second = pipe.run(_LEGACY_QUERY, deepseek_fallback_enabled=True)

    assert _retrieval_path(first) == "legacy_in_memory"
    assert _retrieval_path(second) == "legacy_in_memory"
    assert first.retrieved_ids == second.retrieved_ids
    assert first.model_used == second.model_used == "local-synth-v1"
