"""Dependency vector mutation operators for completeness experiments.

Nine mutation classes covering the full threat model:

    M1: omit_entity_dependency     -- Remove one true entity dependency
    M2: add_irrelevant_dependency  -- Add an entity dep for an unrelated domain
    M3: mutate_entity_key          -- Change the semantic_key of one entity dep
    M4: mutate_access_mode         -- Flip READ <-> WRITE on one entity dep
    M5: mutate_observed_version    -- Increment observed_version by +1 (stale lie)
    M6: multi_entity_write_skew    -- Remove second entity from a multi-write set
    M7: unrelated_entity_update    -- Replace an entity with one from another domain
    M8: omit_evidence_dependency   -- Remove one evidence dependency
    M9: omit_governance_dependency -- Remove the governance (policy) dependency

Each mutant is tagged with its class, a description, and whether the commit
kernel should REJECT (unsafe=True) or ACCEPT it.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from clara_api.glhs.commit_kernel import DependencySpec
from clara_api.glhs.dependency_contract import (
    DependencyGenerationInput,
    generate_dependency_vector,
)


MUTATION_SCHEMA_VERSION = "dep-completeness-mutation.v1"


@dataclass(frozen=True)
class MutationResult:
    """A single mutated dependency vector with its classification."""

    mutation_id: str
    mutation_class: str
    case_id: str
    description: str
    original_dep_count: int
    mutated_dep_count: int
    mutated_dependencies: list[dict[str, Any]]
    should_be_rejected: bool  # True = kernel must reject (omission/corruption)
    is_superset: bool  # True = strictly more deps than minimum


def _dep_to_dict(dep: DependencySpec) -> dict[str, Any]:
    return {
        "dependency_kind": dep.dependency_kind,
        "dependency_key": dep.dependency_key,
        "access_mode": dep.access_mode,
        "observed_version": dep.observed_version,
        "observed_digest": dep.observed_digest,
    }


def _deps_from_case(case: dict[str, Any]) -> list[DependencySpec]:
    """Generate the correct dependency vector from a test case."""
    inp = DependencyGenerationInput(
        operation_kind=case["operation_kind"],
        domain=case["domain"],
        semantic_keys=tuple(case["semantic_keys"]),
        policy_version=case.get("policy_version", "glhs.v1"),
        consent_version=case.get("consent_version", ""),
        evidence_ids=tuple(case.get("evidence_ids", [])),
        observed_entity_versions=case.get("observed_entity_versions", {}),
        policy_domain=case.get("policy_domain"),
    )
    result = generate_dependency_vector(inp)
    return list(result.dependencies)


def _mutate(
    mutation_class: str,
    case_id: str,
    description: str,
    original: list[DependencySpec],
    mutated: list[DependencySpec],
    should_be_rejected: bool,
    is_superset: bool = False,
) -> MutationResult:
    return MutationResult(
        mutation_id=f"mut-{mutation_class}-{uuid4().hex[:8]}",
        mutation_class=mutation_class,
        case_id=case_id,
        description=description,
        original_dep_count=len(original),
        mutated_dep_count=len(mutated),
        mutated_dependencies=[_dep_to_dict(d) for d in mutated],
        should_be_rejected=should_be_rejected,
        is_superset=is_superset,
    )


def m1_omit_entity(case: dict[str, Any]) -> MutationResult | None:
    """M1: Remove one entity dependency."""
    deps = _deps_from_case(case)
    entity_deps = [d for d in deps if d.dependency_kind == "ENTITY"]
    if not entity_deps:
        return None
    target = entity_deps[0]
    mutated = [d for d in deps if d is not target]
    return _mutate(
        "M1_omit_entity", case["case_id"],
        f"Omit entity dep: {target.dependency_key}",
        deps, mutated, should_be_rejected=True,
    )


def m2_add_irrelevant(case: dict[str, Any]) -> MutationResult:
    """M2: Add an unrelated entity dependency (conservative superset)."""
    deps = _deps_from_case(case)
    extra = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key="unrelated_domain:phantom_entity",
        access_mode="READ",
        observed_version=0,
    )
    mutated = deps + [extra]
    return _mutate(
        "M2_add_irrelevant", case["case_id"],
        "Add irrelevant entity dep: unrelated_domain:phantom_entity",
        deps, mutated, should_be_rejected=False, is_superset=True,
    )


def m3_mutate_entity_key(case: dict[str, Any]) -> MutationResult | None:
    """M3: Change the semantic_key portion of one entity dependency."""
    deps = _deps_from_case(case)
    entity_deps = [d for d in deps if d.dependency_kind == "ENTITY"]
    if not entity_deps:
        return None
    target = entity_deps[0]
    corrupted = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key=target.dependency_key + "_CORRUPTED",
        access_mode=target.access_mode,
        observed_version=target.observed_version,
        observed_digest=target.observed_digest,
    )
    mutated = [corrupted if d is target else d for d in deps]
    return _mutate(
        "M3_mutate_entity_key", case["case_id"],
        f"Corrupt entity key: {target.dependency_key} -> {corrupted.dependency_key}",
        deps, mutated, should_be_rejected=True,
    )


def m4_mutate_access_mode(case: dict[str, Any]) -> MutationResult | None:
    """M4: Flip READ <-> WRITE on one entity dependency."""
    deps = _deps_from_case(case)
    entity_deps = [d for d in deps if d.dependency_kind == "ENTITY"]
    if not entity_deps:
        return None
    target = entity_deps[0]
    flipped_mode = "READ" if target.access_mode == "WRITE" else "WRITE"
    corrupted = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key=target.dependency_key,
        access_mode=flipped_mode,
        observed_version=target.observed_version,
        observed_digest=target.observed_digest,
    )
    mutated = [corrupted if d is target else d for d in deps]
    return _mutate(
        "M4_mutate_access_mode", case["case_id"],
        f"Flip access mode on {target.dependency_key}: {target.access_mode} -> {flipped_mode}",
        deps, mutated, should_be_rejected=True,
    )


def m5_mutate_observed_version(case: dict[str, Any]) -> MutationResult | None:
    """M5: Increment observed_version by +1 (claiming stale data is fresh)."""
    deps = _deps_from_case(case)
    entity_deps = [d for d in deps if d.dependency_kind == "ENTITY" and d.observed_version > 0]
    if not entity_deps:
        return None
    target = entity_deps[0]
    corrupted = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key=target.dependency_key,
        access_mode=target.access_mode,
        observed_version=target.observed_version + 1,
        observed_digest=target.observed_digest,
    )
    mutated = [corrupted if d is target else d for d in deps]
    return _mutate(
        "M5_mutate_version", case["case_id"],
        f"Version lie on {target.dependency_key}: {target.observed_version} -> {target.observed_version + 1}",
        deps, mutated, should_be_rejected=True,
    )


def m6_multi_entity_write_skew(case: dict[str, Any]) -> MutationResult | None:
    """M6: Remove the second entity from a multi-entity write set."""
    deps = _deps_from_case(case)
    write_entities = [d for d in deps if d.dependency_kind == "ENTITY" and d.access_mode == "WRITE"]
    if len(write_entities) < 2:
        return None
    target = write_entities[1]
    mutated = [d for d in deps if d is not target]
    return _mutate(
        "M6_write_skew", case["case_id"],
        f"Write-skew: omit second write entity {target.dependency_key}",
        deps, mutated, should_be_rejected=True,
    )


def m7_unrelated_entity_update(case: dict[str, Any]) -> MutationResult | None:
    """M7: Replace one entity with one from a different domain."""
    deps = _deps_from_case(case)
    entity_deps = [d for d in deps if d.dependency_kind == "ENTITY"]
    if not entity_deps:
        return None
    target = entity_deps[0]
    replacement = DependencySpec(
        dependency_kind="ENTITY",
        dependency_key="social_posts:post_12345",
        access_mode=target.access_mode,
        observed_version=0,
    )
    mutated = [replacement if d is target else d for d in deps]
    return _mutate(
        "M7_unrelated_replace", case["case_id"],
        f"Replace {target.dependency_key} with social_posts:post_12345",
        deps, mutated, should_be_rejected=True,
    )


def m8_omit_evidence(case: dict[str, Any]) -> MutationResult | None:
    """M8: Remove one evidence dependency."""
    deps = _deps_from_case(case)
    evidence_deps = [d for d in deps if d.dependency_kind == "EVIDENCE"]
    if not evidence_deps:
        return None
    target = evidence_deps[0]
    mutated = [d for d in deps if d is not target]
    return _mutate(
        "M8_omit_evidence", case["case_id"],
        f"Omit evidence dep: {target.dependency_key}",
        deps, mutated, should_be_rejected=True,
    )


def m9_omit_governance(case: dict[str, Any]) -> MutationResult | None:
    """M9: Remove the governance (policy) dependency."""
    deps = _deps_from_case(case)
    gov_deps = [
        d for d in deps
        if d.dependency_kind == "GOVERNANCE" and "policy" in d.dependency_key
    ]
    if not gov_deps:
        return None
    target = gov_deps[0]
    mutated = [d for d in deps if d is not target]
    return _mutate(
        "M9_omit_governance", case["case_id"],
        f"Omit governance dep: {target.dependency_key}",
        deps, mutated, should_be_rejected=True,
    )


ALL_MUTATORS = [
    m1_omit_entity,
    m2_add_irrelevant,
    m3_mutate_entity_key,
    m4_mutate_access_mode,
    m5_mutate_observed_version,
    m6_multi_entity_write_skew,
    m7_unrelated_entity_update,
    m8_omit_evidence,
    m9_omit_governance,
]


def generate_mutants(cases_path: Path) -> list[MutationResult]:
    """Apply all mutators to all cases."""
    mutants: list[MutationResult] = []
    with cases_path.open(encoding="utf-8") as f:
        for line in f:
            case = json.loads(line)
            for mutator in ALL_MUTATORS:
                result = mutator(case)
                if result is not None:
                    mutants.append(result)
    return mutants


def write_mutants(cases_path: Path, output_dir: Path) -> Path:
    """Write all mutants to JSONL."""
    output_dir.mkdir(parents=True, exist_ok=True)
    mutants = generate_mutants(cases_path)
    out_path = output_dir / "mutants.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for m in mutants:
            row = {
                "mutation_id": m.mutation_id,
                "mutation_class": m.mutation_class,
                "case_id": m.case_id,
                "description": m.description,
                "original_dep_count": m.original_dep_count,
                "mutated_dep_count": m.mutated_dep_count,
                "mutated_dependencies": m.mutated_dependencies,
                "should_be_rejected": m.should_be_rejected,
                "is_superset": m.is_superset,
            }
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate dependency vector mutants")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evaluation/glhs_dependency_completeness/output"))
    args = parser.parse_args()
    path = write_mutants(args.cases, args.output)
    print(f"Generated mutants to {path}")
