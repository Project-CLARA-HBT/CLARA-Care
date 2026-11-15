"""Tests for SACMAT-baselines — baseline fidelity adapters.

Positive controls (each arm runs end to end on synthetic delegated-consent
cases):
- Registry covers all four task-contract arms (B0-B3) with provenance.
- All three in-process engine models (XACML-like, Cedar-like, Zanzibar-like)
  evaluate real delegated-consent requests: a valid grant PERMITs under all
  three, a revoked grant DENYs (XACML/Cedar compiled deny rules) and the
  Zanzibar relation walk drops the deleted tuple.
- B3 candidate temporal conformance detects BOTH temporal fault classes:
  delegation expiry (oracle DENYs a lapsed grant whose final state still
  permits) and policy-version skew (a POLICY_VERSION_BUMP at/after the
  request's decision time). Clean histories (valid grant, grant→revoke→
  regrant with the regrant in force) ADMIT under every arm.
- Core P03 separation: a history-healed version-skew unit (grant→revoke→
  regrant in force, bump after decision time) where every engine agrees
  pointwise is DETECTED by B3 and MISSED by B0, B1 AND B2 — asserted
  explicitly. A pure expiry race where all three engines agree pointwise on
  a permit (XACML/Cedar compiled final state) is likewise B3-only.
- Determinism: identical inputs give byte-identical outcomes.

Adversarial controls:
- A single-engine arm (B1) MISSES the temporal divergence B3 catches — the
  engine-native suite validates engine-internal semantics only (claim C8).
- Unavailable upstream binaries -> NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE
  for the encoding-replay arms (never a toy substitution, never silently
  dropped from the denominator).
- Constant stubs refused: detect-all, detect-none and constant-output
  candidates raise STUB_DETECT_ALL_REFUSED / STUB_DETECT_NONE_REFUSED /
  CONSTANT_STUB_REFUSED via refuse_constant_stub (EXECUTION_CONTRACT rule 8).
- Malformed inputs (missing/empty/non-list history, unknown event kinds,
  bad types, non-monotonic logical times, missing request fields) yield
  first-class INDETERMINATE outcomes with stable reason codes — never
  silently counted as safe rejections.
- Unknown baseline id, non-mapping case and malformed context fail closed
  with stable reason codes (wiring errors).

Failure semantics: every adversarial result is a first-class Outcome, never
an unhandled exception miscounted as a safe rejection (wiring errors are
the documented exception and raise).
"""

from __future__ import annotations

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B3,
    BASELINE_REGISTRY,
    BASELINES_VERSION,
    ENGINE_CEDAR,
    ENGINE_MODELS,
    ENGINE_XACML,
    EVENT_GRANT,
    EVENT_POLICY_VERSION_BUMP,
    EVENT_REGRANT,
    EVENT_REVOKE,
    PURPOSE_CARE_TEAM,
    PURPOSE_RESEARCH,
    PURPOSE_SELF_CARE,
    RC_B3_DELEGATION_EXPIRED,
    RC_B3_VERSION_SKEW,
    RC_BASELINE_UNAVAILABLE,
    RC_EVENT_KIND_UNKNOWN,
    RC_EVENT_TIME_NOT_MONOTONIC,
    RC_HISTORY_EVENT_EMPTY,
    RC_HISTORY_MISSING,
    RC_HISTORY_NOT_A_LIST,
    RC_NO_DIVERGENCE,
    RC_REQUEST_MISSING_FIELD,
    RC_STUB_CONSTANT,
    RC_STUB_DETECT_ALL,
    RC_STUB_DETECT_NONE,
    RC_STUB_SEPARATION_OK,
    CedarPolicyEngine,
    SacmatBaselineError,
    SacmatContext,
    XacmlPolicyEngine,
    ZanzibarPolicyEngine,
    clean_probe_cases,
    conformance_probe_cases,
    evaluate_engine,
    event,
    oracle_decision,
    refuse_constant_stub,
    request,
    run_baseline,
)


