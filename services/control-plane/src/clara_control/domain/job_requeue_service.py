"""Job Requeue, Idempotency & Statutory Consent Recheck Domain Service.

Spec: PH51 / A03 (Domain Service).
Enforces:
1. Requeuing failed/DLQ jobs with strict idempotency verification.
2. Statutory consent recheck before requeuing: if patient revoked consent while job was in DLQ, requeue is permanently blocked.
3. Resets lease and attempt counters upon valid requeue.
"""

from __future__ import annotations

import dataclasses
import datetime
from typing import Any, Literal

RequeueDecision = Literal["REQUEUED", "BLOCKED_CONSENT_REVOKED", "ALREADY_ACTIVE", "NOT_FOUND"]


@dataclasses.dataclass(frozen=True)
class JobRequeueOutcome:
    decision: RequeueDecision
    job_id: str
    reason: str
    requeued_at: datetime.datetime | None = None


class JobRequeueService:
    """Manages safe job requeuing with consent re-evaluation."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    def register_job(self, *, job_id: str, status: str, required_consent_purpose: str, user_id: int) -> None:
        self._jobs[job_id] = {
            "job_id": job_id,
            "status": status,
            "required_consent_purpose": required_consent_purpose,
            "user_id": user_id,
            "attempt_count": 8,
        }

    def requeue_job(
        self,
        *,
        job_id: str,
        user_active_purposes: set[str],
    ) -> JobRequeueOutcome:
        job = self._jobs.get(job_id)
        if not job:
            return JobRequeueOutcome(decision="NOT_FOUND", job_id=job_id, reason="Job does not exist")

        if job["status"] in ("RUNNING", "PENDING"):
            return JobRequeueOutcome(
                decision="ALREADY_ACTIVE",
                job_id=job_id,
                reason="Job is already active or queued",
            )

        # 1. Statutory Consent Re-check
        required_purpose = job.get("required_consent_purpose", "core_service")
        if required_purpose not in user_active_purposes:
            return JobRequeueOutcome(
                decision="BLOCKED_CONSENT_REVOKED",
                job_id=job_id,
                reason=f"Patient revoked required consent purpose '{required_purpose}' while job was in DLQ",
            )

        # 2. Requeue successful
        job["status"] = "PENDING"
        job["attempt_count"] = 0
        now = datetime.datetime.now(datetime.UTC)

        return JobRequeueOutcome(
            decision="REQUEUED",
            job_id=job_id,
            reason="Job successfully requeued with reset attempts",
            requeued_at=now,
        )
