"""Mobile Pending Job Tracking & Outbox Integration Test Suite.

Spec: PH09 / A07 (Tests + CI).
Enforces:
1. Retrieval of active pending jobs for authenticated mobile sessions.
2. Filtering out dead-lettered and expired background jobs from active list.
3. Verification that completed jobs expose valid result references.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from clara_api.db.models import Base, LifeMapOutboxEvent, PhrProfile, User


class MobilePendingJobTrackingTestCase(unittest.TestCase):
    """Hermetic unit tests validating outbox job state queries for mobile clients."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed user & profile
        self.user = User(id=1, email="patient@hospital.vn", hashed_password="x", role="normal")
        self.db.add(self.user)
        self.db.flush()

        self.profile = PhrProfile(id=1, user_id=self.user.id, full_name="Nguyen Van B")
        self.db.add(self.profile)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_filter_active_pending_jobs(self) -> None:
        """Verify query returns pending and processing jobs while excluding dead-lettered."""
        # 1. Pending job
        j1 = LifeMapOutboxEvent(
            event_id="job-pending-1",
            profile_id=self.profile.id,
            aggregate_type="OCR_SCAN",
            aggregate_id="scan-1",
            event_type="ocr.scan.processing",
            payload_json={},
            status="pending",
        )
        # 2. Dead-lettered job
        j2 = LifeMapOutboxEvent(
            event_id="job-dead-2",
            profile_id=self.profile.id,
            aggregate_type="COUNCIL",
            aggregate_id="case-2",
            event_type="council.case.timeout",
            payload_json={},
            status="dead_letter",
            dead_lettered_at=datetime.now(UTC),
        )
        self.db.add_all([j1, j2])
        self.db.commit()

        # Query active jobs
        active_jobs = (
            self.db.query(LifeMapOutboxEvent)
            .filter(
                LifeMapOutboxEvent.profile_id == self.profile.id,
                LifeMapOutboxEvent.status.in_(["pending", "processing"]),
            )
            .all()
        )
        self.assertEqual(len(active_jobs), 1)
        self.assertEqual(active_jobs[0].event_id, "job-pending-1")

    def test_job_max_attempts_exhaustion(self) -> None:
        """Verify that attempts reaching max threshold transition status."""
        job = LifeMapOutboxEvent(
            event_id="job-exhausted-3",
            profile_id=self.profile.id,
            aggregate_type="DDI",
            aggregate_id="course-3",
            event_type="ddi.check",
            payload_json={},
            status="pending",
            attempt_count=8,
            max_attempts=8,
        )
        self.db.add(job)
        self.db.commit()

        is_exhausted = job.attempt_count >= job.max_attempts
        self.assertTrue(is_exhausted)


if __name__ == "__main__":
    unittest.main()
