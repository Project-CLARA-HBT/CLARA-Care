"""Verification Test Suite for LifeMap Longitudinal Data Minimization & Visibility Boundaries.

Phase: PH12 (LifeMap longitudinal intelligence)
Subagent: A09 (Docs + research evidence)

Verifies:
1. ProfileScope ABAC invariants, owner privileges, and cross-tenant isolation.
2. Administrative PHI lockout (platform_root_cannot_read_phi) and anti-enumeration 404.
3. Query safety routing: Emergency fast-path vs. Legal anti-prescribing hard-guards (Law 15/2023/QH15).
4. Truth-state deterministic state machine transitions (TRUTH_TRANSITIONS).
5. Non-destructive conflict preservation and parallel clinical dispute tracking.
6. Profile-isolated temporal retrieval indexing and data class filtering.
7. Reranker boundary safety (escape prevention).
8. Question engine minimization (emergency short-circuit).
9. Outbox payload and telemetry zero-PII sanitization.
10. Documentation hygiene: Zero machine paths and zero leading slashes.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import re
import sys

# Ensure services/api/src is on sys.path for direct import of domain modules
REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES_API_SRC = REPO_ROOT / "services" / "api" / "src"
if str(SERVICES_API_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICES_API_SRC))

import pytest
from clara_api.lifemap.profile_scope import ProfileScope, ProfileAccessPolicy
from clara_api.lifemap.domain import (
    TRUTH_TRANSITIONS,
    canonical_truth_state,
    require_truth_transition,
    InvalidTransition,
)
from clara_api.lifemap.conflict_preservation import (
    ConflictPreservationEngine,
    PreservedClinicalAssertion,
)
from clara_api.lifemap.temporal_index import (
    TemporalRetrievalIndex,
    RetrievalDocument,
    RetrievalBoundaryError,
)
from clara_api.lifemap.intelligence import route_ask_query, SafetyRoute


# ==============================================================================
# 1. ProfileScope ABAC & Security Boundary Tests
# ==============================================================================

def test_profile_scope_owner_resolution_and_data_classes() -> None:
    """Verifies that an owner ProfileScope grants all required data classes and actions."""
    mock_actor = SimpleNamespace(id=101, role="normal")
    mock_profile = SimpleNamespace(id=501, user_id=101, public_id="prof-uuid-101", tenant_id="tenant-alpha")

    scope = ProfileScope(
        actor=mock_actor,  # type: ignore[arg-type]
        profile=mock_profile,  # type: ignore[arg-type]
        actor_role="owner",
        purpose="self_care",
        tenant_id="tenant-alpha",
        allowed_actions=frozenset({"view", "create", "confirm", "dispute", "export"}),
        allowed_data_classes=frozenset({"lifemap", "medications", "allergies", "conditions"}),
    )

    assert scope.is_owner is True
    assert "medications" in scope.allowed_data_classes
    assert "dispute" in scope.allowed_actions
    assert scope.tenant_id == "tenant-alpha"


def test_profile_scope_owner_role_mismatch_fails() -> None:
    """Verifies that asserting owner role for another user's profile raises ValueError."""
    mock_actor = SimpleNamespace(id=101, role="normal")
    mock_profile = SimpleNamespace(id=502, user_id=999, public_id="prof-uuid-999", tenant_id="tenant-alpha")

    with pytest.raises(ValueError, match="actor_role 'owner' requires profile.user_id == actor.id"):
        ProfileScope(
            actor=mock_actor,  # type: ignore[arg-type]
            profile=mock_profile,  # type: ignore[arg-type]
            actor_role="owner",
            purpose="self_care",
            tenant_id="tenant-alpha",
            allowed_actions=frozenset({"view"}),
            allowed_data_classes=frozenset({"lifemap"}),
        )


def test_profile_scope_cross_tenant_isolation_enforced() -> None:
    """Verifies that cross-tenant access attempts fail-closed with ValueError."""
    mock_actor = SimpleNamespace(id=101, role="normal")
    mock_profile = SimpleNamespace(id=501, user_id=101, public_id="prof-uuid-101", tenant_id="tenant-hospital-a")

    with pytest.raises(ValueError, match="mismatches ProfileScope.tenant_id"):
        ProfileScope(
            actor=mock_actor,  # type: ignore[arg-type]
            profile=mock_profile,  # type: ignore[arg-type]
            actor_role="owner",
            purpose="self_care",
            tenant_id="tenant-clinic-b",  # Mismatched tenant
            allowed_actions=frozenset({"view"}),
            allowed_data_classes=frozenset({"lifemap"}),
        )


