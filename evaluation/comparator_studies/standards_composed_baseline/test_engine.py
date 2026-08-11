from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from evaluation.comparator_studies.bitemporal_state_arbitration.engine import (
    ArbitrationEvent,
)
from evaluation.comparator_studies.standards_composed_baseline.engine import (
    MechanismProposal,
    StandardsComposedState,
)
from evaluation.comparator_studies.standards_composed_baseline.validate_manifest import (
    validate_manifest,
)


def _proposal() -> MechanismProposal:
    return MechanismProposal(
        proposal_id="proposal-1",
        profile_id="profile-1",
        actor_id="actor-1",
        purpose="self_care",
        observed_base_version=0,
        provenance_ids=("evidence-1",),
        resource_key="Observation/example",
        value={"status": "final"},
        source_snapshot_id="snapshot-1",
        source_snapshot_digest="digest-1",
    )


def test_strong_baseline_has_version_authorization_provenance_and_audit() -> None:
    state = StandardsComposedState(profile_id="profile-1")
    state.authorize(actor_id="actor-1", purpose="self_care")
    accepted = state.apply(_proposal())
    assert accepted.accepted is True
    assert accepted.resulting_version == 1
    assert state.provenance["Observation/example"] == ("evidence-1",)
    assert state.audit[accepted.audit_index]["accepted"] is True

    stale = state.apply(replace(_proposal(), proposal_id="stale"))
    assert stale.reason_code == "if_match_version_mismatch"
    assert stale.resulting_version == 1


def test_baseline_composes_bitemporal_resolution_with_late_evidence_boundary() -> None:
    cutoff = datetime(2026, 1, 2, tzinfo=UTC)
    state = StandardsComposedState(profile_id="profile-1")
    events = [
        ArbitrationEvent(
            event_id="known-a",
            slot="Observation/example",
            value="preliminary",
            valid_from=cutoff - timedelta(days=1),
            valid_to=None,
            known_at=cutoff - timedelta(days=1),
            authority=1,
        ),
        ArbitrationEvent(
            event_id="known-b",
            slot="Observation/example",
            value="final",
            valid_from=cutoff,
            valid_to=None,
            known_at=cutoff,
            authority=1,
            relation="BRANCH-CONFLICT",
            target_id="known-a",
        ),
        ArbitrationEvent(
            event_id="late",
            slot="Observation/example",
            value="amended",
            valid_from=cutoff,
            valid_to=None,
            known_at=cutoff + timedelta(days=1),
            authority=1,
        ),
    ]
    resolved = state.resolve(events, valid_at=cutoff, known_at=cutoff)
    assert resolved.active_ids == ("known-a", "known-b")
    assert resolved.conflict_ids == ("known-a", "known-b")
    assert "late" not in resolved.historical_ids


def test_baseline_reauthorizes_but_intentionally_does_not_bind_exact_snapshot() -> None:
    state = StandardsComposedState(profile_id="profile-1")
    state.authorize(actor_id="actor-1", purpose="self_care")
    altered = replace(
        _proposal(), source_snapshot_id="wrong-snapshot", source_snapshot_digest="tampered"
    )
    assert state.apply(altered).accepted is True

    next_proposal = replace(
        _proposal(), proposal_id="revoked", observed_base_version=1
    )
    state.revoke(actor_id="actor-1", purpose="self_care")
    assert state.apply(next_proposal).reason_code == "current_authorization_denied"


def test_profile_and_provenance_fail_closed_with_stable_reasons() -> None:
    state = StandardsComposedState(profile_id="profile-1")
    state.authorize(actor_id="actor-1", purpose="self_care")
    assert state.apply(replace(_proposal(), profile_id="profile-2")).reason_code == (
        "profile_mismatch"
    )
    assert state.apply(replace(_proposal(), provenance_ids=())).reason_code == (
        "provenance_required"
    )


def test_frozen_manifest_validates_and_detects_tampering(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parent
    assert validate_manifest(source)["artifact_status"] == "FROZEN_MECHANISM_CONTRACT"

    copied = tmp_path / "comparator"
    shutil.copytree(source, copied, ignore=shutil.ignore_patterns("__pycache__"))
    (copied / "engine.py").write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="comparator_file_digest_mismatch:engine.py"):
        validate_manifest(copied)
