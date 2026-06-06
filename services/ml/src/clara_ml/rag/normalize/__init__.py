"""Medical entity normalization + query expansion (P3).

This package holds the RxNorm/UMLS normalization layer that powers drug→RXCUI/
CUI linking and recall-only query expansion (VN↔EN, brand↔generic). It is the
"moat" layer of the RAG knowledge pipeline.

Modules (built across tasks 7.1–7.6):

* :mod:`umls_client` — license-aware, cached UTS / RxNorm REST client
  (task 7.1). The shared, network-resilient lookup surface every other module
  in this package builds on.
* ``entity_linker`` — text → ``LinkedEntity`` mentions (task 7.2).
* ``query_expander`` — recall-only synonym/translation expansion (task 7.4).

Importing this package performs **no network I/O** and constructs no HTTP
client (Requirement 9.4 graceful-degradation contract: nothing here may fail or
block at import time).
"""

from __future__ import annotations

from .entity_linker import EntityLinker, LinkedEntity
from .query_expander import DEFAULT_VN_EN_LEXICON, ExpandedQuery, QueryExpander
from .umls_client import UmlsClient

__all__ = [
    "UmlsClient",
    "EntityLinker",
    "LinkedEntity",
    "QueryExpander",
    "ExpandedQuery",
    "DEFAULT_VN_EN_LEXICON",
]
