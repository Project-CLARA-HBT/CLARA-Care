from .domain import Document

__all__ = ["Document", "InMemoryRetriever"]


def __getattr__(name: str):
    if name == "InMemoryRetriever":
        from .in_memory import InMemoryRetriever

        return InMemoryRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
