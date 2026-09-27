"""Execution runner for the E01 2^3 factorial component-wise exact-binding ablation.

Executes the frozen schedule corpus (352 schedules x 8 arms = 2,816 executions)
through the isolated evaluation adapter and records every execution in an
append-only, tamper-evident hash-chained stream (runs.jsonl).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import GlhsSnapshotManifest, PhrProfile, User, UserConsent
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    DIGEST_ALGORITHM,
    fast_canonical_digest,
)
from clara_api.glhs.domain import GlhsInvariantError
from evaluation.glhs_binding_component_ablation.adapter import validate_proposal_context
from evaluation.glhs_binding_component_ablation.binding_mask import ALL_ARMS, get_binding_mask
from evaluation.glhs_binding_component_ablation.build_schedules import TOTAL_SCHEDULES
from evaluation.glhs_binding_component_ablation.observer import ExecutionRecord, Observer
from evaluation.glhs_binding_component_ablation.validate import (
    validate_protocol,
    validate_schedules,
)

SCHEMA_VERSION = "glhs-binding-component-ablation-runner.v1"


def _git_sha() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return res.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _create_scope(profile_id: int = 1, user_id: int = 7, purpose: str = "self_care") -> Any:
    return type(
        "Scope",
        (),
        {
            "profile": type("Profile", (), {"public_id": f"p{profile_id}", "id": profile_id, "user_id": user_id})(),
            "purpose": purpose,
        },
    )()


def _create_proposal(
    *,
    schedule: dict[str, Any],
    profile_id: int = 1,
    user_id: int = 7,
    canonical_digest: str,
) -> Any:
    ctx = schedule["context"]
    snap_fields = schedule["snapshot_fields"]
    fam = schedule["family_name"]

    source_id = snap_fields["source_snapshot_id"]
    if fam == "DIGEST-MUT":
        source_digest = "DIGEST-SHA256-MUTATED-CORRUPT"
    else:
        source_digest = canonical_digest

    purpose = "unauthorized_research" if fam == "COORD-SUB" else ctx["purpose"]
    task = "unauthorized_task" if fam == "COORD-SUB" else ctx["task"]
    actor_role = "unauthorized_role" if fam == "COORD-SUB" else ctx["actor_role"]

    return type(
        "Proposal",
        (),
        {
            "target_profile_public_id": f"p{profile_id}",
            "purpose": purpose,
            "actor_user_id": user_id,
            "actor_role": actor_role,
            "task": task,
            "policy_version": "commitloop.v1",
            "consent_version": "medical_disclaimer:v1",
            "base_state_version": 1,
            "context_binding_mode": "snapshot_bound",
            "source_snapshot_id": source_id,
            "source_snapshot_digest": source_digest,
        },
    )()


def run_experiment(
    *,
    protocol_path: Path,
    schedules_path: Path,
    output_dir: Path,
    run_id: str,
    backend: str = "isolated_sqlite",
    database_url: str | None = None,
) -> dict[str, Any]:
    """Execute all 352 schedules x 8 arms and write raw/runs.jsonl."""
    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8"))
    validate_protocol(protocol_data)

    schedules_data = json.loads(schedules_path.read_text(encoding="utf-8"))
    validate_schedules(schedules_data)
    schedules = schedules_data["schedules"]

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    runs_file = raw_dir / "runs.jsonl"
    if runs_file.exists():
        runs_file.unlink()

    observer = Observer(runs_file)

    # Initialize isolated database
    temp_db_path = output_dir / "run_temp.db"
    if temp_db_path.exists():
        temp_db_path.unlink()
    db_url = database_url or f"sqlite:///{temp_db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    session = Session(engine)
    user = User(id=7, email="patient@clara.local", hashed_password="hash", role="patient")
    profile = PhrProfile(id=1, user_id=7, public_id="p1")
    consent = UserConsent(
        id=1,
        user_id=7,
        consent_type="medical_disclaimer",
        consent_version="medical_disclaimer:v1",
        accepted_at=datetime.now(UTC),
    )
    session.add_all([user, profile, consent])
    session.commit()

    sequence = 0
    executed_count = 0

    for sched in schedules:
        fam = sched["family_name"]
        ctx = sched["context"]
        snap_fields = sched["snapshot_fields"]
        ev_set = sched["evidence_set"]
        is_clean = fam == "CLEAN"

        scope = _create_scope(profile_id=1, user_id=7, purpose=ctx["purpose"])

        payload = {"domain": ctx["domain"], "action": ctx["action"]}
        calc_digest = fast_canonical_digest(payload)

        # Build primary (current) snapshot
        current_snap_id = "SNAP-ORIG-001" if fam in ("ID-SUB", "CROSS-SNAPSHOT-SAME-VERSION", "LINEAGE-ROOT-SUB") else snap_fields["source_snapshot_id"]
        exp_seconds = snap_fields.get("expires_in_seconds", 3600)
        expires_at = (
            datetime.now(UTC) - timedelta(hours=2)
            if fam == "EXPIRY-CONTROL"
            else datetime.now(UTC) + timedelta(seconds=exp_seconds)
        )

        # Clear existing manifests in database and session
        session.execute(text("DELETE FROM glhs_snapshot_manifests"))
        session.commit()
        session.expunge_all()

        # If ID substituted, add the referenced foreign/alternate snapshot to DB first (lower ID)
        if fam in ("ID-SUB", "CROSS-SNAPSHOT-SAME-VERSION", "LINEAGE-ROOT-SUB"):
            foreign_snap = GlhsSnapshotManifest(
                public_id=snap_fields["source_snapshot_id"],
                profile_id=1,
                state_version=1,
                policy_version="commitloop.v1",
                consent_version="medical_disclaimer:v1",
                purpose=ctx["purpose"],
                task=ctx["task"],
                actor_user_id=7,
                actor_role=ctx["actor_role"],
                data_classes_json=[ctx["domain"]],
                assertion_ids_json=[],
                conflict_ids_json=[],
                snapshot_payload_json=payload,
                snapshot_digest=calc_digest,
                manifest_digest=calc_digest,
                canonicalization_profile=CANONICALIZATION_PROFILE,
                digest_algorithm=DIGEST_ALGORITHM,
                provenance_ids_json=ev_set["disclosed_provenance_ids"],
                expires_at=expires_at,
            )
            session.add(foreign_snap)
            session.commit()

        # Primary current snapshot (latest state snapshot -> higher ID)
        current_snap = GlhsSnapshotManifest(
            public_id=current_snap_id,
            profile_id=1,
            state_version=1,
            policy_version="commitloop.v1",
            consent_version="medical_disclaimer:v1",
            purpose=ctx["purpose"],
            task=ctx["task"],
            actor_user_id=7,
            actor_role=ctx["actor_role"],
            data_classes_json=[ctx["domain"]],
            assertion_ids_json=[],
            conflict_ids_json=[],
            snapshot_payload_json=payload,
            snapshot_digest=calc_digest,
            manifest_digest=calc_digest,
            canonicalization_profile=CANONICALIZATION_PROFILE,
            digest_algorithm=DIGEST_ALGORITHM,
            provenance_ids_json=ev_set["disclosed_provenance_ids"],
            expires_at=expires_at,
        )
        session.add(current_snap)
        session.commit()

        proposal = _create_proposal(
            schedule=sched,
            profile_id=1,
            user_id=7,
            canonical_digest=calc_digest,
        )

        observed_ev_ids = ev_set["observed_evidence_ids"]

        for arm in ALL_ARMS:
            sequence += 1
            executed_count += 1
            admitted = False
            rejection_code = None

            try:
                validate_proposal_context(
                    session,
                    arm=arm,
                    scope=scope,
                    proposal=proposal,
                    evidence_ids=observed_ev_ids,
                    current_version=1,
                    consent_version="medical_disclaimer:v1",
                )
                admitted = True
            except GlhsInvariantError as exc:
                admitted = False
                rejection_code = str(exc)
            except Exception as exc:
                admitted = False
                rejection_code = f"unexpected_error:{exc}"

            mask = get_binding_mask(arm)
            record = ExecutionRecord(
                run_id=run_id,
                schedule_id=sched["schedule_id"],
                arm=arm,
                sequence=sequence,
                admitted=admitted,
                rejection_reason_code=rejection_code,
                snapshot_coordinates={
                    "source_snapshot_id": proposal.source_snapshot_id,
                    "source_snapshot_digest": proposal.source_snapshot_digest,
                    "evidence_ids": list(observed_ev_ids),
                },
                governance_coordinates={
                    "profile_id": 1,
                    "base_state_version": 1,
                    "policy_version": proposal.policy_version,
                    "consent_version": proposal.consent_version,
                    "purpose": proposal.purpose,
                    "task": proposal.task,
                    "actor_role": proposal.actor_role,
                },
                binding_check_applied=any(mask.as_tuple()),
                expected_admissibility=sched["expected_admissibility"],
            )
            observer.append(record)

    session.close()
    if db_url.startswith("sqlite:///") and (output_dir / "run_temp.db").exists():
        (output_dir / "run_temp.db").unlink(missing_ok=True)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "freeze_id": protocol_data["freeze_id"],
        "git_sha": _git_sha(),
        "backend": backend,
        "executed_executions": executed_count,
        "expected_executions": TOTAL_SCHEDULES * len(ALL_ARMS),
        "total_schedules": TOTAL_SCHEDULES,
        "raw_stream_path": str(runs_file.relative_to(output_dir)),
        "completed_at_utc": datetime.now(UTC).isoformat(),
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("protocols/E01_binding_components/protocol.json"),
    )
    parser.add_argument(
        "--schedules",
        type=Path,
        default=Path("protocols/E01_binding_components/schedules.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E01_binding_components"),
    )
    parser.add_argument("--run-id", default="GLHS-Q2-R2-20260928-R01")
    parser.add_argument("--backend", default="isolated_sqlite")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    manifest = run_experiment(
        protocol_path=args.protocol,
        schedules_path=args.schedules,
        output_dir=args.output_dir,
        run_id=args.run_id,
        backend=args.backend,
        database_url=args.database_url,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