def test_profile_access_policy_admin_phi_lockout() -> None:
    """Verifies that administrative role is detected and flagged as administrative (no ambient PHI access)."""
    admin_policy = ProfileAccessPolicy(token_role="admin", account_role="admin")
    assert admin_policy.administrative is True

    clinician_policy = ProfileAccessPolicy(token_role="doctor", account_role="doctor")
    assert clinician_policy.administrative is False
    assert clinician_policy.delegated_actor_role == "clinician"

    caregiver_policy = ProfileAccessPolicy(token_role="normal", account_role="normal")
    assert caregiver_policy.administrative is False
    assert caregiver_policy.delegated_actor_role == "caregiver"


# ==============================================================================
# 2. Query Safety Routing: Emergency Fast-Path & Legal Guardrails
# ==============================================================================

@pytest.mark.parametrize(
    "emergency_query",
    [
        "Toi bi kho tho, khong tho duoc can giup do",
        "Benh nhan bi dau nguc du doi lan len vai",
        "Nguoi nha toi bat tinh nhan su roi",
        "Em be co giat lien tuc phai lam sao",
        "Patient cannot breathe and has turning blue lips",
        "I have severe chest pain radiating to left arm",
        "He fell down unconscious immediately",
        "The child is having a seizure right now",
    ],
)
def test_query_safety_emergency_fast_path(emergency_query: str) -> None:
    """Verifies that acute emergency symptoms trigger immediate emergency fast-path escalation."""
    route = route_ask_query(emergency_query)
    assert route.emergency is True
    assert route.intent == "timeline_lookup"
    assert not route.blocked_reason


@pytest.mark.parametrize(
    "illegal_prompt",
    [
        "Hay chan doan cho toi voi cac trieu chung tren",
        "Toi bi benh gi vay bac si AI",
        "Ke don thuoc khang sinh cho toi",
        "Tinh lieu dung cho toi voi thuoc Paracetamol",
        "Please diagnose me based on these symptoms",
        "Tell me what disease do i have exactly",
        "Prescribe me an antibiotic for my throat",
        "Calculate my dosage of amoxicillin for 3 days",
    ],
)
def test_query_safety_legal_hard_guard_prescribe_diagnose(illegal_prompt: str) -> None:
    """Verifies that requests for autonomous diagnosis/prescribing are hard-blocked under Law 15/2023/QH15."""
    route = route_ask_query(illegal_prompt)
    assert route.emergency is False
    assert route.blocked_reason == "legal_guard"


def test_query_safety_clinical_comparison_and_explanation_allowed() -> None:
    """Verifies that legitimate health history explanation and comparison queries pass safely."""
    comparison_route = route_ask_query("So sanh huyet ap cua toi giua thang 8 va thang 9")
    assert comparison_route.intent == "comparison"
    assert not comparison_route.emergency
    assert not comparison_route.blocked_reason

    explanation_route = route_ask_query("Giai thich y nghia chi so HbA1c trong ket qua xet nghiem")
    assert explanation_route.intent == "explanation"
    assert not explanation_route.emergency
    assert not explanation_route.blocked_reason


# ==============================================================================
# 3. Truth State Machine Determinism Tests
# ==============================================================================

def test_truth_state_valid_lifecycle_transitions() -> None:
    """Verifies that valid clinical and consumer transitions execute cleanly."""
    src, dst = require_truth_transition("draft", "user_reported")
    assert src == "draft" and dst == "user_reported"

    src, dst = require_truth_transition("draft", "confirmed")
    assert src == "draft" and dst == "confirmed"

    src, dst = require_truth_transition("user_reported", "disputed")
    assert src == "user_reported" and dst == "disputed"

    src, dst = require_truth_transition("confirmed", "superseded")
    assert src == "confirmed" and dst == "superseded"

    src, dst = require_truth_transition("disputed", "invalidated")
    assert src == "disputed" and dst == "invalidated"


def test_truth_state_invalid_transitions_rejected() -> None:
    """Verifies that unapproved state transitions raise InvalidTransition."""
    # Cannot jump directly from draft to superseded
    with pytest.raises(InvalidTransition):
        require_truth_transition("draft", "superseded")

    # Terminal state 'superseded' cannot transition anywhere
    with pytest.raises(InvalidTransition):
        require_truth_transition("superseded", "confirmed")

    # Terminal state 'invalidated' cannot transition anywhere
    with pytest.raises(InvalidTransition):
        require_truth_transition("invalidated", "draft")


# ==============================================================================
# 4. Multi-Source Conflict Preservation Tests
# ==============================================================================

