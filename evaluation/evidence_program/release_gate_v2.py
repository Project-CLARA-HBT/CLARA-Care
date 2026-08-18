"""Fail-closed v2 release schema for systems / nonclinical evidence.

The v2 gate distinguishes, at the schema level, the clinical human-validation
axis from the nonclinical attestations a systems / nonclinical release can
legitimately carry:

- ``clinical_human_validation_status`` is ``NOT_AVAILABLE`` unless genuine,
  byte-resolvable human-validation evidence is attached and verified. A
  self-attested "available" flag is a refusal, never a pass.
- ``dual_model_supportive_review_attested``
- ``external_structural_validation_attested``
- ``real_boundary_governance_attested``
- ``postgres_concurrency_attested``
- ``formal_assurance_attested``

The old ``release_gate`` semantics (headline human validation) are preserved as
legacy: this module never fabricates human validation, and a v2 record is only
approved when every nonclinical attestation is present and
``clinical_human_validation_status`` is either ``NOT_AVAILABLE`` or backed by a
genuine evidence bundle whose on-disk bytes resolve to a declared SHA-256.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

SCHEMA_VERSION = "clara-release-schema.v2"

# Human validation is NOT available unless genuine evidence is attached.
CLINICAL_HUMAN_VALIDATION_NOT_AVAILABLE = "NOT_AVAILABLE"
# Only reachable with a byte-resolvable evidence bundle; never self-attested.
CLINICAL_HUMAN_VALIDATION_AVAILABLE = "AVAILABLE_WITH_GENUINE_EVIDENCE"

REQUIRED = frozenset(
    {
        "schema_version",
        "status",
        "release_id",
        "run_id",
        "code_revision",
        "protocol_sha256",
        "clinical_human_validation_status",
        "dual_model_supportive_review_attested",
        "external_structural_validation_attested",
        "real_boundary_governance_attested",
        "postgres_concurrency_attested",
        "formal_assurance_attested",
        "approved_by",
        "approved_at",
    }
)

_NONCLINICAL_ATTESTATIONS = (
    "dual_model_supportive_review_attested",
    "external_structural_validation_attested",
    "real_boundary_governance_attested",
    "postgres_concurrency_attested",
    "formal_assurance_attested",
)

_HUMAN_VALIDATION_EVIDENCE_KEY = "clinical_human_validation_evidence"


def _require_genuine_human_validation(value: dict, root: Path) -> None:
    """Refuse to mark clinical human validation available without genuine evidence.

    A status other than ``NOT_AVAILABLE`` is accepted only when the record
    carries a byte-resolvable evidence bundle under ``root`` whose SHA-256
    matches the declared hash. This is what makes "genuine" machine-verifiable
    instead of self-attested.
    """
    status = value["clinical_human_validation_status"]
    if status == CLINICAL_HUMAN_VALIDATION_NOT_AVAILABLE:
        return
    if status != CLINICAL_HUMAN_VALIDATION_AVAILABLE:
        raise FreezeError("clinical_human_validation_invalid_status:" + status)
    evidence = value.get(_HUMAN_VALIDATION_EVIDENCE_KEY)
    if not isinstance(evidence, dict):
        raise FreezeError("clinical_human_validation_evidence_missing")
    artifact = evidence.get("artifact_path")
    declared = evidence.get("sha256")
    if not isinstance(artifact, str) or not isinstance(declared, str):
        raise FreezeError("clinical_human_validation_evidence_incomplete")
    root_resolved = root.resolve()
    target = (root / artifact).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise FreezeError("clinical_human_validation_evidence_outside_repository")
    if not target.is_file():
        raise FreezeError("clinical_human_validation_evidence_missing_bytes")
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != declared:
        raise FreezeError("clinical_human_validation_evidence_sha_mismatch")


def validate(path: Path, *, repository_root: Path = Path(".")) -> None:
    """Require an approved systems/nonclinical release record (fail closed)."""

    value = load_frozen_json(path)
    missing = REQUIRED.difference(value)
    if missing:
        raise FreezeError("missing_headline_release_fields:" + ",".join(sorted(missing)))
    if value["schema_version"] != SCHEMA_VERSION:
        raise FreezeError("release_schema_version_mismatch")
    if value["status"] != "approved":
        raise FreezeError("headline_release_not_approved")
    if not all(value[field] for field in _NONCLINICAL_ATTESTATIONS):
        raise FreezeError("nonclinical_release_attestation_missing")
    _require_genuine_human_validation(value, repository_root)
