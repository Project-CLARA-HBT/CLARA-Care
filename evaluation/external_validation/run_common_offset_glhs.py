"""Run frozen eICU source-offset tasks through production GLHS primitives.

The source target is a deterministic relative-offset target, not a clinical
label.  Absolute clinical time and source knowledge time remain unavailable.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import resource
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

import sqlalchemy as sa
from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAssertion,
    GlhsEvidence,
    GlhsStateVersion,
    GlhsTransition,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    current_state_version,
    propose_assertion,
    reconstruct_state,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope
from sqlalchemy.orm import Session, sessionmaker

SCHEMA_VERSION = "clara-common-offset-glhs-run.v1"
PROTOCOL_SCHEMA_VERSION = "clara-common-offset-glhs-protocol.v1"
PROTOCOL_STATUS = "FROZEN_DEVELOPER_PREPARED_SOURCE_DERIVED"
SYSTEMS = (
    "valid_offset_resolver_strong_parity_reference",
    "input_order_baseline",
    "production_glhs_reconstruction",
)
DOMAIN_MAP = {
    "allergies_adverse_reactions": "allergies",
    "diagnoses_problems": "conditions",
    "medications": "medications",
    "observations": "observations",
}
PRODUCTION_PATH = [
    "record_evidence",
    "propose_assertion",
    "apply_transition",
    "reconstruct_state",
]
TEMPORAL_MAPPING = {
    "source_coordinate": "minutes_relative_to_icu_unit_admission",
    "encoding_epoch": "2000-01-01T00:00:00_abstract_naive_coordinate",
    "interval_rule": "event_valid_until_one_microsecond_before_next_distinct_offset",
    "absolute_clinical_time": "UNAVAILABLE_NOT_ESTIMATED",
    "source_knowledge_time": "UNAVAILABLE_NOT_ESTIMATED",
    "known_at_for_reconstruction": "post_ingest_processing_cutoff_not_source_time",
}
# These are deliberately naive abstract coordinates.  Assigning UTC here would
# falsely turn a source-relative ICU offset into an absolute clinical instant.
RELATIVE_EPOCH = datetime(2000, 1, 1, tzinfo=UTC).replace(tzinfo=None)
POST_INGEST_KNOWLEDGE_CUTOFF = datetime(9999, 1, 1, tzinfo=UTC).replace(tzinfo=None)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("common_offset_json_invalid")
    return payload


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _validate_protocol(
    protocol_path: Path,
    tasks_path: Path,
    cohort_manifest_path: Path,
    *,
    enforce_repository_freeze: bool,
) -> dict[str, Any]:
    protocol = _json(protocol_path)
    if (
        protocol.get("schema_version") != PROTOCOL_SCHEMA_VERSION
        or protocol.get("status") != PROTOCOL_STATUS
        or protocol.get("dataset_id") != "eicu_crd_demo_2_0_1"
        or protocol.get("systems") != list(SYSTEMS)
        or protocol.get("primary_invariant")
        != "production_glhs_reconstruction_exact_parity_with_unique_latest_valid_offset"
        or protocol.get("analysis_unit") != "source_subject"
        or protocol.get("failure_policy") != "missing_invalid_or_error_is_failure"
        or protocol.get("production_path") != PRODUCTION_PATH
        or protocol.get("execution_boundary") != "in_process_api_owned_service_layer_sqlite"
        or protocol.get("temporal_mapping") != TEMPORAL_MAPPING
        or protocol.get("clinical_oracle") is not False
        or protocol.get("headline_eligible") is not False
        or protocol.get("provider_calls_planned") != 0
    ):
        raise ValueError("common_offset_protocol_contract_invalid")
    stored_hash = protocol.get("protocol_payload_sha256")
    unsigned = dict(protocol)
    unsigned.pop("protocol_payload_sha256", None)
    if stored_hash != _sha_bytes(_canonical(unsigned).encode()):
        raise ValueError("common_offset_protocol_hash_mismatch")
    cohort = _json(cohort_manifest_path)
    cohort_hash = cohort.get("manifest_payload_sha256")
    cohort_unsigned = dict(cohort)
    cohort_unsigned.pop("manifest_payload_sha256", None)
    if cohort_hash != _sha_bytes(_canonical(cohort_unsigned).encode()):
        raise ValueError("common_offset_cohort_hash_mismatch")
    if (
        protocol.get("tasks_sha256") != _sha_file(tasks_path)
        or protocol.get("cohort_manifest_sha256") != _sha_file(cohort_manifest_path)
        or protocol.get("cohort_manifest_payload_sha256") != cohort_hash
        or cohort.get("tasks_sha256") != protocol.get("tasks_sha256")
        or cohort.get("task_count") != protocol.get("frozen_task_count")
        or cohort.get("event_count") != protocol.get("frozen_event_count")
        or cohort.get("represented_evaluation_subject_count")
        != protocol.get("frozen_subject_count")
    ):
        raise ValueError("common_offset_protocol_input_binding_mismatch")
    runner_path = Path(__file__).resolve()
    if protocol.get("runner_sha256") != _sha_file(runner_path):
        raise ValueError("common_offset_protocol_runner_mismatch")
    validator_path = runner_path.with_name("validate_common_offset_glhs.py")
    if protocol.get("validator_sha256") != _sha_file(validator_path):
        raise ValueError("common_offset_protocol_validator_mismatch")
    if enforce_repository_freeze:
        root = runner_path.parents[2]
        tracked = _git(root, "status", "--porcelain", "--untracked-files=no")
        if tracked:
            raise ValueError("common_offset_run_requires_clean_tracked_worktree")
        implementation = protocol.get("implementation_git_sha")
        if not isinstance(implementation, str) or len(implementation) != 40:
            raise ValueError("common_offset_protocol_implementation_invalid")
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", implementation, "HEAD"],
            cwd=root,
            check=False,
        )
        if ancestry.returncode:
            raise ValueError("common_offset_protocol_implementation_not_ancestor")
    return protocol


def _scope(db: Session, subject_token: str) -> ProfileScope:
    user = User(
        email=f"eicu-{subject_token}@example.invalid",
        hashed_password="non-login-evaluation-account",
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
        allowed_data_classes=frozenset({*DOMAIN_MAP.values(), "evidence"}),
    )


def _relative_time(offset_minutes: int) -> datetime:
    return RELATIVE_EPOCH + timedelta(minutes=offset_minutes)


def _event_windows(events: list[dict[str, Any]]) -> dict[str, tuple[datetime, datetime | None]]:
    offsets = sorted({int(event["valid_offset_minutes"]) for event in events})
    next_offset = {offset: offsets[index + 1] for index, offset in enumerate(offsets[:-1])}
    result: dict[str, tuple[datetime, datetime | None]] = {}
    for event in events:
        offset = int(event["valid_offset_minutes"])
        following = next_offset.get(offset)
        valid_to = (
            _relative_time(following) - timedelta(microseconds=1) if following is not None else None
        )
        result[str(event["event_id"])] = (_relative_time(offset), valid_to)
    return result


def _reference_selection(events: list[dict[str, Any]]) -> str | None:
    latest = max(int(event["valid_offset_minutes"]) for event in events)
    selected = [event for event in events if int(event["valid_offset_minutes"]) == latest]
    return str(selected[0]["event_id"]) if len(selected) == 1 else None


def _input_order_selection(events: list[dict[str, Any]]) -> str | None:
    if not events:
        return None
    return str(max(events, key=lambda event: int(event["source_index"]))["event_id"])


def _ingest_and_reconstruct(
    db: Session,
    scope: ProfileScope,
    task: dict[str, Any],
) -> str | None:
    events = task.get("structured_events")
    if not isinstance(events, list) or len(events) < 2:
        raise ValueError("common_offset_task_events_invalid")
    domain = str(task.get("domain", ""))
    assertion_type = DOMAIN_MAP.get(domain)
    if assertion_type is None:
        raise ValueError("common_offset_task_domain_invalid")
    task_id = str(task.get("task_id", ""))
    semantic_key = f"eicu_offset:{domain}:{task_id}"
    windows = _event_windows(events)
    for event in sorted(events, key=lambda item: int(item["source_index"])):
        event_id = str(event["event_id"])
        valid_from, valid_to = windows[event_id]
        fingerprint = f"eicu-offset:{event_id}"
        source = HealthSourceReference(
            profile_id=scope.profile.id,
            source_kind="external_structured_demo",
            source_identity=str(event["source_pointer_sha256"]),
            checksum=str(event["value_fingerprint"]),
            observed_at=None,
        )
        db.add(source)
        db.flush()
        evidence = record_evidence(
            db,
            profile_id=scope.profile.id,
            data=EvidenceInput(
                source_reference_id=source.id,
                evidence_kind="source_offset_record",
                artifact_type="eicu_demo_row_pointer",
                artifact_public_id=event_id,
                fingerprint=fingerprint,
                valid_from=valid_from,
                valid_to=valid_to,
                time_precision="unknown",
                estimated_time=False,
            ),
        )
        assertion = propose_assertion(
            db,
            profile_id=scope.profile.id,
            actor_user_id=scope.actor.id,
            data=AssertionInput(
                semantic_key=semantic_key,
                assertion_type=assertion_type,
                predicate="source_offset_state",
                value={
                    "event_id": event_id,
                    "value_fingerprint": str(event["value_fingerprint"]),
                    "source_coordinate": {
                        "anchor": "icu_unit_admission",
                        "offset_minutes": int(event["valid_offset_minutes"]),
                    },
                    "absolute_clinical_time": "UNAVAILABLE_NOT_ESTIMATED",
                    "source_knowledge_time": "UNAVAILABLE_NOT_ESTIMATED",
                },
                epistemic_state="extracted",
                valid_from=valid_from,
                valid_to=valid_to,
                time_precision="unknown",
                estimated_time=False,
                process_kind="system",
            ),
            evidence=((evidence, "supports"),),
        )
        transition = apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=current_state_version(db, profile_id=scope.profile.id),
            idempotency_key=f"eicu-offset-{event_id}",
            transition_kind="external_source_import",
            reason_code="source_offset_evaluation",
        )
        if transition.resulting_state_version <= transition.base_state_version:
            raise RuntimeError("common_offset_glhs_version_not_incremented")
    cutoff = _relative_time(max(int(event["valid_offset_minutes"]) for event in events))
    state = reconstruct_state(
        db,
        profile_id=scope.profile.id,
        valid_at=cutoff,
        known_at=POST_INGEST_KNOWLEDGE_CUTOFF,
    )
    selected = [
        row
        for row in state
        if row.get("semantic_key") == semantic_key and isinstance(row.get("value"), dict)
    ]
    if len(selected) != 1:
        return None
    return str(selected[0]["value"].get("event_id", "")) or None


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _gzip_writer(path: Path) -> tuple[BinaryIO, gzip.GzipFile]:
    raw = path.open("xb")
    compressed = gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6)
    return raw, compressed


def _checksums(directory: Path) -> None:
    paths = sorted(
        path for path in directory.iterdir() if path.is_file() and path.name != "checksums.sha256"
    )
    (directory / "checksums.sha256").write_text(
        "".join(f"{_sha_file(path)}  {path.name}\n" for path in paths), encoding="utf-8"
    )


def run(
    tasks_path: Path,
    cohort_manifest_path: Path,
    protocol_path: Path,
    output_dir: Path,
    *,
    enforce_repository_freeze: bool = True,
) -> dict[str, object]:
    protocol = _validate_protocol(
        protocol_path,
        tasks_path,
        cohort_manifest_path,
        enforce_repository_freeze=enforce_repository_freeze,
    )
    partial = output_dir.with_name(f".{output_dir.name}.partial")
    if output_dir.exists() or partial.exists():
        raise ValueError("common_offset_output_exists")
    partial.mkdir(parents=True)
    database_path = partial / "scratch.sqlite3"
    engine = sa.create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    counts: Counter[str] = Counter()
    by_subject: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    by_domain: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    scopes: dict[str, ProfileScope] = {}
    started_at = datetime.now(UTC)
    wall_started = time.perf_counter()
    usage_before = resource.getrusage(resource.RUSAGE_SELF)
    raw_stream, output_stream = _gzip_writer(partial / "system_outputs.jsonl.gz")
    try:
        with raw_stream, output_stream, factory() as db, tasks_path.open(encoding="utf-8") as tasks:
            for line_number, line in enumerate(tasks, start=1):
                task = json.loads(line)
                if not isinstance(task, dict):
                    raise TypeError(f"common_offset_task_invalid:{line_number}")
                subject = str(task.get("subject_token", ""))
                domain = str(task.get("domain", ""))
                target = str(task.get("source_target_event_id", ""))
                events = task.get("structured_events")
                if not subject or not target or not isinstance(events, list):
                    raise ValueError(f"common_offset_task_contract_invalid:{line_number}")
                scope = scopes.get(subject)
                if scope is None:
                    scope = _scope(db, subject)
                    scopes[subject] = scope
                selections: dict[str, str | None] = {
                    SYSTEMS[0]: _reference_selection(events),
                    SYSTEMS[1]: _input_order_selection(events),
                }
                error_code = ""
                try:
                    with db.begin_nested():
                        selections[SYSTEMS[2]] = _ingest_and_reconstruct(db, scope, task)
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                    RuntimeError,
                    sa.exc.SQLAlchemyError,
                ) as exc:
                    selections[SYSTEMS[2]] = None
                    error_code = str(exc) or type(exc).__name__
                    counts[f"error:{error_code}"] += 1
                row_systems: dict[str, object] = {}
                for system in SYSTEMS:
                    selected = selections.get(system)
                    correct = selected == target and selected is not None
                    by_subject[(subject, system)][1] += 1
                    by_subject[(subject, system)][0] += int(correct)
                    by_domain[(domain, system)][1] += 1
                    by_domain[(domain, system)][0] += int(correct)
                    counts[f"correct:{system}"] += int(correct)
                    counts[f"missing:{system}"] += int(selected is None)
                    row_systems[system] = {
                        "selected_event_id": selected,
                        "correct": correct,
                        "status": "PASS" if correct else "FAIL",
                    }
                output_stream.write(
                    (
                        _canonical(
                            {
                                "task_id": task["task_id"],
                                "subject_token": subject,
                                "domain": domain,
                                "source_target_event_id": target,
                                "systems": row_systems,
                                "error_code": error_code,
                            }
                        )
                        + "\n"
                    ).encode()
                )
                counts["tasks"] += 1
                counts["events"] += len(events)
                db.commit()
        database_bytes = database_path.stat().st_size
        with factory() as db:
            row_counts = {
                "evidence": int(
                    db.scalar(sa.select(sa.func.count()).select_from(GlhsEvidence)) or 0
                ),
                "assertions": int(
                    db.scalar(sa.select(sa.func.count()).select_from(GlhsAssertion)) or 0
                ),
                "transitions": int(
                    db.scalar(sa.select(sa.func.count()).select_from(GlhsTransition)) or 0
                ),
                "state_versions": int(
                    db.scalar(sa.select(sa.func.count()).select_from(GlhsStateVersion)) or 0
                ),
            }
    except Exception:
        engine.dispose()
        shutil.rmtree(partial, ignore_errors=True)
        raise
    engine.dispose()
    database_path.unlink()
    wall_seconds = time.perf_counter() - wall_started
    usage_after = resource.getrusage(resource.RUSAGE_SELF)
    subject_rows = [
        {
            "subject_token": subject,
            "system": system,
            "correct": values[0],
            "total": values[1],
            "rate": values[0] / values[1],
        }
        for (subject, system), values in sorted(by_subject.items())
    ]
    domain_rows = [
        {
            "domain": domain,
            "system": system,
            "correct": values[0],
            "total": values[1],
            "rate": values[0] / values[1],
        }
        for (domain, system), values in sorted(by_domain.items())
    ]
    _write_csv(
        partial / "subject_results.csv",
        ["subject_token", "system", "correct", "total", "rate"],
        subject_rows,
    )
    _write_csv(
        partial / "domain_results.csv",
        ["domain", "system", "correct", "total", "rate"],
        domain_rows,
    )
    primary_correct = counts[f"correct:{SYSTEMS[2]}"]
    primary_pass = (
        counts["tasks"] > 0
        and primary_correct == counts["tasks"]
        and counts[f"missing:{SYSTEMS[2]}"] == 0
        and not any(key.startswith("error:") for key in counts)
    )
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if primary_pass else "FAIL",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "dataset_id": protocol["dataset_id"],
        "protocol_payload_sha256": protocol["protocol_payload_sha256"],
        "protocol_file_sha256": _sha_file(protocol_path),
        "cohort_manifest_sha256": _sha_file(cohort_manifest_path),
        "tasks_sha256": _sha_file(tasks_path),
        "systems": list(SYSTEMS),
        "primary_invariant": protocol["primary_invariant"],
        "primary_result": {
            "correct": primary_correct,
            "total": counts["tasks"],
            "missing": counts[f"missing:{SYSTEMS[2]}"],
            "pass": primary_pass,
        },
        "system_results": {
            system: {
                "correct": counts[f"correct:{system}"],
                "total": counts["tasks"],
                "missing": counts[f"missing:{system}"],
            }
            for system in SYSTEMS
        },
        "subject_count": len(scopes),
        "task_count": counts["tasks"],
        "event_count": counts["events"],
        "error_taxonomy": {
            key.removeprefix("error:"): value
            for key, value in sorted(counts.items())
            if key.startswith("error:")
        },
        "production_path": PRODUCTION_PATH,
        "execution_boundary": "in_process_api_owned_service_layer_sqlite",
        "postgresql_or_http_measured": False,
        "relative_time_encoding": TEMPORAL_MAPPING,
        "row_counts": row_counts,
        "operational": {
            "wall_clock_seconds": wall_seconds,
            "tasks_per_second": counts["tasks"] / wall_seconds,
            "events_per_second": counts["events"] / wall_seconds,
            "process_user_seconds": usage_after.ru_utime - usage_before.ru_utime,
            "process_system_seconds": usage_after.ru_stime - usage_before.ru_stime,
            "peak_rss_kib": usage_after.ru_maxrss,
            "scratch_database_bytes_before_removal": database_bytes,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "sqlalchemy": sa.__version__,
            "cpu_count": os.cpu_count(),
        },
        "clinical_oracle": False,
        "headline_eligible": False,
        "provider_calls": 0,
        "claim_limit": "source_offset_state_reconstruction_mechanics_not_clinical_correctness",
    }
    manifest["manifest_payload_sha256"] = _sha_bytes(_canonical(manifest).encode())
    (partial / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (partial / "report.md").write_text(
        "# eICU Demo source-offset GLHS execution\n\n"
        "This is source-derived structural evidence, not clinical validation.\n\n"
        f"- Primary GLHS parity: {primary_correct}/{counts['tasks']}\n"
        f"- Subjects: {len(scopes)}\n"
        f"- Tasks/events: {counts['tasks']}/{counts['events']}\n"
        "- Absolute clinical time and source knowledge time: unavailable, not estimated.\n"
        "- Execution boundary: in-process API-owned service layer on SQLite; no HTTP or "
        "PostgreSQL claim.\n",
        encoding="utf-8",
    )
    _checksums(partial)
    partial.replace(output_dir)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.tasks, args.cohort_manifest, args.protocol, args.output)
    except (OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
