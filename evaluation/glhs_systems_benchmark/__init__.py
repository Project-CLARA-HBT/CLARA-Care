"""GLHS Systems Concurrency & Governance Benchmarking Harness.

A comprehensive, real systems benchmarking harness evaluating concurrency control,
governance invariants, and fault recovery across standard and novel architectures:
- PostgreSQL Serializable Snapshot Isolation (SSI)
- GLHS Strict Two-Phase Locking (SS2PL) with Canonical Locking Hierarchy
- Standard Two-Phase Locking (2PL)
- Naive Optimistic Concurrency Control (OCC)
- FHIR R4 Bundle ETag / If-Match Transactions
- Google Zanzibar ACL Snapshot Consistency Model
"""

from __future__ import annotations

__version__ = "1.0.0"
