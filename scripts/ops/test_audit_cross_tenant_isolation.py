#!/usr/bin/env python3
"""Unit and regression tests for audit_cross_tenant_isolation.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from audit_cross_tenant_isolation import CrossTenantAuditor


@pytest.fixture
def repo_root() -> Path:
    """Returns the repository root path."""
    current = Path(__file__).resolve().parent.parent.parent
    return current


def test_auditor_runs_against_repo(repo_root: Path) -> None:
    auditor = CrossTenantAuditor(repo_root)
    findings = auditor.audit_all()
    assert isinstance(findings, list)
    rule_ids = {f.rule_id for f in findings}
    assert "TEN-ROST-01" in rule_ids
    assert "TEN-ADM-03" in rule_ids
    assert "TEN-AUD-01" in rule_ids
    assert "TEN-FDB-01" in rule_ids


def test_auditor_detects_clean_fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # 1. DB Models
        db_dir = root / "services/api/src/clara_api/db"
        db_dir.mkdir(parents=True)
        (db_dir / "models.py").write_text(
            """
            class WorkspaceFolder(Base):
                user_id: Mapped[int] = mapped_column()
            class WorkspaceChannel(Base):
                user_id: Mapped[int] = mapped_column()
            class WorkspaceNote(Base):
                user_id: Mapped[int] = mapped_column()
            class SessionModel(Base):
                user_id: Mapped[int] = mapped_column()
            class CouncilCase(Base):
                user_id: Mapped[int] = mapped_column()
            class ScribeSession(Base):
                user_id: Mapped[int] = mapped_column()
            class KnowledgeSource(Base):
                owner_user_id: Mapped[int] = mapped_column()
            class KnowledgeDocument(Base):
                owner_user_id: Mapped[int] = mapped_column()
            class PhrProfile(Base):
                user_id: Mapped[int] = mapped_column()
            class GlhsAppliedTransition(Base):
                tenant_id: Mapped[str] = mapped_column()
                profile_id: Mapped[int] = mapped_column()
            """,
            encoding="utf-8",
        )

        # 2. Endpoints
        ep_dir = root / "services/api/src/clara_api/api/v1/endpoints"
        ep_dir.mkdir(parents=True)
        (ep_dir / "workspace.py").write_text(
            """
            def _get_owned_folder(db, *, user_id: int, folder_id: int):
                row = db.execute(select(WorkspaceFolder).where(WorkspaceFolder.id == folder_id, WorkspaceFolder.user_id == user_id)).scalar_one_or_none()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
                return row
            def _get_owned_channel(db, *, user_id: int, channel_id: int):
                row = db.execute(select(WorkspaceChannel).where(WorkspaceChannel.id == channel_id, WorkspaceChannel.user_id == user_id)).scalar_one_or_none()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
                return row
            def _get_owned_conversation(db, *, user_id: int, conversation_id: int):
                row = db.execute(select(SessionModel).where(SessionModel.id == conversation_id, SessionModel.user_id == user_id)).scalar_one_or_none()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
                return row
            def _get_owned_note(db, *, user_id: int, note_id: int):
                row = db.execute(select(WorkspaceNote).where(WorkspaceNote.id == note_id, WorkspaceNote.user_id == user_id)).scalar_one_or_none()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
                return row
            """,
            encoding="utf-8",
        )
        (ep_dir / "council.py").write_text(
            """
            def _get_owned_case(db, *, user_id: int, case_id: int):
                row = db.execute(select(CouncilCase).where(CouncilCase.id == case_id, CouncilCase.user_id == user_id)).scalar_one_or_none()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
                return row
            """,
            encoding="utf-8",
        )
        (ep_dir / "scribe.py").write_text(
            """
            def _get_owned_session(db, *, user_id: int, session_id: int):
                row = db.execute(select(ScribeSession).where(ScribeSession.id == session_id, ScribeSession.user_id == user_id)).scalar_one_or_none()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
                return row
            """,
            encoding="utf-8",
        )
        (ep_dir / "research.py").write_text(
            """
            def _get_owned_source(db, *, source_id: int, owner_user_id: int):
                row = db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id, KnowledgeSource.owner_user_id == owner_user_id)).scalar_one_or_none()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
                return row
            def _get_owned_document(db, *, document_id: int, owner_user_id: int):
                row = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id, KnowledgeDocument.owner_user_id == owner_user_id)).scalar_one_or_none()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
                return row
            """,
            encoding="utf-8",
        )

        # 3. GLHS Kernel
        glhs_dir = root / "services/api/src/clara_api/glhs"
        glhs_dir.mkdir(parents=True)
        (glhs_dir / "commit_kernel.py").write_text(
            """
            lock_dep_inputs.append(
                ("idempotency_key", f"idempotency:{tenant_id}:{operation_kind}:{idempotency_key}", LockMode.EXCLUSIVE)
            )
            GlhsAppliedTransition.tenant_id == tenant_id
            """,
            encoding="utf-8",
        )

        # 4. Profile scope
        lifemap_dir = root / "services/api/src/clara_api/lifemap"
        lifemap_dir.mkdir(parents=True)
        (lifemap_dir / "profile_scope.py").write_text(
            """
            if policy.administrative:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scope_forbidden")
            """,
            encoding="utf-8",
        )

        # 5. Core session security
        core_dir = root / "services/api/src/clara_api/core"
        core_dir.mkdir(parents=True)
        (core_dir / "session_security.py").write_text(
            """
            settings.security_redis_key_prefix
            """,
            encoding="utf-8",
        )

        auditor = CrossTenantAuditor(root)
        findings = auditor.audit_all()
        assert len(findings) == 0, f"Expected 0 findings, got {findings}"


def test_auditor_detects_missing_model_scoping() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        db_dir = root / "services/api/src/clara_api/db"
        db_dir.mkdir(parents=True)
        (db_dir / "models.py").write_text(
            """
            class WorkspaceFolder(Base):
                name: Mapped[str] = mapped_column()
            """,
            encoding="utf-8",
        )

        auditor = CrossTenantAuditor(root)
        findings = auditor.audit_all()
        rule_ids = {f.rule_id for f in findings}
        assert "TEN-MOD-01" in rule_ids


def test_auditor_detects_unscoped_endpoint_query() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        ep_dir = root / "services/api/src/clara_api/api/v1/endpoints"
        ep_dir.mkdir(parents=True)
        (ep_dir / "workspace.py").write_text(
            """
            def _get_owned_folder(db, *, user_id: int, folder_id: int):
                return db.execute(select(WorkspaceFolder).where(WorkspaceFolder.id == folder_id)).scalar_one_or_none()
            """,
            encoding="utf-8",
        )

        auditor = CrossTenantAuditor(root)
        findings = auditor.audit_all()
        rule_ids = {f.rule_id for f in findings}
        assert "TEN-IDR-02" in rule_ids


def test_auditor_detects_unsafe_admin_bypass() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        ep_dir = root / "services/api/src/clara_api/api/v1/endpoints"
        ep_dir.mkdir(parents=True)
        (ep_dir / "workspace.py").write_text(
            """
            @router.get("/folders")
            def list_folders(user=Depends(get_user)):
                if user.role == "admin": return
            """,
            encoding="utf-8",
        )

        auditor = CrossTenantAuditor(root)
        findings = auditor.audit_all()
        rule_ids = {f.rule_id for f in findings}
        assert "TEN-ADM-02" in rule_ids


def test_auditor_detects_unpartitioned_glhs_lock() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        glhs_dir = root / "services/api/src/clara_api/glhs"
        glhs_dir.mkdir(parents=True)
        (glhs_dir / "commit_kernel.py").write_text(
            """
            lock_dep_inputs.append(
                ("idempotency_key", f"idempotency:{idempotency_key}", LockMode.EXCLUSIVE)
            )
            """,
            encoding="utf-8",
        )

        auditor = CrossTenantAuditor(root)
        findings = auditor.audit_all()
        rule_ids = {f.rule_id for f in findings}
        assert "TEN-GLHS-01" in rule_ids


def test_auditor_detects_non_enumeration_oracle() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        ep_dir = root / "services/api/src/clara_api/api/v1/endpoints"
        ep_dir.mkdir(parents=True)
        (ep_dir / "council.py").write_text(
            """
            def _get_owned_case(db, *, user_id: int, case_id: int):
                case = db.execute(select(CouncilCase).where(CouncilCase.id == case_id)).scalar_one_or_none()
                if case and case.user_id != user_id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
                return case
            """,
            encoding="utf-8",
        )

        auditor = CrossTenantAuditor(root)
        findings = auditor.audit_all()
        rule_ids = {f.rule_id for f in findings}
        assert "TEN-NONENUM-01" in rule_ids
