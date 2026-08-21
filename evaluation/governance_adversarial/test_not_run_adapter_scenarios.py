from __future__ import annotations

import pytest
from clara_api.glhs.domain import GlhsInvariantError

from evaluation.glhs_postgres_toctou.barrier import NullBarrier
from evaluation.governance_adversarial.not_run_adapter_scenarios import (
    IMPLEMENTED_FAMILIES,
    REQUIRES_LLM_ATTACK_STUDY_FAMILIES,
    AdapterEnv,
    cross_subject_retrieval_scenario,
    policy_version_change_scenario,
    purpose_mismatch_scenario,
    role_mismatch_scenario,
    run_scenario,
    scenario_manifest,
    unrelated_disclosure_request_scenario,
)

REJECTIONS = {
    "synthetic_policy_epoch_advanced": "assertion_policy_mismatch",
    "synthetic_purpose_switch": "assertion_purpose_mismatch",
    "synthetic_role_coordinate_changed": "proposal_snapshot_actor_role_mismatch",
    "scope_forbidden_cross_subject": "scope_forbidden",
    "scope_forbidden_unrelated_purpose": "scope_forbidden",
}


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.policy_epoch: object | None = None

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True

    def get(self, model: type, ident: object) -> object:
        return None

    def scalar(self, statement: object) -> object:
        return 0

    def load_policy_epoch(self, *, policy_domain: str) -> object | None:
        return self.policy_epoch


class FakeGateway:
    GlhsInvariantError = GlhsInvariantError

    def __init__(self, rejections: dict[str, str] | None = None) -> None:
        self.rejections = dict(rejections or REJECTIONS)
        self.calls: list[tuple[str, str]] = []

    def compile_thss(self, db: object, *, purpose: str) -> object:
        self.calls.append(("compile_thss", purpose))
        return object()

    def propose_assertion(
        self, db: object, *, profile_id: int, actor_user_id: int, data: object, evidence: object
    ) -> object:
        self.calls.append(("propose_assertion", str(profile_id)))
        return type(
            "Assertion",
            (),
            {
                "id": 1,
                "public_id": "prop-notrun",
                "base_state_version": 0,
            },
        )()

    def apply_transition(
        self,
        db: object,
        *,
        scope: object,
        assertion: object,
        action: str,
        expected_state_version: int,
        idempotency_key: str,
        transition_kind: str,
        reason_code: str,
    ) -> object:
        self.calls.append(("apply_transition", reason_code))
        reject = self.rejections.get(reason_code)
        if reject:
            raise GlhsInvariantError(reject)
        return type("Transition", (), {"public_id": "trans-notrun", "resulting_state_version": 1})()

    def resolve_disclosure_scope(self, db: object, *, subject_id: str, purpose: str) -> bool:
        self.calls.append(("resolve_disclosure_scope", subject_id))
        return subject_id == "self" and purpose == "self_care"


def _env() -> AdapterEnv:
    gateway = FakeGateway()
    return AdapterEnv(
        session_factory=FakeSession,
        adapter_factory=lambda session: session,
        gateway=gateway,
        barrier_factory=lambda parties: NullBarrier(),
        scope_factory=None,
        epoch_factory=None,
        consent_record_factory=None,
    )


def test_manifest_excludes_prompt_injection_families() -> None:
    manifest = scenario_manifest()
    assert manifest["status"] == "FROZEN_PROTOCOL_NOT_EXECUTED"
    assert manifest["implemented_families"] == sorted(IMPLEMENTED_FAMILIES)
    assert "gst_bypass_prompt" not in manifest["implemented_families"]
    assert "patient_evidence_prompt_injection" not in manifest["implemented_families"]
    assert manifest["requires_llm_attack_study_families"] == sorted(
        REQUIRES_LLM_ATTACK_STUDY_FAMILIES
    )


def test_policy_version_change_is_rejected_by_strict_gateway() -> None:
    env = _env()
    observation = policy_version_change_scenario(env)
    assert observation.outcome == "assertion_policy_mismatch"
    assert observation.classification == "assertion_policy_mismatch"
    assert observation.safety_success is True
    assert observation.rejection is not None
    assert observation.rejection.reason_code == "assertion_policy_mismatch"
    assert observation.persisted_writers == ("advance_governance_policy_epoch",)
    assert observation.drift_coordinates["drift"] == "policy_version_change"
    assert "advance_governance_policy_epoch" in scenario_manifest()["persisted_writers_reused"]


def test_purpose_mismatch_is_rejected_by_strict_gateway() -> None:
    env = _env()
    observation = purpose_mismatch_scenario(env)
    assert observation.outcome == "assertion_purpose_mismatch"
    assert observation.safety_success is True
    assert observation.persisted_writers == ("purpose_or_authorization_change",)
    assert observation.drift_coordinates["after_purpose"] == "research-adversarial"


def test_role_mismatch_is_rejected_by_strict_gateway() -> None:
    env = _env()
    observation = role_mismatch_scenario(env)
    assert observation.outcome == "proposal_snapshot_actor_role_mismatch"
    assert observation.safety_success is True
    assert observation.persisted_writers == ("role_change",)


def test_cross_subject_retrieval_denied() -> None:
    env = _env()
    observation = cross_subject_retrieval_scenario(env)
    assert observation.outcome == "scope_forbidden_cross_subject"
    assert observation.safety_success is True
    assert observation.persisted_writers == ()


def test_unrelated_disclosure_request_denied() -> None:
    env = _env()
    observation = unrelated_disclosure_request_scenario(env)
    assert observation.outcome == "scope_forbidden_unrelated_purpose"
    assert observation.safety_success is True


def test_run_scenario_dispatcher() -> None:
    env = _env()
    observation = run_scenario(env, "policy_version_change")
    assert observation.family == "policy_version_change"
    assert observation.scenario_id == "policy_version_change-001"


def test_prompt_injection_families_are_not_run_scenarios() -> None:
    env = _env()
    for family in REQUIRES_LLM_ATTACK_STUDY_FAMILIES:
        with pytest.raises(ValueError, match="model_mediated_protocol"):
            run_scenario(env, family)


def test_committed_under_weak_gateway_is_not_fabricated_safe() -> None:
    env = _env()
    gateway = env.gateway
    assert isinstance(gateway, FakeGateway)
    gateway.rejections = {}
    observation = policy_version_change_scenario(env)
    # A misconfigured (unbound-like) gateway that commits is reported as a
    # committed outcome with reconstruction, never as a rejection.
    assert observation.outcome == "transition_committed"
    assert observation.safety_success is False
    assert observation.committed is not None
    assert observation.rejection is None
