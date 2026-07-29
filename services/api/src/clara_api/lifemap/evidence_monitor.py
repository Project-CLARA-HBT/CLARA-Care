"""Durable, fail-closed Living Evidence subscription machinery.

Jobs and notifications intentionally contain record references and bounded
counts, never question text, profile facts, or citation excerpts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    ClinicalWorkflowRun,
    EvidenceApplicabilityRule,
    EvidenceChangeAssessment,
    EvidenceChangeNotification,
    EvidenceMonitorJob,
    EvidenceRecord,
    EvidenceRunSubscription,
    EvidenceSourceCheckpoint,
    PhrProfile,
    UserConsent,
)

ASSESSMENT_RULE_VERSION = "evidence-material-change-v1"
MAX_ATTEMPTS = 5


class EvidenceMonitorError(ValueError):
    """A bounded monitor transition cannot proceed safely."""


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def validate_applicability_rule(
    *,
    required_fact_types: Any,
    rule: Any,
) -> tuple[list[str], dict[str, Any]]:
    """Validate a deterministic, non-inferential applicability rule format."""

    if (
        not isinstance(required_fact_types, list)
        or not required_fact_types
        or len(required_fact_types) > 32
        or len(set(required_fact_types)) != len(required_fact_types)
        or not all(
            isinstance(item, str)
            and 1 <= len(item) <= 64
            and item.replace("_", "").isalnum()
            for item in required_fact_types
        )
    ):
        raise EvidenceMonitorError("Required fact types are invalid")
    if not isinstance(rule, dict) or set(rule) != {"all"}:
        raise EvidenceMonitorError("Applicability rule must contain one all-clause")
    clauses = rule["all"]
    if not isinstance(clauses, list) or not clauses or len(clauses) > 32:
        raise EvidenceMonitorError("Applicability rule clauses are invalid")
    allowed_operators = {"eq", "in", "gte", "lte"}
    for clause in clauses:
        if (
            not isinstance(clause, dict)
            or set(clause) != {"fact_type", "operator", "value"}
            or clause["fact_type"] not in required_fact_types
            or clause["operator"] not in allowed_operators
            or not isinstance(clause["value"], (str, int, float, bool, list))
        ):
            raise EvidenceMonitorError("Applicability rule clause is invalid")
        if isinstance(clause["value"], list) and (
            not clause["value"] or len(clause["value"]) > 32
        ):
            raise EvidenceMonitorError("Applicability rule value list is invalid")
        if clause["operator"] == "in" and not isinstance(clause["value"], list):
            raise EvidenceMonitorError("Applicability in-rule requires a value list")
        if clause["operator"] in {"gte", "lte"} and (
            isinstance(clause["value"], bool)
            or not isinstance(clause["value"], (int, float))
        ):
            raise EvidenceMonitorError(
                "Applicability range rules require a numeric value"
            )
    return list(required_fact_types), dict(rule)


def evaluate_applicability(
    *,
    rule: EvidenceApplicabilityRule | None,
    confirmed_facts: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate only explicitly confirmed inputs; missing inputs stay unknown."""

    if (
        rule is None
        or rule.status != "approved"
        or rule.approved_at is None
        or rule.approved_by_user_id is None
    ):
        return {
            "status": "not_assessed",
            "matches": [],
            "mismatches": [],
            "unknowns": ["approved_applicability_rule_unavailable"],
            "rule_version": None,
        }
    required, definition = validate_applicability_rule(
        required_fact_types=rule.required_fact_types_json,
        rule=rule.rule_json,
    )
    unknowns = [key for key in required if key not in confirmed_facts]
    if unknowns:
        return {
            "status": "not_assessed",
            "matches": [],
            "mismatches": [],
            "unknowns": unknowns,
            "rule_version": rule.version,
        }
    matches: list[str] = []
    mismatches: list[str] = []
    for clause in definition["all"]:
        key = clause["fact_type"]
        actual = confirmed_facts[key]
        expected = clause["value"]
        operator = clause["operator"]
        if operator in {"gte", "lte"} and (
            isinstance(actual, bool) or not isinstance(actual, (int, float))
        ):
            mismatches.append(key)
            continue
        passed = (
            actual == expected
            if operator == "eq"
            else actual in expected
            if operator == "in" and isinstance(expected, list)
            else actual >= expected
            if operator == "gte"
            else actual <= expected
        )
        (matches if passed else mismatches).append(key)
    return {
        "status": "match" if not mismatches else "mismatch",
        "matches": matches,
        "mismatches": mismatches,
        "unknowns": [],
        "rule_version": rule.version,
    }


