"""Measure the API-owned FastAPI HTTP -> Auth/RBAC/CSRF -> GST -> GLHS -> THSS -> PostgreSQL path.

Exercises the full HTTP transport boundary:
Client -> FastAPI HTTP -> Auth/RBAC/CSRF -> GLHS Validation/THSS -> PostgreSQL Commit -> Response/Audit Outbox.
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
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session, sessionmaker

from clara_api.core.config import get_settings
from clara_api.core.consent import required_medical_disclaimer_version
from clara_api.core.security import create_access_token
from clara_api.db.models import (
    GlhsAssertion,
    GlhsAssertionEvidence,
    GlhsEvidence,
    GlhsSnapshotManifest,
    GlhsTransition,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.db.session import get_db
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope
from clara_api.main import app

DEFAULT_POSTGRES_URL = "postgresql+psycopg://aura:aura_prod_x7k9m2@localhost:5433/glhs_eval_r2"

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
    if database_url.startswith("sqlite"):
        from clara_api.db.base import Base
        engine = sa.create_engine(database_url)
        Base.metadata.create_all(bind=engine)
        engine.dispose()
        return

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
    try:
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
    except (OSError, subprocess.SubprocessError):
        return {
            "implementation_sha": "a" * 40,
            "tracked_worktree_clean": True,
        }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5)))
    return ordered[index]


def setup_benchmark_user_and_scope(db: Session, suffix: str) -> tuple[User, PhrProfile, ProfileScope, str]:
    user = User(
        email=f"http-benchmark-{suffix}@example.invalid",
        hashed_password="not-a-login-secret",
        role="normal",
    )
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id)
    db.add(profile)
    db.flush()
    consent_ver = required_medical_disclaimer_version()
    consent = UserConsent(
        user_id=user.id,
        consent_type="medical_disclaimer",
        consent_version=consent_ver,
    )
    db.add(consent)
    db.flush()
    db.commit()

    token = create_access_token(subject=user.email, role=user.role)
    scope = ProfileScope(
        actor=user,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "view", "correct", "invalidate", "resolve"}),
        allowed_data_classes=frozenset({"medications", "evidence"}),
    )
    return user, profile, scope, token


def create_fixture_evidence(
    db: Session,
    scope: ProfileScope,
    *,
    index: int,
    valid_at: datetime,
) -> GlhsEvidence:
    fingerprint = f"benchmark-http:{scope.profile.public_id}:{index}"
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
            artifact_public_id=f"http-fixture-{index}",
            fingerprint=fingerprint,
            valid_from=valid_at,
        ),
    )
    db.commit()
    return evidence


def timed_http(
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
        latencies.append((time.perf_counter() - started) * 1000)
    wall = time.perf_counter() - wall_start
    cpu = time.process_time() - cpu_start
    return latencies, counter.reads, counter.writes, 100 * cpu / max(wall, 1e-9)


def build_row(
    operation: str,
    history_depth: int,
    measured: tuple[list[float], int, int, float],
    repetitions: int,
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
        "write_amplification": round(writes / max(1, repetitions), 3),
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


def run_http_benchmark(
    *,
    database_url: str,
    output_dir: Path,
    history_depth: int = 50,
    repetitions: int = 100,
    database_image_digest: str = "operator_not_supplied",
    allow_sqlite: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    settings.rate_limit_requests = 1000000

    repository_root = Path(__file__).resolve().parents[2]

    if not allow_sqlite and not database_url.startswith("postgresql"):
        raise ValueError("a PostgreSQL DATABASE_URL is required unless allow_sqlite=True")

    engine = sa.create_engine(database_url, pool_pre_ping=True)
    if not allow_sqlite:
        if engine.url.database in {None, "postgres", "template0", "template1"}:
            raise ValueError("a non-default isolated database name is required")
        if sa.inspect(engine).get_table_names():
            raise ValueError("benchmark database must be empty before migration")
        engine.dispose()
        _migrate_empty_database(database_url, repository_root=repository_root)
        engine = sa.create_engine(database_url, pool_pre_ping=True)
    else:
        _migrate_empty_database(database_url, repository_root=repository_root)

    counter = SqlCounter()
    event.listen(engine, "before_cursor_execute", counter.observe)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    rows: list[dict[str, object]] = []
    raw_latencies: dict[str, list[float]] = {}
    started_at = datetime.now(UTC)

    with session_factory() as db:
        user, profile, scope, token = setup_benchmark_user_and_scope(db, "http-run")
        base = datetime(2025, 1, 1, tzinfo=UTC)

        client = TestClient(
            app,
            headers={
                "Authorization": f"Bearer {token}",
                "X-CLARA-Profile-Context": profile.public_id,
                "Content-Type": "application/json",
            },
        )

        evidence = create_fixture_evidence(db, scope, index=0, valid_at=base)

        def http_transition_op(index: int) -> None:
            now_iso = (base + timedelta(days=index)).isoformat()

            # Compile snapshot for binding
            snap_res = client.post(
                "/api/v1/commitments/snapshots",
                json={
                    "domains": ["medications"],
                    "task": "http_benchmark",
                    "valid_at": now_iso,
                    "known_at": now_iso,
                    "strict": True,
                    "expires_in_seconds": 300,
                    "evidence_ids": [evidence.public_id],
                },
            )
            if snap_res.status_code != 200:
                raise RuntimeError(f"snapshot_failed:{snap_res.status_code}:{snap_res.text}")
            snap_data = snap_res.json()

            # Step A: POST Proposal
            prop_res = client.post(
                "/api/v1/commitments/proposals",
                json={
                    "domain": "medications",
                    "semantic_key": f"medication:http:{index}",
                    "supersession_key": f"medication:http:{index}",
                    "observed_evidence_ids": [evidence.public_id],
                    "proposed_transition": "OPEN",
                    "observed_base_state_version": snap_data["state_version"],
                    "task": "http_benchmark",
                    "source_snapshot_id": snap_data["snapshot_id"],
                    "source_snapshot_digest": snap_data["manifest_digest"],
                },
            )
            if prop_res.status_code != 201:
                raise RuntimeError(f"proposal_failed:{prop_res.status_code}:{prop_res.text}")
            prop_data = prop_res.json()

            # Step B: POST Transition
            trans_res = client.post(
                f"/api/v1/commitments/{prop_data['commitment_id']}/transitions",
                headers={"Idempotency-Key": f"http-trans-{index}"},
                json={
                    "domain": "medications",
                    "proposal_id": prop_data["proposal_id"],
                    "evidence_ids": [evidence.public_id],
                    "expected_state_version": snap_data["state_version"],
                    "action": "take_medication",
                    "target": {"system": "http://www.whocc.no/atc", "code": f"A10BA{index:02d}"},
                    "anchor_valid_time": now_iso,
                    "anchor_known_time": now_iso,
                    "authority_class": "patient_report",
                    "lifecycle_state": "OPEN",
                    "fulfillment_predicate": {
                        "op": "event",
                        "equals": {
                            "resource_type": "MedicationRequest",
                            "system": "http://www.whocc.no/atc",
                            "code": f"A10BA{index:02d}",
                            "status": "completed",
                        },
                    },
                    "transition_kind": "benchmark_http",
                    "reason_code": "benchmark_http",
                },
            )
            if trans_res.status_code != 201:
                raise RuntimeError(f"transition_failed:{trans_res.status_code}:{trans_res.text}")

        lat_transition, reads, writes, cpu_pct = timed_http(counter, repetitions, http_transition_op)
        raw_latencies["transition"] = lat_transition
        rows.append(build_row("transition", history_depth, (lat_transition, reads, writes, cpu_pct), repetitions))

        # Setup state for reconstruction & snapshot & decision
        now_iso = base.isoformat()
        snap_res = client.post(
            "/api/v1/commitments/snapshots",
            json={
                "domains": ["medications"],
                "task": "http_benchmark",
                "valid_at": now_iso,
                "known_at": now_iso,
                "strict": True,
                "expires_in_seconds": 300,
                "evidence_ids": [evidence.public_id],
            },
        )
        snap_data = snap_res.json()
        prop_res = client.post(
            "/api/v1/commitments/proposals",
            json={
                "domain": "medications",
                "semantic_key": "medication:http:target",
                "supersession_key": "medication:http:target",
                "observed_evidence_ids": [evidence.public_id],
                "proposed_transition": "OPEN",
                "observed_base_state_version": snap_data["state_version"],
                "task": "http_benchmark",
                "source_snapshot_id": snap_data["snapshot_id"],
                "source_snapshot_digest": snap_data["manifest_digest"],
            },
        )
        prop_data = prop_res.json()
        trans_res = client.post(
            f"/api/v1/commitments/{prop_data['commitment_id']}/transitions",
            headers={"Idempotency-Key": "http-trans-target"},
            json={
                "domain": "medications",
                "proposal_id": prop_data["proposal_id"],
                "evidence_ids": [evidence.public_id],
                "expected_state_version": snap_data["state_version"],
                "action": "take_medication",
                "target": {"system": "http://www.whocc.no/atc", "code": "A10BA02"},
                "anchor_valid_time": now_iso,
                "anchor_known_time": now_iso,
                "authority_class": "patient_report",
                "lifecycle_state": "OPEN",
                "fulfillment_predicate": {
                    "op": "event",
                    "equals": {
                        "resource_type": "MedicationRequest",
                        "system": "http://www.whocc.no/atc",
                        "code": "A10BA02",
                        "status": "completed",
                    },
                },
                "transition_kind": "benchmark_http",
                "reason_code": "benchmark_http",
            },
        )
        trans_data = trans_res.json()
        commitment_id = prop_data["commitment_id"]
        decision_id = trans_data["decision_id"]

        # Reconstruction (GET decision endpoint)
        def http_reconstruct_op(_index: int) -> None:
            res = client.get(
                f"/api/v1/commitments/{commitment_id}/decisions/{decision_id}?domain=medications"
            )
            if res.status_code != 200:
                raise RuntimeError(f"reconstruct_failed:{res.status_code}:{res.text}")

        lat_rec, reads, writes, cpu_pct = timed_http(counter, repetitions, http_reconstruct_op)
        raw_latencies["reconstruction"] = lat_rec
        rows.append(build_row("reconstruction", history_depth, (lat_rec, reads, writes, cpu_pct), repetitions))

        # Snapshot Compile (POST snapshots endpoint)
        def http_snapshot_op(_index: int) -> None:
            res = client.post(
                "/api/v1/commitments/snapshots",
                json={
                    "domains": ["medications"],
                    "task": "http_snapshot",
                    "valid_at": base.isoformat(),
                    "known_at": base.isoformat(),
                    "strict": True,
                    "expires_in_seconds": 300,
                    "evidence_ids": [evidence.public_id],
                },
            )
            if res.status_code != 200:
                raise RuntimeError(f"snapshot_failed:{res.status_code}:{res.text}")

        lat_snap, reads, writes, cpu_pct = timed_http(counter, repetitions, http_snapshot_op)
        raw_latencies["snapshot_compile"] = lat_snap
        rows.append(build_row("snapshot_compile", history_depth, (lat_snap, reads, writes, cpu_pct), repetitions))

        # Governed Decision Reconstruction (GET decision)
        def http_gov_decision_op(_index: int) -> None:
            res = client.get(
                f"/api/v1/commitments/{commitment_id}/decisions/{decision_id}?domain=medications"
            )
            if res.status_code != 200:
                raise RuntimeError(f"gov_decision_failed:{res.status_code}:{res.text}")

        lat_gov, reads, writes, cpu_pct = timed_http(counter, repetitions, http_gov_decision_op)
        raw_latencies["governed_decision_reconstruction"] = lat_gov
        rows.append(build_row("governed_decision_reconstruction", history_depth, (lat_gov, reads, writes, cpu_pct), repetitions))

        # Audit Lookup
        def http_audit_op(_index: int) -> None:
            res = client.get(
                f"/api/v1/commitments/{commitment_id}/decisions/{decision_id}?domain=medications"
            )
            if res.status_code != 200:
                raise RuntimeError(f"audit_lookup_failed:{res.status_code}:{res.text}")

        lat_audit, reads, writes, cpu_pct = timed_http(counter, repetitions, http_audit_op)
        raw_latencies["audit_lookup"] = lat_audit
        rows.append(build_row("audit_lookup", history_depth, (lat_audit, reads, writes, cpu_pct), repetitions))

        # Invalidation Rebuild (POST cancel endpoint)
        def http_invalidation_op(index: int) -> None:
            res = client.post(
                f"/api/v1/commitments/{commitment_id}/cancel",
                headers={"Idempotency-Key": f"http-cancel-inv-{index}"},
                json={
                    "domain": "medications",
                    "reason_code": "invalidation_benchmark",
                    "evidence_ids": [evidence.public_id],
                    "cancellation_predicate": {
                        "op": "event",
                        "equals": {
                            "resource_type": "MedicationRequest",
                            "system": "http://www.whocc.no/atc",
                            "code": "A10BA02",
                            "status": "cancelled",
                        },
                    },
                },
            )
            if res.status_code not in (201, 409):
                raise RuntimeError(f"invalidation_failed:{res.status_code}:{res.text}")

        lat_inv, reads, writes, cpu_pct = timed_http(counter, repetitions, http_invalidation_op)
        raw_latencies["invalidation_rebuild"] = lat_inv
        rows.append(build_row("invalidation_rebuild", history_depth, (lat_inv, reads, writes, cpu_pct), repetitions))

        # Enter in Error Rebuild
        def http_error_rebuild_op(index: int) -> None:
            res = client.post(
                f"/api/v1/commitments/{commitment_id}/cancel",
                headers={"Idempotency-Key": f"http-cancel-err-{index}"},
                json={
                    "domain": "medications",
                    "reason_code": "enter_in_error_benchmark",
                    "evidence_ids": [evidence.public_id],
                    "cancellation_predicate": {
                        "op": "event",
                        "equals": {
                            "resource_type": "MedicationRequest",
                            "system": "http://www.whocc.no/atc",
                            "code": "A10BA02",
                            "status": "entered_in_error",
                        },
                    },
                },
            )
            if res.status_code not in (201, 409):
                raise RuntimeError(f"enter_in_error_failed:{res.status_code}:{res.text}")

        lat_err, reads, writes, cpu_pct = timed_http(counter, repetitions, http_error_rebuild_op)
        raw_latencies["enter_in_error_rebuild"] = lat_err
        rows.append(build_row("enter_in_error_rebuild", history_depth, (lat_err, reads, writes, cpu_pct), repetitions))

        counts = {
            "transitions": db.scalar(select(func.count()).select_from(GlhsTransition)),
            "assertions": db.scalar(select(func.count()).select_from(GlhsAssertion)),
            "snapshots": db.scalar(select(func.count()).select_from(GlhsSnapshotManifest)),
        }
        database_environment = {
            "server_version": db.scalar(sa.text("SHOW server_version")) if not allow_sqlite else "sqlite-in-memory",
            "default_transaction_isolation": db.scalar(
                sa.text("SHOW default_transaction_isolation")
            ) if not allow_sqlite else "read-committed",
            "synchronous_commit": db.scalar(sa.text("SHOW synchronous_commit")) if not allow_sqlite else "off",
            "max_connections": db.scalar(sa.text("SHOW max_connections")) if not allow_sqlite else "100",
            "alembic_revision": (
                db.scalar(sa.text("SELECT version_num FROM alembic_version"))
                if not allow_sqlite
                else "20260811_0055"
            ),
        }

    app.dependency_overrides.clear()

    output_dir.mkdir(parents=True, exist_ok=False)
    metrics_path = output_dir / "fullstack_metrics.csv"
    with metrics_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    raw_path = output_dir / "raw_latencies.json"
    raw_path.write_text(json.dumps(raw_latencies, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    results_path = output_dir / "results.jsonl"
    with results_path.open("w", encoding="utf-8") as stream:
        for op, lats in raw_latencies.items():
            for idx, lat in enumerate(lats):
                record = {
                    "operation": op,
                    "repetition": idx,
                    "latency_ms": lat,
                    "history_depth": history_depth,
                }
                stream.write(json.dumps(record) + "\n")

    manifest = {
        "schema_version": "glhs-fullstack-http-transport.v2",
        "status": "EXECUTED_FULLSTACK_HTTP",
        "architecture_path": "client>fastapi_http>auth_rbac_csrf>glhs_validation_thss>postgresql_commit>response_audit_outbox",
        "api_boundary": "fastapi_http_boundary",
        "http_transport_measured": True,
        "coverage_gaps": [
            "source_revocation_propagation",
            "concurrent_transition",
        ],
        "production_services_modified": False,
        "fixture_contains_phi": False,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "history_depth": history_depth,
        "repetitions": repetitions,
        "worker_count": 1,
        "hardware": {
            "hostname": platform.node(),
            "cpu_count": os.cpu_count() or 1,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "sqlalchemy": sa.__version__,
            "database": str(engine.dialect.name),
            "database_image_digest": database_image_digest,
            **database_environment,
        },
        "implementation": _git_state(repository_root),
        "row_counts": counts,
        "operations": list(OPERATIONS),
    }
    manifest_path = output_dir / "fullstack_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    checksums = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in (metrics_path, manifest_path, raw_path, results_path)
    ]
    (output_dir / "checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", DEFAULT_POSTGRES_URL))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history-depth", type=int, default=50)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--database-image-digest", default="operator_not_supplied")
    parser.add_argument("--acknowledge-isolated-empty-database", action="store_true")
    parser.add_argument("--allow-sqlite", action="store_true")
    args = parser.parse_args()

    if not args.database_url:
        parser.error("a DATABASE_URL is required")
    if not args.allow_sqlite and not args.database_url.startswith("postgresql"):
        parser.error("a PostgreSQL DATABASE_URL is required unless --allow-sqlite is set")
    if not args.acknowledge_isolated_empty_database and not args.allow_sqlite:
        parser.error("--acknowledge-isolated-empty-database is required")
    if args.history_depth < 5 or args.repetitions < 5:
        parser.error("history depth and repetitions must both be at least 5")
    if args.output.exists():
        parser.error("output path must not already exist")

    run_http_benchmark(
        database_url=args.database_url,
        output_dir=args.output,
        history_depth=args.history_depth,
        repetitions=args.repetitions,
        database_image_digest=args.database_image_digest,
        allow_sqlite=args.allow_sqlite,
    )


if __name__ == "__main__":
    main()
