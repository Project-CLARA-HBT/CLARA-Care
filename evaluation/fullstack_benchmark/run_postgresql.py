"""Measure the API-owned PostgreSQL -> GST -> GLHS -> THSS path.

This runner is intentionally executed inside an API container.  GLHS has no
public arbitrary-GST HTTP endpoint: exposing one would weaken its trust
boundary.  The benchmark therefore calls the same API-owned gateway used by
production adapters and records that boundary explicitly in its manifest.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import resource
import statistics
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAssertion,
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
    "invalidation_rebuild",
    "revocation_propagation",
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
    "invalidation_rebuild_ms",
    "revocation_propagation_ms",
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
        allowed_actions=frozenset({"create", "view", "resolve"}),
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
        "invalidation_rebuild_ms": "",
        "revocation_propagation_ms": "",
        "cpu_percent": round(cpu_percent, 3),
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    duration_field = {
        "reconstruction": "reconstruction_ms",
        "snapshot_compile": "snapshot_compile_ms",
        "invalidation_rebuild": "invalidation_rebuild_ms",
        "revocation_propagation": "revocation_propagation_ms",
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
    args = parser.parse_args()
    if not args.database_url or not args.database_url.startswith("postgresql"):
        parser.error("a PostgreSQL DATABASE_URL is required")
    if args.history_depth < 5 or args.repetitions < 5:
        parser.error("history depth and repetitions must both be at least 5")

    engine = sa.create_engine(args.database_url, pool_pre_ping=True)
    # The database is a freshly-created benchmark database.  Creating the
    # complete API schema here keeps the run isolated from production data;
    # production deployments still use Alembic migrations.
    Base.metadata.create_all(engine)
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
                "revocation_propagation",
                args.history_depth,
                args.repetitions,
                timed(
                    db,
                    counter,
                    args.repetitions,
                    lambda index: retire_and_rebuild(index, "revocation"),
                ),
            )
        )

        counts = {
            "transitions": db.scalar(select(func.count()).select_from(GlhsTransition)),
            "assertions": db.scalar(select(func.count()).select_from(GlhsAssertion)),
            "snapshots": db.scalar(select(func.count()).select_from(GlhsSnapshotManifest)),
        }

    args.output.mkdir(parents=True, exist_ok=False)
    metrics_path = args.output / "fullstack_metrics.csv"
    with metrics_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "status": "frozen",
        "architecture_path": "postgresql>gst>glhs>thss>api",
        "api_boundary": "in_process_api_owned_service_layer",
        "http_transport_measured": False,
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
        },
        "row_counts": counts,
        "operations": list(OPERATIONS),
    }
    (args.output / "fullstack_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
