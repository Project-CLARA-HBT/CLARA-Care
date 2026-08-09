REQUIRED_PROPERTIES = {
    "stale_base_version_rejected",
    "supersession_preserves_history",
    "active_assertion_has_evidence_ancestry",
    "comparable_conflict_not_silently_collapsed",
    "revocation_excluded_from_following_snapshot",
    "identical_evidence_idempotent",
    "derived_store_loss_preserves_canonical_state",
    "policy_change_invalidates_context",
}


def test_property_inventory_is_complete() -> None:
    assert len(REQUIRED_PROPERTIES) == 8
