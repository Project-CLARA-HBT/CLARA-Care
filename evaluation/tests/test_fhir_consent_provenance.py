"""Focused Unit and Concurrency Test Suite for FHIR R4 Consent and Provenance Mapping.

Phase: PH11 / Subagent: A04 (ML + Retrieval).
Covers:
1. Allow, deny, malformed, expired, missing, and mismatched FHIR Consent evaluation.
2. Statutory Vietnamese compliance gates (Decree 13/2023 cross-border, Circular 46/2018 EMR).
3. Bidirectional mapping between FHIR Consent and CLARA PolicyEpoch.
4. FHIR R4 Provenance mapping for Model Inference, Scribe SOAP transcripts, and Research Tier-2.
5. Anti-downgrade attestation lineage verification on FHIR Provenance.
6. Statutory PII/PHI redaction verification.
7. Feature flag gating and fail-closed safety invariants.
8. Concurrent execution under multi-threaded load.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import hashlib
import pytest
from clara_ml.attested_dispatch import AttestedDispatchResult
from clara_ml.fhir_consent_provenance import (
    ConsentEnforcementError,
    ConsentEvaluationResult,
    FhirConsentEnforcer,
    FhirConsentGate,
    FhirConsentPurpose,
    FhirProvenanceMapper,
)
from clara_ml.llm.model_gateway import ModelRunProvenance
from clara_ml.policy_epoch import PolicyEpoch
from clara_ml.scribe.provenance import SpanRegistry


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def valid_fhir_consent() -> dict:
    """Fixture providing an active, multi-purpose FHIR R4 Consent resource."""
    now = datetime.datetime.now(datetime.UTC)
    return {
        "resourceType": "Consent",
        "id": "consent-pat-001-v1",
        "status": "active",
        "scope": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                    "code": "patient-privacy",
                }
            ]
        },
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/consentcategorycodes",
                        "code": "npp",
                    }
                ]
            }
        ],
        "patient": {"reference": "Patient/pat-001"},
        "dateTime": now.isoformat(),
        "organization": [{"reference": "Organization/hospital-bach-mai"}],
        "policy": [
            {"authority": "https://chinhphu.vn", "uri": "https://clara.care/compliance/decree-13-2023-nd-cp"}
        ],
        "policyRule": {"text": "Decree 13/2023/ND-CP"},
        "provision": {
            "type": "permit",
            "period": {
                "start": (now - datetime.timedelta(days=1)).isoformat(),
                "end": (now + datetime.timedelta(days=364)).isoformat(),
            },
            "purpose": [
                {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "TREAT"},
                {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HRES"},
                {"system": "https://clara.care/fhir/consent-purpose", "code": "ai_transparency"},
                {"system": "https://clara.care/fhir/consent-purpose", "code": "cross_border_processing"},
                {"system": "https://clara.care/fhir/consent-purpose", "code": "scribe_transcription"},
            ],
            "provision": [
                {
                    "type": "deny",
                    "purpose": [
                        {"system": "https://clara.care/fhir/consent-purpose", "code": "commercial_marketing"}
                    ],
                }
            ],
        },
    }


@pytest.fixture
def sample_model_provenance() -> ModelRunProvenance:
    return ModelRunProvenance(
        run_id="run-test-1234",
        task="clinical_synthesis",
        route_class="Tier2Research",
        provider_id="deepseek",
        deployment_model="deepseek-reasoner",
        prompt_version="v2.1",
        schema_version="1.0.0",
        context_digest="sha256:d8b74a3f2c5e6d1a9b8c7e4f3a2b1c0d",
        latency_ms=845.2,
        safety_outcome="SAFE",
        status="success",
        timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
        token_usage={"prompt_tokens": 512, "completion_tokens": 128},
    )


# ==============================================================================
# 1. Consent Parsing and Validation Tests
# ==============================================================================

def test_parse_valid_consent(valid_fhir_consent: dict) -> None:
    parsed = FhirConsentEnforcer.parse_consent_resource(valid_fhir_consent)
    assert parsed["consent_id"] == "consent-pat-001-v1"
    assert parsed["status"] == "active"
    assert parsed["patient_id"] == "pat-001"
    assert FhirConsentPurpose.CORE_SERVICE in parsed["permitted_purposes"]
    assert FhirConsentPurpose.RESEARCH in parsed["permitted_purposes"]
    assert FhirConsentPurpose.CROSS_BORDER in parsed["permitted_purposes"]
    assert "commercial_marketing" in parsed["denied_purposes"]


def test_parse_malformed_consent_fails() -> None:
    with pytest.raises(Exception):
        FhirConsentEnforcer.parse_consent_resource({"resourceType": "Observation"})

    with pytest.raises(Exception):
        FhirConsentEnforcer.parse_consent_resource({"resourceType": "Consent", "status": "unknown_status"})


# ==============================================================================
# 2. Allow, Deny, Malformed, Missing, and Expired Enforcement Tests
# ==============================================================================

def test_consent_allow_active_purpose(valid_fhir_consent: dict) -> None:
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=valid_fhir_consent,
        user_id="pat-001",
        requested_purpose="core_service",
    )
    assert result.allowed is True
    assert result.status_code == "ALLOWED"
    assert result.user_id == "pat-001"


def test_consent_missing_fail_closed() -> None:
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=None,
        user_id="pat-001",
        requested_purpose="core_service",
    )
    assert result.allowed is False
    assert result.status_code == "ERR_CONSENT_MISSING"


def test_consent_patient_mismatch(valid_fhir_consent: dict) -> None:
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=valid_fhir_consent,
        user_id="pat-999",  # Different patient
        requested_purpose="core_service",
    )
    assert result.allowed is False
    assert result.status_code == "ERR_PATIENT_MISMATCH"


def test_consent_not_active(valid_fhir_consent: dict) -> None:
    inactive_consent = dict(valid_fhir_consent)
    inactive_consent["status"] = "inactive"
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=inactive_consent,
        user_id="pat-001",
        requested_purpose="core_service",
    )
    assert result.allowed is False
    assert result.status_code == "ERR_CONSENT_NOT_ACTIVE"


def test_consent_expired(valid_fhir_consent: dict) -> None:
    now = datetime.datetime.now(datetime.UTC)
    expired_consent = dict(valid_fhir_consent)
    expired_consent["provision"] = dict(valid_fhir_consent["provision"])
    expired_consent["provision"]["period"] = {
        "start": (now - datetime.timedelta(days=60)).isoformat(),
        "end": (now - datetime.timedelta(days=1)).isoformat(),  # Expired yesterday
    }
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=expired_consent,
        user_id="pat-001",
        requested_purpose="core_service",
        execution_timestamp=now,
    )
    assert result.allowed is False
    assert result.status_code == "ERR_CONSENT_EXPIRED"


def test_consent_not_yet_valid(valid_fhir_consent: dict) -> None:
    now = datetime.datetime.now(datetime.UTC)
    future_consent = dict(valid_fhir_consent)
    future_consent["provision"] = dict(valid_fhir_consent["provision"])
    future_consent["provision"]["period"] = {
        "start": (now + datetime.timedelta(days=5)).isoformat(),  # Valid in 5 days
        "end": (now + datetime.timedelta(days=365)).isoformat(),
    }
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=future_consent,
        user_id="pat-001",
        requested_purpose="core_service",
        execution_timestamp=now,
    )
    assert result.allowed is False
    assert result.status_code == "ERR_CONSENT_NOT_YET_VALID"


def test_consent_purpose_not_authorized(valid_fhir_consent: dict) -> None:
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=valid_fhir_consent,
        user_id="pat-001",
        requested_purpose="unconsented_genomic_profiling",
    )
    assert result.allowed is False
    assert result.status_code == "ERR_PURPOSE_NOT_AUTHORIZED"


def test_consent_purpose_explicitly_denied(valid_fhir_consent: dict) -> None:
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=valid_fhir_consent,
        user_id="pat-001",
        requested_purpose="commercial_marketing",
    )
    assert result.allowed is False
    assert result.status_code == "ERR_PURPOSE_DENIED"


# ==============================================================================
# 3. Statutory Vietnamese Compliance Gates (Decree 13 / Circular 46)
# ==============================================================================

def test_statutory_cross_border_permitted(valid_fhir_consent: dict) -> None:
    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=valid_fhir_consent,
        user_id="pat-001",
        requested_purpose="core_service",
        requires_cross_border=True,
    )
    assert result.allowed is True
    assert result.status_code == "ALLOWED"


def test_statutory_cross_border_denied_when_missing(valid_fhir_consent: dict) -> None:
    # Remove cross_border_processing from permit purposes
    no_cross_border_consent = dict(valid_fhir_consent)
    provisions = dict(valid_fhir_consent["provision"])
    provisions["purpose"] = [
        p for p in provisions["purpose"] if p.get("code") != "cross_border_processing"
    ]
    no_cross_border_consent["provision"] = provisions

    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=no_cross_border_consent,
        user_id="pat-001",
        requested_purpose="core_service",
        requires_cross_border=True,
    )
    assert result.allowed is False
    assert result.status_code == "ERR_CROSS_BORDER_NOT_PERMITTED"


def test_research_pipeline_purpose_gate(valid_fhir_consent: dict) -> None:
    # Direct clinical care only consent
    treatment_only = dict(valid_fhir_consent)
    provisions = dict(valid_fhir_consent["provision"])
    provisions["purpose"] = [
        {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "TREAT"}
    ]
    treatment_only["provision"] = provisions

    result = FhirConsentEnforcer.evaluate_pipeline_consent(
        fhir_consent=treatment_only,
        user_id="pat-001",
        requested_purpose="research",
    )
    assert result.allowed is False
    assert result.status_code == "ERR_PURPOSE_NOT_AUTHORIZED"


# ==============================================================================
# 4. Bidirectional Mapping with PolicyEpoch
# ==============================================================================

def test_fhir_to_policy_epoch(valid_fhir_consent: dict) -> None:
    epoch = FhirConsentEnforcer.fhir_consent_to_policy_epoch(valid_fhir_consent)
    assert isinstance(epoch, PolicyEpoch)
    assert epoch.user_id == "pat-001"
    assert "core_service" in epoch.active_purposes
    assert "research" in epoch.active_purposes
    assert "commercial_marketing" in epoch.revoked_purposes


def test_policy_epoch_to_fhir_consent() -> None:
    epoch = PolicyEpoch(
        epoch_id="epoch-test-01",
        user_id="pat-test-123",
        active_purposes={"core_service", "research"},
        revoked_purposes={"cross_border_processing"},
        updated_at=datetime.datetime.now(datetime.UTC),
    )
    fhir_consent = FhirConsentEnforcer.policy_epoch_to_fhir_consent(
        epoch,
        patient_ref="Patient/pat-test-123",
        organization_ref="Organization/clara-health",
    )
    assert fhir_consent["resourceType"] == "Consent"
    assert fhir_consent["status"] == "active"
    assert fhir_consent["patient"]["reference"] == "Patient/pat-test-123"

    # Re-parse exported FHIR consent
    parsed = FhirConsentEnforcer.parse_consent_resource(fhir_consent)
    assert "core_service" in parsed["permitted_purposes"]
    assert "research" in parsed["permitted_purposes"]
    assert "cross_border_processing" in parsed["denied_purposes"]


# ==============================================================================
# 5. FHIR R4 Provenance Construction & Signatures
# ==============================================================================

def test_model_provenance_to_fhir(sample_model_provenance: ModelRunProvenance) -> None:
    prov = FhirProvenanceMapper.model_provenance_to_fhir(
        sample_model_provenance,
        target_reference="Observation/obs-clinical-001",
        tenant_id="org-hospital-1",
        practitioner_ref="Practitioner/dr-nguyen",
    )
    assert prov["resourceType"] == "Provenance"
    assert prov["target"][0]["reference"] == "Observation/obs-clinical-001"
    assert len(prov["agent"]) == 3  # Author, Performer, Custodian
    assert prov["agent"][0]["who"]["reference"] == "Practitioner/dr-nguyen"
    assert prov["entity"][0]["what"]["identifier"]["value"] == sample_model_provenance.context_digest
    assert len(prov["signature"]) == 1
    assert prov["signature"][0]["sigFormat"] == "application/sha256"


def test_model_provenance_with_attested_dispatch(sample_model_provenance: ModelRunProvenance) -> None:
    attestation = AttestedDispatchResult(
        dispatch_attempt_id="att-attempt-987",
        transport_payload_digest="sha256:d3d3d3",
        provider_receipt_digest="sha256:provider_receipt_abc",
        attestation_level="PROVIDER_RECEIPT_VERIFIED",
        response_payload={"model": "deepseek-reasoner"},
        dispatched_at=datetime.datetime.now(datetime.UTC),
    )
    prov = FhirProvenanceMapper.model_provenance_to_fhir(
        sample_model_provenance,
        target_reference="Observation/obs-attested-002",
        tenant_id="org-hospital-1",
        attestation=attestation,
    )
    assert prov["signature"][0]["data"] == "sha256:provider_receipt_abc"
    ext_level = [
        e["valueString"] for e in prov["signature"][0]["extension"] if e["url"].endswith("#attestation-level")
    ][0]
    assert ext_level == "PROVIDER_RECEIPT_VERIFIED"


def test_scribe_provenance_to_fhir() -> None:
    registry = SpanRegistry([
        "Bệnh nhân sốt cao 39 độ",
        "Có tiền sử dị ứng penicillin",
        "Kê đơn paracetamol 500mg",
    ])
    prov = FhirProvenanceMapper.scribe_provenance_to_fhir(
        session_id="sess-scribe-101",
        span_registry=registry,
        target_reference="Composition/soap-sess-scribe-101",
        tenant_id="org-clinic-central",
        practitioner_ref="dr-tran",
    )
    assert prov["resourceType"] == "Provenance"
    assert prov["activity"]["coding"][0]["code"] == "originate"
    assert len(prov["entity"]) == 3
    assert prov["entity"][0]["what"]["identifier"]["value"] == "seg-0000"
    assert prov["signature"][0]["sigFormat"] == "application/sha256"


def test_research_provenance_to_fhir() -> None:
    citations = [
        {"pmid": "31234567", "title": "Clinical Efficacy of Artemisinin in Vietnam"},
        {"doi": "10.1056/NEJMoa1901234", "title": "Malaria Treatment Review"},
    ]
    prov = FhirProvenanceMapper.research_provenance_to_fhir(
        research_run_id="res-run-456",
        citations=citations,
        target_reference="ResearchStudy/study-malaria-01",
        tenant_id="org-institute-research",
    )
    assert prov["resourceType"] == "Provenance"
    assert len(prov["entity"]) == 2
    assert prov["entity"][0]["what"]["identifier"]["system"] == "https://pubmed.ncbi.nlm.nih.gov"
    assert prov["entity"][0]["what"]["identifier"]["value"] == "31234567"
    assert prov["entity"][1]["what"]["identifier"]["system"] == "https://doi.org"


# ==============================================================================
# 6. Immutable Lineage Anti-Downgrade Verification
# ==============================================================================

def test_provenance_lineage_no_downgrade(sample_model_provenance: ModelRunProvenance) -> None:
    att_parent = AttestedDispatchResult(
        dispatch_attempt_id="att-1",
        transport_payload_digest="sha256:d1",
        provider_receipt_digest="sha256:r1",
        attestation_level="PROVIDER_RECEIPT_VERIFIED",
        response_payload={},
        dispatched_at=datetime.datetime.now(datetime.UTC),
    )
    att_child = AttestedDispatchResult(
        dispatch_attempt_id="att-2",
        transport_payload_digest="sha256:d2",
        provider_receipt_digest="sha256:r2",
        attestation_level="PROVIDER_EXECUTION_ATTESTED",
        response_payload={},
        dispatched_at=datetime.datetime.now(datetime.UTC),
    )
    parent_prov = FhirProvenanceMapper.model_provenance_to_fhir(
        sample_model_provenance,
        target_reference="Observation/parent",
        tenant_id="t1",
        attestation=att_parent,
    )
    child_prov = FhirProvenanceMapper.model_provenance_to_fhir(
        sample_model_provenance,
        target_reference="Observation/child",
        tenant_id="t1",
        attestation=att_child,
    )
    res = FhirProvenanceMapper.verify_fhir_provenance_lineage(
        parent_provenance=parent_prov,
        descendant_provenance=child_prov,
    )
    assert res.valid is True


def test_provenance_lineage_downgrade_rejected(sample_model_provenance: ModelRunProvenance) -> None:
    att_high = AttestedDispatchResult(
        dispatch_attempt_id="att-1",
        transport_payload_digest="sha256:d1",
        provider_receipt_digest="sha256:r1",
        attestation_level="PROVIDER_EXECUTION_ATTESTED",
        response_payload={},
        dispatched_at=datetime.datetime.now(datetime.UTC),
    )
    parent_prov = FhirProvenanceMapper.model_provenance_to_fhir(
        sample_model_provenance,
        target_reference="Observation/parent",
        tenant_id="t1",
        attestation=att_high,
    )
    # Child without attestation (defaults to APPLICATION_ENVELOPE_ONLY)
    child_prov = FhirProvenanceMapper.model_provenance_to_fhir(
        sample_model_provenance,
        target_reference="Observation/child",
        tenant_id="t1",
        attestation=None,
    )
    res = FhirProvenanceMapper.verify_fhir_provenance_lineage(
        parent_provenance=parent_prov,
        descendant_provenance=child_prov,
    )
    assert res.valid is False
    assert "Attestation downgrade forbidden" in res.reason


# ==============================================================================
# 7. Statutory Privacy and PII Scrubbing
# ==============================================================================

def test_provenance_pii_redaction() -> None:
    dirty_prov = {
        "resourceType": "Provenance",
        "id": "prov-pii-test",
        "target": [{"reference": "Patient/012345678901"}],  # 12-digit CCCD in patient ref
        "activity": {
            "text": "Consultation with patient Nguyen Van A, phone 0912345678, email nguyen@gmail.com, CCCD 001090123456"
        },
        "agent": [
            {"who": {"display": "Dr. Le contacted 0987654321 regarding patient 123456789"}}
        ],
    }
    cleaned = FhirProvenanceMapper.redact_fhir_provenance_pii(dirty_prov)

    text = cleaned["activity"]["text"]
    assert "0912345678" not in text
    assert "[REDACTED_PHONE]" in text
    assert "nguyen@gmail.com" not in text
    assert "[REDACTED_EMAIL]" in text
    assert "001090123456" not in text
    assert "[REDACTED_NATIONAL_ID]" in text

    agent_text = cleaned["agent"][0]["who"]["display"]
    assert "0987654321" not in agent_text
    assert "123456789" not in agent_text  # 9-digit CMND redacted

    target_ref = cleaned["target"][0]["reference"]
    assert "012345678901" not in target_ref
    assert target_ref.startswith("Patient/anon-")


# ==============================================================================
# 8. Feature Flag Gating and Fail-Closed Guard
# ==============================================================================

def test_gate_flag_disabled_passthrough(valid_fhir_consent: dict) -> None:
    gate = FhirConsentGate(enabled=False)
    res = gate.enforce_ml_execution(
        fhir_consent=None,  # No consent supplied
        user_id="pat-anon",
        requested_purpose="core_service",
    )
    assert res.allowed is True
    assert res.status_code == "PASSTHROUGH_FEATURE_FLAG_DISABLED"


def test_gate_flag_enabled_enforces(valid_fhir_consent: dict) -> None:
    gate = FhirConsentGate(enabled=True)
    # Valid consent succeeds
    res = gate.enforce_ml_execution(
        fhir_consent=valid_fhir_consent,
        user_id="pat-001",
        requested_purpose="core_service",
    )
    assert res.allowed is True

    # Missing consent fails closed with exception
    with pytest.raises(ConsentEnforcementError) as exc_info:
        gate.enforce_ml_execution(
            fhir_consent=None,
            user_id="pat-001",
            requested_purpose="core_service",
        )
    assert "ERR_CONSENT_MISSING" in str(exc_info.value)


# ==============================================================================
# 9. Concurrency & Race-Condition Robustness
# ==============================================================================

def test_concurrent_consent_evaluation(valid_fhir_consent: dict) -> None:
    gate = FhirConsentGate(enabled=True)

    def _eval_worker(i: int) -> bool:
        user = "pat-001" if i % 2 == 0 else "pat-mismatch"
        purpose = "core_service" if i % 3 != 0 else "unauthorized_purpose"
        try:
            res = gate.enforce_ml_execution(
                fhir_consent=valid_fhir_consent,
                user_id=user,
                requested_purpose=purpose,
            )
            return res.allowed
        except ConsentEnforcementError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_eval_worker, idx) for idx in range(100)]
        results = [f.result() for f in futures]

    # Verify deterministic outcomes without race conditions
    assert len(results) == 100
    for idx, allowed in enumerate(results):
        expected = (idx % 2 == 0) and (idx % 3 != 0)
        assert allowed == expected, f"Worker {idx} failed expectation"
