"""Bi-Temporal Knowledge Replay & Clinical Validity Engine.

Spec: PH10 / A04 (ML + Retrieval).
Enforces:
1. Bi-temporal data modeling: separates valid_time (when medical fact occurred in patient life) from transaction_time (when fact was recorded in system).
2. Point-in-time knowledge replay: reconstructs exact historical patient health state at any prior timestamp.
3. Eliminates retrospective knowledge leakage in clinical ML evaluation.
"""

from __future__ import annotations

import dataclasses
import datetime
from typing import Any


@dataclasses.dataclass(frozen=True)
class BiTemporalClinicalFact:
    fact_id: str
    fact_type: str
    payload: dict[str, Any]
    valid_from: datetime.datetime
    valid_to: datetime.datetime | None
    transaction_recorded_at: datetime.datetime
    transaction_superseded_at: datetime.datetime | None = None


class BiTemporalReplayEngine:
    """Reconstructs historical patient health state as of any point in time."""

    def __init__(self, facts: list[BiTemporalClinicalFact] | None = None) -> None:
        self._facts = list(facts or [])

    def add_fact(self, fact: BiTemporalClinicalFact) -> None:
        self._facts.append(fact)

    def replay_as_of(
        self,
        *,
        as_of_valid_time: datetime.datetime,
        as_of_transaction_time: datetime.datetime,
    ) -> list[BiTemporalClinicalFact]:
        """Reconstruct facts that were both clinically valid and known to system as of target timestamps."""
        active_facts: list[BiTemporalClinicalFact] = []
        for f in self._facts:
            # 1. Transaction-time check: was fact recorded in database by target transaction time?
            if f.transaction_recorded_at > as_of_transaction_time:
                continue
            if f.transaction_superseded_at and f.transaction_superseded_at <= as_of_transaction_time:
                continue

            # 2. Valid-time check: was medical fact clinically active at target clinical time?
            if f.valid_from > as_of_valid_time:
                continue
            if f.valid_to and f.valid_to < as_of_valid_time:
                continue

            active_facts.append(f)

        return active_facts
