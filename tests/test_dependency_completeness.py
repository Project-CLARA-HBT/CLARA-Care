"""Top-level test wrapper for dependency completeness contract tests."""

from clara_api.glhs.dependency_contract import (
    CONTRACT_VERSION,
    DependencyGenerationInput,
    generate_dependency_vector,
    lookup_operation_rule,
    validate_proposed_dependencies,
)
from clara_api.glhs.domain import GlhsInvariantError

from services.api.tests.test_dependency_completeness import (
    test_dependency_generation_metadata_structure,
    test_generate_dependency_vector_deterministic,
    test_generate_dependency_vector_requires_evidence,
    test_lookup_operation_rule_unknown_raises,
    test_lookup_operation_rule_valid,
    test_validate_proposed_conservative_superset_accepted,
    test_validate_proposed_exact_match,
    test_validate_proposed_extra_rejected_when_not_allowed,
    test_validate_proposed_omission_rejected,
    test_validate_proposed_version_mismatch,
)

__all__ = [
    "test_lookup_operation_rule_valid",
    "test_lookup_operation_rule_unknown_raises",
    "test_generate_dependency_vector_deterministic",
    "test_generate_dependency_vector_requires_evidence",
    "test_validate_proposed_exact_match",
    "test_validate_proposed_omission_rejected",
    "test_validate_proposed_conservative_superset_accepted",
    "test_validate_proposed_extra_rejected_when_not_allowed",
    "test_validate_proposed_version_mismatch",
    "test_dependency_generation_metadata_structure",
]
