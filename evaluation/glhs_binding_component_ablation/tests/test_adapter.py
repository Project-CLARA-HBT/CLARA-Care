"""Unit tests for GLHS component-wise exact-binding ablation adapter (E01)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from clara_api.glhs import gateway
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    DIGEST_ALGORITHM,
    fast_canonical_digest,
)
from clara_api.glhs.domain import GlhsInvariantError

from evaluation.glhs_binding_component_ablation import adapter, binding_mask
from evaluation.glhs_binding_component_ablation.binding_mask import (
    ARMS,
    B000,
    B001,
    B010,
    B011,
    B100,
    B101,
    B110,
    B111,
    BindingMask,
    get_binding_mask,
)


def _fake_scope(profile_id: int = 1) -> object:
    return type(
        "Scope",
        (),
        {
            "profile": type("Profile", (), {"public_id": f"p{profile_id}", "id": profile_id})(),
            "purpose": "self_care",
        },
    )()


def _fake_proposal(**overrides: Any) -> object:
    defaults = {
        "target_profile_public_id": "p1",
        "purpose": "self_care",
        "actor_user_id": 7,
        "actor_role": "owner",
        "task": "monitoring_repeat",
        "policy_version": "commitloop.v1",
        "consent_version": "medical_disclaimer:v1",
        "base_state_version": 1,
        "context_binding_mode": "snapshot_bound",
        "source_snapshot_id": "s1",
        "source_snapshot_digest": "d_valid",
    }
    defaults.update(overrides)
    return type("Proposal", (), defaults)()


def _fake_snapshot(
    public_id: str = "s1",
    profile_id: int = 1,
    state_version: int = 1,
    payload: dict | None = None,
    digest: str = "d_valid",
    evidence_ids: list[str] | None = None,
    expires_at: datetime | None = None,
) -> object:
    p = payload if payload is not None else {"data": "test"}
    calc_digest = fast_canonical_digest(p) if digest == "d_valid" else digest
    return type(
        "GlhsSnapshotManifest",
        (),
        {
            "id": 1,
            "public_id": public_id,
            "profile_id": profile_id,
            "state_version": state_version,
            "policy_version": "commitloop.v1",
            "consent_version": "medical_disclaimer:v1",
            "purpose": "self_care",
            "task": "monitoring_repeat",
            "actor_user_id": 7,
            "actor_role": "owner",
            "snapshot_payload_json": p,
            "snapshot_digest": calc_digest,
            "manifest_digest": calc_digest,
            "canonicalization_profile": CANONICALIZATION_PROFILE,
            "digest_algorithm": DIGEST_ALGORITHM,
            "provenance_ids_json": evidence_ids if evidence_ids is not None else ["e1", "e2"],
            "expires_at": expires_at or (datetime.now(UTC) + timedelta(hours=1)),
        },
    )()


class FakeDB:
    def __init__(self, snapshots: list[Any]) -> None:
        self.snapshots = snapshots

    def execute(self, statement: Any) -> Any:
        class MockResult:
            def __init__(self, items: list[Any]) -> None:
                self.items = items

            def scalar_one_or_none(self) -> Any:
                return self.items[0] if self.items else None

        return MockResult(self.snapshots)

    def get(self, model: Any, ident: Any) -> Any:
        return type("PhrProfile", (), {"user_id": 7, "id": ident})()


def test_factorial_arms_inventory() -> None:
    assert len(ARMS) == 8
    expected = {
        B000: (False, False, False),
        B100: (True, False, False),
        B010: (False, True, False),
        B001: (False, False, True),
        B110: (True, True, False),
        B101: (True, False, True),
        B011: (False, True, True),
        B111: (True, True, True),
    }
    for arm, expected_tuple in expected.items():
        mask = get_binding_mask(arm)
        assert mask.as_tuple() == expected_tuple
        assert mask.as_code() == arm
        assert (arm != B000) == adapter.binding_check_applied(arm)


def test_unknown_arm_rejected() -> None:
    with pytest.raises(ValueError, match="unknown_ablation_arm"):
        get_binding_mask("B999")
    with pytest.raises(ValueError, match="unknown_ablation_arm"):
        adapter.validate_proposal_context(
            None,
            arm="INVALID",
            scope=None,
            proposal=None,
            evidence_ids=(),
            current_version=1,
            consent_version="c",
        )


def test_non_ablated_checks_run_across_all_arms(monkeypatch: pytest.MonkeyPatch) -> None:
    gov_calls: list[str] = []

    def fake_gov(*args: Any, **kwargs: Any) -> None:
        gov_calls.append(kwargs["purpose"])

    monkeypatch.setattr(adapter, "_validate_proposal_scope_coordinates", lambda **kwargs: None)
    monkeypatch.setattr(adapter, "_current_snapshot", lambda *args, **kwargs: _fake_snapshot())
    monkeypatch.setattr(adapter, "validate_current_governance_coordinates", fake_gov)

    db = FakeDB([_fake_snapshot()])
    scope = _fake_scope()
    valid_payload = {"data": "test"}
    valid_digest = fast_canonical_digest(valid_payload)
    proposal = _fake_proposal(source_snapshot_digest=valid_digest)

    for arm in sorted(ARMS):
        adapter.validate_proposal_context(
            db,
            arm=arm,
            scope=scope,
            proposal=proposal,
            evidence_ids=("e1",),
            current_version=1,
            consent_version="medical_disclaimer:v1",
        )

    assert len(gov_calls) == 8


def test_factor_1_snapshot_identity_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factor 1 (c_id) should reject on B100, B110, B101, B111 when snapshot ID is substituted."""
    current_snap = _fake_snapshot(public_id="s_current")
    other_snap = _fake_snapshot(public_id="s_other")

    monkeypatch.setattr(adapter, "_validate_proposal_scope_coordinates", lambda **kwargs: None)
    monkeypatch.setattr(adapter, "_current_snapshot", lambda *args, **kwargs: current_snap)
    monkeypatch.setattr(adapter, "validate_current_governance_coordinates", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway, "validate_current_governance_coordinates", lambda *args, **kwargs: None)

    # Proposal cites "s_other" while current is "s_current"
    valid_payload = {"data": "test"}
    valid_digest = fast_canonical_digest(valid_payload)
    proposal = _fake_proposal(
        source_snapshot_id="s_other",
        source_snapshot_digest=valid_digest,
    )

    for arm in sorted(ARMS):
        mask = get_binding_mask(arm)
        db = FakeDB([other_snap])
        if mask.snapshot_identity:
            with pytest.raises(GlhsInvariantError):
                adapter.validate_proposal_context(
                    db,
                    arm=arm,
                    scope=_fake_scope(),
                    proposal=proposal,
                    evidence_ids=("e1",),
                    current_version=1,
                    consent_version="medical_disclaimer:v1",
                )
        else:
            adapter.validate_proposal_context(
                db,
                arm=arm,
                scope=_fake_scope(),
                proposal=proposal,
                evidence_ids=("e1",),
                current_version=1,
                consent_version="medical_disclaimer:v1",
            )


