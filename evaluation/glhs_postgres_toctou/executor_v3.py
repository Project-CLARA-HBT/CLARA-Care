"""Repeat/jitter runner for the GLHS-CONCURRENCY-REPETITION-V1 study.

Builds on ``executor_v2`` (no new framework): the frozen v2/v2.1 schedule
drivers are reused verbatim. For each logical schedule the runner executes
``repeat_manifest.repetitions_per_logical_schedule`` (50) timing repetitions
under deterministic pre-barrier jitter, records per-repetition concurrency
metadata, resolves durable commit timestamps where the isolated research
PostgreSQL permits, and aggregates at logical-schedule level.

Scientific invariants (see ``repeat_manifest`` and master spec rules 7, 3.4,
3.5, GLHS-C04):

- Repetitions are robustness executions, NOT new scientific N: N stays at the
  frozen 12 logical schedules.
- A schedule is robust only if ALL 50 repetitions satisfy the invariant;
  mixed classifications are reported, never majority-voted into safety.
- Deadlock / serialization failure / lock timeout are operational outcomes and
  are never safety successes.
- Commit order is never inferred from txid numeric order; without durable
  commit timestamps the ordering confidence is recorded INDETERMINATE.

Fail-closed gates (mirroring ``executor_v2``): refuses to run without the
isolated-research attestation and an operator-owned ``postgresql://`` URL that
is not a shared/default database, and refuses any non-frozen protocol or
repeat manifest. Results are never fabricated: when PostgreSQL is unreachable
the caller must freeze the runner and record the pending state instead of
emitting fake repeat data.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from evaluation.glhs_postgres_toctou.commit_order import (
    CommitTimestampProbe,
    probe_commit_timestamp_availability,
)
from evaluation.glhs_postgres_toctou.executor_v2 import (
    _DRIVERS,
    _V21_DRIVERS,
    DEFAULT_PROTOCOL_PATH,
    _random_schema_name,
    _real_env,
    _require_final_isolated_postgres,
    _source_revision,
    load_protocol,
    validate_protocol,
)
from evaluation.glhs_postgres_toctou.jitter import (
    JitteredBarrier,
    interleaving_mode_for_repetition,
)
from evaluation.glhs_postgres_toctou.observer_v2 import RawScheduleOutcome
from evaluation.glhs_postgres_toctou.repeat_manifest import (
    DB_ISOLATION_LEVEL,
    FREEZE_ID,
    FROZEN_V2_SCHEDULE_IDS,
    ORDERING_CONFIDENCE_INDETERMINATE,
    REPETITIONS_PER_LOGICAL_SCHEDULE,
    SCIENTIFIC_N,
    validate_repeat_manifest,
)

DEFAULT_MANIFEST_PATH = Path("research/glhs_journal/concurrency_repetition_v1/repeat_manifest.json")
DEFAULT_OUTPUT_DIR = Path("research/glhs_journal/concurrency_repetition_v1")


@dataclass
class BarrierLog:
    """Collects every barrier created during one repetition."""

    barriers: list[JitteredBarrier] = field(default_factory=list)


def build_repeat_env(
    base_env: object,
    *,
    seed: int,
    jitter_range_ns: int,
    barrier_log: BarrierLog,
    commit_probe: CommitTimestampProbe | None = None,
    interleaving_mode: str = "randomized",
) -> object:
    """Return an ``ExecutorEnv`` with the frozen jittered barrier injected.

    Only the barrier factory is replaced and, when a ``commit_probe`` is
    supplied, each created session's ``commit()`` is wrapped to capture the
    committing transaction's xid immediately before the commit. Sessions,
    gateway, locks, writers and postgres metadata all delegate to the base
    (real or fake) environment.
    """
    from evaluation.glhs_postgres_toctou.executor_v2 import ExecutorEnv

    base: ExecutorEnv = base_env  # type: ignore[assignment]

    def barrier_factory(parties: int) -> JitteredBarrier:
        inner = base.barrier_factory(parties)
        jittered = JitteredBarrier(
            inner,
            seed=seed,
            range_ns=jitter_range_ns,
            parties=parties,
            mode=interleaving_mode,
            timeout_s=30.0,
        )
        barrier_log.barriers.append(jittered)
        return jittered

    def session_factory() -> object:
        session = base.session_factory()
        if commit_probe is not None:
            original_commit = session.commit

            def capture_and_commit() -> None:
                commit_probe.capture_xid_before_commit(session, party=None)
                original_commit()

            session.commit = capture_and_commit  # type: ignore[method-assign]
        return session

    return ExecutorEnv(
        session_factory=session_factory,
        adapter_factory=base.adapter_factory,
        gateway=base.gateway,
        barrier_factory=barrier_factory,
        lock_factory=base.lock_factory,
        consent_record_factory=base.consent_record_factory,
        epoch_factory=base.epoch_factory,
        postgres_metadata=base.postgres_metadata,
    )


def _commit_events(raw: RawScheduleOutcome) -> list[dict[str, object]]:
    if raw.trace is None:
        return []
    events = []
    for event in raw.trace.events:
        if event.event == "commit":
            events.append(
                {
                    "monotonic_ns": event.monotonic_ns,
                    "backend_pid": event.backend_pid,
                    "txid": event.txid,
                }
            )
    return events


def _barrier_timestamps(barrier_log: BarrierLog) -> list[dict[str, object]]:
    timestamps: list[dict[str, object]] = []
    for barrier in barrier_log.barriers:
        for record in barrier.phase_records:
            timestamps.append(
                {
                    "phase": record.name,
                    "release_ns": record.release_ns,
                    "parties": record.parties,
                }
            )
        timestamps.extend(dict(record) for record in barrier.jitter_records)
    return timestamps


def build_repeat_record(
    *,
    schedule_id: str,
    repeat_id: int,
    seed: int,
    interleaving_mode: str,
    observation: Mapping[str, object],
    audit: Mapping[str, object],
    raw: RawScheduleOutcome,
    barrier_log: BarrierLog,
    resolved_commit: Mapping[str, object],
    ordering_confidence: str,
    ordering_reason: str,
    commit_timestamp_availability: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build one frozen per-repetition record (pure; no DB access)."""
    trace = raw.trace.to_dict() if raw.trace is not None else {"events": [], "lock_waits": []}
    outcome = observation["outcome"]
    rejection = observation.get("rejection_auditability")
    committed = observation.get("committed_reconstructability")
    txid_after_commit: list[object] = [
        {"party": party, "txid": item["txid"]} for party, item in resolved_commit.items()
    ]
    backend_pids: list[object] = [
        {"party": "trace", "backend_pid": event.get("backend_pid")}
        for event in trace["events"]
        if event.get("backend_pid") is not None
    ] or [{"party": party, "backend_pid": None} for party in resolved_commit]
    return {
        "schedule_id": schedule_id,
        "repeat_id": repeat_id,
        "seed": seed,
        "interleaving_mode": interleaving_mode,
        "txid_after_commit": txid_after_commit,
        "backend_pid": backend_pids,
        "barrier_timestamps": _barrier_timestamps(barrier_log),
        "lock_waits": list(trace["lock_waits"]),
        "writer_commit_metadata": _commit_events(raw),
        "proposal_commit_metadata": _commit_events(raw),
        "transaction_trace": trace,
        "commit_timestamp_availability": (
            dict(commit_timestamp_availability)
            if commit_timestamp_availability is not None
            else {"available": False, "track_commit_timestamp": "not_probed"}
        ),
        "audit": {
            "expected_classification": audit.get("expected_classification"),
            "observed_classification": audit.get("observed_classification"),
            "matches": bool(audit.get("matches")),
        },
        "outcome": {
            "commit_outcome": outcome.get("commit_outcome"),
            "classification": outcome.get("classification"),
            "forbidden_commit_observed": outcome.get("forbidden_commit_observed"),
            "operational_outcome": bool(outcome.get("operational_outcome")),
            "safety_success": bool(outcome.get("safety_success")),
        },
        "reconstruction": {
            "rejection_auditability": dict(rejection) if rejection is not None else None,
            "committed_reconstructability": (dict(committed) if committed is not None else None),
        },
        "ordering_confidence": ordering_confidence,
        "ordering_reason": ordering_reason,
        "resolved_commit_timestamps": {party: item for party, item in resolved_commit.items()},
        "latency_ms": round(float(observation.get("latency_ms", 0.0)), 3),
    }


