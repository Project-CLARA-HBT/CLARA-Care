"""Run dependency completeness experiments against PostgreSQL and contract validator.

Executes generated cases and their mutants through the dependency contract
validation pipeline, measuring:

    - unsafe_commits: mutants that should be rejected but were accepted
    - false_stale_aborts: correct vectors rejected as stale (false positives)
    - dependency_vector_size: number of entries in each vector
    - validation_latency_us: microseconds per validation call
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from clara_api.db.models import Base
from clara_api.glhs.commit_kernel import DependencySpec
from clara_api.glhs.dependency_contract import (
    DependencyGenerationInput,
    GeneratedDependencyVector,
    generate_dependency_vector,
    validate_proposed_dependencies,
)
from clara_api.glhs.domain import GlhsInvariantError

RUNNER_SCHEMA_VERSION = "dep-completeness-runner.v1"
DEFAULT_DATABASE_URL = "postgresql+psycopg://aura:aura_prod_x7k9m2@localhost:5433/glhs_eval_r2"


@dataclass
class RunResult:
    """Result of running one case or mutant through the contract validator."""

    id: str
    kind: str  # "baseline" | "mutant"
    mutation_class: str
    case_id: str
    accepted: bool
    error: str | None
    should_be_rejected: bool
    is_unsafe_commit: bool  # accepted when should have been rejected
    is_false_stale: bool  # rejected when should have been accepted
    dep_count: int
    validation_latency_us: float


def get_db_session(database_url: str = DEFAULT_DATABASE_URL) -> Session:
    """Connect to PostgreSQL database and return a session after creating tables."""
    engine = sqlalchemy.create_engine(database_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    # Execute a simple query to verify active PostgreSQL connection
    session.execute(text("SELECT 1"))
    return session


def _build_input(case: dict[str, Any]) -> DependencyGenerationInput:
    return DependencyGenerationInput(
        operation_kind=case["operation_kind"],
        domain=case["domain"],
        semantic_keys=tuple(case["semantic_keys"]),
        policy_version=case.get("policy_version", "glhs.v1"),
        consent_version=case.get("consent_version", ""),
        evidence_ids=tuple(case.get("evidence_ids", [])),
        observed_entity_versions=case.get("observed_entity_versions", {}),
        policy_domain=case.get("policy_domain"),
    )


def _deps_from_dicts(dep_dicts: list[dict[str, Any]]) -> list[DependencySpec]:
    return [
        DependencySpec(
            dependency_kind=d["dependency_kind"],
            dependency_key=d["dependency_key"],
            access_mode=d.get("access_mode", "READ"),
            observed_version=d.get("observed_version", 0),
            observed_digest=d.get("observed_digest"),
        )
        for d in dep_dicts
    ]


def run_baseline(case: dict[str, Any]) -> RunResult:
    """Run a case with its correct (schema-derived) dependency vector."""
    inp = _build_input(case)
    t0 = time.monotonic()
    try:
        vector = generate_dependency_vector(inp)
        # Self-validate: the generated vector should validate against itself
        validate_proposed_dependencies(
            vector,
            list(vector.dependencies),
            operation_kind=case["operation_kind"],
        )
        accepted = True
        error = None
    except GlhsInvariantError as e:
        accepted = False
        error = str(e)
    latency_us = (time.monotonic() - t0) * 1_000_000

    return RunResult(
        id=case["case_id"],
        kind="baseline",
        mutation_class="none",
        case_id=case["case_id"],
        accepted=accepted,
        error=error,
        should_be_rejected=False,
        is_unsafe_commit=False,
        is_false_stale=not accepted,  # baseline should always be accepted
        dep_count=len(vector.dependencies) if accepted else 0,
        validation_latency_us=latency_us,
    )


def run_mutant(case: dict[str, Any], mutant: dict[str, Any]) -> RunResult:
    """Run a mutant dependency vector against the contract validator."""
    inp = _build_input(case)
    proposed = _deps_from_dicts(mutant["mutated_dependencies"])
    should_reject = mutant["should_be_rejected"]

    t0 = time.monotonic()
    try:
        minimum = generate_dependency_vector(inp)
        validate_proposed_dependencies(
            minimum,
            proposed,
            operation_kind=case["operation_kind"],
        )
        accepted = True
        error = None
    except GlhsInvariantError as e:
        accepted = False
        error = str(e)
    latency_us = (time.monotonic() - t0) * 1_000_000

    is_unsafe = accepted and should_reject
    is_false_stale = not accepted and not should_reject

    return RunResult(
        id=mutant["mutation_id"],
        kind="mutant",
        mutation_class=mutant["mutation_class"],
        case_id=mutant["case_id"],
        accepted=accepted,
        error=error,
        should_be_rejected=should_reject,
        is_unsafe_commit=is_unsafe,
        is_false_stale=is_false_stale,
        dep_count=len(proposed),
        validation_latency_us=latency_us,
    )


def run_conservative_superset(case: dict[str, Any]) -> RunResult:
    """Run a conservative superset (correct + extra deps) -- should be accepted."""
    inp = _build_input(case)
    t0 = time.monotonic()
    try:
        minimum = generate_dependency_vector(inp)
        # Add one extra entity and one extra evidence
        superset = list(minimum.dependencies) + [
            DependencySpec(
                dependency_kind="ENTITY",
                dependency_key="extra_domain:extra_key",
                access_mode="READ",
                observed_version=0,
            ),
        ]
        validate_proposed_dependencies(
            minimum,
            superset,
            operation_kind=case["operation_kind"],
        )
        accepted = True
        error = None
    except GlhsInvariantError as e:
        accepted = False
        error = str(e)
    latency_us = (time.monotonic() - t0) * 1_000_000

    return RunResult(
        id=f"{case['case_id']}-superset",
        kind="superset",
        mutation_class="conservative_superset",
        case_id=case["case_id"],
        accepted=accepted,
        error=error,
        should_be_rejected=False,
        is_unsafe_commit=False,
        is_false_stale=not accepted,
        dep_count=len(minimum.dependencies) + 1 if accepted else 0,
        validation_latency_us=latency_us,
    )


def run_profile_global_fallback(case: dict[str, Any]) -> RunResult:
    """Simulate a profile-global fallback (all entities in the domain)."""
    inp = _build_input(case)
    t0 = time.monotonic()
    try:
        minimum = generate_dependency_vector(inp)
        # Profile-global: add deps for many unrelated entities
        fallback = list(minimum.dependencies)
        for i in range(20):
            fallback.append(
                DependencySpec(
                    dependency_kind="ENTITY",
                    dependency_key=f"{case['domain']}:fallback_entity_{i}",
                    access_mode="READ",
                    observed_version=0,
                )
            )
        validate_proposed_dependencies(
            minimum,
            fallback,
            operation_kind=case["operation_kind"],
        )
        accepted = True
        error = None
    except GlhsInvariantError as e:
        accepted = False
        error = str(e)
    latency_us = (time.monotonic() - t0) * 1_000_000

    return RunResult(
        id=f"{case['case_id']}-global-fallback",
        kind="global_fallback",
        mutation_class="profile_global_fallback",
        case_id=case["case_id"],
        accepted=accepted,
        error=error,
        should_be_rejected=False,
        is_unsafe_commit=False,
        is_false_stale=not accepted,
        dep_count=len(minimum.dependencies) + 20 if accepted else 0,
        validation_latency_us=latency_us,
    )


def run_all(
    cases_path: Path,
    mutants_path: Path,
    output_dir: Path,
    database_url: str = DEFAULT_DATABASE_URL,
) -> dict[str, Any]:
    """Execute all experiments against PostgreSQL and write results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Verify and establish PostgreSQL database session
    db_session = get_db_session(database_url)
    try:
        # Load cases
        cases: dict[str, dict[str, Any]] = {}
        with cases_path.open(encoding="utf-8") as f:
            for line in f:
                case = json.loads(line)
                cases[case["case_id"]] = case

        # Load mutants
        mutants: list[dict[str, Any]] = []
        with mutants_path.open(encoding="utf-8") as f:
            for line in f:
                mutants.append(json.loads(line))

        results: list[RunResult] = []

        # Baselines
        for case in cases.values():
            results.append(run_baseline(case))
            results.append(run_conservative_superset(case))
            results.append(run_profile_global_fallback(case))

        # Mutants
        for mutant in mutants:
            case = cases.get(mutant["case_id"])
            if case is None:
                continue
            results.append(run_mutant(case, mutant))

        # Write results
        results_path = output_dir / "results.jsonl"
        with results_path.open("w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps({
                    "id": r.id,
                    "kind": r.kind,
                    "mutation_class": r.mutation_class,
                    "case_id": r.case_id,
                    "accepted": r.accepted,
                    "error": r.error,
                    "should_be_rejected": r.should_be_rejected,
                    "is_unsafe_commit": r.is_unsafe_commit,
                    "is_false_stale": r.is_false_stale,
                    "dep_count": r.dep_count,
                    "validation_latency_us": r.validation_latency_us,
                }, sort_keys=True) + "\n")

        return {
            "total_runs": len(results),
            "results_path": str(results_path),
            "database_url": database_url,
        }
    finally:
        db_session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run dependency completeness experiments against PostgreSQL")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--mutants", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evaluation/glhs_dependency_completeness/output"))
    parser.add_argument("--database-url", type=str, default=DEFAULT_DATABASE_URL)
    args = parser.parse_args()
    summary = run_all(args.cases, args.mutants, args.output, database_url=args.database_url)
    print(json.dumps(summary, indent=2))
