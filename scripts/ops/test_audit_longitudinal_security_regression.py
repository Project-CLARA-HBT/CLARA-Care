#!/usr/bin/env python3
"""Tests for Longitudinal Data Security & Privacy Regression Auditor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
import pytest

# Ensure repo root, API source, and scripts/ops are in sys.path
_repo_root = Path(__file__).resolve().parents[2]
_api_src = _repo_root / "services/api/src"
_scripts_ops = _repo_root / "scripts/ops"
for _p in (str(_repo_root), str(_api_src), str(_scripts_ops)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from audit_longitudinal_security_regression import (
    LongitudinalSecurityAuditor,
    LongitudinalSecurityFinding,
)

from clara_api.lifemap.temporal_index import (
    RetrievalBoundaryError,
    RetrievalDocument,
    TemporalRetrievalIndex,
)
from clara_api.lifemap.intelligence import route_ask_query


@pytest.fixture
def repo_root() -> Path:
    """Detect repo root relative to this test file."""
    return Path(__file__).resolve().parents[2]


def test_auditor_clean_run_passes(repo_root: Path) -> None:
    """Auditor against clean production repository yields zero findings."""
    auditor = LongitudinalSecurityAuditor(repo_root=repo_root)
    findings = auditor.audit_all(verify_runtime=True)
    high_or_crit = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]
    assert len(high_or_crit) == 0, f"Unexpected high/critical findings: {high_or_crit}"
    assert len(findings) == 0, f"Unexpected findings: {findings}"


def test_auditor_detects_missing_profile_scope(repo_root: Path, tmp_path: Path) -> None:
    """Auditor detects missing ProfileScope or profile predicate in timeline endpoint."""
    fake_endpoints_dir = tmp_path / "services/api/src/clara_api/api/v1/endpoints"
    fake_endpoints_dir.mkdir(parents=True)
    fake_endpoints = fake_endpoints_dir / "lifemap.py"
    fake_endpoints.write_text(
        """
@router.get("/timeline")
def lifemap_timeline(db: Session = Depends(get_db)):
    # Flawed implementation without _scope or ProfileScope
    query = select(LifeMapEvent)
    return db.execute(query).scalars().all()
""",
        encoding="utf-8",
    )

    auditor = LongitudinalSecurityAuditor(repo_root=tmp_path)
    auditor._audit_profile_scope_enforcement()
    rule_ids = {f.rule_id for f in auditor.findings}
    assert "RULE_PROFILE_SCOPE_ENFORCEMENT" in rule_ids
    assert any(f.severity == "CRITICAL" for f in auditor.findings)


def test_auditor_detects_unpartitioned_temporal_index(tmp_path: Path) -> None:
    """Auditor flags a temporal index that does not partition by profile."""
    fake_lifemap_dir = tmp_path / "services/api/src/clara_api/lifemap"
    fake_lifemap_dir.mkdir(parents=True)
    fake_index = fake_lifemap_dir / "temporal_index.py"
    fake_index.write_text(
        """
class TemporalRetrievalIndex:
    def __init__(self):
        # Flawed: unpartitioned flat dictionary
        self._all_docs = {}
""",
        encoding="utf-8",
    )

    auditor = LongitudinalSecurityAuditor(repo_root=tmp_path)
    auditor._audit_temporal_index_partitioning()
    rule_ids = {f.rule_id for f in auditor.findings}
    assert "RULE_TEMPORAL_INDEX_PARTITIONING" in rule_ids


def test_auditor_detects_missing_reranker_escape_check(tmp_path: Path) -> None:
    """Auditor detects when reranker candidate escape validation is missing."""
    fake_lifemap_dir = tmp_path / "services/api/src/clara_api/lifemap"
    fake_lifemap_dir.mkdir(parents=True)
    fake_index = fake_lifemap_dir / "temporal_index.py"
    fake_index.write_text(
        """
class TemporalRetrievalIndex:
    def search(self, reranker=None):
        if reranker is not None:
            # Flawed: blindly trusts reranker output without containment check
            return reranker(hits)
