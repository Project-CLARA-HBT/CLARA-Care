"""LangGraph PoC workflow wired to the real RAG pipeline.

This module builds a small ``query -> retrieve -> generate`` LangGraph workflow.
It is a **proof-of-concept seam**: nothing on the production request path
(``/v1/chat/routed``, ``/v1/research/*``) calls :func:`build_langgraph_workflow`
— the production flow goes through :class:`clara_ml.rag.pipeline.RagPipelineP1`
directly. Keeping the PoC off the hot path means wiring its nodes to the real
pipeline cannot change production behavior.

Design choices that keep this safe and import-light:

- The graph nodes delegate to the real :class:`RagPipelineP1` instead of the
  former ``doc::{query}`` placeholders, so the PoC exercises the same retrieval
  and synthesis the production pipeline uses.
- ``RagPipelineP1`` is imported lazily inside the pipeline factory, so importing
  this module performs no side effects and opens no clients (the agent registry
  imports it during discovery, which must stay cheap and free of agents).
- The ``retrieve`` node runs the pipeline in **retrieval-only** mode with all
  external connectors off, so the PoC is deterministic and network-free by
  default; the produced grounded answer is the pipeline's own deterministic
  local synthesis (which always carries safety wording).
- The ``generate`` node only issues a live LLM generation when
  ``generation_enabled=True`` is explicitly requested; otherwise it returns the
  deterministic retrieval-grounded answer from the retrieve node.

If ``langgraph`` is not installed, :func:`build_langgraph_workflow` returns
``None`` so the service still starts in a baseline-compatible mode.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict

__all__ = ["GraphState", "PipelineFactory", "build_langgraph_workflow"]


class GraphState(TypedDict, total=False):
    query: str
    retrieved: list[str]
    retrieved_context: list[dict[str, Any]]
    answer: str


#: A zero-arg factory returning an object with a ``run`` method compatible with
#: :meth:`clara_ml.rag.pipeline.RagPipelineP1.run`. Injectable so tests can
#: supply a fake pipeline without performing real retrieval.
PipelineFactory = Callable[[], Any]


def _default_pipeline_factory() -> Any:
    """Lazily build the real RAG pipeline (kept off module import).

    Importing :class:`RagPipelineP1` here rather than at module top keeps
    ``import clara_ml.agents.langgraph_workflow`` cheap and side-effect free for
    the agent-registry discovery path.
    """

    from clara_ml.rag.pipeline import RagPipelineP1

    return RagPipelineP1()


def _make_retrieve_node(pipeline_factory: PipelineFactory) -> Callable[[GraphState], GraphState]:
    """Build the retrieve node: real retrieval-only pipeline run.

    Runs the pipeline with generation disabled and every external connector off
    so the PoC stays deterministic and network-free. The pipeline's deterministic
    retrieval-grounded answer is carried forward for the generate node to use as
    its offline default.
    """

    def _retrieve(state: GraphState) -> GraphState:
        query = str(state.get("query", "")).strip()
        if not query:
            return {"retrieved": [], "retrieved_context": [], "answer": ""}

        pipeline = pipeline_factory()
        result = pipeline.run(
            query,
            generation_enabled=False,
            deepseek_fallback_enabled=False,
            scientific_retrieval_enabled=False,
            web_retrieval_enabled=False,
            file_retrieval_enabled=False,
        )
        return {
            "retrieved": [str(item) for item in getattr(result, "retrieved_ids", []) or []],
            "retrieved_context": list(getattr(result, "retrieved_context", []) or []),
            "answer": str(getattr(result, "answer", "") or ""),
        }

    return _retrieve


def _make_generate_node(
    pipeline_factory: PipelineFactory,
    *,
    generation_enabled: bool,
) -> Callable[[GraphState], GraphState]:
    """Build the generate node.

    Default (``generation_enabled=False``): return the deterministic,
    retrieval-grounded answer produced in the retrieve node — fully offline. When
    ``generation_enabled=True`` is explicitly requested, run the real pipeline
    generation path for the query.
    """

    def _generate(state: GraphState) -> GraphState:
        if not generation_enabled:
            return {"answer": str(state.get("answer", "") or "")}

        query = str(state.get("query", "")).strip()
        if not query:
            return {"answer": str(state.get("answer", "") or "")}

        pipeline = pipeline_factory()
        result = pipeline.run(query, generation_enabled=True)
        return {"answer": str(getattr(result, "answer", "") or "")}

    return _generate


def build_langgraph_workflow(
    *,
    pipeline_factory: PipelineFactory | None = None,
    generation_enabled: bool = False,
) -> Any:
    """Build the ``query -> retrieve -> generate`` PoC graph wired to RagPipelineP1.

    Args:
        pipeline_factory: Optional zero-arg factory for the pipeline (injectable
            for tests). Defaults to lazily constructing :class:`RagPipelineP1`.
        generation_enabled: When ``False`` (default), the graph is deterministic
            and network-free (retrieval-only grounded answer). When ``True``, the
            generate node runs the real LLM generation path.

    Returns:
        A compiled LangGraph workflow, or ``None`` when ``langgraph`` is not
        installed (so the service still starts in baseline mode).
    """

    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    factory = pipeline_factory or _default_pipeline_factory

    graph = StateGraph(GraphState)
    graph.add_node("retrieve", _make_retrieve_node(factory))
    graph.add_node("generate", _make_generate_node(factory, generation_enabled=generation_enabled))
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
