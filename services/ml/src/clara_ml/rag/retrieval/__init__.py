from .domain import Document

__all__ = [
    "Document",
    "InMemoryRetriever",
    "EvidenceReranker",
    "NeuralReranker",
    "RerankResult",
]


def __getattr__(name: str):
    if name == "InMemoryRetriever":
        from .in_memory import InMemoryRetriever

        return InMemoryRetriever
    if name in {"EvidenceReranker", "NeuralReranker", "RerankResult"}:
        from .reranker import EvidenceReranker, NeuralReranker, RerankResult

        return {
            "EvidenceReranker": EvidenceReranker,
            "NeuralReranker": NeuralReranker,
            "RerankResult": RerankResult,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