""",
        encoding="utf-8",
    )

    auditor = LongitudinalSecurityAuditor(repo_root=tmp_path)
    auditor._audit_reranker_sandbox()
    rule_ids = {f.rule_id for f in auditor.findings}
    assert "RULE_RERANKER_CANDIDATE_SANDBOX" in rule_ids


def test_auditor_detects_missing_projection_cycle_bounding(tmp_path: Path) -> None:
    """Auditor flags projection invalidation missing visited set for cycle termination."""
    fake_lifemap_dir = tmp_path / "services/api/src/clara_api/lifemap"
    fake_lifemap_dir.mkdir(parents=True)
    fake_inval = fake_lifemap_dir / "projection_invalidation.py"
    fake_inval.write_text(
        """
def invalidate_projection_graph(db, *, profile_id, reason):
    # Flawed: recursive traversal without visited set
    queue = deque()
    while queue:
        item = queue.popleft()
        queue.extend(get_children(item))
""",
        encoding="utf-8",
    )

    auditor = LongitudinalSecurityAuditor(repo_root=tmp_path)
    auditor._audit_projection_invalidation_logic()
    rule_ids = {f.rule_id for f in auditor.findings}
    assert "RULE_PROJECTION_INVALIDATION_RECURSION" in rule_ids


def test_auditor_detects_missing_capture_artifact_deletion(tmp_path: Path) -> None:
    """Auditor flags capture cleanup when physical artifact deletion is absent."""
    fake_lifemap_dir = tmp_path / "services/api/src/clara_api/lifemap"
    fake_lifemap_dir.mkdir(parents=True)
    fake_cleanup = fake_lifemap_dir / "capture_cleanup.py"
    fake_cleanup.write_text(
        """
def expire_capture_drafts(db, *, store, now=None, batch_size=100):
    if batch_size < 1 or batch_size > 1000:
        raise ValueError()
    # Flawed: sets session status to expired without store.delete()
    session.status = "expired"
""",
        encoding="utf-8",
    )

    auditor = LongitudinalSecurityAuditor(repo_root=tmp_path)
    auditor._audit_capture_cleanup_and_artifact_deletion()
    rule_ids = {f.rule_id for f in auditor.findings}
    assert "RULE_CAPTURE_DRAFT_RETENTION_EXPIRY" in rule_ids


def test_auditor_detects_weakened_statutory_retention(tmp_path: Path) -> None:
    """Auditor flags compliance retention policy when compliance_event retention is reduced."""
    fake_compliance_dir = tmp_path / "services/api/src/clara_api/compliance"
    fake_compliance_dir.mkdir(parents=True)
    fake_retention = fake_compliance_dir / "retention.py"
    fake_retention.write_text(
        """
