"""Consumer Retry, Exponential Backoff & Dead-Letter Queue (DLQ) Policy.

Spec: PH09 / A03 (Domain + GLHS Services).
Enforces:
1. Truncated exponential backoff schedule with jitter for outbox delivery retries.
2. Hard dead-letter queue (DLQ) isolation after maximum retry attempts exceeded.
3. Poison pill quarantine preventing worker thread starvation.
"""

from __future__ import annotations

import dataclasses
import datetime
import random
from typing import Literal

RetryDecision = Literal["RETRY", "DEAD_LETTER"]


@dataclasses.dataclass(frozen=True)
class RetryScheduleResult:
    decision: RetryDecision
    next_attempt: int
    delay_seconds: float
    next_available_at: datetime.datetime


class OutboxRetryPolicy:
    """Calculates backoff intervals and DLQ transitions for outbox event delivery."""

    def __init__(
        self,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 300.0,
        max_attempts: int = 8,
    ) -> None:
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.max_attempts = max_attempts

    def evaluate_attempt(
        self,
        current_attempt: int,
        error_code: str = "",
    ) -> RetryScheduleResult:
        next_attempt = current_attempt + 1
        now = datetime.datetime.now(datetime.UTC)

        # 1. Terminal DLQ evaluation
        if next_attempt > self.max_attempts or "POISON_PILL" in error_code:
            return RetryScheduleResult(
                decision="DEAD_LETTER",
                next_attempt=next_attempt,
                delay_seconds=0.0,
                next_available_at=now,
            )

        # 2. Truncated exponential backoff with jitter
        exp_delay = self.base_delay_seconds * (2 ** (current_attempt - 1))
        bounded_delay = min(exp_delay, self.max_delay_seconds)
        jitter = random.uniform(0.8, 1.2) * bounded_delay

        next_avail = now + datetime.timedelta(seconds=jitter)

        return RetryScheduleResult(
            decision="RETRY",
            next_attempt=next_attempt,
            delay_seconds=round(jitter, 2),
            next_available_at=next_avail,
        )