def _active_medical_consent(db: Session, *, user_id: int) -> bool:
    return (
        db.execute(
            select(UserConsent.id).where(
                UserConsent.user_id == user_id,
                UserConsent.consent_type == "medical_disclaimer",
                UserConsent.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        is not None
    )


def enqueue_due_monitor_jobs(
    db: Session,
    *,
    enabled: bool,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    """Schedule at most one job per subscription/time bucket."""

    if not enabled:
        return 0
    current = _as_utc(now or _now())
    subscriptions = list(
        db.execute(
            select(EvidenceRunSubscription)
            .where(
                EvidenceRunSubscription.status == "active",
                EvidenceRunSubscription.revoked_at.is_(None),
                EvidenceRunSubscription.next_check_at <= current,
            )
            .order_by(EvidenceRunSubscription.next_check_at)
            .limit(max(1, min(limit, 500)))
        ).scalars()
    )
    created = 0
    for subscription in subscriptions:
        profile = db.get(PhrProfile, subscription.profile_id)
        if (
            profile is None
            or profile.user_id != subscription.user_id
            or not _active_medical_consent(db, user_id=subscription.user_id)
        ):
            continue
        bucket = current.replace(minute=0, second=0, microsecond=0).isoformat()
        dedupe_key = hashlib.sha256(
            f"{subscription.public_id}:{bucket}".encode()
        ).hexdigest()
        if db.execute(
            select(EvidenceMonitorJob.id).where(
                EvidenceMonitorJob.dedupe_key == dedupe_key
            )
        ).scalar_one_or_none():
            continue
        db.add(
            EvidenceMonitorJob(
                subscription_id=subscription.id,
                dedupe_key=dedupe_key,
                scheduled_for=current,
                next_attempt_at=current,
            )
        )
        created += 1
    db.flush()
    return created


def claim_monitor_jobs(
    db: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
    limit: int = 10,
    lease_seconds: int = 120,
) -> list[EvidenceMonitorJob]:
    current = _as_utc(now or _now())
    rows = list(
        db.execute(
            select(EvidenceMonitorJob)
            .where(
                EvidenceMonitorJob.next_attempt_at <= current,
                or_(
                    EvidenceMonitorJob.status.in_({"pending", "retry"}),
                    (
                        (EvidenceMonitorJob.status == "processing")
                        & (EvidenceMonitorJob.lease_until < current)
                    ),
                ),
            )
            .order_by(EvidenceMonitorJob.scheduled_for, EvidenceMonitorJob.id)
            .limit(max(1, min(limit, 100)))
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    lease_until = current + timedelta(seconds=max(30, lease_seconds))
    claimed: list[EvidenceMonitorJob] = []
    for row in rows:
        subscription = db.get(EvidenceRunSubscription, row.subscription_id)
        if (
            subscription is None
            or subscription.status != "active"
            or subscription.revoked_at is not None
            or not _active_medical_consent(db, user_id=subscription.user_id)
        ):
            row.status = "cancelled"
            row.failure_code = "authorization_or_consent_unavailable"
            row.completed_at = current
            continue
        row.status = "processing"
        row.lease_owner = worker_id[:96]
        row.lease_until = lease_until
        row.attempts += 1
        claimed.append(row)
    db.flush()
    return claimed


def _evidence_identity(row: EvidenceRecord) -> str:
    citation = row.citation_json if isinstance(row.citation_json, dict) else {}
    identifiers = citation.get("identifiers")
    normalized = identifiers if isinstance(identifiers, dict) else {}
    payload = {
        "source_class": row.source_type,
        "provider": citation.get("provider"),
        "source_id": row.source_id,
        "identifiers": normalized,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def assess_monitor_result(
    db: Session,
    *,
    job: EvidenceMonitorJob,
    current_run: ClinicalWorkflowRun,
    now: datetime | None = None,
) -> EvidenceChangeAssessment:
    """Compare stable source identities; never infer materiality from prose."""

    current = _as_utc(now or _now())
    subscription = db.get(EvidenceRunSubscription, job.subscription_id)
    if (
        subscription is None
        or subscription.status != "active"
        or subscription.revoked_at is not None
    ):
        raise EvidenceMonitorError("Subscription is no longer active")
    previous_run = db.get(ClinicalWorkflowRun, subscription.workflow_run_id)
    if previous_run is None or current_run.case_id != previous_run.case_id:
        raise EvidenceMonitorError("Monitor result does not match the subscription")
    previous_rows = list(
        db.execute(
            select(EvidenceRecord).where(
                EvidenceRecord.workflow_run_id == previous_run.id
            )
        ).scalars()
    )
    current_rows = list(
        db.execute(
            select(EvidenceRecord).where(
                EvidenceRecord.workflow_run_id == current_run.id
            )
        ).scalars()
    )
    before = {_evidence_identity(row) for row in previous_rows}
    after = {_evidence_identity(row) for row in current_rows}
    added = after - before
    removed = before - after
    summary = (
        current_run.result_summary_json
        if isinstance(current_run.result_summary_json, dict)
        else {}
    )
    structured = summary.get("material_change_assessment")
    accepted_ids = {row.public_id for row in current_rows}
    structured_material = (
        isinstance(structured, dict)
        and structured.get("status") == "material_change"
        and isinstance(structured.get("evidence_ids"), list)
        and bool(structured["evidence_ids"])
        and set(map(str, structured["evidence_ids"])).issubset(accepted_ids)
    )
    previous_summary = (
        previous_run.result_summary_json
        if isinstance(previous_run.result_summary_json, dict)
        else {}
    )
    contradiction_changed = (
        previous_summary.get("contradictions") != summary.get("contradictions")
    )
    classification = (
        "candidate_material_change"
        if structured_material or contradiction_changed
        else "new_results"
        if added or removed
        else "no_change"
    )
    assessment = EvidenceChangeAssessment(
        monitor_job_id=job.id,
        subscription_id=subscription.id,
        previous_run_id=previous_run.id,
        current_run_id=current_run.id,
        classification=classification,
        contradiction_status=(
            "changed" if contradiction_changed else "unchanged"
        ),
        rule_version=ASSESSMENT_RULE_VERSION,
        model_version=str(summary.get("change_model_version") or "none")[:96],
        review_status=(
            "pending" if classification == "candidate_material_change" else "not_required"
        ),
        safe_projection_json={
            "added_source_count": len(added),
            "removed_source_count": len(removed),
            "contradiction_status": (
                "changed" if contradiction_changed else "unchanged"
            ),
            "consumer_message": (
                "Một thay đổi bằng chứng đang chờ chuyên gia rà soát."
                if classification == "candidate_material_change"
                else "Chưa có thay đổi đã được xác nhận để thông báo."
            ),
        },
    )
    db.add(assessment)
    job.result_run_id = current_run.id
    job.status = "completed"
    job.completed_at = current
    job.lease_until = None
    subscription.last_checked_at = current
    subscription.next_check_at = current + timedelta(
        hours=max(24, min(subscription.interval_hours, 24 * 30))
    )
    for row in current_rows:
        citation = row.citation_json if isinstance(row.citation_json, dict) else {}
        provider = str(citation.get("provider") or "unknown")[:64]
        checkpoint = db.execute(
            select(EvidenceSourceCheckpoint).where(
                EvidenceSourceCheckpoint.subscription_id == subscription.id,
                EvidenceSourceCheckpoint.source_class == row.source_type,
                EvidenceSourceCheckpoint.provider == provider,
            )
        ).scalar_one_or_none()
        digest = _evidence_identity(row)
        if checkpoint is None:
            checkpoint = EvidenceSourceCheckpoint(
                subscription_id=subscription.id,
                source_class=row.source_type,
                provider=provider,
            )
            db.add(checkpoint)
        checkpoint.cursor = row.source_id[:512]
        checkpoint.watermark_digest = digest
        checkpoint.checked_at = current
    db.flush()
    return assessment


def fail_monitor_job(
    db: Session,
    *,
    job: EvidenceMonitorJob,
    failure_code: str,
    now: datetime | None = None,
) -> None:
    current = _as_utc(now or _now())
    job.failure_code = failure_code[:64]
    job.lease_until = None
    job.lease_owner = ""
    if job.attempts >= MAX_ATTEMPTS:
        job.status = "dead_letter"
        job.completed_at = current
    else:
        job.status = "retry"
        job.next_attempt_at = current + timedelta(
            minutes=min(60, 2 ** max(0, job.attempts - 1))
        )
    db.flush()


def review_change_assessment(
    db: Session,
    *,
    assessment: EvidenceChangeAssessment,
    reviewer_user_id: int,
    action: Literal["accept", "reject"],
    reason: str,
) -> EvidenceChangeAssessment:
    if assessment.review_status != "pending":
        raise EvidenceMonitorError("Assessment is not awaiting review")
    if assessment.classification != "candidate_material_change":
        raise EvidenceMonitorError("Only candidate material changes can be reviewed")
    assessment.review_status = "accepted" if action == "accept" else "rejected"
    assessment.reviewed_by_user_id = reviewer_user_id
    assessment.reviewed_at = _now()
    assessment.review_reason = reason.strip()[:255]
    if action == "accept":
        subscription = db.get(
            EvidenceRunSubscription, assessment.subscription_id
        )
        if (
            subscription is None
            or subscription.status != "active"
            or subscription.revoked_at is not None
            or not _active_medical_consent(db, user_id=subscription.user_id)
        ):
            raise EvidenceMonitorError(
                "Notification authorization or consent is no longer active"
            )
        db.add(
            EvidenceChangeNotification(
                assessment_id=assessment.id,
                user_id=subscription.user_id,
                profile_id=subscription.profile_id,
                payload_json={
                    "kind": "accepted_material_evidence_change",
                    "assessment_id": assessment.public_id,
                    "message": (
                        "Có thay đổi bằng chứng đã được rà soát cho một câu hỏi "
                        "bạn đang theo dõi."
                    ),
                },
            )
        )
    db.flush()
    return assessment
