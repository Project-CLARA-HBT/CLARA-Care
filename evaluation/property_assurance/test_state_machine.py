"""Stateful gateway assurance substrate for the SOICT protocol.

This is deliberately in-process development evidence.  Its traces are not the
SOICT mutation results or an API-bound headline experiment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import clara_api.glhs.gateway as gateway_module
from clara_api.db.base import Base
from clara_api.db.models import HealthSourceReference, PhrProfile, User, UserConsent
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    current_state_version,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class GovernedGatewayMachine(RuleBasedStateMachine):
    """Reference-model checks for idempotency and stale-write state transitions."""

    def __init__(self) -> None:
        super().__init__()
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        owner = User(email=f"soict-{uuid4()}@example.test", hashed_password="x", role="normal")
        self.db.add(owner)
        self.db.flush()
        profile = PhrProfile(user_id=owner.id)
        self.db.add(profile)
        self.db.flush()
        self.scope = ProfileScope(
            actor=owner,
            profile=profile,
            actor_role="owner",
            purpose="self_care",
            allowed_actions=frozenset({"create", "correct", "resolve", "view"}),
            allowed_data_classes=frozenset({"medications"}),
        )
        self.expected_version = 0
        self.active: list[tuple[object, str, int, int]] = []
        self.governance_epoch = 0

    def _candidate(self, dose: int):
        now = datetime.now(UTC)
        fingerprint = f"soict:{uuid4()}"
        source = HealthSourceReference(
            profile_id=self.scope.profile.id,
            source_kind="soict-state-machine",
            source_identity=f"soict:{uuid4()}",
            checksum=fingerprint,
            observed_at=now,
        )
        self.db.add(source)
        self.db.flush()
        evidence = record_evidence(
            self.db,
            profile_id=self.scope.profile.id,
            data=EvidenceInput(
                source_reference_id=source.id,
                evidence_kind="soict-state-machine",
                artifact_type="synthetic",
                artifact_public_id=fingerprint,
                fingerprint=fingerprint,
                valid_from=now,
            ),
        )
        return propose_assertion(
            self.db,
            profile_id=self.scope.profile.id,
            actor_user_id=self.scope.actor.id,
            data=AssertionInput(
                semantic_key=f"medication:soict:{uuid4()}",
                assertion_type="medications",
                predicate="dose",
                value={"dose": str(dose)},
                epistemic_state="reported",
                valid_from=now,
            ),
            evidence=((evidence, "supports"),),
        )

    def _candidate_from_snapshot(self, snapshot, *, label: str):
        now = datetime.now(UTC)
        source = HealthSourceReference(
            profile_id=self.scope.profile.id,
            source_kind=label,
            source_identity=f"soict:{uuid4()}",
            checksum=f"soict:{uuid4()}",
            observed_at=now,
        )
        self.db.add(source)
        self.db.flush()
        evidence = record_evidence(
            self.db,
            profile_id=self.scope.profile.id,
            data=EvidenceInput(
                source_reference_id=source.id,
                evidence_kind=label,
                artifact_type="synthetic",
                artifact_public_id=f"soict:{uuid4()}",
                fingerprint=f"soict:{uuid4()}",
                valid_from=now,
            ),
        )
        return propose_assertion(
            self.db,
            profile_id=self.scope.profile.id,
            actor_user_id=self.scope.actor.id,
            data=AssertionInput(
                semantic_key=f"medication:{label}:{uuid4()}",
                assertion_type="medications",
                predicate="dose",
                value={"dose": "1"},
                epistemic_state="reported",
                valid_from=now,
                source_snapshot_id=snapshot.snapshot_id,
                source_snapshot_digest=snapshot.manifest_digest,
                proposal_consumed_thss=True,
            ),
            evidence=((evidence, "supports"),),
        )

    @rule(dose=st.integers(min_value=1, max_value=1000))
    def activate(self, dose: int) -> None:
        assertion = self._candidate(dose)
        key = f"activate:{uuid4()}"
        transition = apply_transition(
            self.db,
            scope=self.scope,
            assertion=assertion,
            action="activate",
            expected_state_version=self.expected_version,
            idempotency_key=key,
            transition_kind="soict-state-machine",
            reason_code="synthetic",
        )
        self.expected_version += 1
        self.active.append((assertion, key, transition.id, self.governance_epoch))

    @rule()
    def exact_retry_is_idempotent(self) -> None:
        if not self.active:
            return
        assertion, key, transition_id, proposal_governance_epoch = self.active[-1]
        try:
            replay = apply_transition(
                self.db,
                scope=self.scope,
                assertion=assertion,
                action="activate",
                expected_state_version=self.expected_version - 1,
                idempotency_key=key,
                transition_kind="soict-state-machine",
                reason_code="synthetic",
            )
        except GlhsInvariantError as exc:
            # A changed consent prevents reuse of prior governed authority.
            # It must still not create a duplicate transition.
            assert self.governance_epoch > proposal_governance_epoch
            assert str(exc) == "assertion_consent_mismatch"
            assert current_state_version(self.db, profile_id=self.scope.profile.id) == self.expected_version
        else:
            assert self.governance_epoch == proposal_governance_epoch
            assert replay.id == transition_id

    @rule()
    def stale_write_is_rejected(self) -> None:
        if not self.active or self.expected_version < 1:
            return
        assertion, _, _, proposal_governance_epoch = self.active[-1]
        try:
            apply_transition(
                self.db,
                scope=self.scope,
                assertion=assertion,
                action="resolve",
                expected_state_version=self.expected_version - 1,
                idempotency_key=f"stale:{uuid4()}",
                transition_kind="soict-state-machine",
                reason_code="synthetic",
            )
        except GlhsInvariantError as exc:
            expected = (
                "assertion_consent_mismatch"
                if self.governance_epoch > proposal_governance_epoch
                else "stale_state_version"
            )
            assert str(exc) == expected
        else:  # pragma: no cover - state-machine oracle failure
            raise AssertionError("stale write unexpectedly committed")

    @rule()
    def policy_changed_snapshot_cannot_seed_a_proposal(self) -> None:
        """Model a disclosure followed by a policy mutation before proposal."""

        snapshot = compile_thss(
            self.db,
            scope=self.scope,
            task="soict-state-machine",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
        )
        original_policy = gateway_module.POLICY_VERSION
        gateway_module.POLICY_VERSION = f"{original_policy}-changed"
        try:
            try:
                self._candidate_from_snapshot(snapshot, label="soict-policy-change")
            except GlhsInvariantError as exc:
                assert str(exc) == "proposal_snapshot_policy_mismatch"
            else:  # pragma: no cover - state-machine oracle failure
                raise AssertionError("policy-invalid snapshot unexpectedly admitted")
        finally:
            gateway_module.POLICY_VERSION = original_policy

    @rule()
    def consent_changed_snapshot_cannot_seed_a_proposal(self) -> None:
        """Model disclosure followed by a newly accepted governing consent."""

        snapshot = compile_thss(
            self.db,
            scope=self.scope,
            task="soict-state-machine",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
        )
        self.db.add(
            UserConsent(
                user_id=self.scope.profile.user_id,
                consent_type="medical_disclaimer",
                consent_version=f"soict-consent-{uuid4()}",
            )
        )
        self.db.flush()
        self.governance_epoch += 1
        try:
            self._candidate_from_snapshot(snapshot, label="soict-consent-change")
        except GlhsInvariantError as exc:
            assert str(exc) == "proposal_snapshot_consent_mismatch"
        else:  # pragma: no cover - state-machine oracle failure
            raise AssertionError("consent-invalid snapshot unexpectedly admitted")

    @invariant()
    def version_matches_reference_model(self) -> None:
        assert current_state_version(self.db, profile_id=self.scope.profile.id) == self.expected_version

    def teardown(self) -> None:
        self.db.close()
        self.engine.dispose()


TestGovernedGatewayMachine = GovernedGatewayMachine.TestCase
TestGovernedGatewayMachine.settings = settings(max_examples=10, stateful_step_count=12, deadline=None)
