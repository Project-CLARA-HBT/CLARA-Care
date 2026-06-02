from .domain import Document

__all__ = ["Document", "InMemoryRetriever", "NeuralReranker", "RerankResult"]


def __getattr__(name: str):
    if name == "InMemoryRetriever":
        from .in_memory import InMemoryRetriever

        return InMemoryRetriever
    if name in {"NeuralReranker", "RerankResult"}:
        from .reranker import NeuralReranker, RerankResult

        return {"NeuralReranker": NeuralReranker, "RerankResult": RerankResult}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