def _ctx(**overrides: object) -> SacmatContext:
    return SacmatContext(**overrides)  # type: ignore[arg-type]


def _expired_grant_case(case_id: str = "SACMAT-T-EXPIRY") -> dict[str, object]:
    """Grant lapsed before the request; final state still shows a permit."""
    return {
        "case_id": case_id,
        "history": [
            event(EVENT_GRANT, 100, "patient-a", "patient-a", PURPOSE_SELF_CARE, expiry=1000),
        ],
        "request": request("patient-a", PURPOSE_SELF_CARE, 1500),
    }


def _pure_skew_case(case_id: str = "SACMAT-T-SKEW") -> dict[str, object]:
    """History-healed delegation (regrant in force) + version bump AFTER the
    request's decision time: all engines agree pointwise, B3 alone detects."""
    return {
        "case_id": case_id,
        "history": [
            event(EVENT_GRANT, 100, "patient-g", "patient-g", PURPOSE_SELF_CARE, expiry=9000),
            event(EVENT_REVOKE, 1500, "patient-g", "patient-g", PURPOSE_SELF_CARE),
            event(EVENT_REGRANT, 1600, "patient-g", "patient-g", PURPOSE_SELF_CARE, expiry=9000),
            event(EVENT_POLICY_VERSION_BUMP, 2500, "system", "system", "*"),
        ],
        "request": request("patient-g", PURPOSE_SELF_CARE, 1700),
    }


def _valid_grant_case(case_id: str = "SACMAT-T-VALID") -> dict[str, object]:
    return {
        "case_id": case_id,
        "history": [
            event(EVENT_GRANT, 100, "patient-c", "patient-c", PURPOSE_SELF_CARE, expiry=9000),
        ],
        "request": request("patient-c", PURPOSE_SELF_CARE, 500),
    }


# ---------------------------------------------------------------------------
# Positive controls — each arm runs end to end.
# ---------------------------------------------------------------------------


