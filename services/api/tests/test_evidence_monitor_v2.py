"""Fail-closed Living Evidence applicability and durable monitor contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    ClinicalCase,
    ClinicalWorkflowRun,
    EvidenceApplicabilityRule,
    EvidenceChangeNotification,
    EvidenceMonitorJob,
    EvidenceRecord,
    EvidenceRunSubscription,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.lifemap.evidence_monitor import (
    EvidenceMonitorError,
    assess_monitor_result,
    claim_monitor_jobs,
    enqueue_due_monitor_jobs,
    evaluate_applicability,
    fail_monitor_job,
    review_change_assessment,
    validate_applicability_rule,
)


@pytest.fixture
def db(tmp_path) -> Session:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'monitor.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _graph(db: Session):
    now = datetime.now(UTC)
    user = User(email="monitor@normal.clara", hashed_password="x")
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id, full_name="Monitor")
    consent = UserConsent(
        user_id=user.id,
        consent_type="medical_disclaimer",
        consent_version="test",
    )
    case = ClinicalCase(owner_user_id=user.id, case_type="lifemap_evidence_question")
    db.add_all([profile, consent, case])
    db.flush()
    run = ClinicalWorkflowRun(
        case_id=case.id,
        owner_user_id=user.id,
        protocol="evidence_brief",
        status="completed",
        idempotency_key="original",
        request_json={},
        result_summary_json={"contradictions": []},
    )
    db.add(run)
    db.flush()
    subscription = EvidenceRunSubscription(
        user_id=user.id,
        profile_id=profile.id,
        workflow_run_id=run.id,
        next_check_at=now - timedelta(minutes=1),
    )
    db.add(subscription)
    db.commit()
    return user, profile, run, subscription


def test_applicability_requires_approved_rule_and_confirmed_typed_facts(db) -> None:
    assert evaluate_applicability(rule=None, confirmed_facts={})["status"] == "not_assessed"
    rule = EvidenceApplicabilityRule(
        question_class="hypertension",
        version="1.0",
        required_fact_types_json=["age_years", "diagnosis_confirmed"],
        rule_json={
            "all": [
                {"fact_type": "age_years", "operator": "gte", "value": 18},
                {
                    "fact_type": "diagnosis_confirmed",
                    "operator": "eq",
                    "value": True,
                },
            ]
        },
        status="approved",
        approved_by_user_id=1,
        approved_at=datetime.now(UTC),
    )
    missing = evaluate_applicability(
        rule=rule, confirmed_facts={"diagnosis_confirmed": True}
    )
    assert missing["status"] == "not_assessed"
    assert missing["unknowns"] == ["age_years"]
    assert evaluate_applicability(
        rule=rule,
        confirmed_facts={"age_years": 42, "diagnosis_confirmed": True},
    )["status"] == "match"
    assert evaluate_applicability(
        rule=rule,
        confirmed_facts={"age_years": "unknown", "diagnosis_confirmed": True},
    )["status"] == "mismatch"
    with pytest.raises(EvidenceMonitorError):
        validate_applicability_rule(
            required_fact_types=["age_years"],
            rule={
                "all": [
                    {"fact_type": "age_years", "operator": "gte", "value": "18"}
                ]
            },
        )


def test_scheduler_dedupes_leases_and_cancels_after_consent_withdrawal(db) -> None:
    user, _, _, subscription = _graph(db)
    now = datetime.now(UTC)
    assert enqueue_due_monitor_jobs(db, enabled=False, now=now) == 0
    assert enqueue_due_monitor_jobs(db, enabled=True, now=now) == 1
    assert enqueue_due_monitor_jobs(db, enabled=True, now=now) == 0
    claimed = claim_monitor_jobs(db, worker_id="worker-a", now=now)
    assert len(claimed) == 1
    assert claimed[0].attempts == 1
    fail_monitor_job(db, job=claimed[0], failure_code="temporary", now=now)
    assert claimed[0].status == "retry"

    consent = db.query(UserConsent).filter(UserConsent.user_id == user.id).one()
    consent.revoked_at = now
    claimed[0].next_attempt_at = now
    db.flush()
    assert claim_monitor_jobs(db, worker_id="worker-b", now=now) == []
    assert claimed[0].status == "cancelled"
    assert subscription.status == "active"


def test_only_reviewed_material_change_creates_notification(db) -> None:
    user, _, previous, subscription = _graph(db)
    db.add(
        EvidenceRecord(
            case_id=previous.case_id,
            workflow_run_id=previous.id,
            source_type="guideline",
            source_id="guideline-v1",
            citation_json={"provider": "nice", "identifiers": {"id": "g1"}},
        )
    )
    current = ClinicalWorkflowRun(
        case_id=previous.case_id,
        owner_user_id=user.id,
        protocol="evidence_brief",
        status="completed",
        idempotency_key="monitor-result",
        request_json={},
        result_summary_json={
            "contradictions": [{"status": "changed"}],
            "change_model_version": "deepseek-review-v1",
        },
    )
    db.add(current)
    db.flush()
    db.add(
        EvidenceRecord(
            case_id=current.case_id,
            workflow_run_id=current.id,
            source_type="guideline",
            source_id="guideline-v2",
            citation_json={"provider": "nice", "identifiers": {"id": "g2"}},
        )
    )
    job = EvidenceMonitorJob(
        subscription_id=subscription.id,
        dedupe_key="material-job",
        status="processing",
        scheduled_for=datetime.now(UTC),
        next_attempt_at=datetime.now(UTC),
        lease_owner="worker",
        attempts=1,
    )
    db.add(job)
    db.flush()
    assessment = assess_monitor_result(db, job=job, current_run=current)
    assert assessment.classification == "candidate_material_change"
    assert assessment.review_status == "pending"
    assert db.query(EvidenceChangeNotification).count() == 0

    review_change_assessment(
        db,
        assessment=assessment,
        reviewer_user_id=user.id,
        action="accept",
        reason="Confirmed against cited guideline.",
    )
    assert assessment.review_status == "accepted"
    notification = db.query(EvidenceChangeNotification).one()
    assert notification.payload_json["kind"] == "accepted_material_evidence_change"
    with pytest.raises(EvidenceMonitorError):
        review_change_assessment(
            db,
            assessment=assessment,
            reviewer_user_id=user.id,
            action="accept",
            reason="duplicate",
        )