def repetition_satisfies_invariant(record: Mapping[str, object]) -> bool:
    """A repetition satisfies the invariant iff it is not operational, not a
    forbidden commit, and its classification matches the frozen expectation.

    INDETERMINATE ordering confidence is never a safety success, but it does
    not by itself fail an *expected* indeterminate schedule; the schedule-level
    rule (all 50 must satisfy) still applies on top of the reported confidence.
    """
    outcome = record["outcome"]
    if bool(outcome.get("operational_outcome")):
        return False
    if outcome.get("forbidden_commit_observed") is True:
        return False
    if outcome.get("safety_success") is False:
        return False
    return bool(record["audit"]["matches"])


def aggregate_schedule(
    records: Sequence[Mapping[str, object]],
    schedule: Mapping[str, object],
) -> dict[str, object]:
    """Aggregate per-logical-schedule robustness (pure, fail-closed).

    A schedule is robust only when ALL repetitions satisfy the invariant.
    Mixed classifications are reported with their full distributions and never
    majority-voted into safety. Operational outcomes are counted separately and
    never treated as safety successes.
    """
    total = len(records)
    satisfying = [record for record in records if repetition_satisfies_invariant(record)]
    operational = [record for record in records if record["outcome"]["operational_outcome"]]
    indeterminate = [
        record
        for record in records
        if record["ordering_confidence"] == ORDERING_CONFIDENCE_INDETERMINATE
    ]
    classifications = Counter(str(record["outcome"]["classification"]) for record in records)
    confidence = Counter(str(record["ordering_confidence"]) for record in records)
    robust = total == REPETITIONS_PER_LOGICAL_SCHEDULE and len(satisfying) == total
    return {
        "schedule_id": str(schedule["id"]),
        "expected_classification": schedule.get("expected_classification"),
        "repetitions_total": total,
        "repetitions_satisfying_invariant": len(satisfying),
        "robust": robust,
        "mixed": (not robust) and 0 < len(satisfying) < total,
        "operational_count": len(operational),
        "indeterminate_ordering_count": len(indeterminate),
        "classification_distribution": dict(sorted(classifications.items())),
        "ordering_confidence_distribution": dict(sorted(confidence.items())),
        "operational_outcomes": [
            str(record["outcome"]["commit_outcome"]) for record in operational
        ],
        "indeterminate_repeat_ids": [int(record["repeat_id"]) for record in indeterminate],
    }


