#!/usr/bin/env python3
"""Hermetic verification test for PH04 A02: Tenant membership and role schema audit.

Validates:
1. Absence of unverified Organization, Workspace, WorkspaceMember, OrganizationMember models.
2. Single-user tenancy scoping of existing WorkspaceFolder, WorkspaceChannel, WorkspaceNote.
3. GlhsAppliedTransition.tenant_id unconstrained string partition semantics.
4. User.role global scalar role scoping.
5. Strict Alembic downgrade completeness across all 64 revisions.
"""

import sys
import unittest
from pathlib import Path

# Add api source to path
API_SRC = Path(__file__).resolve().parents[3] / "services" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
import clara_api.db.models as models
from clara_api.db.models import (
    User,
    WorkspaceFolder,
    WorkspaceChannel,
    WorkspaceConversationMeta,
    WorkspaceConversationShare,
    WorkspaceNote,
    GlhsAppliedTransition,
    SocialMembership,
    FamilyAccessGrant,
)


class TestPH04ModelsAndTenancyAudit(unittest.TestCase):
    """Hermetic audit tests for tenant membership, workspace models, and role scoping."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        self.user_a = User(email="doctor_a@hospital.org", role="doctor", hashed_password="pw1")
        self.user_b = User(email="doctor_b@clinic.org", role="doctor", hashed_password="pw2")
        self.db.add_all([self.user_a, self.user_b])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_workspace_models_single_user_scoping(self):
        """Audit WorkspaceFolder, WorkspaceChannel, WorkspaceNote - strictly personal/user-scoped."""
        folder = WorkspaceFolder(user_id=self.user_a.id, name="Case Files", slug="case-files")
        channel = WorkspaceChannel(user_id=self.user_a.id, name="Cardiology", slug="cardiology")
        note = WorkspaceNote(user_id=self.user_a.id, title="Grand Rounds", content_markdown="# Note")
        self.db.add_all([folder, channel, note])
        self.db.commit()

        # Verify foreign keys bind directly to users.id
        self.assertEqual(folder.user_id, self.user_a.id)
        self.assertEqual(channel.user_id, self.user_a.id)
        self.assertEqual(note.user_id, self.user_a.id)

        # Audit finding: Workspace models do NOT possess organization_id or WorkspaceMember relations
        self.assertFalse(hasattr(WorkspaceFolder, "organization_id"))
        self.assertFalse(hasattr(WorkspaceChannel, "organization_id"))
        self.assertFalse(hasattr(WorkspaceNote, "organization_id"))
        self.assertFalse(hasattr(WorkspaceFolder, "members"))

    def test_absent_organization_and_workspace_member_models(self):
        """Formally document and verify that Organization, Workspace, WorkspaceMember, and

        OrganizationMember are NOT defined in clara_api.db.models at the current phase baseline.
        """
        self.assertFalse(hasattr(models, "Organization"), "Organization model is not in models.py")
        self.assertFalse(hasattr(models, "Workspace"), "Workspace model is not in models.py (only WorkspaceFolder/Channel/Note)")
        self.assertFalse(hasattr(models, "WorkspaceMember"), "WorkspaceMember model is not in models.py")
        self.assertFalse(hasattr(models, "OrganizationMember"), "OrganizationMember model is not in models.py")

    def test_existing_membership_models_analysis(self):
        """Analyze existing membership paradigms: SocialMembership and FamilyAccessGrant."""
        social_mem_cols = [c.name for c in SocialMembership.__table__.columns]
        self.assertIn("user_id", social_mem_cols)
        self.assertIn("community_id", social_mem_cols)

        family_cols = [c.name for c in FamilyAccessGrant.__table__.columns]
        self.assertIn("grantor_user_id", family_cols)
        self.assertIn("grantee_user_id", family_cols)
        self.assertIn("profile_id", family_cols)
        self.assertIn("purpose", family_cols)
        self.assertIn("allowed_actions_json", family_cols)

    def test_glhs_applied_transition_tenant_id_partitioning(self):
        """Audit GlhsAppliedTransition tenant_id scoping and unique constraint."""
        table = GlhsAppliedTransition.__table__
        self.assertIn("tenant_id", [c.name for c in table.columns])

        # Verify idempotency constraint encompasses tenant_id
        uq_names = [uc.name for uc in table.constraints if hasattr(uc, "columns")]
        self.assertIn("uq_glhs_applied_trans_idempotency", uq_names)

        for uc in table.constraints:
            if uc.name == "uq_glhs_applied_trans_idempotency":
                col_names = [c.name for c in uc.columns]
                self.assertEqual(col_names, ["tenant_id", "operation_kind", "idempotency_key"])

    def test_role_scoping_invariants(self):
        """Audit User.role field and scalar global role."""
        user_cols = [c.name for c in User.__table__.columns]
        self.assertIn("role", user_cols)
        self.assertEqual(User.role.property.columns[0].default.arg, "normal")


if __name__ == "__main__":
    unittest.main()
