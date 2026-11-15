"""Tests for SH-psc_interface — Policy-Scoped Commit advisory witness interface.

Positive controls: a valid scope with a fresh consent/policy epoch and a fully
resolved dependency closure yields ``COMMIT``; an unresolved dependency yields
the first-class ``INDETERMINATE`` (never a silent safe rejection). Adversarial
controls: missing/malformed scope fields, stale consent epoch, policy version
downgrade and dispatch/claimed scope confusion are all rejected with stable
reason codes. All decisions are deterministic (same input twice => identical
decision) and JSON-serializable round-trip.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.venue2027._shared.psc import (  # noqa: E402
    ENFORCEMENT_ADVISORY,
    OUTCOME_COMMIT,
    OUTCOME_INDETERMINATE,
    OUTCOME_REJECT,
    PSC_INTERFACE_VERSION,
    DependencyOracleError,
    DependencyRef,
    DependencyResolution,
    FrozenDependencyOracle,
    FrozenEpochSource,
    GovernanceEpochError,
    GovernanceEpochs,
    PolicyScope,
    PscContractError,
    PscDecision,
    PscRequest,
    evaluate_psc,
)

TENANT = "tenant_hospital_a"  # noqa: E402
PRINCIPAL = "dr_ash"
PURPOSE = "med_review"
CONSENT_EPOCH = "consent-2026-11-14"
POLICY_VERSION = "1.2.0"
LIVE_EPOCHS = GovernanceEpochs(consent_epoch=CONSENT_EPOCH, policy_version=POLICY_VERSION)
ALLERGY_KEY = "med/allergy-list"
ALLERGY_DIGEST = "a" * 64
MED_KEY = "med/active-list"
MED_DIGEST = "b" * 64
STALE_DIGEST = "c" * 64


def _scope(**overrides: str) -> PolicyScope:
    values = dict(
        tenant=TENANT,
        principal=PRINCIPAL,
        purpose=PURPOSE,
        consent_epoch=CONSENT_EPOCH,
        policy_version=POLICY_VERSION,
    )
    values.update(overrides)
    return PolicyScope(**values)


def _deps(*pairs: tuple[str, str, str]) -> tuple[DependencyRef, ...]:
    return tuple(
        DependencyRef(key=key, version=version, digest=digest) for key, version, digest in pairs
    )


def _request(
    scope: PolicyScope | None = None,
    dispatch: PolicyScope | None = None,
    deps: tuple[DependencyRef, ...] | None = None,
    request_id: str = "req-0001",
) -> PscRequest:
    return PscRequest(
        request_id=request_id,
        scope=scope if scope is not None else _scope(),
        dispatch_scope=dispatch
        if dispatch is not None
        else scope
        if scope is not None
        else _scope(),
        operation_kind="med_state_write",
        required_dependencies=deps
        if deps is not None
        else _deps((ALLERGY_KEY, "v7", ALLERGY_DIGEST)),
    )


def _oracle(**overrides: str) -> FrozenDependencyOracle:
    table = {
        ALLERGY_KEY: (
            overrides.pop("allergy_version", "v7"),
            overrides.pop("allergy_digest", ALLERGY_DIGEST),
        ),
        MED_KEY: (overrides.pop("med_version", "v3"), overrides.pop("med_digest", MED_DIGEST)),
    }
    assert not overrides, f"unknown oracle overrides: {sorted(overrides)}"
    return FrozenDependencyOracle(oracle_id="frozen_oracle.v1", table=table)


def _epochs(
    tenant: str = TENANT, principal: str = PRINCIPAL, **overrides: str
) -> FrozenEpochSource:
    epochs = GovernanceEpochs(
        consent_epoch=overrides.pop("consent_epoch", CONSENT_EPOCH),
        policy_version=overrides.pop("policy_version", POLICY_VERSION),
    )
    assert not overrides, f"unknown epoch overrides: {sorted(overrides)}"
    return FrozenEpochSource(
        source_id="frozen_epochs.v1", epochs_by_principal={(tenant, principal): epochs}
    )


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_valid_scope_commits_with_full_dependency_closure() -> None:
    decision = evaluate_psc(
        _request(deps=_deps((ALLERGY_KEY, "v7", ALLERGY_DIGEST), (MED_KEY, "v3", MED_DIGEST))),
        dependency_oracle=_oracle(),
        epoch_source=_epochs(),
    )
    assert decision.outcome == OUTCOME_COMMIT
    assert decision.reason_code == "ADVISORY_COMMIT_ELIGIBLE"
    assert decision.verified_dependency_keys == (ALLERGY_KEY, MED_KEY)
    assert decision.enforcement == ENFORCEMENT_ADVISORY
    assert decision.contract_version == PSC_INTERFACE_VERSION
    assert decision.scope == _scope()
    assert decision.is_commit is True


def test_decision_deterministic_and_json_round_trip() -> None:
    request = _request()
    first = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    second = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert first == second
    assert first.to_dict() == second.to_dict()
    revived = PscDecision.from_dict(json.loads(json.dumps(first.to_dict())))
    assert revived == first


def test_unresolved_dependency_is_first_class_indeterminate() -> None:
    request = _request(
        deps=_deps((ALLERGY_KEY, "v7", ALLERGY_DIGEST), ("med/unknown-row", "v1", MED_DIGEST))
    )
    decision = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_INDETERMINATE
    assert decision.reason_code == "DEPENDENCY_UNRESOLVED"
    assert decision.verified_dependency_keys == (ALLERGY_KEY,)
    assert "never as safe rejections" in decision.detail


def test_unresolved_dependency_is_never_counted_as_reject_or_commit() -> None:
    decision = evaluate_psc(
        _request(deps=_deps(("ghost/key", "v1", MED_DIGEST))),
        dependency_oracle=_oracle(),
        epoch_source=_epochs(),
    )
    assert decision.outcome not in (OUTCOME_REJECT, OUTCOME_COMMIT)
    assert decision.outcome == OUTCOME_INDETERMINATE


def test_request_dict_coercion_matches_typed_request() -> None:
    typed = _request(deps=_deps((ALLERGY_KEY, "v7", ALLERGY_DIGEST)))
    as_dict = json.loads(json.dumps(typed.to_dict()))
    from_dict = PscRequest.from_dict(as_dict)
    assert from_dict == typed
    decision_dict = evaluate_psc(as_dict, dependency_oracle=_oracle(), epoch_source=_epochs())
    decision_typed = evaluate_psc(typed, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision_dict == decision_typed
    assert decision_dict.request_sha256 == typed.canonical_sha256


def test_frozen_oracle_unmutatable_copy_of_table() -> None:
    table: dict[str, tuple[str, str]] = {ALLERGY_KEY: ("v7", ALLERGY_DIGEST)}
    oracle = FrozenDependencyOracle(oracle_id="o", table=table)
    table[ALLERGY_KEY] = ("v9", STALE_DIGEST)
    resolution = oracle.resolve(ALLERGY_KEY)
    assert (resolution.version, resolution.digest) == ("v7", ALLERGY_DIGEST)
    missing = oracle.resolve("ghost/key")
    assert missing.status == "UNRESOLVED"
    assert missing.reason_code == "UNKNOWN_KEY"


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_missing_tenant_rejected() -> None:
    with pytest.raises(PscContractError) as excinfo:
        _scope(tenant="")
    assert excinfo.value.reason_code == "SCOPE_MALFORMED"
    raw = json.loads(json.dumps(_request().to_dict()))
    del raw["scope"]["tenant"]
    decision = evaluate_psc(raw, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "SCOPE_MISSING_FIELD"


def test_missing_purpose_rejected() -> None:
    with pytest.raises(PscContractError) as excinfo:
        _scope(purpose="")
    assert excinfo.value.reason_code == "SCOPE_MALFORMED"
    raw = json.loads(json.dumps(_request().to_dict()))
    del raw["scope"]["purpose"]
    decision = evaluate_psc(raw, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "SCOPE_MISSING_FIELD"
    blank = json.loads(json.dumps(_request().to_dict()))
    blank["scope"]["purpose"] = ""
    blank_decision = evaluate_psc(blank, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert blank_decision.outcome == OUTCOME_REJECT
    assert blank_decision.reason_code == "SCOPE_MALFORMED"


def test_unknown_scope_field_rejected() -> None:
    raw = json.loads(json.dumps(_request().to_dict()))
    raw["scope"]["role"] = "admin"
    decision = evaluate_psc(raw, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "SCOPE_UNKNOWN_FIELD"


def test_empty_required_closure_rejected() -> None:
    with pytest.raises(PscContractError) as excinfo:
        _request(deps=())
    assert excinfo.value.reason_code == "DEPENDENCY_CLOSURE_EMPTY"


def test_stale_consent_epoch_rejected() -> None:
    request = _request(scope=_scope(consent_epoch="consent-2026-11-01"))
    decision = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "EPOCH_CONSENT_STALE"
    assert decision.verified_dependency_keys == ()


def test_policy_version_downgrade_rejected() -> None:
    request = _request(scope=_scope(policy_version="1.1.9"))
    decision = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "EPOCH_POLICY_DOWNGRADE"


def test_policy_version_divergent_relation_rejected() -> None:
    request = _request(scope=_scope(policy_version="2.0.0"))
    decision = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "EPOCH_POLICY_DIVERGENT"


def test_scope_confusion_cross_purpose_rejected() -> None:
    claimed = _scope()
    dispatch = _scope(purpose="claim_adjudication")
    decision = evaluate_psc(
        _request(scope=claimed, dispatch=dispatch),
        dependency_oracle=_oracle(),
        epoch_source=_epochs(),
    )
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "SCOPE_CONFUSION"
    assert "purpose" in decision.detail


def test_scope_confusion_cross_tenant_and_principal_rejected() -> None:
    for dispatch in (_scope(tenant="tenant_hospital_b"), _scope(principal="dr_other")):
        decision = evaluate_psc(
            _request(dispatch=dispatch),
            dependency_oracle=_oracle(),
            epoch_source=_epochs(),
        )
        assert decision.outcome == OUTCOME_REJECT
        assert decision.reason_code == "SCOPE_CONFUSION"


def test_stale_dependency_digest_rejected() -> None:
    request = _request(deps=_deps((ALLERGY_KEY, "v7", STALE_DIGEST)))
    decision = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "DEPENDENCY_STALE"


def test_stale_dependency_version_rejected() -> None:
    request = _request(deps=_deps((ALLERGY_KEY, "v6", ALLERGY_DIGEST)))
    decision = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "DEPENDENCY_STALE"


def test_unknown_principal_is_indeterminate_not_reject() -> None:
    request = _request(scope=_scope(principal="dr_unknown"))
    decision = evaluate_psc(request, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_INDETERMINATE
    assert decision.reason_code == "EPOCH_SOURCE_UNKNOWN_PRINCIPAL"


def test_epoch_source_crash_is_indeterminate_with_sanitized_detail() -> None:
    class ExplodingSource:
        source_id = "boom"

        def current_epochs(self, tenant: str, principal: str) -> GovernanceEpochs:
            raise RuntimeError("patient record leak should not propagate")

    decision = evaluate_psc(_request(), dependency_oracle=_oracle(), epoch_source=ExplodingSource())
    assert decision.outcome == OUTCOME_INDETERMINATE
    assert decision.reason_code == "EPOCH_SOURCE_ERROR"
    assert decision.detail == "epoch source raised: RuntimeError"
    assert "patient" not in decision.detail


def test_dependency_oracle_crash_is_indeterminate() -> None:
    class ExplodingOracle:
        oracle_id = "boom"

        def resolve(self, key: str) -> DependencyResolution:
            raise RuntimeError("internal oracle state")

    decision = evaluate_psc(_request(), dependency_oracle=ExplodingOracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_INDETERMINATE
    assert decision.reason_code == "DEPENDENCY_ORACLE_ERROR"
    assert "RuntimeError" in decision.detail
    assert "internal oracle state" not in decision.detail


def test_non_callable_wiring_raises_with_stable_codes() -> None:
    class NoResolve:
        oracle_id = "bad"

    class NoCurrent:
        source_id = "bad"

    with pytest.raises(PscContractError) as excinfo:
        evaluate_psc(_request(), dependency_oracle=NoResolve(), epoch_source=_epochs())
    assert excinfo.value.reason_code == "DEPENDENCY_ORACLE_NOT_CALLABLE"
    with pytest.raises(PscContractError) as excinfo:
        evaluate_psc(_request(), dependency_oracle=_oracle(), epoch_source=NoCurrent())
    assert excinfo.value.reason_code == "EPOCH_SOURCE_NOT_CALLABLE"


def test_decision_enforcement_field_cannot_claim_enforcing() -> None:
    with pytest.raises(PscContractError) as excinfo:
        dataclasses_replace_enforcement = json.loads(json.dumps(_request().to_dict()))
        assert dataclasses_replace_enforcement  # keep the test hermetic
        decision = evaluate_psc(_request(), dependency_oracle=_oracle(), epoch_source=_epochs())
        forged = decision.to_dict()
        forged["enforcement"] = "ENFORCING"
        PscDecision.from_dict(forged)
    assert excinfo.value.reason_code == "DECISION_MALFORMED"


def test_indeterminate_outcome_cannot_carry_duplicated_keys() -> None:
    with pytest.raises(PscContractError) as excinfo:
        PscDecision(
            request_id="req-0002",
            outcome=OUTCOME_INDETERMINATE,
            reason_code="DEPENDENCY_UNRESOLVED",
            scope=_scope(),
            request_sha256="d" * 64,
            verified_dependency_keys=(ALLERGY_KEY, ALLERGY_KEY),
        )
    assert excinfo.value.reason_code == "DECISION_MALFORMED"


def test_commit_outcome_cannot_carry_empty_or_duplicate_keys() -> None:
    for keys in ((), (ALLERGY_KEY, ALLERGY_KEY)):
        with pytest.raises(PscContractError) as excinfo:
            PscDecision(
                request_id="req-0003",
                outcome=OUTCOME_COMMIT,
                reason_code="ADVISORY_COMMIT_ELIGIBLE",
                scope=_scope(),
                request_sha256="d" * 64,
                verified_dependency_keys=keys,
            )
        assert excinfo.value.reason_code == "DECISION_MALFORMED"


def test_governance_epoch_source_malformed_policy_version() -> None:
    with pytest.raises(GovernanceEpochError) as excinfo:
        GovernanceEpochs(consent_epoch=CONSENT_EPOCH, policy_version="one.two")
    assert excinfo.value.reason_code == "EPOCH_SOURCE_MALFORMED"
    with pytest.raises(DependencyOracleError) as excinfo:
        DependencyResolution(key=ALLERGY_KEY, status="RESOLVED", version="v7", digest="nothex")
    assert excinfo.value.reason_code == "DEPENDENCY_BAD_RESOLUTION"


def test_injection_via_dependency_dict_cannot_bypass_closure() -> None:
    raw = json.loads(
        json.dumps(_request(deps=_deps((ALLERGY_KEY, "v7", ALLERGY_DIGEST))).to_dict())
    )
    raw["required_dependencies"] = []
    decision = evaluate_psc(raw, dependency_oracle=_oracle(), epoch_source=_epochs())
    assert decision.outcome == OUTCOME_REJECT
    assert decision.reason_code == "DEPENDENCY_CLOSURE_EMPTY"
