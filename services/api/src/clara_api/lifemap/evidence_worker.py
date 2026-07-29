"""Standalone Living Evidence monitor worker.

The worker is dark unless ``LIFEMAP_EVIDENCE_MONITOR_ENABLED=true``. It claims
reference-only jobs, rechecks subscription/consent at claim time, reuses the
verified evidence retrieval path, and leaves material changes pending human
review.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from datetime import UTC, datetime

from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import (
    ClinicalCase,
    ClinicalStageRun,
    ClinicalWorkflowRun,
    EvidenceMonitorJob,
    EvidenceRunSubscription,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.evidence_monitor import (
    assess_monitor_result,
    claim_monitor_jobs,
    enqueue_due_monitor_jobs,
    fail_monitor_job,
)

logger = logging.getLogger("clara.evidence-monitor")


def _worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _execute_claimed_job(job_public_id: str, *, worker_id: str) -> None:
    from clara_api.api.v1.endpoints.evidence_questions import (
        _PROTOCOL,
        _SCHEMA_VERSION,
        _execute_evidence_run,
        _question_data,
    )

    with SessionLocal() as db:
        job = db.execute(
            select(EvidenceMonitorJob).where(
                EvidenceMonitorJob.public_id == job_public_id,
                EvidenceMonitorJob.status == "processing",
                EvidenceMonitorJob.lease_owner == worker_id,
            )
        ).scalar_one_or_none()
        if job is None:
            return
        subscription = db.get(EvidenceRunSubscription, job.subscription_id)
        previous = (
            db.get(ClinicalWorkflowRun, subscription.workflow_run_id)
            if subscription is not None
            else None
        )
        case = db.get(ClinicalCase, previous.case_id) if previous else None
        user = db.get(User, subscription.user_id) if subscription else None
        if subscription is None or previous is None or case is None or user is None:
            fail_monitor_job(
                db, job=job, failure_code="monitor_reference_unavailable"
            )
            db.commit()
            return
        question = _question_data(case)
        now = datetime.now(UTC)
        run = ClinicalWorkflowRun(
            case_id=case.id,
            owner_user_id=user.id,
            protocol=_PROTOCOL,
            status="running",
            idempotency_key=f"evidence-monitor:{job.public_id}",
            request_json={
                "schema_version": _SCHEMA_VERSION,
                "question": question,
                "monitor_job_id": job.public_id,
                "retrieval_contract": {
                    "mode": "deep",
                    "source_classes": question["study_design_needs"],
                    "no_fallback_evidence": True,
                },
            },
            started_at=now,
        )
        db.add(run)
        db.flush()
        db.add(
            ClinicalStageRun(
                workflow_run_id=run.id,
                stage_key="research_retrieval",
                status="running",
                started_at=now,
            )
        )
        job.result_run_id = run.id
        db.commit()
        run_id = run.id
        user_email = user.email
        role = user.role

    _execute_evidence_run(run_id, {"sub": user_email, "role": role})

    with SessionLocal() as db:
        job = db.execute(
            select(EvidenceMonitorJob).where(
                EvidenceMonitorJob.public_id == job_public_id
            )
        ).scalar_one()
        result = db.get(ClinicalWorkflowRun, job.result_run_id)
        if result is None or result.status != "completed":
            fail_monitor_job(db, job=job, failure_code="research_unavailable")
        else:
            assess_monitor_result(db, job=job, current_run=result)
        db.commit()


def run_evidence_monitor_cycle(*, limit: int = 10) -> dict[str, int]:
    settings = get_settings()
    if not settings.lifemap_evidence_monitor_enabled:
        return {"scheduled": 0, "claimed": 0, "completed": 0}
    worker_id = _worker_id()
    with SessionLocal() as db:
        scheduled = enqueue_due_monitor_jobs(
            db, enabled=True, limit=max(limit, 1) * 10
        )
        claimed = claim_monitor_jobs(
            db, worker_id=worker_id, limit=max(1, limit)
        )
        public_ids = [row.public_id for row in claimed]
        db.commit()
    completed = 0
    for public_id in public_ids:
        try:
            _execute_claimed_job(public_id, worker_id=worker_id)
            completed += 1
        except Exception:  # noqa: BLE001 - bounded failure is persisted below
            logger.exception(
                "Evidence monitor job failed",
                extra={"job_ref": public_id},
            )
            with SessionLocal() as db:
                job = db.execute(
                    select(EvidenceMonitorJob).where(
                        EvidenceMonitorJob.public_id == public_id
                    )
                ).scalar_one_or_none()
                if job is not None and job.status == "processing":
                    fail_monitor_job(
                        db, job=job, failure_code="worker_exception"
                    )
                    db.commit()
    return {
        "scheduled": scheduled,
        "claimed": len(public_ids),
        "completed": completed,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    while True:
        outcome = run_evidence_monitor_cycle()
        logger.info("Evidence monitor cycle", extra=outcome)
        time.sleep(30)


if __name__ == "__main__":
    main()