def test_factor_2_snapshot_digest_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factor 2 (c_digest) should reject on B010, B110, B011, B111 when digest is corrupted."""
    snap = _fake_snapshot(public_id="s1")

    monkeypatch.setattr(adapter, "_validate_proposal_scope_coordinates", lambda **kwargs: None)
    monkeypatch.setattr(adapter, "_current_snapshot", lambda *args, **kwargs: snap)
    monkeypatch.setattr(adapter, "validate_current_governance_coordinates", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway, "validate_current_governance_coordinates", lambda *args, **kwargs: None)

    # Proposal has mutated/wrong digest
    proposal = _fake_proposal(
        source_snapshot_id="s1",
        source_snapshot_digest="d_corrupted_9999",
    )
    db = FakeDB([snap])

    for arm in sorted(ARMS):
        mask = get_binding_mask(arm)
        if mask.snapshot_digest:
            with pytest.raises(GlhsInvariantError, match="proposal_snapshot_digest_mismatch"):
                adapter.validate_proposal_context(
                    db,
                    arm=arm,
                    scope=_fake_scope(),
                    proposal=proposal,
                    evidence_ids=("e1",),
                    current_version=1,
                    consent_version="medical_disclaimer:v1",
                )
        else:
            adapter.validate_proposal_context(
                db,
                arm=arm,
                scope=_fake_scope(),
                proposal=proposal,
                evidence_ids=("e1",),
                current_version=1,
                consent_version="medical_disclaimer:v1",
            )


def test_factor_3_evidence_membership_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factor 3 (c_evidence) should reject on B001, B101, B011, B111 when evidence is not disclosed."""
    snap = _fake_snapshot(public_id="s1", evidence_ids=["e1", "e2"])

    monkeypatch.setattr(adapter, "_validate_proposal_scope_coordinates", lambda **kwargs: None)
    monkeypatch.setattr(adapter, "_current_snapshot", lambda *args, **kwargs: snap)
    monkeypatch.setattr(adapter, "validate_current_governance_coordinates", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway, "validate_current_governance_coordinates", lambda *args, **kwargs: None)

    valid_payload = {"data": "test"}
    valid_digest = fast_canonical_digest(valid_payload)
    proposal = _fake_proposal(
        source_snapshot_id="s1",
        source_snapshot_digest=valid_digest,
    )
    db = FakeDB([snap])

    for arm in sorted(ARMS):
        mask = get_binding_mask(arm)
        if mask.evidence_membership:
            with pytest.raises(GlhsInvariantError, match="proposal_evidence_not_disclosed"):
                adapter.validate_proposal_context(
                    db,
                    arm=arm,
                    scope=_fake_scope(),
                    proposal=proposal,
                    evidence_ids=("e1", "e_alien_999"),  # e_alien_999 not disclosed in snap
                    current_version=1,
                    consent_version="medical_disclaimer:v1",
                )
        else:
            adapter.validate_proposal_context(
                db,
                arm=arm,
                scope=_fake_scope(),
                proposal=proposal,
                evidence_ids=("e1", "e_alien_999"),
                current_version=1,
                consent_version="medical_disclaimer:v1",
            )


def test_adapter_refuses_production_import(tmp_path: Path) -> None:
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "probe.py").write_text(
        "import evaluation.glhs_binding_component_ablation.adapter\n", encoding="utf-8"
    )
    import importlib

    sys.path.insert(0, str(tmp_path))
    module_name = "evaluation.glhs_binding_component_ablation.adapter"
    cached = sys.modules.pop(module_name, None)
    try:
        with pytest.raises(RuntimeError, match="evaluation-only"):
            importlib.import_module("services.probe")
    finally:
        if cached is not None:
            sys.modules[module_name] = cached
        sys.path.remove(str(tmp_path))


def test_production_code_clean_of_ablation_import() -> None:
    """Verify that no code in services/ imports glhs_binding_component_ablation."""
    root = Path(__file__).resolve().parents[3]
    services_path = root / "services"
    offenders: list[str] = []
    for py_file in services_path.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        if "glhs_binding_component_ablation" in text:
            offenders.append(str(py_file))
    assert offenders == []
