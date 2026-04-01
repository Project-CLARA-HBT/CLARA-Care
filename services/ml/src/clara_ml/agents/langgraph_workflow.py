from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    query: str
    retrieved: list[str]
    answer: str


def _retrieve_stub(state: GraphState) -> GraphState:
    query = state.get("query", "")
    return {"retrieved": [f"doc::{query[:20]}"]}


def _generate_stub(state: GraphState) -> GraphState:
    retrieved = state.get("retrieved", [])
    return {"answer": f"[LangGraph PoC] Dựa trên {retrieved}"}


def build_langgraph_workflow() -> Any:
    """Xây graph workflow cơ bản query -> retrieve -> generate.

    Trả object graph nếu thư viện có sẵn; nếu thiếu dependency thì trả None
    để service vẫn khởi động ở chế độ baseline tương thích.
    """

    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    graph = StateGraph(GraphState)
    graph.add_node("retrieve", _retrieve_stub)
    graph.add_node("generate", _generate_stub)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
