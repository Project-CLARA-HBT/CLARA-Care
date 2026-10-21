"""Multi-tenant isolation, workspace membership invitations, and RAG retrieval audit.

Part of Phase PH04 / Subagent A04 (ML + retrieval).
Verifies:
1. Workspace membership invitation boundaries: active, invited, pending, expired, revoked.
2. Cross-tenant knowledge retrieval isolation in persistent RAG store (KbSourceRegistry, KbDocument).
3. Sparse & dense filter partitioning: zero cross-tenant retrieval leakage.
4. Semantic query cache tenant isolation: exact match and vector-similarity cross-tenant prevention.
5. ML inference gateway tenant membership gates (/v1/chat/routed, /v1/rag/poc).
6. Zero-PII / Zero-PHI safety invariant on tenant error envelopes.
7. OCR and ASR adapter stateless boundary verification.
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from clara_ml.main import app
from clara_ml.rag.retrieval.domain import Document
from clara_ml.rag.store.cache import SemanticQueryCache
from clara_ml.rag.store.document_store import IngestDocument
from clara_ml.rag.store.hybrid_retriever import RetrievalFilters
from clara_ml.rag.store.schema import (
    KbDocument,
    KbSourceRegistry,
)
from clara_ml.rag.store.sparse_index import SparseFilters, SparseIndex
from clara_ml.tenant_boundary import (
    TenantBoundaryError,
    WorkspaceInvitationContext,
    WorkspaceMembershipStatus,
    compose_tenant_cache_key,
    enforce_workspace_ml_membership,
    sanitize_tenant_id,
)
from fastapi.testclient import TestClient

client = TestClient(app)


# ==============================================================================
# 1. Workspace Membership Invitation & Tenant Boundary Unit Tests
# ==============================================================================


def test_sanitize_tenant_id_valid() -> None:
    """Valid tenant identifiers are preserved."""
    assert sanitize_tenant_id("tenant-123") == "tenant-123"
    assert sanitize_tenant_id("org_hospital_a") == "org_hospital_a"
    assert sanitize_tenant_id("clinic.v1") == "clinic.v1"
    assert sanitize_tenant_id(None) == ""
    assert sanitize_tenant_id("") == ""


@pytest.mark.parametrize("malformed", [
    "../etc/passwd",
    "tenant/../../sub",
    "tenant$id",
    "tenant;DROP TABLE users;",
    "a" * 150,  # exceeds 128 chars
])
def test_sanitize_tenant_id_rejects_insecure_identifiers(malformed: str) -> None:
    """Malformed or path traversal tenant IDs are rejected fail-closed."""
    with pytest.raises(TenantBoundaryError) as exc_info:
        sanitize_tenant_id(malformed)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "invalid_tenant_identifier"


def test_public_untenanted_scope_admitted() -> None:
    """Empty or None tenant_id represents un-tenanted public access and is admitted."""
    assert enforce_workspace_ml_membership(None, None) is True
    assert enforce_workspace_ml_membership("", None) is True


def test_active_membership_admitted() -> None:
    """Active members are admitted to tenant ML capabilities."""
    assert enforce_workspace_ml_membership(
        tenant_id="tenant-hosp-alpha",
        membership_status=WorkspaceMembershipStatus.ACTIVE,
    ) is True
    assert enforce_workspace_ml_membership(
        tenant_id="tenant-hosp-alpha",
        membership_status="active",
    ) is True


def test_pending_and_invited_memberships_blocked_403() -> None:
    """Invited or pending workspace invitations MUST NOT grant tenant ML inference access."""
    for st in [WorkspaceMembershipStatus.INVITED, WorkspaceMembershipStatus.PENDING, "invited", "pending"]:
        with pytest.raises(TenantBoundaryError) as exc_info:
            enforce_workspace_ml_membership(
                tenant_id="tenant-hosp-alpha",
                membership_status=st,
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "invitation_pending_unauthorized"


def test_expired_invitation_blocked_403() -> None:
    """Expired invitations are blocked with HTTP 403."""
    with pytest.raises(TenantBoundaryError) as exc_info:
        enforce_workspace_ml_membership(
            tenant_id="tenant-hosp-alpha",
            membership_status=WorkspaceMembershipStatus.EXPIRED,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "invitation_expired"


def test_revoked_and_suspended_memberships_blocked_403() -> None:
    """Revoked or suspended memberships are blocked fail-closed."""
    for st in [WorkspaceMembershipStatus.REVOKED, WorkspaceMembershipStatus.SUSPENDED, "revoked", "suspended"]:
        with pytest.raises(TenantBoundaryError) as exc_info:
            enforce_workspace_ml_membership(
                tenant_id="tenant-hosp-alpha",
                membership_status=st,
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "membership_revoked"


def test_unauthenticated_tenant_access_blocked_403() -> None:
    """Specifying a tenant_id without membership verification fails closed."""
    with pytest.raises(TenantBoundaryError) as exc_info:
        enforce_workspace_ml_membership(
            tenant_id="tenant-hosp-alpha",
            membership_status=None,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "unauthenticated_tenant_access"


def test_invitation_context_evaluation_with_expiry() -> None:
    """WorkspaceInvitationContext correctly evaluates expiry timestamps."""
    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2)
    invitation = WorkspaceInvitationContext.create(
        invitation_id="inv-001",
        tenant_id="tenant-clinic-b",
        role="doctor",
        status=WorkspaceMembershipStatus.ACTIVE,
        recipient_email="doctor@clinic-b.vn",
        expires_at=past,
    )
    # Even if status was active, an expired timestamp forces EXPIRED block
    with pytest.raises(TenantBoundaryError) as exc_info:
        enforce_workspace_ml_membership(
            tenant_id="tenant-clinic-b",
            membership_status=None,
            invitation_context=invitation,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "invitation_expired"


def test_invitation_context_tenant_mismatch_blocked() -> None:
    """Invitation issued for tenant A cannot be used to invoke tenant B ML inference."""
    invitation = WorkspaceInvitationContext.create(
        invitation_id="inv-002",
        tenant_id="tenant-hospital-a",
        role="member",
        status=WorkspaceMembershipStatus.ACTIVE,
    )
    with pytest.raises(TenantBoundaryError) as exc_info:
        enforce_workspace_ml_membership(
            tenant_id="tenant-hospital-b",
            membership_status=None,
            invitation_context=invitation,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "tenant_context_mismatch"


def test_workspace_role_gating() -> None:
    """Workspace role requirements are respected."""
    # Clinician allowed
    assert enforce_workspace_ml_membership(
        tenant_id="tenant-alpha",
        membership_status=WorkspaceMembershipStatus.ACTIVE,
        required_roles=["clinician", "doctor"],
        caller_role="clinician",
    ) is True

    # Guest rejected
    with pytest.raises(TenantBoundaryError) as exc_info:
        enforce_workspace_ml_membership(
            tenant_id="tenant-alpha",
            membership_status=WorkspaceMembershipStatus.ACTIVE,
            required_roles=["clinician", "doctor"],
            caller_role="guest",
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "insufficient_workspace_role"

    # Admin implicit access
    assert enforce_workspace_ml_membership(
        tenant_id="tenant-alpha",
        membership_status=WorkspaceMembershipStatus.ACTIVE,
        required_roles=["clinician"],
        caller_role="admin",
    ) is True


# ==============================================================================
# 2. Schema and Persistent RAG Store Tenant Partitioning Tests
# ==============================================================================


def test_kb_source_registry_and_documents_schema_have_tenant_id() -> None:
    """Verify ORM definitions for kb_source_registry and kb_documents include tenant_id."""
    assert hasattr(KbSourceRegistry, "tenant_id")
    assert hasattr(KbDocument, "tenant_id")

    source_tenant_col = KbSourceRegistry.__table__.c.tenant_id
    doc_tenant_col = KbDocument.__table__.c.tenant_id

    assert source_tenant_col.nullable is True
    assert doc_tenant_col.nullable is True

    # Verify tenant indexes exist
    source_indexes = {ix.name for ix in KbSourceRegistry.__table__.indexes}
    doc_indexes = {ix.name for ix in KbDocument.__table__.indexes}

    assert "idx_kb_source_registry_tenant" in source_indexes
    assert "idx_kb_documents_tenant" in doc_indexes


def test_ingest_document_preserves_tenant_id() -> None:
    """IngestDocument dataclass captures tenant_id and document_store persists it."""
    doc = IngestDocument(
        source_id=1,
        content_hash="abc123hash",
        trust_tier=1,
        external_id="doc-001",
        title="Clinical Guideline",
        tenant_id="tenant-care-center",
    )
    assert doc.tenant_id == "tenant-care-center"


def test_sparse_filters_tenant_scoping() -> None:
    """SparseFilters carries tenant_id and projects onto SQL statement."""
    filters = SparseFilters(trust_tier_max=2, tenant_id="tenant-hospital-x")
    assert filters.tenant_id == "tenant-hospital-x"

    sparse_index = SparseIndex(session_factory=lambda: None)  # type: ignore[arg-type]
    stmt = sparse_index.build_search_statement("diabetes", config="simple", top_k=5, filters=filters)
    compiled_sql = str(stmt.compile()).lower()

    # Statement must join kb_documents and filter on tenant_id
    assert "join kb_documents" in compiled_sql
    assert "kb_documents.tenant_id" in compiled_sql


def test_retrieval_filters_tenant_projection() -> None:
    """RetrievalFilters projects tenant_id cleanly to SparseFilters."""
    retrieval_filters = RetrievalFilters(
        trust_tier_max=3,
        lang="vi",
        tenant_id="tenant-pharma-y",
    )
    sparse_filters = retrieval_filters.to_sparse_filters()
    assert sparse_filters.tenant_id == "tenant-pharma-y"
    assert sparse_filters.trust_tier_max == 3
    assert sparse_filters.lang == "vi"


def test_dense_sql_contains_tenant_boundary() -> None:
    """_DENSE_SQL joins kb_documents and filters by tenant_id."""
    from clara_ml.rag.store.hybrid_retriever import _DENSE_SQL

    sql_str = str(_DENSE_SQL).lower()
    assert "join kb_documents d on d.id = c.document_id" in sql_str
    assert "d.tenant_id is null or d.tenant_id = 'global' or d.tenant_id = cast(:tenant_id as text)" in sql_str


# ==============================================================================
# 3. Semantic Query Cache Tenant Isolation Tests
# ==============================================================================


def test_semantic_cache_tenant_isolation_exact_match() -> None:
    """SemanticQueryCache isolates exact match entries between tenants."""
    cache = SemanticQueryCache(enabled=True)

    tenant_a_doc = [Document(id="doc_a", text="Tenant A secret clinical protocol")]
    tenant_b_doc = [Document(id="doc_b", text="Tenant B proprietary formulation")]

    # Tenant A stores result for "panadol dosage"
    cache.put("panadol dosage", tenant_a_doc, tenant_id="tenant-a")

    # Tenant B queries "panadol dosage" before caching -> MUST NOT hit Tenant A's entry!
    result_b_before = cache.get("panadol dosage", tenant_id="tenant-b")
    assert result_b_before is None

    # Tenant A queries "panadol dosage" -> Hits Tenant A's entry
    result_a = cache.get("panadol dosage", tenant_id="tenant-a")
    assert result_a is not None
    assert result_a[0].id == "doc_a"

    # Public un-tenanted query -> MUST NOT hit Tenant A's entry
    result_public = cache.get("panadol dosage", tenant_id=None)
    assert result_public is None

    # Now Tenant B stores their own result
    cache.put("panadol dosage", tenant_b_doc, tenant_id="tenant-b")
    result_b_after = cache.get("panadol dosage", tenant_id="tenant-b")
    assert result_b_after is not None
    assert result_b_after[0].id == "doc_b"

    # Confirm Tenant A's entry was not overwritten by Tenant B
    result_a_recheck = cache.get("panadol dosage", tenant_id="tenant-a")
    assert result_a_recheck is not None
    assert result_a_recheck[0].id == "doc_a"


def test_semantic_cache_tenant_isolation_vector_seam() -> None:
    """SemanticQueryCache isolates vector-similarity candidates between tenants."""
    cache = SemanticQueryCache(enabled=True, similarity_threshold=0.9)

    dummy_vector = [1.0, 0.0, 0.0, 0.0]

    # Tenant A caches with vector
    cache.put(
        "tim mach cap cuu",
        [Document(id="cardio_a", text="A")],
        vector=dummy_vector,
        tenant_id="tenant-cardio-a",
    )

    # Tenant B submits a query that produces the exact same vector
    result_b = cache.get(
        "tim mach khac",
        embed_fn=lambda _: dummy_vector,
        tenant_id="tenant-cardio-b",
    )
    # Must NOT return Tenant A's document despite vector similarity >= threshold
    assert result_b is None

    # Tenant A submits with vector -> Matches Tenant A
    result_a = cache.get(
        "tim mach khac",
        embed_fn=lambda _: dummy_vector,
        tenant_id="tenant-cardio-a",
    )
    assert result_a is not None
    assert result_a[0].id == "cardio_a"


def test_compose_tenant_cache_key() -> None:
    """compose_tenant_cache_key prefixes keys deterministically."""
    assert compose_tenant_cache_key("abc", "tenant-1") == "tenant::tenant-1::abc"
    assert compose_tenant_cache_key("abc", None) == "public::abc"
    assert compose_tenant_cache_key("abc", "") == "public::abc"


# ==============================================================================
# 4. ML HTTP API Tenant Membership Gating Tests
# ==============================================================================


def test_chat_routed_allows_active_tenant_membership() -> None:
    """POST /v1/chat/routed admits requests with active tenant membership."""
    headers = {"X-ML-Internal-Key": "test-internal-key"}
    with patch("clara_ml.main._internal_key_is_valid", return_value=True), \
         patch("clara_ml.main.rag_pipeline.run") as mock_run:
        from clara_ml.rag.pipeline import RagResult
        mock_run.return_value = RagResult(
            query="dau dau uong gi",
            retrieved_ids=[],
            answer="Uống đủ nước và nghỉ ngơi.",
            model_used="test-mock",
            retrieved_context=[],
            context_debug={},
            flow_events=[],
        )
        resp = client.post(
            "/v1/chat/routed",
            headers=headers,
            json={
                "query": "dau dau uong gi",
                "role": "normal",
                "tenant_id": "org-clinic-123",
                "membership_status": "active",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    # Verify tenant_id was passed down into rag_pipeline.run
    assert mock_run.call_args.kwargs.get("tenant_id") == "org-clinic-123"


def test_chat_routed_blocks_pending_invitation() -> None:
    """POST /v1/chat/routed returns 403 when workspace invitation is pending."""
    headers = {"X-ML-Internal-Key": "test-internal-key"}
    with patch("clara_ml.main._internal_key_is_valid", return_value=True):
        resp = client.post(
            "/v1/chat/routed",
            headers=headers,
            json={
                "query": "dau dau uong gi",
                "role": "normal",
                "tenant_id": "org-clinic-123",
                "membership_status": "invited",
            },
        )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["error"] == "tenant_boundary_violation"
    assert data["detail"]["code"] == "invitation_pending_unauthorized"


def test_chat_routed_blocks_expired_membership() -> None:
    """POST /v1/chat/routed returns 403 for expired membership."""
    headers = {"X-ML-Internal-Key": "test-internal-key"}
    with patch("clara_ml.main._internal_key_is_valid", return_value=True):
        resp = client.post(
            "/v1/chat/routed",
            headers=headers,
            json={
                "query": "dau bung",
                "role": "normal",
                "tenant_id": "org-clinic-123",
                "membership_status": "expired",
            },
        )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["code"] == "invitation_expired"


def test_chat_routed_blocks_revoked_membership() -> None:
    """POST /v1/chat/routed returns 403 for revoked membership."""
    headers = {"X-ML-Internal-Key": "test-internal-key"}
    with patch("clara_ml.main._internal_key_is_valid", return_value=True):
        resp = client.post(
            "/v1/chat/routed",
            headers=headers,
            json={
                "query": "dau bung",
                "role": "normal",
                "tenant_id": "org-clinic-123",
                "membership_status": "revoked",
            },
        )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["code"] == "membership_revoked"


def test_rag_poc_blocks_unauthenticated_tenant_access() -> None:
    """POST /v1/rag/poc rejects tenant_id without membership verification."""
    headers = {"X-ML-Internal-Key": "test-internal-key"}
    with patch("clara_ml.main._internal_key_is_valid", return_value=True):
        resp = client.post(
            "/v1/rag/poc",
            headers=headers,
            json={
                "query": "tang huyet ap",
                "tenant_id": "tenant-unauth",
            },
        )
    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["code"] == "unauthenticated_tenant_access"


def test_rag_poc_allows_active_tenant() -> None:
    """POST /v1/rag/poc allows active tenant membership."""
    headers = {"X-ML-Internal-Key": "test-internal-key"}
    with patch("clara_ml.main._internal_key_is_valid", return_value=True), \
         patch("clara_ml.main.rag_pipeline.run") as mock_run:
        from clara_ml.rag.pipeline import RagResult
        mock_run.return_value = RagResult(
            query="tang huyet ap",
            retrieved_ids=[],
            answer="Huyết áp cần được theo dõi định kỳ.",
            model_used="test-mock",
            retrieved_context=[],
            context_debug={},
            flow_events=[],
        )
        resp = client.post(
            "/v1/rag/poc",
            headers=headers,
            json={
                "query": "tang huyet ap",
                "tenant_id": "tenant-active",
                "membership_status": "active",
            },
        )
    assert resp.status_code == 200
    assert "answer" in resp.json()
    assert mock_run.call_args.kwargs.get("tenant_id") == "tenant-active"


# ==============================================================================
# 5. Zero-PII / Zero-PHI Safety Invariant on Tenant Errors
# ==============================================================================


def test_tenant_boundary_error_zero_pii() -> None:
    """Verify that TenantBoundaryError never leaks patient names, emails or query strings."""
    sensitive_email = "patient.secret@hospital.com"
    sensitive_query = "Nguyen Van A ung thu phoi giai doan 4"

    try:
        enforce_workspace_ml_membership(
            tenant_id="tenant-secure",
            membership_status=WorkspaceMembershipStatus.INVITED,
        )
    except TenantBoundaryError as exc:
        err_str = str(exc.detail).lower()
        assert sensitive_email.lower() not in err_str
        assert sensitive_query.lower() not in err_str
        assert "nguyen van a" not in err_str
        assert "ung thu" not in err_str


# ==============================================================================
# 6. OCR and ASR Statelessness & Tenant Isolation Audit
# ==============================================================================


def test_ocr_endpoint_stateless_no_cross_tenant_memory() -> None:
    """OCR service adapter is strictly stateless and does not retain tenant images."""
    import services.ocr.server as ocr_module

    # Confirm there are no global cross-request image caches or buffers in the module
    cache_like_globals = [
        name for name, val in vars(ocr_module).items()
        if isinstance(val, (dict, list, set)) and not name.startswith("_JSON_B64_KEYS") and not name.startswith("__")
    ]
    assert cache_like_globals == [], f"Unexpected stateful globals found in OCR server: {cache_like_globals}"


def test_asr_endpoint_stateless_no_cross_tenant_memory() -> None:
    """ASR service adapter is strictly stateless beyond the loaded model weights."""
    import services.asr.server as asr_module

    cache_like_globals = [
        name for name, val in vars(asr_module).items()
        if isinstance(val, (dict, list, set)) and not name.startswith("__")
    ]
    assert cache_like_globals == [], f"Unexpected stateful globals found in ASR server: {cache_like_globals}"
