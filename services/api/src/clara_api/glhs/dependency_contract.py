"""Schema-derived dependency contract for GLHS commit operations.

Prohibits unconstrained LLM-generated dependency vectors by deriving the
required dependency set from structured application semantics (operation type,
domain, entity keys, governance coordinates).  Only conservative supersets
(adding strictly more dependencies) are permitted; omissions are rejected.

The generation algorithm is deterministic, versioned, and auditable:
    1. Resolve operation type to its declared dependency rule.
    2. Build the ENTITY, GOVERNANCE, and EVIDENCE dependency entries from
       the structured inputs (domain, semantic_keys, evidence_ids).
    3. Return the canonical dependency vector and its generation metadata.

LLM or model code may supply a ``proposed_dependencies`` list, but it is
validated against (and must be a superset of) the schema-derived minimum.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    fast_canonical_digest,
)
from clara_api.glhs.commit_kernel import DependencySpec
from clara_api.glhs.domain import GlhsInvariantError

CONTRACT_VERSION = "dependency-contract.v1"

# ---------------------------------------------------------------------------
# Operation type registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OperationDependencyRule:
    """Declared dependency shape for one operation type.

    Fields
    ------
    operation_kind : str
        The commit kernel ``operation_kind`` value (e.g. ``COMMIT_PROPOSAL``).
    requires_governance : bool
        Whether a GOVERNANCE dependency on the policy epoch is mandatory.
    requires_consent : bool
        Whether a GOVERNANCE dependency on the consent version is mandatory.
    requires_evidence : bool
        Whether at least one EVIDENCE dependency is mandatory.
    entity_access_mode : str
        Default access mode for entity dependencies (``READ`` or ``WRITE``).
    allow_additional_entities : bool
        Whether the caller may declare extra entity dependencies beyond those
        derived from ``semantic_keys``.  True enables conservative supersets.
    min_entity_count : int
        Minimum number of entity dependencies required.
    """

    operation_kind: str
    requires_governance: bool = True
    requires_consent: bool = True
    requires_evidence: bool = False
    entity_access_mode: str = "WRITE"
    allow_additional_entities: bool = True
    min_entity_count: int = 1


OperationDependencyContract = OperationDependencyRule
# Adding a new operation type requires a code change here.
_OPERATION_RULES: dict[str, OperationDependencyRule] = {
    "COMMIT_PROPOSAL": OperationDependencyRule(
        operation_kind="COMMIT_PROPOSAL",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=True,
        entity_access_mode="WRITE",
        min_entity_count=1,
    ),
    "ACTIVATE_ASSERTION": OperationDependencyRule(
        operation_kind="ACTIVATE_ASSERTION",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=True,
        entity_access_mode="WRITE",
        min_entity_count=1,
    ),
    "SUPERSEDE_ASSERTION": OperationDependencyRule(
        operation_kind="SUPERSEDE_ASSERTION",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=False,
        entity_access_mode="WRITE",
        min_entity_count=1,
    ),
    "RESOLVE_CONFLICT": OperationDependencyRule(
        operation_kind="RESOLVE_CONFLICT",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=False,
        entity_access_mode="WRITE",
        min_entity_count=1,
    ),
    "RECONCILE_MEDICATION": OperationDependencyRule(
        operation_kind="RECONCILE_MEDICATION",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=True,
        entity_access_mode="WRITE",
        min_entity_count=1,
    ),
    "IMPORT_FHIR_BUNDLE": OperationDependencyRule(
        operation_kind="IMPORT_FHIR_BUNDLE",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=False,
        entity_access_mode="WRITE",
        min_entity_count=1,
        allow_additional_entities=True,
    ),
    "RECORD_OBSERVATION": OperationDependencyRule(
        operation_kind="RECORD_OBSERVATION",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=True,
        entity_access_mode="WRITE",
        min_entity_count=1,
    ),
    "CONSENT_TRANSITION": OperationDependencyRule(
        operation_kind="CONSENT_TRANSITION",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=False,
        entity_access_mode="READ",
        min_entity_count=0,
        allow_additional_entities=False,
    ),
    "COMMIT_COMMITMENT_TRANSITION": OperationDependencyRule(
        operation_kind="COMMIT_COMMITMENT_TRANSITION",
        requires_governance=True,
        requires_consent=True,
        requires_evidence=False,
        entity_access_mode="WRITE",
        min_entity_count=1,
        allow_additional_entities=True,
    ),
    "APPLY_TRANSITION": OperationDependencyRule(
        operation_kind="APPLY_TRANSITION",
        requires_governance=False,
        requires_consent=False,
        requires_evidence=False,
        entity_access_mode="WRITE",
        min_entity_count=0,
        allow_additional_entities=True,
    ),
}


def lookup_operation_rule(operation_kind: str) -> OperationDependencyRule:
    """Resolve an operation kind to its declared dependency rule.

    Raises ``GlhsInvariantError`` for unknown operation kinds, preventing
    unconstrained dependency vectors from being accepted.
    """
    rule = _OPERATION_RULES.get(operation_kind.strip().upper())
    if rule is None:
        raise GlhsInvariantError(
            f"dependency_contract_unknown_operation: {operation_kind}"
        )
    return rule


# ---------------------------------------------------------------------------
# Schema-derived dependency generation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeneratedDependencyVector:
    """Result of schema-derived dependency generation."""

    dependencies: tuple[DependencySpec, ...]
    contract_version: str = CONTRACT_VERSION
    generation_rule: str = ""
    generation_digest: str = ""
    generated_at: str = ""
    is_superset: bool = False
    superset_extra_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class DependencyGenerationInput:
    """Structured application-semantic input for dependency generation.

    Every field here is a concrete, schema-derived value -- none are
    free-text strings from an LLM.
    """

    operation_kind: str
    domain: str
    semantic_keys: tuple[str, ...]
    policy_version: str = ""
    consent_version: str = ""
    evidence_ids: tuple[str, ...] = ()
    observed_entity_versions: dict[str, int] = field(default_factory=dict)
    observed_entity_digests: dict[str, str] = field(default_factory=dict)
    policy_domain: str | None = None


def generate_dependency_vector(
    inp: DependencyGenerationInput,
) -> GeneratedDependencyVector:
    """Deterministically derive the minimum dependency vector from structured input.

    This is the single entry point for dependency generation.  It is called
    by API-owned code paths (gateway, commitment gateway, adapters) and its
    output is the *minimum correct* dependency set.  Callers may supply a
    conservative superset, but never a subset.
    """
    rule = lookup_operation_rule(inp.operation_kind)

    deps: list[DependencySpec] = []

    # --- GOVERNANCE: policy epoch ---
    if rule.requires_governance:
        policy_key = (
            f"policy_epoch:{inp.policy_domain}"
            if inp.policy_domain
            else "policy_epoch:__global__"
        )
        deps.append(
            DependencySpec(
                dependency_kind="GOVERNANCE",
                dependency_key=policy_key,
                access_mode="READ",
                observed_version=0,
                observed_digest=inp.policy_version or None,
            )
        )

    # --- GOVERNANCE: consent ---
    if rule.requires_consent:
        deps.append(
            DependencySpec(
                dependency_kind="GOVERNANCE",
                dependency_key=f"consent:{inp.consent_version}",
                access_mode="READ",
                observed_version=0,
                observed_digest=inp.consent_version or None,
            )
        )

    # --- ENTITY: one per semantic key ---
    if len(inp.semantic_keys) < rule.min_entity_count:
        raise GlhsInvariantError(
            f"dependency_contract_insufficient_entities: "
            f"need {rule.min_entity_count}, got {len(inp.semantic_keys)}"
        )

    for sk in sorted(set(inp.semantic_keys)):
        entity_key = f"{inp.domain}:{sk}"
        deps.append(
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key=entity_key,
                access_mode=rule.entity_access_mode,
                observed_version=inp.observed_entity_versions.get(entity_key, 0),
                observed_digest=inp.observed_entity_digests.get(entity_key),
            )
        )

    # --- EVIDENCE ---
    if rule.requires_evidence and not inp.evidence_ids:
        raise GlhsInvariantError("dependency_contract_evidence_required")

    for eid in sorted(set(inp.evidence_ids)):
        deps.append(
            DependencySpec(
                dependency_kind="EVIDENCE",
                dependency_key=f"evidence:{eid}",
                access_mode="READ",
                observed_version=0,
            )
        )

    canonical_deps = tuple(sorted(
        deps,
        key=lambda d: (d.dependency_kind, d.dependency_key, d.access_mode),
    ))

    generation_envelope = {
        "contract_version": CONTRACT_VERSION,
        "operation_kind": inp.operation_kind,
        "domain": inp.domain,
        "semantic_keys": sorted(set(inp.semantic_keys)),
        "evidence_ids": sorted(set(inp.evidence_ids)),
        "policy_version": inp.policy_version,
        "consent_version": inp.consent_version,
        "dep_count": len(canonical_deps),
    }
    generation_digest = fast_canonical_digest(generation_envelope)

    return GeneratedDependencyVector(
        dependencies=canonical_deps,
        contract_version=CONTRACT_VERSION,
        generation_rule=inp.operation_kind,
        generation_digest=generation_digest,
        generated_at=datetime.now(UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# Superset validation -- proposed vs schema-derived minimum
# ---------------------------------------------------------------------------

def _dep_identity(dep: DependencySpec) -> tuple[str, str, str]:
    """Return the identity triple that determines dependency coverage."""
    return (dep.dependency_kind, dep.dependency_key, dep.access_mode)


def validate_proposed_dependencies(
    minimum: GeneratedDependencyVector | Sequence[DependencySpec] | None = None,
    proposed: list[DependencySpec] | Sequence[DependencySpec] | None = None,
    *,
    operation_kind: str,
    required_deps: GeneratedDependencyVector | Sequence[DependencySpec] | None = None,
    proposed_deps: Sequence[DependencySpec] | None = None,
) -> GeneratedDependencyVector:
    """Validate that ``proposed`` is a superset of ``minimum`` (or ``required_deps``).

    Returns a ``GeneratedDependencyVector`` with ``is_superset=True`` and the
    extra keys recorded when the proposed set is strictly larger.

    Raises ``GlhsInvariantError`` if any minimum dependency is missing or corrupted.
    """
    effective_min = required_deps if required_deps is not None else minimum
    if effective_min is None:
        raise GlhsInvariantError("dependency_contract_minimum_required")

    effective_prop = proposed_deps if proposed_deps is not None else proposed
    if effective_prop is None:
        raise GlhsInvariantError("dependency_contract_proposed_required")

    proposed_list = list(effective_prop)
    rule = lookup_operation_rule(operation_kind)

    min_deps: tuple[DependencySpec, ...]
    if isinstance(effective_min, GeneratedDependencyVector):
        min_deps = effective_min.dependencies
        contract_version = effective_min.contract_version
        generation_rule = effective_min.generation_rule
        generation_digest = effective_min.generation_digest
        generated_at = effective_min.generated_at
    else:
        min_deps = tuple(effective_min)
        contract_version = CONTRACT_VERSION
        generation_rule = operation_kind
        generation_digest = ""
        generated_at = datetime.now(UTC).isoformat()

    minimum_ids = {_dep_identity(d) for d in min_deps}
    proposed_ids = {_dep_identity(d) for d in proposed_list}

    # Validate access mode match for matching kind and key (catches mode corruptions M3)
    min_kind_keys = {(d.dependency_kind, d.dependency_key): d for d in min_deps}
    for pdep in proposed_list:
        kk = (pdep.dependency_kind, pdep.dependency_key)
        if kk in min_kind_keys:
            mdep = min_kind_keys[kk]
            if mdep.access_mode != pdep.access_mode:
                raise GlhsInvariantError(
                    f"dependency_contract_access_mode_mismatch: dependency_contract_omission: {kk[0]}:{kk[1]} "
                    f"expected {mdep.access_mode}, got {pdep.access_mode}"
                )

    missing = minimum_ids - proposed_ids
    if missing:
        missing_keys = sorted(f"{k}:{key}:{m}" for k, key, m in missing)
        raise GlhsInvariantError(
            f"dependency_contract_omission: missing {missing_keys}"
        )

    extra = proposed_ids - minimum_ids
    if extra and not rule.allow_additional_entities:
        extra_keys = sorted(f"{k}:{key}:{m}" for k, key, m in extra)
        raise GlhsInvariantError(
            f"dependency_contract_unexpected_extra: {extra_keys}"
        )

    # Validate version / digest consistency for matching deps
    minimum_map = {_dep_identity(d): d for d in min_deps}
    for pdep in proposed_list:
        pid = _dep_identity(pdep)
        if pid in minimum_map:
            mdep = minimum_map[pid]
            # Proposed version must match minimum's observed version
            if mdep.observed_version != 0 and pdep.observed_version != mdep.observed_version:
                raise GlhsInvariantError(
                    f"dependency_contract_version_mismatch: {pid} "
                    f"expected {mdep.observed_version}, got {pdep.observed_version}"
                )
            # Proposed digest must match when minimum specifies one
            if (
                mdep.observed_digest is not None
                and pdep.observed_digest is not None
                and mdep.observed_digest != pdep.observed_digest
            ):
                raise GlhsInvariantError(
                    f"dependency_contract_digest_mismatch: {pid}"
                )

    extra_keys = tuple(sorted(f"{k}:{key}:{m}" for k, key, m in extra))

    return GeneratedDependencyVector(
        dependencies=tuple(sorted(
            proposed_list,
            key=lambda d: (d.dependency_kind, d.dependency_key, d.access_mode),
        )),
        contract_version=contract_version,
        generation_rule=generation_rule,
        generation_digest=generation_digest,
        generated_at=generated_at,
        is_superset=bool(extra),
        superset_extra_keys=extra_keys,
    )


# ---------------------------------------------------------------------------
# Persistence metadata
# ---------------------------------------------------------------------------

def dependency_generation_metadata(
    vector: GeneratedDependencyVector,
) -> dict[str, Any]:
    """Return the metadata envelope to persist alongside a committed proposal.

    Stored in the ``GlhsAppliedTransition`` or proposal record so the
    generation rule and contract version are durably reconstructable.
    """
    return {
        "contract_version": vector.contract_version,
        "generation_rule": vector.generation_rule,
        "generation_digest": vector.generation_digest,
        "generated_at": vector.generated_at,
        "dependency_count": len(vector.dependencies),
        "is_superset": vector.is_superset,
        "superset_extra_keys": list(vector.superset_extra_keys),
    }
