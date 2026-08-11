"""Run a network-free synthetic GLHS/CommitLoop performance microbenchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
    reconstruct_commitments,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.gateway import EvidenceInput, current_state_version, record_evidence
from clara_api.lifemap.profile_scope import ProfileScope
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def _latency_summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "p99_ms": _percentile(values, 0.99),
        "mean_ms": sum(values) / len(values),
    }


def _scope(db: Session) -> ProfileScope:
    return ProfileScope(
        actor=db.execute(select(User)).scalar_one(),
        profile=db.execute(select(PhrProfile)).scalar_one(),
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"observations"}),
    )


def run_assurance(*, output: Path, subjects: int = 32) -> dict[str, Any]:
    if not 1 <= subjects <= 1000:
        raise ValueError("subjects_out_of_range")
    output.mkdir(parents=True, exist_ok=False)
    stage_latencies: dict[str, list[float]] = {
        "evidence_ingestion": [],
        "thss_compile": [],
        "proposal_validation": [],
        "gst_commit": [],
    }
    with tempfile.TemporaryDirectory(prefix="clara-glhs-assurance-") as temp_dir:
        database = Path(temp_dir) / "assurance.db"
        engine = create_engine(f"sqlite+pysqlite:///{database}")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            owner = User(
                email="synthetic-assurance@example.invalid",
                hashed_password="not-a-real-secret",
                role="normal",
            )
            db.add(owner)
            db.flush()
            db.add(PhrProfile(user_id=owner.id))
            db.commit()
            baseline_storage_bytes = database.stat().st_size
            scope = _scope(db)
            anchor = datetime(2026, 1, 1, tzinfo=UTC)
            loop_started = time.perf_counter()
            for index in range(subjects):
                began = time.perf_counter()
                source = HealthSourceReference(
                    profile_id=scope.profile.id,
                    source_kind="synthetic_assurance",
                    source_identity=f"assurance-source-{index}",
                    checksum=f"sha256:assurance-{index}",
                    observed_at=anchor,
                )
                db.add(source)
                db.flush()
                evidence = record_evidence(
                    db,
                    profile_id=scope.profile.id,
                    data=EvidenceInput(
                        source_reference_id=source.id,
                        evidence_kind="source_event",
                        artifact_type="fhir_resource",
                        artifact_public_id=f"Observation/assurance-{index}",
                        fingerprint=f"assurance-evidence-{index}",
                        valid_from=anchor,
                    ),
                )
                stage_latencies["evidence_ingestion"].append(
                    (time.perf_counter() - began) * 1000.0
                )

                commitment = get_or_create_commitment(
                    db,
                    scope=scope,
                    semantic_key=f"observation:assurance:{index}",
                    domain="observations",
                    supersession_key=f"observation:assurance:{index}",
                )
                began = time.perf_counter()
                snapshot = compile_commitment_thss(
                    db,
                    scope=scope,
                    task="commitment_proposal",
                    purpose="self_care",
                    valid_at=anchor,
                    known_at=datetime.now(UTC) + timedelta(seconds=1),
                    allowed_domains=frozenset({"observations"}),
                    disclosed_evidence=(evidence,),
                )
                stage_latencies["thss_compile"].append(
                    (time.perf_counter() - began) * 1000.0
                )

                began = time.perf_counter()
                proposal = propose_bound_commitment_transition(
                    db,
                    scope=scope,
                    commitment=commitment,
                    observed_evidence=(evidence,),
                    proposed_transition="OPEN",
                    origin="user",
                    observed_base_state_version=snapshot.state_version,
                    task=snapshot.task,
                    source_snapshot_id=snapshot.snapshot_id,
                    source_snapshot_digest=snapshot.manifest_digest,
                )
                stage_latencies["proposal_validation"].append(
                    (time.perf_counter() - began) * 1000.0
                )

                began = time.perf_counter()
                apply_commitment_transition(
                    db,
                    scope=scope,
                    commitment=commitment,
                    proposal=proposal,
                    evidence=(evidence,),
                    data=CommitmentVersionInput(
                        action="repeat_measurement",
                        target={
                            "system": "http://loinc.org",
                            "code": f"assurance-{index}",
                        },
                        anchor_valid_time=anchor,
                        anchor_known_time=anchor,
                        authority_class="patient_report",
                        fulfillment_predicate={
                            "op": "event",
                            "equals": {
                                "resource_type": "Observation",
                                "system": "http://loinc.org",
                                "code": f"assurance-{index}",
                                "status": "final",
                            },
                        },
                    ),
                    expected_state_version=index,
                    idempotency_key=f"assurance-transition-{index}",
                    transition_kind="commitment_opened",
                    reason_code="synthetic_assurance",
                )
                db.commit()
                stage_latencies["gst_commit"].append(
                    (time.perf_counter() - began) * 1000.0
                )
            transition_loop_elapsed = time.perf_counter() - loop_started

            began = time.perf_counter()
            final_snapshot = compile_commitment_thss(
                db,
                scope=scope,
                task="assurance_reconstruction",
                purpose="self_care",
                valid_at=anchor + timedelta(days=1),
                known_at=datetime.now(UTC) + timedelta(seconds=1),
                allowed_domains=frozenset({"observations"}),
            )
            final_compile_ms = (time.perf_counter() - began) * 1000.0
            manifest = db.execute(
                select(GlhsSnapshotManifest).where(
                    GlhsSnapshotManifest.public_id == final_snapshot.snapshot_id
                )
            ).scalar_one()
            began = time.perf_counter()
            reconstructed = reconstruct_commitments(
                db,
                profile_id=scope.profile.id,
                valid_at=anchor + timedelta(days=1),
                known_at=datetime.now(UTC) + timedelta(seconds=1),
            )
            replay_ms = (time.perf_counter() - began) * 1000.0
            db.commit()
            final_state_version = current_state_version(db, profile_id=scope.profile.id)
            context_bytes = len(_canonical_bytes(manifest.snapshot_payload_json))
            canonical_product_bytes = len(_canonical_bytes(reconstructed))
        engine.dispose()
        storage_bytes = database.stat().st_size

    incremental_storage_bytes = max(0, storage_bytes - baseline_storage_bytes)
    metrics: dict[str, Any] = {
        "schema_version": "glhs-local-assurance.v1",
        "execution_mode": "network_disabled_synthetic",
        "synthetic_software_evaluation": True,
        "subjects": subjects,
        "transitions": subjects,
        "final_state_version": final_state_version,
        "reconstructed_commitments": len(reconstructed),
        "thss_pipeline_order": [
            str(stage["name"]) for stage in final_snapshot.pipeline_trace
        ],
        "latency": {
            stage: _latency_summary(values) for stage, values in stage_latencies.items()
        },
        "final_compile_ms": final_compile_ms,
        "replay_ms": replay_ms,
        "throughput_transitions_per_second": subjects / transition_loop_elapsed,
        "storage": {
            "baseline_schema_bytes": baseline_storage_bytes,
            "sqlite_file_bytes": storage_bytes,
            "incremental_bytes": incremental_storage_bytes,
            "incremental_bytes_per_transition": incremental_storage_bytes / subjects,
        },
        "context": {
            "snapshot_payload_bytes": context_bytes,
            "canonical_product_bytes": canonical_product_bytes,
            "governance_overhead_bytes": max(
                0, context_bytes - canonical_product_bytes
            ),
            "context_to_canonical_ratio": (
                context_bytes / canonical_product_bytes
                if canonical_product_bytes
                else None
            ),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "external_calls": 0,
        "clinical_adjudication": "NOT_RUN",
    }
    metrics_path = output / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(metrics_path.read_bytes()).hexdigest()
    (output / "checksums.sha256").write_text(
        f"{digest}  metrics.json\n", encoding="utf-8"
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subjects", type=int, default=32)
    args = parser.parse_args()
    result = run_assurance(output=args.output, subjects=args.subjects)
    print(
        json.dumps(
            {
                "status": "COMPLETE",
                "external_calls": result["external_calls"],
                "subjects": result["subjects"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
