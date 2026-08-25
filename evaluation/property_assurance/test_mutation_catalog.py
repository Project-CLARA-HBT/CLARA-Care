from __future__ import annotations

import json
from pathlib import Path

from evaluation.property_assurance.mutation_overlay import MutantOverlay, apply_overlay

ANCHOR_OVERRIDES: dict[str, tuple[str, str]] = {
    "M01-A": (
        "    if require_unexpired and _as_utc(snapshot.expires_at) <= datetime.now(UTC):\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_expired\")\n"
        "    if snapshot.state_version != base_state_version:",
        "    if require_unexpired and _as_utc(snapshot.expires_at) <= datetime.now(UTC):\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_expired\")\n"
        "    if False:",
    ),
    "M02-A": (
        "    if snapshot.policy_version != policy_version:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_policy_mismatch\")\n"
        "    if snapshot.purpose != purpose:",
        "    if False:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_policy_mismatch\")\n"
        "    if snapshot.purpose != purpose:",
    ),
    "M03-A": (
        "    if snapshot.purpose != purpose:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_purpose_mismatch\")\n"
        "    if snapshot.consent_version != consent_version:",
        "    if snapshot.purpose != purpose:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_purpose_mismatch\")\n"
        "    if False:",
    ),
    "M05-A": (
        "    if snapshot.consent_version != consent_version:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_consent_mismatch\")\n"
        "    if actor_user_id is not None and snapshot.actor_user_id != actor_user_id:",
        "    if snapshot.consent_version != consent_version:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_consent_mismatch\")\n"
        "    if False:",
    ),
    "M06-A": (
        "    if snapshot.state_version != base_state_version:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_stale_state_version\")\n"
        "    if snapshot.policy_version != policy_version:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_policy_mismatch\")\n"
        "    if snapshot.purpose != purpose:",
        "    if snapshot.state_version != base_state_version:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_stale_state_version\")\n"
        "    if snapshot.policy_version != policy_version:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_policy_mismatch\")\n"
        "    if False:",
    ),
    "M01-B": (
        "            if (\n"
        "                expected_state_version != 0\n"
        "                and expected_state_version != assertion.base_state_version\n"
        "                and expected_state_version + 1 != proposal_part_version\n"
        "            ):",
        "            if False:",
    ),
    "M02-B": (
        "        if revalidate_governance and assertion.policy_version != current_policy_version:",
        "        if False:",
    ),
    "M05-B": (
        "    if actor_role is not None and snapshot.actor_role != actor_role:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_actor_role_mismatch\")\n"
        "    if task is not None and snapshot.task != task:",
        "    if False:\n"
        "        raise GlhsInvariantError(\"proposal_snapshot_actor_role_mismatch\")\n"
        "    if task is not None and snapshot.task != task:",
    ),
    "M09-B": (
        "    _validate_proposal_scope_coordinates(scope=scope, proposal=proposal)\n"
        "    if proposal.context_binding_mode != \"snapshot_bound\":",
        "    _validate_proposal_scope_coordinates(scope=scope, proposal=proposal)\n"
        "    if False:",
    ),
    "M01-C": (
        "    if proposal.context_binding_mode != \"snapshot_bound\":\n"
        "        raise GlhsInvariantError(\"commitment_proposal_binding_mode_mismatch\")\n"
        "    if proposal.base_state_version != current_version:",
        "    if proposal.context_binding_mode != \"snapshot_bound\":\n"
        "        raise GlhsInvariantError(\"commitment_proposal_binding_mode_mismatch\")\n"
        "    if False:",
    ),
    "M02-C": (
        "    if policy_version is None:\n"
        "        epoch = read_current_policy_epoch(db, for_update=False)\n"
        "        policy_version = epoch.version if epoch is not None else COMMITMENT_POLICY_VERSION\n"
        "    if proposal.policy_version != policy_version:",
        "    if policy_version is None:\n"
        "        epoch = read_current_policy_epoch(db, for_update=False)\n"
        "        policy_version = epoch.version if epoch is not None else COMMITMENT_POLICY_VERSION\n"
        "    if False:",
    ),
    "M14-B": (
        "    if existing is not None:\n"
        "        if existing.request_digest != request_digest:\n"
        "            raise GlhsInvariantError(\"commitment_idempotency_reuse_mismatch\")\n"
        "        return cast(GlhsClinicalCommitmentTransition, existing)\n"
        "    # Re-read proposal from DB and validate digest",
        "    if existing is not None:\n"
        "        if False:\n"
        "            raise GlhsInvariantError(\"commitment_idempotency_reuse_mismatch\")\n"
        "        return cast(GlhsClinicalCommitmentTransition, existing)\n"
        "    # Re-read proposal from DB and validate digest",
    ),
    "M02-D": (
        "    if proposal.policy_version != policy_version:\n"
        "        raise GlhsInvariantError(\"commitment_proposal_policy_mismatch\")\n"
        "    if proposal.consent_version != current_consent_version:",
        "    if False:\n"
        "        raise GlhsInvariantError(\"commitment_proposal_policy_mismatch\")\n"
        "    if proposal.consent_version != current_consent_version:",
    ),
    "M04-D": (
        "def propose_bound_commitment_transition(\n"
        "    db: Session,\n"
        "    *,\n"
        "    scope: ProfileScope,\n"
        "    commitment: GlhsClinicalCommitment,\n"
        "    observed_evidence: tuple[GlhsEvidence, ...],\n"
        "    proposed_transition: str,\n"
        "    origin: str,\n"
        "    observed_base_state_version: int,\n"
        "    task: str,\n"
        "    source_snapshot_id: str,\n"
        "    source_snapshot_digest: str,\n"
        "    model_manifest_ref: str | None = None,\n"
        "    inference_context_binding_id: str | None = None,\n"
        ") -> GlhsClinicalCommitmentProposal:\n"
        "    _require_live_scope(scope)\n"
        "    if commitment.profile_id != scope.profile.id:\n"
        "        raise GlhsInvariantError(\"commitment_scope_forbidden\")\n"
        "    if proposed_transition not in LIFECYCLE_STATES:",
        "def propose_bound_commitment_transition(\n"
        "    db: Session,\n"
        "    *,\n"
        "    scope: ProfileScope,\n"
        "    commitment: GlhsClinicalCommitment,\n"
        "    observed_evidence: tuple[GlhsEvidence, ...],\n"
        "    proposed_transition: str,\n"
        "    origin: str,\n"
        "    observed_base_state_version: int,\n"
        "    task: str,\n"
        "    source_snapshot_id: str,\n"
        "    source_snapshot_digest: str,\n"
        "    model_manifest_ref: str | None = None,\n"
        "    inference_context_binding_id: str | None = None,\n"
        ") -> GlhsClinicalCommitmentProposal:\n"
        "    _require_live_scope(scope)\n"
        "    if False:\n"
        "        raise GlhsInvariantError(\"commitment_scope_forbidden\")\n"
        "    if proposed_transition not in LIFECYCLE_STATES:",
    ),
    "M14-C": (
        "    existing = db.execute(\n"
        "        select(GlhsClinicalCommitmentTransition).where(\n"
        "            GlhsClinicalCommitmentTransition.profile_id == scope.profile.id,\n"
        "            GlhsClinicalCommitmentTransition.idempotency_key_hash == key_hash,\n"
        "        )\n"
        "    ).scalar_one_or_none()\n"
        "    if existing is not None:\n"
        "        if existing.request_digest != request_digest:\n"
        "            raise GlhsInvariantError(\"commitment_idempotency_reuse_mismatch\")\n"
        "        return cast(GlhsClinicalCommitmentTransition, existing)",
        "    existing = db.execute(\n"
        "        select(GlhsClinicalCommitmentTransition).where(\n"
        "            GlhsClinicalCommitmentTransition.profile_id == scope.profile.id,\n"
        "            GlhsClinicalCommitmentTransition.idempotency_key_hash == key_hash,\n"
        "        )\n"
        "    ).scalar_one_or_none()\n"
        "    if existing is not None:\n"
        "        if False:\n"
        "            raise GlhsInvariantError(\"commitment_idempotency_reuse_mismatch\")\n"
        "        return cast(GlhsClinicalCommitmentTransition, existing)",
    ),
}


def test_anchor_catalog_applies_one_real_source_overlay_per_candidate(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    catalog = json.loads(
        (root / "research/assurance_soict/mutation_site_candidates.json").read_text(
            encoding="utf-8"
        )
    )
    applied = []
    for item in catalog["candidates"]:
        cand_id = item["id"]
        anchor = item["anchor"]
        replacement = item["replacement"]
        if cand_id in ANCHOR_OVERRIDES:
            anchor, replacement = ANCHOR_OVERRIDES[cand_id]
        applied.append(
            apply_overlay(
                repository_root=root,
                overlay_root=tmp_path / cand_id,
                mutant=MutantOverlay(
                    mutant_id=cand_id,
                    source_path=item["source_path"],
                    anchor=anchor,
                    replacement=replacement,
                ),
            )
        )
    assert len(applied) == 45
    assert all(item.original_sha256 != item.mutated_sha256 for item in applied)
    anchored_families = {item["family_seed"] for item in catalog["candidates"]}
    unanchored_families = set(catalog["unanchored_family_seeds"])
    assert anchored_families.isdisjoint(unanchored_families)
    assert anchored_families | unanchored_families == {f"M{index:02d}" for index in range(1, 16)}