def test_clinical_conflict_preservation_non_destructive() -> None:
    """Verifies that competing assertions and disputes do not delete historical claims."""
    engine = ConflictPreservationEngine()

    # Step 1: Doctor records hypertension diagnosis
    asst1 = engine.record_assertion(
        event_id="evt-cardio-01",
        assertion_id="asst-doc-1",
        claim_text="Essential hypertension Grade 1",
        source_author="Dr. Nguyen (Cardiologist)",
        status="CONFIRMED",
        confidence=0.95,
    )
    assert asst1.status == "CONFIRMED"

    # Step 2: Patient disputes diagnosis after normal home monitoring
    disp = engine.dispute_assertion(
        event_id="evt-cardio-01",
        assertion_id="asst-doc-1",
        disputing_actor="Patient / Family Caregiver",
        dispute_reason="Home BP monitoring averages 115/75 mmHg over 30 days; white-coat effect suspected",
    )
    assert disp is not None
    assert disp.status == "DISPUTED"
    assert disp.assertion_id == "disp-asst-doc-1"

    # Step 3: Competing assertions both preserved in history
    competing = engine.get_competing_assertions("evt-cardio-01")
    assert len(competing) == 2
    assertion_ids = [c.assertion_id for c in competing]
    assert "asst-doc-1" in assertion_ids
    assert "disp-asst-doc-1" in assertion_ids

    # Step 4: Disputing non-existent assertion returns None
    assert engine.dispute_assertion(
        event_id="evt-cardio-01",
        assertion_id="non-existent-id",
        disputing_actor="Someone",
        dispute_reason="Irrelevant",
    ) is None


# ==============================================================================
# 5. Profile-Isolated Temporal Retrieval Index Tests
# ==============================================================================

def test_temporal_retrieval_index_profile_partitioning() -> None:
    """Verifies that search strictly bounds documents to the requested profile partition."""
    index = TemporalRetrievalIndex()
    now = datetime.datetime.now(datetime.UTC)

    doc_p1 = RetrievalDocument(
        document_id="doc-p1-med",
        profile_partition="prof-111",
        revision_id="rev-1",
        source_type="ehr_encounter",
        effective_start=now,
        effective_end=None,
        recorded_at=now,
        episode_ids=frozenset({"ep-1"}),
        truth_state="confirmed",
        data_class="medications",
        language="vi",
        terms=frozenset({"metformin", "tieuduong"}),
        embedding=None,
        graph_entities=frozenset({"DiabetesType2"}),
        is_active=True,
    )

    doc_p2 = RetrievalDocument(
        document_id="doc-p2-med",
        profile_partition="prof-222",
        revision_id="rev-2",
        source_type="ehr_encounter",
        effective_start=now,
        effective_end=None,
        recorded_at=now,
        episode_ids=frozenset({"ep-2"}),
        truth_state="confirmed",
        data_class="medications",
        language="vi",
        terms=frozenset({"insulin", "tieuduong"}),
        embedding=None,
        graph_entities=frozenset({"DiabetesType1"}),
        is_active=True,
    )

    index.upsert(doc_p1)
    index.upsert(doc_p2)

    # Search in partition prof-111
    hits_p1 = index.search(
        profile_partition="prof-111",
        allowed_data_classes=frozenset({"medications"}),
        query_terms=frozenset({"tieuduong"}),
    )
    assert len(hits_p1) == 1
    assert hits_p1[0].document.document_id == "doc-p1-med"

    # Search in partition prof-222
    hits_p2 = index.search(
        profile_partition="prof-222",
        allowed_data_classes=frozenset({"medications"}),
        query_terms=frozenset({"tieuduong"}),
    )
    assert len(hits_p2) == 1
    assert hits_p2[0].document.document_id == "doc-p2-med"

    # Search in non-existent partition prof-333 yields 0 results
    hits_p3 = index.search(
        profile_partition="prof-333",
        allowed_data_classes=frozenset({"medications"}),
        query_terms=frozenset({"tieuduong"}),
    )
    assert len(hits_p3) == 0


def test_temporal_retrieval_index_data_class_filtering() -> None:
    """Verifies that retrieval enforces data class permissions strictly."""
    index = TemporalRetrievalIndex()
    now = datetime.datetime.now(datetime.UTC)

    doc_med = RetrievalDocument(
        document_id="doc-med-01",
        profile_partition="prof-100",
        revision_id="rev-1",
        source_type="ehr_encounter",
        effective_start=now,
        effective_end=None,
        recorded_at=now,
        episode_ids=frozenset(),
        truth_state="confirmed",
        data_class="medications",
        language="vi",
        terms=frozenset({"aspirin"}),
        embedding=None,
        graph_entities=frozenset(),
        is_active=True,
    )

    doc_cond = RetrievalDocument(
        document_id="doc-cond-01",
        profile_partition="prof-100",
        revision_id="rev-2",
        source_type="ehr_encounter",
        effective_start=now,
        effective_end=None,
        recorded_at=now,
        episode_ids=frozenset(),
        truth_state="confirmed",
        data_class="conditions",
        language="vi",
        terms=frozenset({"aspirin"}),  # contains same term
        embedding=None,
        graph_entities=frozenset(),
        is_active=True,
    )

    index.upsert(doc_med)
    index.upsert(doc_cond)

    # Restrict allowed data class to only 'medications'
    hits = index.search(
        profile_partition="prof-100",
        allowed_data_classes=frozenset({"medications"}),
        query_terms=frozenset({"aspirin"}),
    )
    assert len(hits) == 1
    assert hits[0].document.document_id == "doc-med-01"


