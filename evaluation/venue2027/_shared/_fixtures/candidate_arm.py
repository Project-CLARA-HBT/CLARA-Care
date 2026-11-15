"""Fixture candidate arm module — the code an independent oracle must NOT import.

Real (not a mock of the oracle): a tiny deterministic scoring function that a
candidate evaluation arm could call. Importing this from an oracle would make
the oracle candidate-derived and must be refused with ``CANDIDATE_IMPORT``.

Version: fixture for task SH-independent_oracle, pinned to the task commit.
"""

from __future__ import annotations

from collections.abc import Mapping

CANDIDATE_ARM_VERSION = "1.0.0"


def candidate_score(features: Mapping[str, float]) -> float:
    """Deterministic candidate scoring; used ONLY inside candidate arms."""
    return float(sum(features.values()))
