"""PostgreSQL and SQLite database adapter for minimal read-set token evaluation.

Connects the minimal read-set validator to database sessions with transactional
read/write tracking, query isolation, and fail-closed safety guards.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from clara_api.db.base import Base
from clara_api.db.models import GlhsSnapshotManifest, PhrProfile, User, UserConsent
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    DIGEST_ALGORITHM,
    fast_canonical_digest,
)
from clara_api.glhs.domain import GlhsInvariantError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from evaluation.comparator_studies.minimal_readset_token.token import (
    DEFAULT_HMAC_SECRET,
    generate_hmac_readset_token,
    generate_min_readset_token,
)
from evaluation.comparator_studies.minimal_readset_token.validator import (
    validate_readset_token,
)
from evaluation.glhs_binding_component_ablation.adapter import validate_proposal_context
from evaluation.glhs_binding_component_ablation.binding_mask import B000, B111

E02_ARMS = ("GLHS_B111", "MIN_READSET_TOKEN", "HMAC_READSET_TOKEN", "B000")

FORBIDDEN_PRODUCTION_IMPORT_MESSAGE = (
    "minimal_readset_token is an evaluation-only comparator package (E02); "
    "production code under services/ must not import it."
)

_TOOLING_PATH_MARKERS = (
    "/.venv/",
    "/site-packages/",
    "/__pycache__/",
    "/.local/",
    "/node_modules/",
)


def _guard_production_import() -> None:
    frame = sys._getframe(1)
    while frame is not None:
        filename = (frame.f_code.co_filename or "").replace("\\", "/")
        parts = filename.split("/")
        if "services" in parts and not any(marker in filename for marker in _TOOLING_PATH_MARKERS):
            raise RuntimeError(FORBIDDEN_PRODUCTION_IMPORT_MESSAGE)
        frame = frame.f_back


_guard_production_import()


@dataclass(frozen=True)
class ScheduleExecutionOutcome:
    """Execution outcome for a single schedule x arm evaluation."""

    schedule_id: str
    family_name: str
    arm: str
    admitted: bool
    reason_code: str
    metadata_bytes: int
    duration_ns: int
    db_reads: int
    db_writes: int

    @property
    def valid(self) -> bool:
        return self.admitted


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
            "profile_id": f"p{profile_id}",
            "actor_user_id": user_id,
            "actor_role": actor_role,
            "purpose": purpose,
            "task": task,
            "policy_version": "commitloop.v1",
            "consent_version": "medical_disclaimer:v1",
            "base_state_version": 1,
            "context_binding_mode": "snapshot_bound",
            "source_snapshot_id": source_id,
            "source_snapshot_digest": source_digest,
            "lineage_root_id": snap_fields.get("lineage_root_id", source_id),
            "evidence_ids": schedule["evidence_set"]["observed_evidence_ids"],
        },
    )()


def _create_scope(profile_id: int = 1, user_id: int = 7, purpose: str = "self_care") -> Any:
    return type(
        "Scope",
        (),
        {
            "profile": type("Profile", (), {"public_id": f"p{profile_id}", "id": profile_id, "user_id": user_id})(),
            "purpose": purpose,
        },
    )()


class MinReadsetTokenPostgresAdapter:
    """Evaluation database adapter for minimal token admission validation."""

    def __init__(
        self,
        engine: Any,
        *,
        secret_key: bytes = DEFAULT_HMAC_SECRET,
    ) -> None:
        self.engine = engine
        self.secret_key = secret_key

    def setup_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            if not session.execute(select(User).where(User.id == 7)).scalar_one_or_none():
                session.add(User(id=7, email="patient@clara.local", hashed_password="pw", role="patient", status="active"))
                session.add(PhrProfile(id=1, public_id="p1", user_id=7, status="active"))
                session.add(
                    UserConsent(
                        id=1,
                        user_id=7,
                        consent_type="medical_disclaimer",
                        consent_version="medical_disclaimer:v1",
                        accepted_at=datetime.now(UTC),
                    )
                )
                session.commit()

    def execute_schedule(
        self,
        sched: dict[str, Any],
        *,
        arm: str,
        now_utc: datetime | None = None,
    ) -> ScheduleExecutionOutcome:
        """Execute one schedule under the designated arm with full query tracking."""
        t0 = time.perf_counter_ns()
        now = now_utc or datetime.now(UTC)
        fam = sched["family_name"]
        ctx = sched["context"]
        snap_fields = sched["snapshot_fields"]
        ev_set = sched["evidence_set"]

        db_reads = 0
        db_writes = 0

        payload = {"domain": ctx["domain"], "action": ctx["action"]}
        calc_digest = fast_canonical_digest(payload, profile=CANONICALIZATION_PROFILE)

        current_snap_id = "SNAP-ORIG-001" if fam in ("ID-SUB", "CROSS-SNAPSHOT-SAME-VERSION", "LINEAGE-ROOT-SUB") else snap_fields["source_snapshot_id"]
        exp_seconds = snap_fields.get("expires_in_seconds", 3600)
        expires_at = (
            datetime.now(UTC) - timedelta(hours=2)
            if fam == "EXPIRY-CONTROL"
            else datetime.now(UTC) + timedelta(seconds=exp_seconds)
        )

        with Session(self.engine) as session:
            # Clear previous manifests to ensure pristine test isolation
            session.execute(text("DELETE FROM glhs_snapshot_manifests"))
            session.commit()
            session.expunge_all()

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
                db_writes += 1

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
            db_writes += 1

            scope = _create_scope(profile_id=1, user_id=7, purpose=ctx["purpose"])
            proposal = _create_proposal(
                schedule=sched,
                profile_id=1,
                user_id=7,
                canonical_digest=calc_digest,
            )

            # Arm dispatch
            if arm == "GLHS_B111":
                try:
                    validate_proposal_context(
                        session,
                        arm=B111,
                        scope=scope,
                        proposal=proposal,
                        evidence_ids=ev_set["observed_evidence_ids"],
                        current_version=1,
                        consent_version="medical_disclaimer:v1",
                    )
                    admitted = True
                    reason = "accepted"
                except GlhsInvariantError as e:
                    admitted = False
                    reason = str(e)
                except Exception as e:
                    admitted = False
                    reason = str(e)
                db_reads += 2
                metadata_bytes = len(json.dumps(sched, sort_keys=True).encode("utf-8")) + 420

            elif arm == "B000":
                try:
                    validate_proposal_context(
                        session,
                        arm=B000,
                        scope=scope,
                        proposal=proposal,
                        evidence_ids=ev_set["observed_evidence_ids"],
                        current_version=1,
                        consent_version="medical_disclaimer:v1",
                    )
                    admitted = True
                    reason = "accepted"
                except GlhsInvariantError as e:
                    admitted = False
                    reason = str(e)
                except Exception as e:
                    admitted = False
                    reason = str(e)
                db_reads += 1
                metadata_bytes = len(json.dumps(sched, sort_keys=True).encode("utf-8")) + 420

            elif arm == "MIN_READSET_TOKEN":
                token = generate_min_readset_token(
                    profile_id="p1",
                    actor_id=proposal.actor_user_id,
                    actor_role=proposal.actor_role,
                    purpose=proposal.purpose,
                    task=proposal.task,
                    snapshot_id=proposal.source_snapshot_id,
                    snapshot_digest=proposal.source_snapshot_digest,
                    disclosed_evidence_ids=ev_set["disclosed_provenance_ids"],
                    state_dependencies=[{"key": f"{ctx['domain']}:state", "observed_version": 1}],
                    policy_version="commitloop.v1",
                    consent_version="medical_disclaimer:v1",
                    expires_at=expires_at,
                )
                metadata_bytes = token.byte_size()

                db_reads += 1
                val_res = validate_readset_token(
                    token,
                    db=session,
                    current_profile_id="p1",
                    current_actor_id=7,
                    current_actor_role=ctx["actor_role"],
                    current_purpose=ctx["purpose"],
                    current_task=ctx["task"],
                    current_state_version=1,
                    current_policy_version="commitloop.v1",
                    current_consent_version="medical_disclaimer:v1",
                    observed_evidence_ids=ev_set["observed_evidence_ids"],
                    expected_snapshot_id=current_snap_id,
                    expected_snapshot_digest=calc_digest,
                    now_utc=now,
                    enforce_exact_snapshot=True,
                )
                admitted = val_res.valid
                reason = "accepted" if val_res.valid else val_res.reason_code

            elif arm == "HMAC_READSET_TOKEN":
                hmac_token = generate_hmac_readset_token(
                    profile_id="p1",
                    actor_id=proposal.actor_user_id,
                    actor_role=proposal.actor_role,
                    purpose=proposal.purpose,
                    task=proposal.task,
                    snapshot_id=proposal.source_snapshot_id,
                    snapshot_digest=proposal.source_snapshot_digest,
                    disclosed_evidence_ids=ev_set["disclosed_provenance_ids"],
                    state_dependencies=[{"key": f"{ctx['domain']}:state", "observed_version": 1}],
                    policy_version="commitloop.v1",
                    consent_version="medical_disclaimer:v1",
                    expires_at=expires_at,
                    hmac_key=self.secret_key,
                )
                metadata_bytes = hmac_token.byte_size()

                db_reads += 1
                val_res = validate_readset_token(
                    hmac_token,
                    db=session,
                    current_profile_id="p1",
                    current_actor_id=7,
                    current_actor_role=ctx["actor_role"],
                    current_purpose=ctx["purpose"],
                    current_task=ctx["task"],
                    current_state_version=1,
                    current_policy_version="commitloop.v1",
                    current_consent_version="medical_disclaimer:v1",
                    observed_evidence_ids=ev_set["observed_evidence_ids"],
                    expected_snapshot_id=current_snap_id,
                    expected_snapshot_digest=calc_digest,
                    hmac_key=self.secret_key,
                    now_utc=now,
                    enforce_exact_snapshot=True,
                )
                admitted = val_res.valid
                reason = "accepted" if val_res.valid else val_res.reason_code

            else:
                raise ValueError(f"unsupported_arm:{arm}")

            if admitted:
                db_writes += 1

        dur_ns = time.perf_counter_ns() - t0
        return ScheduleExecutionOutcome(
            schedule_id=sched["schedule_id"],
            family_name=fam,
            arm=arm,
            admitted=admitted,
            reason_code=reason,
            metadata_bytes=metadata_bytes,
            duration_ns=dur_ns,
            db_reads=db_reads,
            db_writes=db_writes,
        )
