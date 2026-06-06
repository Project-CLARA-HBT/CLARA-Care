"""Offline ingestion plane for the RAG knowledge pipeline (Epic P1).

This package owns the offline corpus build: source connectors, cleaning,
structure-aware chunking, embed-once, and the idempotent/resumable
orchestrator. Importing this package performs no side effects and does not
require a database connection.

Modules (created across P1/P3/P4/P5 tasks):
- ``connectors/`` — API-first source connectors + robots-respecting gap-fill crawl.
- ``cleaning.py`` — boilerplate strip, VN unicode normalize, PII redaction.
- ``chunking.py`` — structure-aware, full-coverage parent/child chunker.
- ``embedding_builder.py`` — embed once (dense + bge-m3 sparse).
- ``orchestrator.py`` — idempotent, resumable, atomic-per-document orchestrator.
- ``scheduler.py`` — incremental schedule + per-source watermark management.
- ``backfill.py`` — watermark-driven backfill entrypoint.
"""
