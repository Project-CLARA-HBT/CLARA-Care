"""Measure true and false stale rejections on the production GLHS write path."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import sqlalchemy as sa
from clara_api.db.models import GlhsAssertion, PhrProfile, User
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import apply_transition
from clara_api.lifemap.profile_scope import ProfileScope
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from evaluation.contention_analysis.strategy_model import STRATEGIES, matrix
from evaluation.fullstack_benchmark.run_postgresql import (
    SqlCounter,
    _git_state,
    _migrate_empty_database,
    candidate,
    percentile,
    scope_for,
)

CONCURRENCY_LEVELS = (1, 2, 4, 8, 16)
WORKLOADS = ("same_dependency", "unrelated_slots")
IMPLEMENTATION_FILES = (
    "evaluation/contention_analysis/run_postgresql.py",
    "evaluation/contention_analysis/strategy_model.py",
    "evaluation/contention_analysis/validate.py",
    "evaluation/fullstack_benchmark/run_postgresql.py",
    "services/api/src/clara_api/glhs/gateway.py",
    "services/api/alembic/versions/20260811_0055_glhs_manifest_binding.py",
)
ATTEMPT_FIELDS = (
    "workload",
    "concurrency",
    "batch",
    "writer",
    "result",
    "reason_code",
    "stale_class",
    "latency_ms",
    "batch_wall_ms",
    "batch_db_reads",
    "batch_db_writes",
)
SUMMARY_FIELDS = (
    "workload",
    "concurrency",
    "independent_profile_batches",
    "attempts",
    "accepted_valid_commits",
    "true_stale_rejections",
    "false_stale_rejections",
    "database_errors",
    "retry_count",
    "successful_retries",
    "false_stale_rate_per_attempt",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "throughput_per_second",
    "db_reads",
    "db_writes",
    "writes_per_accepted_commit",
    "peak_rss_bytes",
)


@dataclass(frozen=True)
class RaceResult:
    writer: int
    result: str
    reason_code: str
    stale_class: str
    latency_ms: float


def _as_float(value: object) -> float:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise TypeError("contention_numeric_value_required")
    return float(value)


def _as_int(value: object) -> int:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise TypeError("contention_integer_value_required")
    return int(value)


def _implementation_state(repository_root: Path) -> dict[str, object]:
    state = _git_state(repository_root)
    state["implementation_paths_tracked"] = (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", *IMPLEMENTATION_FILES],
            cwd=repository_root,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    state["files_sha256"] = {
        path: hashlib.sha256((repository_root / path).read_bytes()).hexdigest()
        for path in IMPLEMENTATION_FILES
    }
    return state


def _race(
    engine: sa.Engine,
    *,
    profile_id: int,
    assertion_ids: list[str],
    workload: str,
    batch: int,
) -> tuple[list[RaceResult], float]:
    barrier = Barrier(len(assertion_ids))

    def write(item: tuple[int, str]) -> RaceResult:
        writer, assertion_id = item
        with Session(engine) as db:
            profile = db.get(PhrProfile, profile_id)
            if profile is None:
                raise RuntimeError("contention_profile_missing")
            actor = db.get(User, profile.user_id)
            assertion = db.scalar(
                select(GlhsAssertion).where(GlhsAssertion.public_id == assertion_id)
            )
            if actor is None or assertion is None:
                raise RuntimeError("contention_fixture_missing")
            scope = ProfileScope(
                actor=actor,
                profile=profile,
                actor_role="owner",
                purpose="self_care",
                allowed_actions=frozenset({"create"}),
                allowed_data_classes=frozenset({"medications"}),
            )
            barrier.wait(timeout=30)
            started = time.perf_counter()
            try:
                apply_transition(
                    db,
                    scope=scope,
                    assertion=assertion,
                    action="activate",
                    expected_state_version=0,
                    idempotency_key=f"contention-{workload}-{batch}-{writer}",
                    transition_kind="contention_analysis",
                    reason_code="contention_analysis",
                )
                db.commit()
            except GlhsInvariantError as exc:
                db.rollback()
                reason = str(exc)
                return RaceResult(
                    writer=writer,
                    result="rejected",
                    reason_code=reason,
                    stale_class=(
                        "true_stale"
                        if reason == "stale_state_version" and workload == "same_dependency"
                        else "false_stale"
                        if reason == "stale_state_version" and workload == "unrelated_slots"
                        else "unclassified_failure"
                    ),
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            except sa.exc.SQLAlchemyError as exc:
                db.rollback()
                return RaceResult(
                    writer=writer,
                    result="database_error",
                    reason_code=type(exc).__name__,
                    stale_class="database_error",
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            return RaceResult(
                writer=writer,
                result="accepted",
                reason_code="accepted",
                stale_class="none",
                latency_ms=(time.perf_counter() - started) * 1000,
            )

    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(assertion_ids)) as pool:
        results = list(pool.map(write, enumerate(assertion_ids)))
    return results, (time.perf_counter() - wall_started) * 1000


def _seed(
    engine: sa.Engine,
    *,
    workload: str,
    concurrency: int,
    batch: int,
) -> tuple[int, list[str]]:
    with Session(engine) as db:
        scope = scope_for(db, f"contention-{workload}-{concurrency}-{batch}")
        assertion_ids = []
        for writer in range(concurrency):
            semantic_key = (
                "medication:shared-dependency"
                if workload == "same_dependency"
                else f"medication:unrelated:{writer}"
            )
            assertion = candidate(
                db,
                scope,
                index=writer,
                semantic_key=semantic_key,
                valid_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            assertion_ids.append(assertion.public_id)
        db.commit()
        return scope.profile.id, assertion_ids


def _summaries(
    attempts: list[dict[str, object]], *, repetitions: int
) -> list[dict[str, object]]:
    summaries = []
    for workload in WORKLOADS:
        for concurrency in CONCURRENCY_LEVELS:
            rows = [
                row
                for row in attempts
                if row["workload"] == workload and row["concurrency"] == concurrency
            ]
            latencies = [_as_float(row["latency_ms"]) for row in rows]
            batch_wall = {
                _as_int(row["batch"]): _as_float(row["batch_wall_ms"]) for row in rows
            }
            batch_reads = {
                _as_int(row["batch"]): _as_int(row["batch_db_reads"]) for row in rows
            }
            batch_writes = {
                _as_int(row["batch"]): _as_int(row["batch_db_writes"])
                for row in rows
            }
            accepted = sum(row["result"] == "accepted" for row in rows)
            false_stale = sum(row["stale_class"] == "false_stale" for row in rows)
            summaries.append(
                {
                    "workload": workload,
                    "concurrency": concurrency,
                    "independent_profile_batches": repetitions,
                    "attempts": len(rows),
                    "accepted_valid_commits": accepted,
                    "true_stale_rejections": sum(
                        row["stale_class"] == "true_stale" for row in rows
                    ),
                    "false_stale_rejections": false_stale,
                    "database_errors": sum(row["result"] == "database_error" for row in rows),
                    "retry_count": 0,
                    "successful_retries": 0,
                    "false_stale_rate_per_attempt": round(false_stale / len(rows), 6),
                    "p50_ms": round(percentile(latencies, 0.50), 3),
                    "p95_ms": round(percentile(latencies, 0.95), 3),
                    "p99_ms": round(percentile(latencies, 0.99), 3),
                    "throughput_per_second": round(
                        1000 * len(rows) / sum(batch_wall.values()), 3
                    ),
                    "db_reads": sum(batch_reads.values()),
                    "db_writes": sum(batch_writes.values()),
                    "writes_per_accepted_commit": round(
                        sum(batch_writes.values()) / max(accepted, 1), 3
                    ),
                    "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    * 1024,
                }
            )
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--database-image-digest", required=True)
    parser.add_argument("--acknowledge-isolated-empty-database", action="store_true")
    args = parser.parse_args()
    if not args.database_url or not args.database_url.startswith("postgresql"):
        parser.error("a PostgreSQL DATABASE_URL is required")
    if not args.acknowledge_isolated_empty_database:
        parser.error("--acknowledge-isolated-empty-database is required")
    if args.output.exists():
        parser.error("output path must not already exist")
    if args.repetitions < 3:
        parser.error("repetitions must be at least 3")

    repository_root = Path(__file__).resolve().parents[2]
    engine = sa.create_engine(
        args.database_url,
        pool_pre_ping=True,
        pool_size=max(CONCURRENCY_LEVELS),
        max_overflow=4,
    )
    if engine.url.database in {None, "postgres", "template0", "template1"}:
        parser.error("a non-default isolated database name is required")
    if sa.inspect(engine).get_table_names():
        parser.error("contention database must be empty before migration")
    engine.dispose()
    _migrate_empty_database(args.database_url, repository_root=repository_root)
    engine = sa.create_engine(
        args.database_url,
        pool_pre_ping=True,
        pool_size=max(CONCURRENCY_LEVELS),
        max_overflow=4,
    )
    counter = SqlCounter()
    event.listen(engine, "before_cursor_execute", counter.observe)
    attempts: list[dict[str, object]] = []
    started_at = datetime.now(UTC)
    for workload in WORKLOADS:
        for concurrency in CONCURRENCY_LEVELS:
            for batch in range(args.repetitions):
                profile_id, assertion_ids = _seed(
                    engine,
                    workload=workload,
                    concurrency=concurrency,
                    batch=batch,
                )
                counter.reset()
                results, batch_wall_ms = _race(
                    engine,
                    profile_id=profile_id,
                    assertion_ids=assertion_ids,
                    workload=workload,
                    batch=batch,
                )
                for result in results:
                    attempts.append(
                        {
                            "workload": workload,
                            "concurrency": concurrency,
                            "batch": batch,
                            "writer": result.writer,
                            "result": result.result,
                            "reason_code": result.reason_code,
                            "stale_class": result.stale_class,
                            "latency_ms": round(result.latency_ms, 3),
                            "batch_wall_ms": round(batch_wall_ms, 3),
                            "batch_db_reads": counter.reads,
                            "batch_db_writes": counter.writes,
                        }
                    )
    summaries = _summaries(attempts, repetitions=args.repetitions)
    with Session(engine) as db:
        database_environment = {
            "server_version": db.scalar(sa.text("SHOW server_version")),
            "default_transaction_isolation": db.scalar(
                sa.text("SHOW default_transaction_isolation")
            ),
            "synchronous_commit": db.scalar(sa.text("SHOW synchronous_commit")),
            "alembic_revision": db.scalar(sa.text("SELECT version_num FROM alembic_version")),
            "database_size_bytes": db.scalar(
                sa.text("SELECT pg_database_size(current_database())")
            ),
        }

    args.output.mkdir(parents=True, exist_ok=False)
    attempts_path = args.output / "attempts.csv"
    with attempts_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ATTEMPT_FIELDS)
        writer.writeheader()
        writer.writerows(attempts)
    summary_path = args.output / "summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summaries)
    strategy_model_path = args.output / "strategy_model.json"
    strategy_model_path.write_text(
        json.dumps(
            {
                "schema_version": "glhs-version-strategy-model.v1",
                "status": "DETERMINISTIC_MECHANISM_MODEL_NOT_PRODUCTION_EXECUTION",
                "latency_measured": False,
                "strategies": list(STRATEGIES),
                "rows": matrix(WORKLOADS, CONCURRENCY_LEVELS),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "glhs-contention-analysis.v1",
        "status": "EXECUTED_PARTIAL_PRODUCTION_STRATEGY",
        "implementation": _implementation_state(repository_root),
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "experimental_unit": "independently_seeded_profile_race_batch",
        "observational_unit": "writer_attempt",
        "aggregation": "workload_by_concurrency_level",
        "false_stale_definition": (
            "rejected_only_because_an_intervening_profile_transition_was_outside_"
            "the_proposals_declared_semantic_dependency"
        ),
        "dependency_operationalization": "assertion_semantic_key",
        "inference": "descriptive_no_hypothesis_test",
        "missing_output_policy": "missing_or_unclassified_attempt_is_failure",
        "strategy": "production_profile_global_version",
        "workloads": list(WORKLOADS),
        "concurrency_levels": list(CONCURRENCY_LEVELS),
        "repetitions": args.repetitions,
        "retry_policy": "no_retry_in_primary_race",
        "coverage_gaps": [
            "alternative_strategy_postgresql_performance",
            "consent_or_policy_change_workload",
            "mixed_read_snapshot_write_workload",
            "retry_success_study",
        ],
        "fixture_contains_phi": False,
        "external_calls": 0,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "sqlalchemy": sa.__version__,
            "database": "postgresql",
            "database_image_digest": args.database_image_digest,
            **database_environment,
        },
    }
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifact_paths = (attempts_path, summary_path, strategy_model_path, manifest_path)
    (args.output / "checksums.sha256").write_text(
        "\n".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
            for path in artifact_paths
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
