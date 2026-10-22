"""Consent Gates & Revocation Verification Test Suite.

Spec: PH05 / A07 (Tests + CI).
Enforces:
1. Consent ledger is append-only upon grant and withdrawal.
2. Revocation immediately gates processing intents (fail-closed).
3. Purpose-based policy evaluation correctly distinguishes allowed and denied intents.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from clara_api.compliance import consent as consent_ledger
from clara_api.db.models import Base, User, UserConsent


class ConsentGatesAndRevocationTestCase(unittest.TestCase):
    """Hermetic unit tests validating consent grant, append-only revocation, and gating."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed test user
        self.user = User(id=1, email="test_patient@example.vn", hashed_password="x", role="normal")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_grant_and_verify_consent(self) -> None:
        """Verify that granting a purpose establishes active consent."""
        purpose = consent_ledger.PURPOSE_AI_TRANSPARENCY
        consent_ledger.grant(self.db, user_id=self.user.id, purpose=purpose, version="2026-04-v1")
        self.db.commit()

        self.assertTrue(consent_ledger.has_consent(self.db, user_id=self.user.id, purpose=purpose))
        self.assertEqual(
            consent_ledger.acknowledged_version(self.db, user_id=self.user.id, purpose=purpose),
            "2026-04-v1",
        )

    def test_revocation_appends_and_gates_immediately(self) -> None:
        """Verify revocation appends a row with revoked_at and has_consent returns False."""
        purpose = consent_ledger.PURPOSE_RESEARCH
        # Grant
        consent_ledger.grant(self.db, user_id=self.user.id, purpose=purpose, version="v1")
        self.db.commit()
        self.assertTrue(consent_ledger.has_consent(self.db, user_id=self.user.id, purpose=purpose))

        # Revoke
        consent_ledger.withdraw(self.db, user_id=self.user.id, purpose=purpose)
        self.db.commit()

        # Verify active status is revoked
        self.assertFalse(consent_ledger.has_consent(self.db, user_id=self.user.id, purpose=purpose))

        # Verify append-only property: both rows exist
        rows = self.db.query(UserConsent).filter_by(
            user_id=self.user.id,
            consent_type=consent_ledger.consent_type_for(purpose),
        ).all()
        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[0].revoked_at)
        self.assertIsNotNone(rows[1].revoked_at)

    def test_unregistered_purpose_fails_safe(self) -> None:
        """Verify queries for invalid purposes safely evaluate to False."""
        self.assertFalse(consent_ledger.has_consent(self.db, user_id=self.user.id, purpose="unregistered_purpose"))


if __name__ == "__main__":
    unittest.main()
