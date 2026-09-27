"""Unit tests for GLHS Schema-Derived Dependency Completeness Contract (E06)."""

from __future__ import annotations

import pytest

from clara_api.glhs.commit_kernel import DependencySpec
from clara_api.glhs.dependency_contract import (
    CONTRACT_VERSION,
    DependencyGenerationInput,
    GeneratedDependencyVector,
    dependency_generation_metadata,
    generate_dependency_vector,
    lookup_operation_rule,
    validate_proposed_dependencies,
)
from clara_api.glhs.domain import GlhsInvariantError


def test_lookup_operation_rule_valid():
    """Verify known operation rules can be retrieved."""
    rule = lookup_operation_rule("COMMIT_PROPOSAL")
    assert rule.operation_kind == "COMMIT_PROPOSAL"
    assert rule.requires_governance is True
    assert rule.requires_consent is True
    assert rule.requires_evidence is True
    assert rule.entity_access_mode == "WRITE"


def test_lookup_operation_rule_unknown_raises():
    """Verify unknown operation kinds fail closed with GlhsInvariantError."""
    with pytest.raises(GlhsInvariantError, match="dependency_contract_unknown_operation"):
        lookup_operation_rule("LLM_HALLUCINATED_OP")


def test_generate_dependency_vector_deterministic():
    """Verify deterministic generation of minimum dependency vector."""
    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin", "lisinopril"),
        policy_version="glhs.v1",
        consent_version="disclaimer.v3",
        evidence_ids=("ev-1",),
        observed_entity_versions={"medications:metformin": 2, "medications:lisinopril": 1},
    )

    vec1 = generate_dependency_vector(inp)
    vec2 = generate_dependency_vector(inp)

    assert vec1.contract_version == CONTRACT_VERSION
    assert vec1.generation_rule == "COMMIT_PROPOSAL"
    assert vec1.generation_digest == vec2.generation_digest
    assert len(vec1.dependencies) == 5  # 2 gov + 2 entity + 1 evidence

    kinds = [d.dependency_kind for d in vec1.dependencies]
    assert kinds.count("GOVERNANCE") == 2
    assert kinds.count("ENTITY") == 2
    assert kinds.count("EVIDENCE") == 1


def test_generate_dependency_vector_requires_evidence():
    """Verify operation requiring evidence fails if evidence_ids is empty."""
    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=(),
    )
    with pytest.raises(GlhsInvariantError, match="dependency_contract_evidence_required"):
        generate_dependency_vector(inp)


def test_validate_proposed_exact_match():
    """Verify proposed exact match vector is accepted."""
    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=("ev-1",),
    )
    minimum = generate_dependency_vector(inp)
    validated = validate_proposed_dependencies(minimum, list(minimum.dependencies), operation_kind="COMMIT_PROPOSAL")

    assert validated.is_superset is False
    assert len(validated.superset_extra_keys) == 0


test_cases_omissions = [
    # Omit governance dependency
    ("M9_omit_governance", lambda deps: [d for d in deps if d.dependency_kind != "GOVERNANCE"]),
    # Omit entity dependency
    ("M1_omit_entity", lambda deps: [d for d in deps if d.dependency_kind != "ENTITY"]),
    # Omit evidence dependency
    ("M8_omit_evidence", lambda deps: [d for d in deps if d.dependency_kind != "EVIDENCE"]),
]


@pytest.mark.parametrize("name,mutator", test_cases_omissions)
def test_validate_proposed_omission_rejected(name: str, mutator):
    """Verify omission of any minimum dependency raises GlhsInvariantError."""
    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=("ev-1",),
    )
    minimum = generate_dependency_vector(inp)
    incomplete = mutator(list(minimum.dependencies))

    with pytest.raises(GlhsInvariantError, match="dependency_contract_omission"):
        validate_proposed_dependencies(minimum, incomplete, operation_kind="COMMIT_PROPOSAL")


def test_validate_proposed_conservative_superset_accepted():
    """Verify conservative superset with extra entities is accepted."""
    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=("ev-1",),
    )
    minimum = generate_dependency_vector(inp)

    extra_dep = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key="medications:lisinopril",
        access_mode="READ",
        observed_version=0,
    )
    superset = list(minimum.dependencies) + [extra_dep]

    validated = validate_proposed_dependencies(minimum, superset, operation_kind="COMMIT_PROPOSAL")
    assert validated.is_superset is True
    assert len(validated.superset_extra_keys) == 1
    assert "ENTITY:medications:lisinopril:READ" in validated.superset_extra_keys


def test_validate_proposed_extra_rejected_when_not_allowed():
    """Verify extra dependencies are rejected when allow_additional_entities is False."""
    inp = DependencyGenerationInput(
        operation_kind="CONSENT_TRANSITION",
        domain="consent",
        semantic_keys=(),
    )
    minimum = generate_dependency_vector(inp)

    extra_dep = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key="medications:lisinopril",
        access_mode="READ",
        observed_version=0,
    )
    superset = list(minimum.dependencies) + [extra_dep]

    with pytest.raises(GlhsInvariantError, match="dependency_contract_unexpected_extra"):
        validate_proposed_dependencies(minimum, superset, operation_kind="CONSENT_TRANSITION")


def test_validate_proposed_version_mismatch():
    """Verify proposed version mismatch raises GlhsInvariantError."""
    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=("ev-1",),
        observed_entity_versions={"medications:metformin": 5},
    )
    minimum = generate_dependency_vector(inp)

    # Change version to 6
    corrupted = [
        DependencySpec(
            dependency_kind=d.dependency_kind,
            dependency_key=d.dependency_key,
            access_mode=d.access_mode,
            observed_version=6 if d.dependency_key == "medications:metformin" else d.observed_version,
            observed_digest=d.observed_digest,
        )
        for d in minimum.dependencies
    ]

    with pytest.raises(GlhsInvariantError, match="dependency_contract_version_mismatch"):
        validate_proposed_dependencies(minimum, corrupted, operation_kind="COMMIT_PROPOSAL")


def test_dependency_generation_metadata_structure():
    """Verify metadata Envelope contains all required audit attributes."""
    inp = DependencyGenerationInput(
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=("metformin",),
        evidence_ids=("ev-1",),
    )
    minimum = generate_dependency_vector(inp)
    meta = dependency_generation_metadata(minimum)

    assert meta["contract_version"] == CONTRACT_VERSION
    assert meta["generation_rule"] == "COMMIT_PROPOSAL"
    assert "generation_digest" in meta
    assert "generated_at" in meta
    assert meta["dependency_count"] == len(minimum.dependencies)
    assert meta["is_superset"] is False
    assert meta["superset_extra_keys"] == []
