"""GLHS append-only contract tests for the GRWC admission projection (R4).

Purpose
-------
Pin the intended append-only contract for
``GlhsClinicalCommitmentProposal`` while the R4 regression is reproduced:

1. ``test_projection_whitelist`` documents the DESIRED behaviour: updating
   only the admission projection fields (``admission_decision``, ``sealed_at``)
   must be permitted and must leave the canonical ``proposal_digest``
   unchanged.  The model uses a projection allow-list listener
   (``_protect_glhs_proposal_content``) registered by task
   ``SH-repair_immutable``; the earlier ``xfail(strict=True)`` defect marker
   has been removed now that the desired behaviour holds.
2. ``test_reject_canonical_update`` documents the adversarial control that
   must genuinely pass today: mutating canonical proposal content
   (``origin`` / ``proposed_transition`` / ``source_snapshot_digest``) raises
   ``ValueError`` (message contains "immutable") and the row is unchanged
   after rollback.
3. ``test_atomic_rollback_preserves_canonical_hash`` proves atomicity: after
   a rejected canonical mutation inside a transaction, a ``ROLLBACK`` leaves
   the canonical content digest unchanged.

Allowed input
-------------
Real SQLAlchemy models from ``clara_api.db.models`` against a per-test
in-memory SQLite database created from ``Base.metadata`` (the repo's fixture
convention, e.g. ``tests/test_glhs_r4_admission.py``).  No production DB, no
whole-system mocks, no disabling of the immutable event listeners.

Failure semantics
-----------------
Canonical mutations must raise ``ValueError`` whose message contains
"immutable" (the stable guard text from ``_reject_glhs_ledger_mutation``);
projection updates must succeed silently and preserve ``proposal_digest``.
Field names are discovered via ``sqlalchemy.inspect`` rather than assumed.

Version
-------
``1.0.0`` (task SH-guard_regression, phase P00, shared).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    PhrProfile,
    User,
)
from clara_api.glhs.canonical_json import consistency_fingerprint
from clara_api.glhs.commitment_gateway import _proposal_envelope

PROJECTION_FIELDS = frozenset({"admission_decision", "sealed_at"})
CANONICAL_FIELDS = ("origin", "proposed_transition", "source_snapshot_digest")


def _discovered_column_names(model: type[GlhsClinicalCommitmentProposal]) -> set[str]:
    """Discover actual mapped column names via SQLAlchemy inspection."""

    return {column.key for column in inspect(model).columns}


def _make_proposal(db: Session) -> GlhsClinicalCommitmentProposal:
    """Create one minimal, sealed-canonical GLHS clinical commitment proposal."""

    owner = User(
        email=f"sh-guard-{uuid4().hex[:8]}@example.test", hashed_password="x", role="normal"
    )
    db.add(owner)
    db.flush()
    profile = PhrProfile(user_id=owner.id)
    db.add(profile)
    db.flush()
    commitment = GlhsClinicalCommitment(
        profile_id=profile.id,
        semantic_key=f"observation:sh-guard:{uuid4().hex}",
        domain="observations",
        supersession_key=f"observation:sh-guard:{uuid4().hex}",
    )
    db.add(commitment)
    db.flush()
    proposal = GlhsClinicalCommitmentProposal(
        public_id=str(uuid4()),
        commitment_id=commitment.id,
        target_profile_public_id=profile.public_id,
        base_state_version=1,
        observed_evidence_ids_json=[],
        proposed_transition="OPEN",
        purpose="self_care",
        task="sh_guard_regression",
        # base_version_only mode forbids origin="model" (lineage check
        # constraint), so the fixture uses a manual user origin.
        origin="user",
        actor_user_id=owner.id,
        actor_role="owner",
        context_binding_mode="base_version_only",
        policy_version="commitloop.v1",
        consent_version="not_required",
        proposal_digest="",
    )
    # Seal canonical content at INSERT time: the canonical envelope fields are
    # all known before flush, and any post-insert UPDATE of proposal_digest
    # would itself be rejected by the immutable guard under test.  The
    # projection fields (admission_decision/sealed_at) are NOT part of the
    # envelope, so stamping them must never change this digest.
    proposal.proposal_digest = consistency_fingerprint(_proposal_envelope(proposal))
    db.add(proposal)
    db.commit()
    return proposal


def _row_digest(db: Session, proposal_id: int) -> str:
    row = db.execute(
        select(GlhsClinicalCommitmentProposal).where(
            GlhsClinicalCommitmentProposal.id == proposal_id
        )
    ).scalar_one()
    return consistency_fingerprint(_proposal_envelope(row))


def test_projection_whitelist() -> None:
    """Desired behaviour: projection-only UPDATE is permitted, digest unchanged.

    The mutation mirrors the GRWC admission projection path
    (``clara_api/glhs/admission.py``: ``admission_decision``/``sealed_at``
    writes) that currently trips the blanket immutable guard.
    """

    # Discover the actual column names first: the contract only makes sense
    # if the projection fields exist on the model as currently mapped.
    discovered = _discovered_column_names(GlhsClinicalCommitmentProposal)
    missing = PROJECTION_FIELDS - discovered
    assert not missing, f"projection fields missing from model: {sorted(missing)}"

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        proposal = _make_proposal(db)
        before_digest = _row_digest(db, proposal.id)

        # The exact mutation path used by GRWC admission
        # (clara_api/glhs/admission.py:697-700): stamp the projection fields.
        proposal.admission_decision = "ADMITTED"
        proposal.sealed_at = datetime.now(UTC)
        db.commit()

        proposal_id = proposal.id
        db.expire_all()
        refreshed = db.get(GlhsClinicalCommitmentProposal, proposal_id)
        assert refreshed is not None
        assert refreshed.admission_decision == "ADMITTED"
        assert refreshed.sealed_at is not None
        # Canonical digest must be unchanged: projection fields are not part
        # of the canonical proposal envelope.
        assert _row_digest(db, proposal_id) == before_digest


def test_reject_canonical_update() -> None:
    """Adversarial control: canonical UPDATE raises and the row is unchanged.

    Must genuinely pass today: the projection allow-list rejects any UPDATE
    touching canonical proposal fields before the flush reaches the DB.
    """

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        proposal = _make_proposal(db)
        before_digest = _row_digest(db, proposal.id)
        before_decision = proposal.admission_decision

        # Attempt to rewrite the canonical lineage of the proposal.
        proposal.origin = "clinician"
        proposal.proposed_transition = "CANCEL"
        if "source_snapshot_digest" in _discovered_column_names(
            GlhsClinicalCommitmentProposal
        ):
            proposal.source_snapshot_digest = "sha256:tampered"

        with pytest.raises(ValueError, match="immutable"):
            db.commit()

        # Roll back the rejected transaction; the stored row must be untouched.
        db.rollback()
        proposal_id = proposal.id
        db.expire_all()
        refreshed = db.get(GlhsClinicalCommitmentProposal, proposal_id)
        assert refreshed is not None
        assert refreshed.origin == "user"
        assert refreshed.proposed_transition == "OPEN"
        assert refreshed.source_snapshot_digest is None
        assert refreshed.admission_decision == before_decision
        assert _row_digest(db, proposal_id) == before_digest


def test_atomic_rollback_preserves_canonical_hash() -> None:
    """After a rejected canonical mutation, ROLLBACK preserves the digest."""

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        proposal = _make_proposal(db)
        before_digest = _row_digest(db, proposal.id)

        proposal.origin = "system"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()

        proposal_id = proposal.id
        db.expire_all()
        refreshed = db.get(GlhsClinicalCommitmentProposal, proposal_id)
        assert refreshed is not None
        # Canonical content digest is preserved by the atomic rollback.
        assert _row_digest(db, proposal_id) == before_digest
