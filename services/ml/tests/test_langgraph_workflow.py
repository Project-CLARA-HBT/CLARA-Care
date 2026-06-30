"""Tests for the LangGraph PoC workflow wired to the RAG pipeline.

Feature: rag-knowledge-pipeline. The PoC graph (``query -> retrieve ->
generate``) is off the production request path; these tests assert it:

- delegates to the injected pipeline (no more ``doc::{query}`` placeholders),
- runs retrieval in offline retrieval-only mode by default (generation off),
- carries the pipeline's retrieved ids/context and grounded answer through the
  graph state, and
- returns ``None`` gracefully when ``langgraph`` is not installed.

A fake pipeline is injected so the test is deterministic and network-free; the
real :class:`RagPipelineP1` is never constructed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from clara_ml.agents import langgraph_workflow as lw


@dataclass
class _FakeResult:
    query: str
    retrieved_ids: list[str] = field(default_factory=list)
    retrieved_context: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""


class _FakePipeline:
    """Records ``run`` kwargs and returns a canned retrieval-only result."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, query: str, **kwargs: Any) -> _FakeResult:
        self.calls.append({"query": query, **kwargs})
        return _FakeResult(
            query=query,
            retrieved_ids=["doc-1", "doc-2"],
            retrieved_context=[{"id": "doc-1", "text": "ctx"}],
            answer="Câu trả lời grounded từ pipeline.",
        )


def _build(pipeline: _FakePipeline, **kwargs: Any):
    workflow = lw.build_langgraph_workflow(
        pipeline_factory=lambda: pipeline,
        **kwargs,
    )
    if workflow is None:
        pytest.skip("langgraph is not installed in this environment")
    return workflow


def test_retrieve_node_runs_pipeline_in_offline_retrieval_only_mode() -> None:
    pipeline = _FakePipeline()
    node = lw._make_retrieve_node(lambda: pipeline)

    out = node({"query": "tương tác thuốc warfarin"})

    # Retrieval-only and fully offline: generation + every external connector off.
    assert pipeline.calls[0]["generation_enabled"] is False
    assert pipeline.calls[0]["deepseek_fallback_enabled"] is False
    assert pipeline.calls[0]["scientific_retrieval_enabled"] is False
    assert pipeline.calls[0]["web_retrieval_enabled"] is False
    assert pipeline.calls[0]["file_retrieval_enabled"] is False

    assert out["retrieved"] == ["doc-1", "doc-2"]
    assert out["retrieved_context"] == [{"id": "doc-1", "text": "ctx"}]
    assert out["answer"] == "Câu trả lời grounded từ pipeline."


def test_retrieve_node_empty_query_short_circuits() -> None:
    pipeline = _FakePipeline()
    node = lw._make_retrieve_node(lambda: pipeline)

    out = node({"query": "   "})

    assert pipeline.calls == []  # no pipeline run for an empty query
    assert out == {"retrieved": [], "retrieved_context": [], "answer": ""}


def test_generate_node_default_returns_retrieval_grounded_answer() -> None:
    pipeline = _FakePipeline()
    node = lw._make_generate_node(lambda: pipeline, generation_enabled=False)

    out = node({"query": "x", "answer": "grounded"})

    # Default (generation off): deterministic pass-through, no extra pipeline run.
    assert out == {"answer": "grounded"}
    assert pipeline.calls == []


def test_generate_node_with_generation_enabled_runs_pipeline() -> None:
    pipeline = _FakePipeline()
    node = lw._make_generate_node(lambda: pipeline, generation_enabled=True)

    out = node({"query": "tương tác thuốc", "answer": "ignored-grounded"})

    assert pipeline.calls[0]["query"] == "tương tác thuốc"
    assert pipeline.calls[0]["generation_enabled"] is True
    assert out["answer"] == "Câu trả lời grounded từ pipeline."


def test_compiled_workflow_invokes_real_nodes_end_to_end() -> None:
    pipeline = _FakePipeline()
    workflow = _build(pipeline)

    final = workflow.invoke({"query": "warfarin và aspirin"})

    assert final["retrieved"] == ["doc-1", "doc-2"]
    assert final["answer"] == "Câu trả lời grounded từ pipeline."
    # Default graph is offline retrieval-only: exactly one pipeline run.
    assert len(pipeline.calls) == 1
    assert pipeline.calls[0]["generation_enabled"] is False


def test_build_returns_none_when_langgraph_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """If importing langgraph fails, the builder returns None (baseline mode)."""

    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any):
        if name == "langgraph.graph" or name.startswith("langgraph"):
            raise ImportError("simulated missing langgraph")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    assert lw.build_langgraph_workflow(pipeline_factory=lambda: _FakePipeline()) is None
