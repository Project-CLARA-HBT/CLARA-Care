"""Measure the API-owned PostgreSQL -> GST -> GLHS -> THSS path.

This runner is intentionally executed inside an API container.  GLHS has no
public arbitrary-GST HTTP endpoint: exposing one would weaken its trust
boundary.  The benchmark therefore calls the same API-owned gateway used by
production adapters and records that boundary explicitly in its manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from clara_api.db.models import (
    GlhsAssertion,
    GlhsAssertionEvidence,
    GlhsEvidence,
    GlhsSnapshotManifest,
    GlhsTransition,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    current_state_version,
    propose_assertion,
    reconstruct_governed_decision,
    reconstruct_state,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

OPERATIONS = (
    "transition",
    "reconstruction",
    "snapshot_compile",
    "governed_decision_reconstruction",
    "audit_lookup",
    "invalidation_rebuild",
    "enter_in_error_rebuild",
)
FIELDNAMES = (
    "operation",
    "history_depth",
    "concurrency",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "throughput_per_second",
    "db_reads",
    "db_writes",
    "write_amplification",
    "reconstruction_ms",
    "snapshot_compile_ms",
    "governed_decision_reconstruction_ms",
    "audit_lookup_ms",
    "invalidation_rebuild_ms",
    "enter_in_error_rebuild_ms",
    "cpu_percent",
    "peak_rss_bytes",
)


class SqlCounter:
    def __init__(self) -> None:
        self.reads = 0
        self.writes = 0

    def reset(self) -> None:
        self.reads = 0
        self.writes = 0

    def observe(self, _conn, _cursor, statement, _parameters, _context, _many) -> None:
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb in {"SELECT", "SHOW", "WITH"}:
            self.reads += 1
        elif verb in {"INSERT", "UPDATE", "DELETE"}:
            self.writes += 1


def _migrate_empty_database(database_url: str, *, repository_root: Path) -> None:
    api_root = repository_root / "services" / "api"
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=api_root,
        env=env,
        check=True,
    )


def _git_state(repository_root: Path) -> dict[str, object]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tracked_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        "implementation_sha": revision,
        "tracked_worktree_clean": not bool(tracked_status.strip()),
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5)))
    return ordered[index]


def scope_for(db: Session, suffix: str) -> ProfileScope:
    user = User(
        email=f"evidence-benchmark-{suffix}@example.invalid",
        hashed_password="not-a-login-secret",
        role="normal",
    )
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id)
    db.add(profile)
    db.flush()
    return ProfileScope(
        actor=user,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "view", "correct", "invalidate", "resolve"}),
        allowed_data_classes=frozenset({"medications", "evidence"}),
    )


def candidate(
    db: Session,
    scope: ProfileScope,
    *,
    index: int,
    semantic_key: str,
    valid_at: datetime,
) -> GlhsAssertion:
    fingerprint = f"benchmark:{scope.profile.public_id}:{index}:{semantic_key}"
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="benchmark_fixture",
        source_identity=fingerprint,
        checksum=fingerprint,
        observed_at=valid_at,
    )
    db.add(source)
    db.flush()
    evidence = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="structured_fixture",
            artifact_type="benchmark_fixture",
            artifact_public_id=f"fixture-{index}",
            fingerprint=fingerprint,
            valid_from=valid_at,
        ),
    )
    return propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=semantic_key,
            assertion_type="medications",
            predicate="active",
            value={"fixture_index": index},
            epistemic_state="reported",
            valid_from=valid_at,
            process_kind="user",
        ),
        evidence=((evidence, "supports"),),
    )


def timed(
    db: Session,
    counter: SqlCounter,
    repetitions: int,
    operation: Callable[[int], Any],
) -> tuple[list[float], int, int, float]:
    counter.reset()
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    latencies: list[float] = []
    for index in range(repetitions):
        started = time.perf_counter()
        operation(index)
        db.commit()
        latencies.append((time.perf_counter() - started) * 1000)
    wall = time.perf_counter() - wall_start
    cpu = time.process_time() - cpu_start
    return latencies, counter.reads, counter.writes, 100 * cpu / max(wall, 1e-9)


def row(
    operation: str,
    history_depth: int,
    repetitions: int,
    measured: tuple[list[float], int, int, float],
) -> dict[str, object]:
    latencies, reads, writes, cpu_percent = measured
    mean_ms = statistics.fmean(latencies)
    output: dict[str, object] = {
        "operation": operation,
        "history_depth": history_depth,
        "concurrency": 1,
        "p50_ms": round(percentile(latencies, 0.50), 3),
        "p95_ms": round(percentile(latencies, 0.95), 3),
        "p99_ms": round(percentile(latencies, 0.99), 3),
        "throughput_per_second": round(1000 / mean_ms, 3),
        "db_reads": reads,
        "db_writes": writes,
        "write_amplification": round(writes / repetitions, 3),
        "reconstruction_ms": "",
        "snapshot_compile_ms": "",
        "governed_decision_reconstruction_ms": "",
        "audit_lookup_ms": "",
        "invalidation_rebuild_ms": "",
        "enter_in_error_rebuild_ms": "",
        "cpu_percent": round(cpu_percent, 3),
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    duration_field = {
        "reconstruction": "reconstruction_ms",
        "snapshot_compile": "snapshot_compile_ms",
        "governed_decision_reconstruction": "governed_decision_reconstruction_ms",
        "audit_lookup": "audit_lookup_ms",
        "invalidation_rebuild": "invalidation_rebuild_ms",
        "enter_in_error_rebuild": "enter_in_error_rebuild_ms",
    }.get(operation)
    if duration_field:
        output[duration_field] = round(mean_ms, 3)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history-depth", type=int, default=50)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--database-image-digest", default="operator_not_supplied")
    parser.add_argument("--acknowledge-isolated-empty-database", action="store_true")
    args = parser.parse_args()
    if not args.database_url or not args.database_url.startswith("postgresql"):
        parser.error("a PostgreSQL DATABASE_URL is required")
    if not args.acknowledge_isolated_empty_database:
        parser.error("--acknowledge-isolated-empty-database is required")
    if args.history_depth < 5 or args.repetitions < 5:
        parser.error("history depth and repetitions must both be at least 5")
    if args.output.exists():
        parser.error("output path must not already exist")

    repository_root = Path(__file__).resolve().parents[2]
    engine = sa.create_engine(args.database_url, pool_pre_ping=True)
    if engine.url.database in {None, "postgres", "template0", "template1"}:
        parser.error("a non-default isolated database name is required")
    if sa.inspect(engine).get_table_names():
        parser.error("benchmark database must be empty before migration")
    engine.dispose()
    _migrate_empty_database(args.database_url, repository_root=repository_root)
    engine = sa.create_engine(args.database_url, pool_pre_ping=True)
    counter = SqlCounter()
    event.listen(engine, "before_cursor_execute", counter.observe)
    rows: list[dict[str, object]] = []
    started_at = datetime.now(UTC)
    with Session(engine) as db:
        transition_scope = scope_for(db, "transition")
        base = datetime(2025, 1, 1, tzinfo=UTC)

        def transition_op(index: int) -> None:
            assertion = candidate(
                db,
                transition_scope,
                index=index,
                semantic_key=f"medication:fixture:{index}",
                valid_at=base + timedelta(days=index),
            )
            apply_transition(
                db,
                scope=transition_scope,
                assertion=assertion,
                action="activate",
                expected_state_version=current_state_version(
                    db, profile_id=transition_scope.profile.id
                ),
                idempotency_key=f"benchmark-transition-{index}",
                transition_kind="benchmark_fixture",
                reason_code="benchmark_fixture",
            )

        rows.append(
            row(
                "transition",
                args.history_depth,
                args.repetitions,
                timed(db, counter, args.repetitions, transition_op),
            )
        )

        history_scope = scope_for(db, "history")
        assertions: list[GlhsAssertion] = []
        for index in range(args.history_depth):
            assertion = candidate(
                db,
                history_scope,
                index=index,
                semantic_key=f"medication:history:{index}",
                valid_at=base + timedelta(days=index),
            )
            apply_transition(
                db,
                scope=history_scope,
                assertion=assertion,
                action="activate",
                expected_state_version=current_state_version(
                    db, profile_id=history_scope.profile.id
                ),
                idempotency_key=f"benchmark-history-{index}",
                transition_kind="benchmark_fixture",
                reason_code="benchmark_fixture",
            )
            assertions.append(assertion)
        db.commit()
        as_of = base + timedelta(days=args.history_depth + 1)
        rows.append(
            row(
                "reconstruction",
                args.history_depth,
                args.repetitions,
                timed(
                    db,
                    counter,
                    args.repetitions,
                    lambda _index: reconstruct_state(
                        db, profile_id=history_scope.profile.id, valid_at=as_of
                    ),
                ),
            )
        )
        rows.append(
            row(
                "snapshot_compile",
                args.history_depth,
                args.repetitions,
                timed(
                    db,
                    counter,
                    args.repetitions,
                    lambda _index: compile_thss(
                        db,
                        scope=history_scope,
                        task="benchmark",
                        purpose="self_care",
                        allowed_data_classes=frozenset({"medications"}),
                        as_of=as_of,
                    ),
                ),
            )
        )

        decision_scope = scope_for(db, "decision")
        disclosed_assertion = candidate(
            db,
            decision_scope,
            index=0,
            semantic_key="medication:decision:source",
            valid_at=base,
        )
        apply_transition(
            db,
            scope=decision_scope,
            assertion=disclosed_assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key="benchmark-decision-source",
            transition_kind="benchmark_fixture",
            reason_code="benchmark_fixture",
        )
        disclosed_snapshot = compile_thss(
            db,
            scope=decision_scope,
            task="benchmark_decision",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
            as_of=as_of,
        )
        disclosed_evidence_id = db.scalar(
            select(GlhsAssertionEvidence.evidence_id).where(
                GlhsAssertionEvidence.assertion_id == disclosed_assertion.id
            )
        )
        disclosed_evidence = db.get(GlhsEvidence, disclosed_evidence_id)
        if disclosed_evidence is None:
            raise RuntimeError("benchmark_disclosed_evidence_missing")
        bound_assertion = propose_assertion(
            db,
            profile_id=decision_scope.profile.id,
            actor_user_id=decision_scope.actor.id,
            data=AssertionInput(
                semantic_key="medication:decision:bound",
                assertion_type="medications",
                predicate="active",
                value={"fixture": "bound-decision"},
                epistemic_state="reported",
                valid_from=base,
                process_kind="user",
                source_snapshot_id=disclosed_snapshot.snapshot_id,
                source_snapshot_digest=disclosed_snapshot.manifest_digest,
            ),
            evidence=((disclosed_evidence, "supports"),),
        )
        bound_transition = apply_transition(
            db,
            scope=decision_scope,
            assertion=bound_assertion,
            action="activate",
            expected_state_version=disclosed_snapshot.state_version,
            idempotency_key="benchmark-decision-bound",
            transition_kind="benchmark_bound_decision",
            reason_code="benchmark_bound_decision",
        )
        db.commit()
        rows.append(
            row(
                "governed_decision_reconstruction",
                args.history_depth,
                args.repetitions,
                timed(
                    db,
                    counter,
                    args.repetitions,
                    lambda _index: reconstruct_governed_decision(
                        db,
                        profile_id=decision_scope.profile.id,
                        snapshot_id=disclosed_snapshot.snapshot_id,
                        transition_id=bound_transition.public_id,
                    ),
                ),
            )
        )
        rows.append(
            row(
                "audit_lookup",
                args.history_depth,
                args.repetitions,
                timed(
                    db,
                    counter,
                    args.repetitions,
                    lambda _index: db.execute(
                        select(
                            GlhsTransition.public_id,
                            GlhsTransition.base_state_version,
                            GlhsTransition.resulting_state_version,
                            GlhsTransition.reason_code,
                        ).where(GlhsTransition.public_id == bound_transition.public_id)
                    ).one(),
                ),
            )
        )

        def retire_and_rebuild(index: int, kind: str) -> None:
            assertion = assertions[index % len(assertions)]
            if assertion.lifecycle_status not in {"active", "disputed"}:
                replacement = candidate(
                    db,
                    history_scope,
                    index=args.history_depth + index,
                    semantic_key=f"medication:replacement:{kind}:{index}",
                    valid_at=as_of + timedelta(minutes=index),
                )
                apply_transition(
                    db,
                    scope=history_scope,
                    assertion=replacement,
                    action="activate",
                    expected_state_version=current_state_version(
                        db, profile_id=history_scope.profile.id
                    ),
                    idempotency_key=f"benchmark-{kind}-replacement-{index}",
                    transition_kind="benchmark_fixture",
                    reason_code="benchmark_fixture",
                )
                assertion = replacement
                assertions[index % len(assertions)] = replacement
            apply_transition(
                db,
                scope=history_scope,
                assertion=assertion,
                action="supersede" if kind == "invalidation" else "enter_in_error",
                expected_state_version=current_state_version(
                    db, profile_id=history_scope.profile.id
                ),
                idempotency_key=f"benchmark-{kind}-{index}",
                transition_kind=f"benchmark_{kind}",
                reason_code=f"benchmark_{kind}",
            )
            compile_thss(
                db,
                scope=history_scope,
                task="benchmark_rebuild",
                purpose="self_care",
                allowed_data_classes=frozenset({"medications"}),
                as_of=as_of + timedelta(days=1),
            )

        rows.append(
            row(
                "invalidation_rebuild",
                args.history_depth,
                args.repetitions,
                timed(
                    db,
                    counter,
                    args.repetitions,
                    lambda index: retire_and_rebuild(index, "invalidation"),
                ),
            )
        )
        rows.append(
            row(
                "enter_in_error_rebuild",
                args.history_depth,
                args.repetitions,
                timed(
                    db,
                    counter,
                    args.repetitions,
                    lambda index: retire_and_rebuild(index, "enter_in_error"),
                ),
            )
        )

        counts = {
            "transitions": db.scalar(select(func.count()).select_from(GlhsTransition)),
            "assertions": db.scalar(select(func.count()).select_from(GlhsAssertion)),
            "snapshots": db.scalar(select(func.count()).select_from(GlhsSnapshotManifest)),
        }
        database_environment = {
            "server_version": db.scalar(sa.text("SHOW server_version")),
            "default_transaction_isolation": db.scalar(
                sa.text("SHOW default_transaction_isolation")
            ),
            "synchronous_commit": db.scalar(sa.text("SHOW synchronous_commit")),
            "max_connections": db.scalar(sa.text("SHOW max_connections")),
            "alembic_revision": db.scalar(sa.text("SELECT version_num FROM alembic_version")),
        }

    args.output.mkdir(parents=True, exist_ok=False)
    metrics_path = args.output / "fullstack_metrics.csv"
    with metrics_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "schema_version": "glhs-fullstack-service-layer.v2",
        "status": "EXECUTED_PARTIAL_SERVICE_LAYER",
        "architecture_path": "postgresql>gst>glhs>thss>api",
        "api_boundary": "in_process_api_owned_service_layer",
        "http_transport_measured": False,
        "coverage_gaps": [
            "http_transport",
            "source_revocation_propagation",
            "concurrent_transition",
        ],
        "production_services_modified": False,
        "fixture_contains_phi": False,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "history_depth": args.history_depth,
        "repetitions": args.repetitions,
        "worker_count": 1,
        "hardware": {
            "hostname": platform.node(),
            "cpu_count": os.cpu_count(),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "sqlalchemy": sa.__version__,
            "database": str(engine.dialect.name),
            "database_image_digest": args.database_image_digest,
            **database_environment,
        },
        "implementation": _git_state(repository_root),
        "row_counts": counts,
        "operations": list(OPERATIONS),
    }
    manifest_path = args.output / "fullstack_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksums = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in (metrics_path, manifest_path)
    ]
    (args.output / "checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
