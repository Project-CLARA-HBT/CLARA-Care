"""Governed inventory, context, immutable manifests and signed artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from clara_api.db.models import MLRegistryObject
from clara_api.db.session import SessionLocal
from clara_api.ml_governance.artifacts import (
    ArtifactVerificationError,
    sign_manifest_for_offline_pipeline,
    verify_artifact,
)
from clara_api.ml_governance.provider_identity import (
    ProviderIdentityError,
    ProviderModelIdentity,
    resolve_provider_model,
    verify_provider_response,
)
from clara_api.ml_governance.registry import (
    GovernanceError,
    compile_private_context,
    require_transition,
    safe_operational_manifest,
    validate_catalog_entry,
)

CATALOG = Path(__file__).parents[1] / "src/clara_api/ml_governance/catalog.json"
GOVERNANCE_DOCS = Path(__file__).parents[3] / "docs/ml-governance"


def test_catalog_truthfully_registers_the_deployed_ai_inventory() -> None:
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = [validate_catalog_entry(item) for item in document["entries"]]
    ids = {item["id"] for item in entries}
    assert len(ids) == len(entries)
    assert {
        "deepseek-chat-synthesis",
        "deepseek-research-tier2",
        "deepseek-council-agents",
        "council-fixed-weight-shadow",
        "http-dense-embedding",
        "embedding-cosine-reranker-v1",
        "claim-v2-nli",
        "fides-critical-claim-verifier",
        "careguard-ddi-rule-engine",
        "google-cloud-vision-ocr",
        "tgc-medication-ocr",
        "tesseract-ocr-fallback",
        "deepseek-whisper-asr",
        "phowhisper-asr",
        "google-chirp3-asr",
        "lifemap-deterministic-baseline-v2",
        "lifemap-next-question-rules-v2",
        "lifemap-evidence-change-rules-v1",
    } == ids
    shadow = next(item for item in entries if item["id"] == "council-fixed-weight-shadow")
    assert shadow["kind"] == "fixed_weight_heuristic"
    assert shadow["release_state"] == "shadow"


def test_release_templates_cover_identity_risk_evidence_and_approval() -> None:
    expected = {
        "use-case-template.md": (
            "Stable use-case ID",
            "Forbidden uses",
            "Safety metrics and stop thresholds",
            "Approvers and dates",
        ),
        "datasheet-template.md": (
            "Stable dataset ID and version",
            "Leakage audit",
            "Withdrawal/deletion lineage",
            "Reviewer approvals and dates",
        ),
        "model-card-template.md": (
            "Stable artifact ID/version/checksum/signing key",
            "Calibration, OOD, abstention",
            "Monitoring and recall thresholds",
            "Approver signatures and dates",
        ),
        "evaluation-report-template.md": (
            "Frozen test-set reference",
            "Overall and slice metrics with uncertainty",
            "Residual hazards and mitigations",
            "Independent reviewers and dates",
        ),
        "change-control-template.md": (
            "current/new immutable identities",
            "Required re-evaluation",
            "Rollback/recall artifact",
            "Approvals",
        ),
    }
    for filename, fields in expected.items():
        content = (GOVERNANCE_DOCS / filename).read_text(encoding="utf-8")
        assert all(field in content for field in fields), filename


def test_release_state_machine_is_forward_only_and_recallable() -> None:
    require_transition("research", "offline_passed")
    require_transition("champion", "recalled")
    with pytest.raises(GovernanceError, match="invalid_release_transition"):
        require_transition("research", "champion")
    with pytest.raises(GovernanceError, match="invalid_release_transition"):
        require_transition("retired", "pilot")


def test_context_compiles_authority_before_ml_and_contains_only_lineage() -> None:
    use_case = {
        "use_case_id": "lifemap.ask",
        "release_state": "shadow",
        "allowed_purposes": ["self_care"],
        "allowed_data_classes": ["events", "episodes"],
        "requires_consent": True,
    }
    manifest = compile_private_context(
        use_case=use_case,
        profile_id=7,
        purpose="self_care",
        actor_category="owner",
        requested_data_classes={"events"},
        revision_refs=["event-revision-2", "event-revision-1"],
        consent_version="2026-04-v1",
        grant_version=None,
        now=datetime(2026, 7, 29, tzinfo=UTC),
    )
    assert manifest["revision_refs"] == ["event-revision-1", "event-revision-2"]
    assert len(manifest["context_digest"]) == 64
    assert not {
        "text",
        "payload",
        "name",
        "email",
        "medications",
    } & set(manifest)
    with pytest.raises(GovernanceError, match="data_class_not_allowed"):
        compile_private_context(
            use_case=use_case,
            profile_id=7,
            purpose="self_care",
            actor_category="owner",
            requested_data_classes={"documents"},
            revision_refs=["revision-1"],
            consent_version="2026-04-v1",
            grant_version=None,
        )


def test_operational_manifest_rejects_content_fields() -> None:
    assert (
        safe_operational_manifest(
            {"latency_ms": 25, "input_revision_count": 2, "abstained": False}
        )["latency_ms"]
        == 25
    )
    with pytest.raises(GovernanceError, match="unknown_fields"):
        safe_operational_manifest({"free_text": "private health content"})


def test_artifact_signature_checksum_and_path_are_fail_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"governed artifact bytes")
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    manifest = {
        "use_case_id": "lifemap.pattern.shadow",
        "artifact_id": "model-a",
        "version": "1",
        "relative_path": "model.bin",
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "release_state": "shadow",
    }
    signature = sign_manifest_for_offline_pipeline(manifest, private_key)
    verified = verify_artifact(
        root=tmp_path,
        manifest=manifest,
        signature_base64=signature,
        key_id="test-key",
        public_keys={"test-key": base64.b64encode(public_key).decode()},
    )
    assert verified.path == artifact

    artifact.write_bytes(b"tampered")
    with pytest.raises(ArtifactVerificationError, match="checksum_mismatch"):
        verify_artifact(
            root=tmp_path,
            manifest=manifest,
            signature_base64=signature,
            key_id="test-key",
            public_keys={"test-key": base64.b64encode(public_key).decode()},
        )
    with pytest.raises(ArtifactVerificationError, match="path_invalid"):
        verify_artifact(
            root=tmp_path,
            manifest={**manifest, "relative_path": "../escape.bin"},
            signature_base64=sign_manifest_for_offline_pipeline(
                {**manifest, "relative_path": "../escape.bin"}, private_key
            ),
            key_id="test-key",
            public_keys={"test-key": base64.b64encode(public_key).decode()},
        )


def test_registry_rows_are_append_only() -> None:
    with SessionLocal() as db:
        row = MLRegistryObject(
            object_kind="evaluation",
            stable_id="test-eval",
            version="1",
            status="draft",
            manifest_json={"metric": "citation_validity"},
            parent_refs_json=[],
        )
        db.add(row)
        db.commit()
        row.status = "approved"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
        with pytest.raises(ValueError, match="immutable"):
            db.delete(row)
            db.commit()
        db.rollback()


def test_provider_alias_resolves_to_exact_identity_and_detects_silent_change() -> None:
    identity = ProviderModelIdentity(
        provider="deepseek",
        alias="clara-default",
        immutable_id="deepseek-chat-2026-07-15",
        endpoint_class="chat-completions",
    )
    resolved = resolve_provider_model(
        provider="deepseek",
        configured_model="clara-default",
        allowlist={"clara-default": identity},
    )
    assert resolved.reference == "deepseek:deepseek-chat-2026-07-15"
    verify_provider_response(resolved, "deepseek-chat-2026-07-15")
    with pytest.raises(ProviderIdentityError, match="provider_model_changed"):
        verify_provider_response(resolved, "deepseek-chat-latest")
    with pytest.raises(ProviderIdentityError, match="not_allowlisted"):
        resolve_provider_model(
            provider="deepseek",
            configured_model="latest",
            allowlist={"clara-default": identity},
        )