class TestPositiveControls:
    def test_registry_covers_task_contract_arms(self) -> None:
        assert set(BASELINE_REGISTRY) >= {BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3}
        for spec in BASELINE_REGISTRY.values():
            assert spec.registry_name and spec.title and spec.upstream_url
        assert BASELINE_REGISTRY[BASELINE_B0].registry_name == "B5-static-policy-diff"
        assert BASELINE_REGISTRY[BASELINE_B1].registry_name == "B6-single-engine-testing"

    def test_engine_models_evaluate_real_delegated_consent(self) -> None:
        valid = _validated_history(_valid_grant_case())
        for engine_id in ENGINE_MODELS:
            assert evaluate_engine(engine_id, valid, valid.request) == "PERMIT"  # type: ignore[attr-defined]

    def test_xacml_engine_deny_overrides_on_revoked_grant(self) -> None:
        history = _validated_history(
            {
                "case_id": "SACMAT-T-XACML-DENY",
                "history": [
                    event(
                        EVENT_GRANT, 100, "patient-r", "patient-r", PURPOSE_CARE_TEAM, expiry=9000
                    ),
                    event(EVENT_REVOKE, 2000, "patient-r", "patient-r", PURPOSE_CARE_TEAM),
                ],
                "request": request("patient-r", PURPOSE_CARE_TEAM, 3000),
            }
        )
        assert XacmlPolicyEngine().evaluate(history, history.request) == "DENY"

    def test_cedar_engine_forbid_precedence_on_revoked_grant(self) -> None:
        history = _validated_history(
            {
                "case_id": "SACMAT-T-CEDAR-DENY",
                "history": [
                    event(
                        EVENT_GRANT, 100, "patient-r", "patient-r", PURPOSE_CARE_TEAM, expiry=9000
                    ),
                    event(EVENT_REVOKE, 2000, "patient-r", "patient-r", PURPOSE_CARE_TEAM),
                ],
                "request": request("patient-r", PURPOSE_CARE_TEAM, 3000),
            }
        )
        assert CedarPolicyEngine().evaluate(history, history.request) == "DENY"

    def test_zanzibar_relation_walk_drops_revoked_tuple(self) -> None:
        history = _validated_history(
            {
                "case_id": "SACMAT-T-ZANZIBAR",
                "history": [
                    event(
                        EVENT_GRANT, 100, "patient-r", "patient-r", PURPOSE_CARE_TEAM, expiry=9000
                    ),
                    event(EVENT_REVOKE, 2000, "patient-r", "patient-r", PURPOSE_CARE_TEAM),
                ],
                "request": request("patient-r", PURPOSE_CARE_TEAM, 3000),
            }
        )
        # Tuple deleted by the revoke: relation walk finds no active grant.
        assert ZanzibarPolicyEngine().evaluate(history, history.request) == "NOT_APPLICABLE"
        # Zanzibar evaluates at read time: before the revoke the tuple exists.
        early = history.request.__class__("patient-r", PURPOSE_CARE_TEAM, 1500)
        assert ZanzibarPolicyEngine().evaluate(history, early) == "PERMIT"

    def test_oracle_is_history_sensitive_and_four_valued(self) -> None:
        # Expiry race: oracle DENYs (explicit temporal invalidation).
        assert oracle_decision(_validated_history(_expired_grant_case())) == "DENY"
        # Valid grant: PERMIT.
        assert oracle_decision(_validated_history(_valid_grant_case())) == "PERMIT"
        # No delegation relationship at all: NOT_APPLICABLE.
        unrelated = {
            "case_id": "SACMAT-T-UNRELATED",
            "history": [
                event(EVENT_GRANT, 100, "patient-x", "patient-x", PURPOSE_RESEARCH, expiry=9000),
            ],
            "request": request("patient-y", PURPOSE_SELF_CARE, 500),
        }
        assert oracle_decision(_validated_history(unrelated)) == "NOT_APPLICABLE"

    def test_b3_detects_delegation_expiry_divergence(self) -> None:
        outcome = run_baseline(BASELINE_B3, _expired_grant_case(), _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is True
        assert RC_B3_DELEGATION_EXPIRED in outcome.detail

    def test_b3_detects_policy_version_skew(self) -> None:
        outcome = run_baseline(BASELINE_B3, _pure_skew_case(), _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert RC_B3_VERSION_SKEW in outcome.detail

    def test_clean_histories_admit_under_every_arm(self) -> None:
        for case in clean_probe_cases():
            for baseline_id in (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3):
                outcome = run_baseline(baseline_id, case, _ctx())
                assert outcome.observed_outcome == "ADMIT", (baseline_id, case["case_id"])
                assert outcome.counted_as_success is True
                assert RC_NO_DIVERGENCE in outcome.detail


# ---------------------------------------------------------------------------
# Core P03 separation: B3 detects what B0/B1/B2 all miss.
# ---------------------------------------------------------------------------


class TestTemporalSeparation:
    def test_b3_detects_history_healed_skew_that_b0_b1_b2_miss(self) -> None:
        """Every engine agrees pointwise; only ordered-history replay sees it."""
        case = _pure_skew_case()
        assert run_baseline(BASELINE_B0, case, _ctx()).observed_outcome == "ADMIT"
        assert run_baseline(BASELINE_B1, case, _ctx()).observed_outcome == "ADMIT"
        assert run_baseline(BASELINE_B2, case, _ctx()).observed_outcome == "ADMIT"
        outcome = run_baseline(BASELINE_B3, case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert RC_B3_VERSION_SKEW in outcome.detail

    def test_b3_detects_expiry_race_that_b0_b1_miss(self) -> None:
        """The compiled final-state engines (XACML/Cedar) both PERMIT the
        lapsed grant pointwise — the expiry race is invisible to any
        final-state structural or single-engine view (B0/B1 admit). The
        read-time Zanzibar walk drops the tuple, so B2 sees cross-engine
        disagreement; B3 detects it via the oracle's temporal DENY."""
        case = {
            "case_id": "SACMAT-T-EXPIRY-AGREE",
            "history": [
                event(EVENT_GRANT, 100, "patient-f", "patient-f", PURPOSE_CARE_TEAM, expiry=1000),
            ],
            "request": request("patient-f", PURPOSE_CARE_TEAM, 1500),
        }
        history = _validated_history(case)
        # Compiled final-state engines agree pointwise on PERMIT.
        assert evaluate_engine(ENGINE_XACML, history, history.request) == "PERMIT"
        assert evaluate_engine(ENGINE_CEDAR, history, history.request) == "PERMIT"
        assert run_baseline(BASELINE_B0, case, _ctx()).observed_outcome == "ADMIT"
        assert run_baseline(BASELINE_B1, case, _ctx()).observed_outcome == "ADMIT"
        outcome = run_baseline(BASELINE_B3, case, _ctx())
        assert outcome.observed_outcome == "REJECT"
        assert RC_B3_DELEGATION_EXPIRED in outcome.detail

    def test_b1_single_engine_misses_temporal_divergence_b3_catches(self) -> None:
        """Adversarial-in-positive-form (claim C8): the engine-native suite
        is green while the cross-engine temporal fault is present."""
        case = _pure_skew_case()
        b1 = run_baseline(BASELINE_B1, case, _ctx())
        b3 = run_baseline(BASELINE_B3, case, _ctx())
        assert b1.observed_outcome == "ADMIT"
        assert b3.observed_outcome == "REJECT"
        # The miss is the scientifically recorded result, not a stub: B1
        # really evaluated all three engines' pointwise decisions.
        assert "decisions=" in b1.detail

    def test_b0_static_diff_misses_temporal_divergence(self) -> None:
        """Static structural diff cannot see semantics: identical compiled
        structures, divergent ordered histories."""
        case = _pure_skew_case()
        outcome = run_baseline(BASELINE_B0, case, _ctx())
        assert outcome.observed_outcome == "ADMIT"

    def test_conformance_probes_are_oracle_divergent_and_arm_separated(self) -> None:
        for probe in conformance_probe_cases():
            history = _validated_history(probe)
            assert oracle_decision(history) == "DENY"
            assert run_baseline(BASELINE_B3, probe, _ctx()).observed_outcome == "REJECT"


# ---------------------------------------------------------------------------
# Adversarial controls — external availability, stubs, malformed inputs.
# ---------------------------------------------------------------------------


class TestExternalAvailability:
    def test_unavailable_upstream_is_not_run_external(self) -> None:
        ctx = _ctx(simulate_unavailable_upstream=True)
        for baseline_id in (BASELINE_B1, BASELINE_B2, BASELINE_B3):
            outcome = run_baseline(baseline_id, conformance_probe_cases()[0], ctx)
            assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
            assert outcome.counted_as_success is False
            assert outcome.retriable is True
            assert RC_BASELINE_UNAVAILABLE in outcome.detail

    def test_not_run_external_never_counts_as_success(self) -> None:
        ctx = _ctx(simulate_unavailable_upstream=True)
        outcome = run_baseline(BASELINE_B3, _pure_skew_case(), ctx)
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False
        # Outcome post-init would have raised on a false-zero violation.
        assert outcome.to_dict()["observed_outcome"] == "NOT_RUN_EXTERNAL"

    def test_b0_runs_even_without_external_upstreams(self) -> None:
        """B0 is a pure in-process structural diff: no engine replay needed."""
        ctx = _ctx(simulate_unavailable_upstream=True)
        outcome = run_baseline(BASELINE_B0, _valid_grant_case(), ctx)
        assert outcome.observed_outcome == "ADMIT"


class TestConstantStubRefusal:
    def test_b3_candidate_separates_probes(self) -> None:
        outcome = refuse_constant_stub(lambda case: run_baseline(BASELINE_B3, case, _ctx()))
        assert outcome.observed_outcome == "ADMIT"
        assert RC_STUB_SEPARATION_OK in outcome.detail

    def test_detect_all_stub_refused(self) -> None:
        def detect_all(case: object) -> Outcome:
            return Outcome(
                observed_outcome="REJECT",
                counted_as_success=True,
                detail=f"stub|{getattr(case, 'get', lambda *_: '')('case_id')}",
            )

        with pytest.raises(SacmatBaselineError) as excinfo:
            refuse_constant_stub(detect_all)
        assert excinfo.value.reason_code == RC_STUB_DETECT_ALL

    def test_detect_none_stub_refused(self) -> None:
        def detect_none(case: object) -> Outcome:
            return Outcome(
                observed_outcome="ADMIT",
                counted_as_success=True,
                detail=f"stub|{getattr(case, 'get', lambda *_: '')('case_id')}",
            )

        with pytest.raises(SacmatBaselineError) as excinfo:
            refuse_constant_stub(detect_none)
        assert excinfo.value.reason_code == RC_STUB_DETECT_NONE

    def test_constant_output_stub_refused(self) -> None:
        with pytest.raises(SacmatBaselineError) as excinfo:
            refuse_constant_stub(
                lambda _case: Outcome(observed_outcome="ADMIT", counted_as_success=True)
            )
        assert excinfo.value.reason_code == RC_STUB_CONSTANT

    def test_constant_bool_stub_refused(self) -> None:
        with pytest.raises(SacmatBaselineError) as excinfo:
            refuse_constant_stub(lambda _case: True)
        assert excinfo.value.reason_code == RC_STUB_CONSTANT

    def test_empty_probe_sets_refused(self) -> None:
        with pytest.raises(SacmatBaselineError) as excinfo:
            refuse_constant_stub(lambda _case: True, conformance_probes=[])
        assert excinfo.value.reason_code == "CONTEXT_MALFORMED"


class TestMalformedInputs:
    def test_missing_history_is_indeterminate(self) -> None:
        outcome = run_baseline(BASELINE_B3, {"case_id": "SACMAT-T-M1"}, _ctx())
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.counted_as_success is False
        assert RC_HISTORY_MISSING in outcome.detail

    def test_empty_history_is_indeterminate(self) -> None:
        case = {
            "case_id": "SACMAT-T-M2",
            "history": [],
            "request": request("a", PURPOSE_SELF_CARE, 0),
        }
        outcome = run_baseline(BASELINE_B3, case, _ctx())
        assert outcome.observed_outcome == "INDETERMINATE"
        assert RC_HISTORY_EVENT_EMPTY in outcome.detail

    def test_non_list_history_is_indeterminate(self) -> None:
        case = {
            "case_id": "SACMAT-T-M3",
            "history": "grant(a)",
            "request": request("a", PURPOSE_SELF_CARE, 0),
        }
        outcome = run_baseline(BASELINE_B2, case, _ctx())
        assert outcome.observed_outcome == "INDETERMINATE"
        assert RC_HISTORY_NOT_A_LIST in outcome.detail

    def test_unknown_event_kind_is_indeterminate(self) -> None:
        case = {
            "case_id": "SACMAT-T-M4",
            "history": [{"event_kind": "TIME_TRAVEL", "logical_time": 0}],
            "request": request("a", PURPOSE_SELF_CARE, 0),
        }
        outcome = run_baseline(BASELINE_B3, case, _ctx())
        assert outcome.observed_outcome == "INDETERMINATE"
        assert RC_EVENT_KIND_UNKNOWN in outcome.detail

    def test_non_monotonic_history_is_indeterminate(self) -> None:
        case = {
            "case_id": "SACMAT-T-M5",
            "history": [
                event(EVENT_GRANT, 500, "a", "a", PURPOSE_SELF_CARE, expiry=9000),
                event(EVENT_REVOKE, 400, "a", "a", PURPOSE_SELF_CARE),
            ],
            "request": request("a", PURPOSE_SELF_CARE, 600),
        }
        outcome = run_baseline(BASELINE_B3, case, _ctx())
        assert outcome.observed_outcome == "INDETERMINATE"
        assert RC_EVENT_TIME_NOT_MONOTONIC in outcome.detail

    def test_missing_request_field_is_indeterminate(self) -> None:
        case = {
            "case_id": "SACMAT-T-M6",
            "history": [
                event(EVENT_GRANT, 100, "a", "a", PURPOSE_SELF_CARE, expiry=9000),
            ],
            "request": {"actor_id": "a", "purpose": PURPOSE_SELF_CARE},
        }
        outcome = run_baseline(BASELINE_B3, case, _ctx())
        assert outcome.observed_outcome == "INDETERMINATE"
        assert RC_REQUEST_MISSING_FIELD in outcome.detail

    def test_missing_case_id_is_indeterminate(self) -> None:
        outcome = run_baseline(
            BASELINE_B3,
            {
                "history": [event(EVENT_GRANT, 0, "a", "a", PURPOSE_SELF_CARE, expiry=9)],
                "request": request("a", PURPOSE_SELF_CARE, 1),
            },
            _ctx(),
        )
        assert outcome.observed_outcome == "INDETERMINATE"


class TestWiringErrors:
    def test_unknown_baseline_id_fails_closed(self) -> None:
        with pytest.raises(SacmatBaselineError) as excinfo:
            run_baseline("B9", _valid_grant_case(), _ctx())
        assert excinfo.value.reason_code == "BASELINE_UNKNOWN_ID"

    def test_non_mapping_case_fails_closed(self) -> None:
        with pytest.raises(SacmatBaselineError) as excinfo:
            run_baseline(BASELINE_B3, "not-a-case", _ctx())
        assert excinfo.value.reason_code == "CASE_NOT_AN_OBJECT"

    def test_malformed_context_fails_closed(self) -> None:
        with pytest.raises(SacmatBaselineError) as excinfo:
            run_baseline(BASELINE_B3, _valid_grant_case(), "not-a-ctx")  # type: ignore[arg-type]
        assert excinfo.value.reason_code == "CONTEXT_MALFORMED"

    def test_negative_deadline_fails_closed(self) -> None:
        with pytest.raises(SacmatBaselineError) as excinfo:
            _ctx(deadline_seconds=-1)
        assert excinfo.value.reason_code == "CONTEXT_MALFORMED"


class TestDeterminismAndHygiene:
    def test_identical_inputs_give_identical_outcomes(self) -> None:
        cases = conformance_probe_cases() + clean_probe_cases()
        for case in cases:
            for baseline_id in (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3):
                first = run_baseline(baseline_id, case, _ctx())
                second = run_baseline(baseline_id, case, _ctx())
                assert (first.observed_outcome, first.detail) == (
                    second.observed_outcome,
                    second.detail,
                )

    def test_version_pin(self) -> None:
        assert BASELINES_VERSION == "1.0.0"

    def test_baselines_module_imports_no_oracle_module(self) -> None:
        """Oracle independence: the adapters module never imports oracle code.

        The four-valued oracle lives inside this module as the declarative
        reference semantics; no external oracle/candidate implementation is
        imported (GATES independence rule).
        """
        import ast
        import pathlib

        source = (
            pathlib.Path(__file__)
            .resolve()
            .parents[3]
            .joinpath("evaluation/venue2027/sacmat/baselines.py")
            .read_text(encoding="utf-8")
        )
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any("candidate" in name for name in imported), imported

    def test_engines_and_oracle_decide_independently_by_construction(self) -> None:
        """The oracle derives its verdict from history semantics, not from
        any single engine model: for the pure-skew unit the engines all
        PERMIT while the oracle independently flags the skew divergence."""
        case = _pure_skew_case()
        history = _validated_history(case)
        for engine_id in ENGINE_MODELS:
            assert evaluate_engine(engine_id, history, history.request) == "PERMIT"
        outcome = run_baseline(BASELINE_B3, case, _ctx())
        assert outcome.observed_outcome == "REJECT"


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _validated_history(case: dict[str, object]) -> object:
    from evaluation.venue2027.sacmat.baselines import _validate_case

    result = _validate_case(case)  # type: ignore[arg-type]
    assert not isinstance(result, Outcome), result
    return result
