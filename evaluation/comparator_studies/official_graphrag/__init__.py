"""Faithful-execution contract for a pinned upstream Microsoft GraphRAG release.

This package deliberately does not emulate GraphRAG.  It prepares and verifies
an execution of the upstream CLI; a benchmark arm remains unavailable until an
upstream-produced index and query ledger pass the contract validator.
"""

from .contract import (
    GraphRAGContractError,
    GraphRAGExecutionContract,
    build_settings,
    materialize_visible_evidence,
    validate_execution_manifest,
)

__all__ = [
    "GraphRAGContractError",
    "GraphRAGExecutionContract",
    "build_settings",
    "materialize_visible_evidence",
    "validate_execution_manifest",
]