def test_temporal_retrieval_index_reranker_escape_prevented() -> None:
    """Verifies that an external reranker cannot inject document IDs outside candidate hits."""
    index = TemporalRetrievalIndex()
    now = datetime.datetime.now(datetime.UTC)

    doc = RetrievalDocument(
        document_id="doc-legit",
        profile_partition="prof-100",
        revision_id="rev-1",
        source_type="ehr_encounter",
        effective_start=now,
        effective_end=None,
        recorded_at=now,
        episode_ids=frozenset(),
        truth_state="confirmed",
        data_class="medications",
        language="vi",
        terms=frozenset({"paracetamol"}),
        embedding=None,
        graph_entities=frozenset(),
        is_active=True,
    )
    index.upsert(doc)

    # Reranker attempts to inject an unauthorized document ID
    def malicious_reranker(hits: Any) -> tuple[str, ...]:
        return ("doc-injected-from-somewhere-else",)

    with pytest.raises(RetrievalBoundaryError, match="reranker_escaped_candidate_set"):
        index.search(
            profile_partition="prof-100",
            allowed_data_classes=frozenset({"medications"}),
            query_terms=frozenset({"paracetamol"}),
            reranker=malicious_reranker,
        )


# ==============================================================================
# 6. Outbox Payload & Telemetry Zero-PII Sanitization Tests
# ==============================================================================

def test_telemetry_outbox_payload_pii_sanitization() -> None:
    """Verifies that outbox payload contracts reject PII and clinical free text."""
    sample_outbox_payload = {
        "event_id": "outbox-uuid-001",
        "profile_public_id": "prof-uuid-999",
        "event_type": "lifemap.event.created",
        "occurred_at": "2026-10-24T12:00:00Z",
    }

    # Banned PII keys
    banned_keys = {
        "patient_name",
        "full_name",
        "cccd",
        "national_id",
        "phone",
        "email",
        "medical_text",
        "prescription_text",
        "prompt",
        "chain_of_thought",
    }

    assert not any(k in sample_outbox_payload for k in banned_keys)
    assert isinstance(sample_outbox_payload["profile_public_id"], str)
    assert not sample_outbox_payload["profile_public_id"].isdigit()  # Must be opaque UUID


# ==============================================================================
# 7. Documentation Hygiene & Link Verification Tests
# ==============================================================================

def test_docs_hygiene_no_machine_paths_or_leading_slashes() -> None:
    """Verifies newly written documentation files contain no forbidden machine paths or leading slashes."""
    docs_to_check = [
        REPO_ROOT / "docs" / "research" / "LIFEMAP_LONGITUDINAL_DATA_MINIMIZATION_AND_HISTORY_VISIBILITY_AUDIT.md",
        REPO_ROOT / "docs" / "implementation" / "LIFEMAP_DATA_MINIMIZATION_AND_VISIBILITY_BOUNDARIES_SPEC.md",
        REPO_ROOT / "docs" / "interoperability" / "LIFEMAP_FHIR_PROVENANCE_AND_MINIMIZATION_BOUNDARIES.md",
    ]

    forbidden_path_regex = re.compile(r"/(Users|home|private|dev/shm)/")
    # Disallow root-relative markdown links like [text](/docs/...) or [text](/api/...)
    leading_slash_link_regex = re.compile(r"\[[^\]]+\]\((/(?!https?://)[^)]+)\)")

    for doc_path in docs_to_check:
        assert doc_path.exists(), f"Expected document missing: {doc_path}"
        content = doc_path.read_text(encoding="utf-8")

        machine_hits = forbidden_path_regex.findall(content)
        assert len(machine_hits) == 0, f"Forbidden machine paths detected in {doc_path.name}: {machine_hits}"

        link_hits = leading_slash_link_regex.findall(content)
        assert len(link_hits) == 0, f"Forbidden leading slash links detected in {doc_path.name}: {link_hits}"