RETENTION_POLICY = (
    RetentionCategory(
        category="compliance_event",
        retention_days=30, # FLAWED: reduced from 3650
        basis="legal defensibility",
        action=ACTION_DELETE, # FLAWED: changed from retain
    ),
)
""",
        encoding="utf-8",
    )

    auditor = LongitudinalSecurityAuditor(repo_root=tmp_path)
    auditor._audit_statutory_retention_policy()
    rule_ids = {f.rule_id for f in auditor.findings}
    assert "RULE_STATUTORY_RETENTION_BOUNDARIES" in rule_ids


def test_runtime_temporal_retrieval_isolation() -> None:
    """Verifies in-memory cross-profile non-interference in TemporalRetrievalIndex."""
    index = TemporalRetrievalIndex()

    now = datetime.now(UTC)
    doc_patient_a = RetrievalDocument(
        document_id="doc-a-1",
        profile_partition="patient-alpha",
        revision_id="rev-a1",
        source_type="event",
        effective_start=now - timedelta(days=10),
        effective_end=None,
        recorded_at=now,
        episode_ids=frozenset({"ep-a"}),
        truth_state="confirmed",
        data_class="vitals",
        language="vi",
        terms=frozenset({"huyet_ap", "cao"}),
        embedding=(0.9, 0.1),
        graph_entities=frozenset({"hypertension"}),
    )

    doc_patient_b = RetrievalDocument(
        document_id="doc-b-1",
        profile_partition="patient-beta",
        revision_id="rev-b1",
        source_type="event",
        effective_start=now - timedelta(days=5),
        effective_end=None,
        recorded_at=now,
        episode_ids=frozenset({"ep-b"}),
        truth_state="confirmed",
        data_class="vitals",
        language="vi",
        terms=frozenset({"huyet_ap", "cao"}),
        embedding=(0.9, 0.1),
        graph_entities=frozenset({"hypertension"}),
    )

    index.upsert(doc_patient_a)
    index.upsert(doc_patient_b)

    # Search in Patient A's partition
    hits_a = index.search(
        profile_partition="patient-alpha",
        allowed_data_classes=frozenset({"vitals"}),
        query_terms=frozenset({"huyet_ap"}),
    )
    doc_ids_a = [h.document.document_id for h in hits_a]
    assert "doc-a-1" in doc_ids_a
    assert "doc-b-1" not in doc_ids_a

    # Search in Patient B's partition
    hits_b = index.search(
        profile_partition="patient-beta",
        allowed_data_classes=frozenset({"vitals"}),
        query_terms=frozenset({"huyet_ap"}),
    )
    doc_ids_b = [h.document.document_id for h in hits_b]
    assert "doc-b-1" in doc_ids_b
    assert "doc-a-1" not in doc_ids_b

    # Search in an empty/non-existent partition
    hits_c = index.search(
        profile_partition="patient-gamma",
        allowed_data_classes=frozenset({"vitals"}),
        query_terms=frozenset({"huyet_ap"}),
    )
    assert len(hits_c) == 0


def test_runtime_reranker_boundary_enforcement() -> None:
    """Verifies reranker cannot escape candidate set or duplicate document IDs."""
    index = TemporalRetrievalIndex()
    now = datetime.now(UTC)

    doc = RetrievalDocument(
        document_id="valid-doc-1",
        profile_partition="patient-1",
        revision_id="rev-1",
        source_type="event",
        effective_start=now,
        effective_end=None,
        recorded_at=now,
        episode_ids=frozenset({"ep-1"}),
        truth_state="confirmed",
        data_class="lifemap",
        language="vi",
        terms=frozenset({"ho"}),
        embedding=(1.0, 0.0),
        graph_entities=frozenset({"cough"}),
    )
    index.upsert(doc)

    # Valid reranker that preserves or reorders candidates
    valid_hits = index.search(
        profile_partition="patient-1",
        allowed_data_classes=frozenset({"lifemap"}),
        query_terms=frozenset({"ho"}),
        reranker=lambda hits: tuple(h.document.document_id for h in hits),
    )
    assert len(valid_hits) == 1
    assert valid_hits[0].document.document_id == "valid-doc-1"

    # Malicious/invalid reranker returning foreign document ID
    with pytest.raises(RetrievalBoundaryError, match="reranker_escaped_candidate_set"):
        index.search(
            profile_partition="patient-1",
            allowed_data_classes=frozenset({"lifemap"}),
            query_terms=frozenset({"ho"}),
            reranker=lambda _hits: ("injected-foreign-doc-id",),
        )

    # Reranker returning duplicate IDs
    with pytest.raises(RetrievalBoundaryError, match="reranker_escaped_candidate_set"):
        index.search(
            profile_partition="patient-1",
            allowed_data_classes=frozenset({"lifemap"}),
            query_terms=frozenset({"ho"}),
            reranker=lambda _hits: ("valid-doc-1", "valid-doc-1"),
        )


def test_runtime_route_ask_query_emergency_and_forbidden() -> None:
    """Verifies Ask My LifeMap heuristic route handles emergencies and blocks diagnoses."""
    # Emergency cases in Vietnamese and English
    acute_vi = route_ask_query("Bệnh nhân khó thở, không thở được và đau ngực dữ dội")
    assert acute_vi.emergency is True
    assert acute_vi.intent == "timeline_lookup"

    acute_en = route_ask_query("Severe chest pain and cannot breathe")
    assert acute_en.emergency is True

    # Forbidden diagnosis requests
    diag_vi = route_ask_query("Hãy chẩn đoán cho tôi tôi bị bệnh gì và kê đơn thuốc")
    assert diag_vi.blocked_reason == "legal_guard"

    diag_en = route_ask_query("Diagnose me and tell me my dosage")
    assert diag_en.blocked_reason == "legal_guard"

    # Normal timeline and comparison queries
    timeline_query = route_ask_query("Lịch sử đo huyết áp tuần trước thế nào?")
    assert timeline_query.emergency is False
    assert timeline_query.blocked_reason == ""

    compare_query = route_ask_query("So sánh chỉ số đường huyết tháng này và tháng trước")
    assert compare_query.intent == "comparison"
    assert compare_query.emergency is False
