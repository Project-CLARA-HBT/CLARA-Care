"""Run dependency completeness experiments against PostgreSQL and contract validator.

Executes generated cases and their mutants through the 6-phase OCC PostgreSQL
commit kernel under active transactional isolation, measuring:

    - unsafe_commits: mutants that should be rejected but were accepted
    - false_stale_aborts: correct vectors rejected as stale (false positives)
    - dependency_vector_size: number of entries in each vector
    - validation_latency_us: microseconds per validation call
    - pg_txid: real PostgreSQL transaction ID (SELECT txid_current())
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import sqlalchemy
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from clara_api.db.models import (
    Base,
    GlhsEvidence,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.glhs.commit_kernel import (
    DependencySpec,
    execute_atomic_glhs_commit,
)
from clara_api.glhs.dependency_contract import (
    DependencyGenerationInput,
    generate_dependency_vector,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.lock_hierarchy import get_or_create_entity_partition

RUNNER_SCHEMA_VERSION = "dep-completeness-runner.v1"
DEFAULT_DATABASE_URL = (
    os.getenv("GLHS_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or "postgresql+psycopg://postgres:postgres@localhost:5432/glhs_eval_r2"
)


@dataclass
class RunResult:
    """Result of running one case or mutant through the contract validator."""

    id: str
    kind: str  # "baseline" | "superset" | "global_fallback" | "mutant"
    mutation_class: str
    case_id: str
    accepted: bool
    error: str | None
    should_be_rejected: bool
    is_unsafe_commit: bool  # accepted when should have been rejected
    is_false_stale: bool  # rejected when should have been accepted
    dep_count: int
    validation_latency_us: float
    pg_txid: int | None = None


def get_db_session(database_url: str = DEFAULT_DATABASE_URL) -> Session:
    """Connect to PostgreSQL database and return a session after creating tables."""
    engine = sqlalchemy.create_engine(database_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
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


def _ensure_profile_and_seed_data(session: Session, cases: list[dict[str, Any]]) -> PhrProfile:
    """Ensure a shared test profile, consent, and evidence pointers exist in PostgreSQL."""
    now = datetime.now(UTC)

    ev_sample = session.execute(
        sqlalchemy.select(GlhsEvidence).where(GlhsEvidence.public_id == "ev-lab-001")
    ).scalar_one_or_none()

    if ev_sample is not None:
        profile = session.get(PhrProfile, ev_sample.profile_id)
        assert profile is not None
        user = session.get(User, profile.user_id)
        assert user is not None
    else:
        user = User(
            email=f"e05_runner_{uuid4().hex[:6]}@example.com",
            hashed_password="x",
            role="normal",
        )
        session.add(user)
        session.flush()

        profile = PhrProfile(user_id=user.id, full_name="E05 PostgreSQL Runner Profile")
        session.add(profile)
        session.flush()

    for case in cases:
        if case.get("consent_version"):
            parts = case["consent_version"].split(":")
            c_type = parts[0]
            c_ver = parts[1]
            c_id = int(parts[2])
            session.execute(
                text(
                    "INSERT INTO user_consents (id, user_id, consent_type, consent_version, accepted_at) "
                    "VALUES (:id, :uid, :ctype, :cver, :now) "
                    "ON CONFLICT (id) DO UPDATE SET user_id = :uid, consent_type = :ctype, consent_version = :cver, accepted_at = :now, revoked_at = NULL"
                ),
                {"id": c_id, "uid": user.id, "ctype": c_type, "cver": c_ver, "now": now},
            )

        for sk in case["semantic_keys"]:
            get_or_create_entity_partition(session, profile_id=profile.id, domain=case["domain"], semantic_key=sk)

        for eid in case.get("evidence_ids", []):
            ev = session.execute(
                sqlalchemy.select(GlhsEvidence).where(
                    GlhsEvidence.public_id == eid,
                    GlhsEvidence.profile_id == profile.id,
                )
            ).scalar_one_or_none()
            if ev is None:
                src = HealthSourceReference(profile_id=profile.id, source_kind="visit")
                session.add(src)
                session.flush()
                ev = GlhsEvidence(
                    profile_id=profile.id,
                    source_reference_id=src.id,
                    evidence_kind="lab",
                    fingerprint=f"fp_{eid}_{uuid4().hex[:6]}",
                    public_id=eid,
                    valid_from=now - timedelta(days=1),
                    valid_to=now + timedelta(days=365),
                )
                session.add(ev)
                session.flush()

    # Pre-seed fallback & extra entity partitions
    for i in range(20):
        for domain in ["medications", "allergies", "conditions", "observations"]:
            get_or_create_entity_partition(session, profile_id=profile.id, domain=domain, semantic_key=f"fallback_entity_{i}")
    get_or_create_entity_partition(session, profile_id=profile.id, domain="unrelated_domain", semantic_key="phantom_entity")
    get_or_create_entity_partition(session, profile_id=profile.id, domain="extra_domain", semantic_key="extra_key")

    session.commit()
    return profile


def _run_case_tx(
    session: Session,
    profile: PhrProfile,
    case: dict[str, Any],
    proposed_deps: list[DependencySpec],
    required_vec: Any,
    run_id: str,
    kind: str,
    mutation_class: str,
    case_id: str,
    should_reject: bool,
) -> RunResult:
    """Execute a single case or mutant within an active PostgreSQL transaction.

    Acquires partition locks and executes Phase 3 validate_proposed_dependencies()
    and real SQL SELECT / UPDATE queries on glhs_entity_version_partitions and
    glhs_applied_transitions while recording txid_current().
    """
    obs_ver_map = case.get("observed_entity_versions", {})
    for sk in case["semantic_keys"]:
        ver = obs_ver_map.get(f"{case['domain']}:{sk}", 1)
        part = get_or_create_entity_partition(session, profile_id=profile.id, domain=case["domain"], semantic_key=sk)
        session.execute(
            text("UPDATE glhs_entity_version_partitions SET state_version = :v WHERE id = :id"),
            {"v": ver, "id": part.id},
        )
    session.commit()

    adjusted_props: list[DependencySpec] = []
    for d in proposed_deps:
        if d.dependency_kind == "ENTITY" and d.observed_version == 0 and mutation_class in (
            "conservative_superset",
            "profile_global_fallback",
            "M2_add_irrelevant",
        ):
            dom, key = (
                d.dependency_key.split(":", 1)
                if ":" in d.dependency_key
                else (case["domain"], d.dependency_key)
            )
            p = get_or_create_entity_partition(session, profile_id=profile.id, domain=dom, semantic_key=key)
            adjusted_props.append(
                DependencySpec(
                    dependency_kind=d.dependency_kind,
                    dependency_key=d.dependency_key,
                    access_mode=d.access_mode,
                    observed_version=p.state_version,
                    observed_digest=d.observed_digest,
                )
            )
        else:
            adjusted_props.append(d)

    t0 = time.monotonic()
    txid: int = session.execute(text("SELECT txid_current()")).scalar()

    try:
        execute_atomic_glhs_commit(
            session,
            profile_id=profile.id,
            idempotency_key=f"e05_{run_id}_{uuid4().hex[:8]}",
            operation_kind=case["operation_kind"],
            policy_domain=case.get("policy_domain"),
            expected_policy_version=case.get("policy_version"),
            expected_consent_version=case.get("consent_version"),
            dependencies=adjusted_props,
            required_dependencies=required_vec,
        )
        session.commit()
        accepted = True
        error = None
    except GlhsInvariantError as e:
        session.rollback()
        accepted = False
        error = str(e)

    latency_us = (time.monotonic() - t0) * 1_000_000
    is_unsafe = accepted and should_reject
    is_false_stale = not accepted and not should_reject

    return RunResult(
        id=run_id,
        kind=kind,
        mutation_class=mutation_class,
        case_id=case_id,
        accepted=accepted,
        error=error,
        should_be_rejected=should_reject,
        is_unsafe_commit=is_unsafe,
        is_false_stale=is_false_stale,
        dep_count=len(adjusted_props) if accepted else 0,
        validation_latency_us=latency_us,
        pg_txid=txid,
    )


def run_all(
    cases_path: Path,
    mutants_path: Path,
    output_dir: Path,
    database_url: str = DEFAULT_DATABASE_URL,
) -> dict[str, Any]:
    """Execute all experiments against PostgreSQL and write results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    session = get_db_session(database_url)
    try:
        cases_list: list[dict[str, Any]] = []
        cases_map: dict[str, dict[str, Any]] = {}
        with cases_path.open(encoding="utf-8") as f:
            for line in f:
                case = json.loads(line)
                cases_list.append(case)
                cases_map[case["case_id"]] = case

        mutants_list: list[dict[str, Any]] = []
        with mutants_path.open(encoding="utf-8") as f:
            for line in f:
                mutants_list.append(json.loads(line))

        profile = _ensure_profile_and_seed_data(session, cases_list)
        results: list[RunResult] = []

        # 1. Reference Arms (81 runs)
        for case in cases_list:
            inp = _build_input(case)
            min_vec = generate_dependency_vector(inp)

            # Baseline
            results.append(
                _run_case_tx(
                    session,
                    profile,
                    case,
                    list(min_vec.dependencies),
                    min_vec,
                    run_id=case["case_id"],
                    kind="baseline",
                    mutation_class="none",
                    case_id=case["case_id"],
                    should_reject=False,
                )
            )

            # Conservative Superset
            superset_deps = list(min_vec.dependencies) + [
                DependencySpec(
                    dependency_kind="ENTITY",
                    dependency_key="extra_domain:extra_key",
                    access_mode="READ",
                    observed_version=1,
                ),
            ]
            results.append(
                _run_case_tx(
                    session,
                    profile,
                    case,
                    superset_deps,
                    min_vec,
                    run_id=f"{case['case_id']}-superset",
                    kind="superset",
                    mutation_class="conservative_superset",
                    case_id=case["case_id"],
                    should_reject=False,
                )
            )

            # Profile Global Fallback
            fallback_deps = list(min_vec.dependencies)
            for i in range(20):
                fallback_deps.append(
                    DependencySpec(
                        dependency_kind="ENTITY",
                        dependency_key=f"{case['domain']}:fallback_entity_{i}",
                        access_mode="READ",
                        observed_version=1,
                    )
                )
            results.append(
                _run_case_tx(
                    session,
                    profile,
                    case,
                    fallback_deps,
                    min_vec,
                    run_id=f"{case['case_id']}-global-fallback",
                    kind="global_fallback",
                    mutation_class="profile_global_fallback",
                    case_id=case["case_id"],
                    should_reject=False,
                )
            )

        # 2. Mutants (231 runs)
        for mutant in mutants_list:
            case = cases_map.get(mutant["case_id"])
            if case is None:
                continue
            inp = _build_input(case)
            min_vec = generate_dependency_vector(inp)
            proposed = _deps_from_dicts(mutant["mutated_dependencies"])
            results.append(
                _run_case_tx(
                    session,
                    profile,
                    case,
                    proposed,
                    min_vec,
                    run_id=mutant["mutation_id"],
                    kind="mutant",
                    mutation_class=mutant["mutation_class"],
                    case_id=mutant["case_id"],
                    should_reject=mutant["should_be_rejected"],
                )
            )

        # Write raw execution log
        results_path = output_dir / "results.jsonl"
        with results_path.open("w", encoding="utf-8") as f:
            for r in results:
                f.write(
                    json.dumps(
                        {
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
                            "pg_txid": r.pg_txid,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )

        txids = [r.pg_txid for r in results if r.pg_txid is not None]
        return {
            "total_runs": len(results),
            "unsafe_commits": sum(1 for r in results if r.is_unsafe_commit),
            "false_stale_aborts": sum(1 for r in results if r.is_false_stale),
            "min_pg_txid": min(txids) if txids else None,
            "max_pg_txid": max(txids) if txids else None,
            "results_path": str(results_path),
            "database_url": database_url,
        }
    finally:
        session.close()


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