def run_repeat_study(
    env: object,
    protocol: Mapping[str, object],
    manifest: Mapping[str, object],
    *,
    commit_resolver: Callable[[CommitTimestampProbe], Mapping[str, object]] | None = None,
    out_dir: Path = DEFAULT_OUTPUT_DIR,
    source_revision: str = "unknown",
    run_freeze_id: str = FREEZE_ID,
    require_frozen_schedule_set: bool = True,
    commit_timestamp_availability: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Run the full repetition study over the frozen protocol schedules.

    ``env`` is the base (real or fake) ``ExecutorEnv``. ``commit_resolver``
    resolves durable commit timestamps for a probe's captured xids (real
    execution supplies a resolver against the isolated engine; tests inject a
    fake). Every repetition goes through the real v2/v2.1 driver and observer,
    so no result is ever fabricated.
    """
    from evaluation.glhs_postgres_toctou.executor_v2 import (
        _run_one_schedule,
    )

    validate_repeat_manifest(manifest)
    validate_protocol(protocol)
    schedules = protocol["schedules"]
    if not isinstance(schedules, list):
        raise TypeError("v2_protocol_schedules_missing")
    if require_frozen_schedule_set:
        schedule_ids = tuple(str(schedule.get("id")) for schedule in schedules)
        if len(schedule_ids) != SCIENTIFIC_N or set(schedule_ids) != set(FROZEN_V2_SCHEDULE_IDS):
            raise ValueError("repeat_protocol_requires_frozen_12_schedule_set")
    schema_version = str(protocol.get("schema_version", ""))
    drivers = dict(_DRIVERS)
    if schema_version == "glhs-postgres-governance-toctou-final-v2.1":
        drivers.update(_V21_DRIVERS)

    jitter_range_ns = int(manifest["jitter"]["range_ns"])
    seeds = [int(seed) for seed in manifest["jitter"]["seeds"]]
    resolved_default: Callable[[CommitTimestampProbe], Mapping[str, object]] = (
        commit_resolver
        if commit_resolver is not None
        else lambda probe: {
            party: {
                "txid": xid,
                "commit_timestamp": None,
                "durable_available": False,
            }
            for party, xid in probe.captured.items()
        }
    )

    all_records: list[dict[str, object]] = []
    schedule_summaries: list[dict[str, object]] = []
    for schedule in schedules:
        schedule_id = str(schedule["id"])
        driver = drivers.get(schedule_id)
        if driver is None:
            raise ValueError(f"v2_unknown_schedule:{schedule_id}")
        records: list[dict[str, object]] = []
        for repeat_id, seed in enumerate(seeds):
            probe = CommitTimestampProbe(availability=commit_timestamp_availability)
            barrier_log = BarrierLog()
            interleaving_mode = interleaving_mode_for_repetition(
                seed, manifest["interleaving_modes"]
            )
            repeat_env = build_repeat_env(
                env,
                seed=seed,
                jitter_range_ns=jitter_range_ns,
                barrier_log=barrier_log,
                commit_probe=probe,
                interleaving_mode=interleaving_mode,
            )
            observation, audit, raw = _run_one_schedule(repeat_env, schedule, drivers=drivers)
            resolved_all = resolved_default(probe)
            trace_txids = (
                {
                    int(event.txid)
                    for event in raw.trace.events
                    if event.event == "commit" and event.txid is not None
                }
                if raw.trace is not None
                else set()
            )
            resolved = (
                {
                    party: item
                    for party, item in resolved_all.items()
                    if int(item.get("txid", -1)) in trace_txids
                }
                if trace_txids
                else dict(resolved_all)
            )
            confidence, reason = probe.classify(resolved)
            records.append(
                build_repeat_record(
                    schedule_id=schedule_id,
                    repeat_id=repeat_id,
                    seed=seed,
                    interleaving_mode=interleaving_mode,
                    observation=observation,
                    audit=audit,
                    raw=raw,
                    barrier_log=barrier_log,
                    resolved_commit=resolved,
                    ordering_confidence=confidence,
                    ordering_reason=reason,
                    commit_timestamp_availability=probe.availability,
                )
            )
        all_records.extend(records)
        schedule_summaries.append(aggregate_schedule(records, schedule))

    robust = [summary["schedule_id"] for summary in schedule_summaries if summary["robust"]]
    mixed = [summary["schedule_id"] for summary in schedule_summaries if summary["mixed"]]
    analysis: dict[str, object] = {
        "freeze_id": run_freeze_id,
        "schema_version": "glhs-concurrency-repetition-analysis-v1",
        "status": "EXECUTED",
        "backend": "isolated_postgresql_random_schema",
        "source_revision": source_revision,
        "executed_at": datetime.now(UTC).isoformat(),
        "scientific_n": int(manifest["scientific_n"]),
        "repetitions_per_logical_schedule": int(manifest["repetitions_per_logical_schedule"]),
        "repetition_role": str(manifest["repetition_role"]),
        "total_repetitions_executed": len(all_records),
        "logical_schedule_count": len(schedules),
        "robust_schedule_ids": sorted(robust),
        "mixed_schedule_ids": sorted(mixed),
        "schedule_summaries": schedule_summaries,
        "aggregation_rule": str(manifest["aggregation_rule"]),
        "no_majority_voting_into_safety": bool(manifest["no_majority_voting_into_safety"]),
        "no_txid_numeric_order_inference": bool(manifest["no_txid_numeric_order_inference"]),
        "commit_timestamp_availability": dict(
            commit_timestamp_availability
            or {"available": False, "track_commit_timestamp": "not_probed"}
        ),
        "note": (
            "Robust requires ALL 50 repetitions to satisfy the invariant; mixed "
            "classifications are reported, never majority-voted into safety. "
            "Operational outcomes are never safety successes. N stays at the "
            "frozen logical schedule count (repetitions are robustness, not N)."
        ),
    }

    raw_lines = [json.dumps(record, sort_keys=True) + "\n" for record in all_records]
    raw_path = out_dir / "repeat_raw.jsonl"
    analysis_path = out_dir / "analysis.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("".join(raw_lines), encoding="utf-8")
    analysis_path.write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return analysis


def execute_repeat_study(
    protocol_path: Path = DEFAULT_PROTOCOL_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    database_url: str | None = None,
    out_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, object]:
    """Execute the repetition study against the isolated research PostgreSQL.

    Fail-closed: requires the isolation attestation and an operator-owned,
    non-default PostgreSQL URL; refuses draft/frozen violations. Probes
    ``track_commit_timestamp`` and records INDETERMINATE ordering honestly when
    durable commit timestamps are unavailable.
    """
    protocol = load_protocol(protocol_path)
    validate_protocol(protocol)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_repeat_manifest(manifest)
    url = _require_final_isolated_postgres(database_url)

    schema = _random_schema_name()
    admin = create_engine(url, pool_pre_ping=True)
    engine: Engine | None = None
    schema_created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True
        engine = create_engine(
            url,
            pool_pre_ping=True,
            isolation_level=DB_ISOLATION_LEVEL.upper(),
            connect_args={
                "options": (
                    f"-csearch_path={schema} "
                    f"-clock_timeout={int(manifest['db']['lock_timeout_ms'])}ms "
                    f"-cstatement_timeout={int(manifest['db']['statement_timeout_ms'])}ms"
                )
            },
        )
        from clara_api.db.base import Base

        Base.metadata.create_all(engine)

        probe = CommitTimestampProbe()
        with engine.connect() as connection:
            probe.record_availability(probe_commit_timestamp_availability(connection))

        def resolver(capturing_probe: CommitTimestampProbe) -> Mapping[str, object]:
            with engine.connect() as connection:
                return capturing_probe.resolve_commit_timestamps(connection)

        env = _real_env(engine)
        return run_repeat_study(
            env,
            protocol,
            manifest,
            commit_resolver=resolver,
            out_dir=out_dir,
            source_revision=_source_revision(),
            commit_timestamp_availability=probe.availability,
        )
    finally:
        if engine is not None:
            engine.dispose()
        if schema_created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--database-url")
    args = parser.parse_args()
    try:
        result = execute_repeat_study(
            args.protocol,
            args.manifest,
            database_url=args.database_url,
            out_dir=args.output_dir,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, TypeError, ValueError, SQLAlchemyError) as exc:
        print(json.dumps({"status": "REFUSED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
