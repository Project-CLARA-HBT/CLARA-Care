"""Baseline fidelity vectors for the SACMAT 2027 PolicyTrace study (task SACMAT-baseline_tests).

Purpose
-------
For EACH strong-baseline arm in ``evaluation/venue2027/sacmat/baselines.py``
(B0 static policy diff, B1 single-engine testing, B2 multi-engine differential,
B3 candidate temporal conformance) this suite pins ONE positive vector and ONE
adversarial negative vector:

- POSITIVE: on a CONFORMANT delegated-consent case (a grant in force at the
  request's decision time, no version bump in play) the arm returns the correct
  conformance decision ``ADMIT`` / ``NO_DIVERGENCE`` — the arm neither
  under- nor over-reports on clean input.
- ADVERSARIAL NEGATIVE: an expiry/skew divergence where the candidate arm B3
  DETECTS (``REJECT`` / ``B3_TEMPORAL_CONFORMANCE_DIVERGENCE``) and the weaker
  arms MISS. The real module semantics make the separation precise:

  * version-skew divergence, history-healed (grant -> revoke -> regrant in
    force, ``POLICY_VERSION_BUMP`` after the request's decision time): all
    three engine models agree pointwise on PERMIT, so B0, B1 AND B2 all ADMIT
    (miss) while B3 alone detects the skew;
  * pure expiry race (delegation lapsed at decision time, bump after it): the
    compiled final-state engines still PERMIT (B0/B1 miss) and B3 detects via
    the oracle's temporal DENY. B2 partially detects this variant through the
    read-time Zanzibar tuple walk, so B2's miss-vector is the healed-skew
    divergence above.

  Each weaker arm's miss is asserted against the REAL evaluator on the SAME
  divergence case B3 catches — that four-arm contrast IS the fidelity
  evidence, never a stub.

All vectors are synthetic ``(policy history, request)`` units in monotonic
logical time (GRANT / REVOKE / REGRANT / POLICY_VERSION_BUMP events; no
PHI/PII, no network, no live provider, no hidden clock or randomness). The
REAL baseline module ``evaluation.venue2027.sacmat.baselines`` is imported and
driven through its public dispatch entry ``run_baseline``; nothing here
re-implements an arm. Expectations are adjudicated by the module's independent
four-valued oracle (``oracle_decision``), which derives its verdict from
ordered-history state, never from an engine model or arm.

Unavailable upstream binaries
-----------------------------
The pinned upstream policy-engine binaries (Cedar v4.14.1, OpenFGA v1.22.1,
OPA v1.22.4) belong to the downstream adapter tasks SACMAT-X03/X04/X05 and are
NOT runnable in this in-process fidelity suite. With the injected
``SacmatContext(simulate_unavailable_upstream=True)`` flag the module
documents for exactly this purpose, the replay arms (B1/B2/B3) are asserted to
return the transparent first-class outcome ``NOT_RUN_EXTERNAL`` with reason
code ``BASELINE_UNAVAILABLE`` (never counted as a completion, never a toy
substitution); B0 is a pure in-process structural diff and still runs.

Failure semantics
-----------------
Every arm verdict is a first-class harness ``Outcome``. Any verdict outside
the documented set, or any ADMIT on a divergence case the oracle DENYs / that
carries a version bump after decision time, fails the test. Version: pinned
via ``BASELINES_VERSION``.
"""

from __future__ import annotations

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B3,
    BASELINES_VERSION,
    EVENT_GRANT,
    EVENT_POLICY_VERSION_BUMP,
    EVENT_REGRANT,
    EVENT_REVOKE,
    PURPOSE_SELF_CARE,
    RC_B0_STRUCTURAL_DIFF,
    RC_B1_ENGINE_SELF_TEST,
    RC_B2_CROSS_ENGINE_DISAGREEMENT,
    RC_B3_TEMPORAL_CONFORMANCE,
    RC_B3_VERSION_SKEW,
    RC_BASELINE_UNAVAILABLE,
    RC_NO_DIVERGENCE,
    SacmatContext,
    event,
    oracle_decision,
    request,
    run_baseline,
)

REJECT = "REJECT"
ADMIT = "ADMIT"
NOT_RUN_EXTERNAL = "NOT_RUN_EXTERNAL"

#: The fidelity contract under test: one positive + one adversarial negative
#: vector for EACH task-contract arm (B0-B3).
ALL_ARMS = (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3)


def _ctx(**overrides: object) -> SacmatContext:
    return SacmatContext(**overrides)  # type: ignore[arg-type]


def _validated(case: dict[str, object]) -> object:
    from evaluation.venue2027.sacmat.baselines import _validate_case

    result = _validate_case(case)  # type: ignore[arg-type]
    assert not isinstance(result, Outcome), result
    return result


def _conformant_delegated_consent_case(case_id: str) -> dict[str, object]:
    """Positive vector shared by all four arms.

    A conformant delegated-consent unit: the delegating owner granted their
    own ``self_care`` delegation in force at the request's decision time
    (grant at t=100, expiry t=9000, request decided at t=500). The independent
    four-valued oracle labels it PERMIT; the correct conformance decision for
    every arm is ADMIT / NO_DIVERGENCE.
    """
    return {
        "case_id": case_id,
        "history": [
            event(EVENT_GRANT, 100, "patient-pos", "patient-pos", PURPOSE_SELF_CARE, expiry=9000),
        ],
        "request": request("patient-pos", PURPOSE_SELF_CARE, 500),
    }


def _history_healed_skew_divergence_case(case_id: str) -> dict[str, object]:
    """Adversarial negative vector: version-skew divergence, history healed.

    grant (t=100) -> revoke (t=1500) -> regrant in force (t=1600) with a
    ``POLICY_VERSION_BUMP`` at t=2500, AFTER the request's decision time
    (t=1700). All three engine models agree pointwise on PERMIT — the final
    state has "healed" — so B0, B1 and B2 all ADMIT (miss), while B3's
    ordered-history replay detects the version skew (bump at/after decision
    time). This is the single strongest separation case of the suite.
    """
    return {
        "case_id": case_id,
        "history": [
            event(EVENT_GRANT, 100, "patient-neg", "patient-neg", PURPOSE_SELF_CARE, expiry=9000),
            event(EVENT_REVOKE, 1500, "patient-neg", "patient-neg", PURPOSE_SELF_CARE),
            event(
                EVENT_REGRANT, 1600, "patient-neg", "patient-neg", PURPOSE_SELF_CARE, expiry=9000
            ),
            event(EVENT_POLICY_VERSION_BUMP, 2500, "system", "system", "*"),
        ],
        "request": request("patient-neg", PURPOSE_SELF_CARE, 1700),
    }


def _expiry_race_divergence_case(case_id: str) -> dict[str, object]:
    """Adversarial negative vector: pure delegation-expiry divergence.

    The delegation lapsed at decision time (grant expiry t=1000, request
    decided at t=1500) and the compiled policy was bumped at t=2000, after the
    request. The compiled final-state engines still show a grant for
    (patient-exp, self_care), so B0 and B1 see nothing; the independent
    oracle DENYs the lapsed grant and B3 detects the temporal divergence.
    """
    return {
        "case_id": case_id,
        "history": [
            event(EVENT_GRANT, 100, "patient-exp", "patient-exp", PURPOSE_SELF_CARE, expiry=1000),
            event(EVENT_POLICY_VERSION_BUMP, 2000, "system", "system", "*"),
        ],
        "request": request("patient-exp", PURPOSE_SELF_CARE, 1500),
    }


class TestVersionAndOracleIndependence:
    def test_module_version_pin(self) -> None:
        assert BASELINES_VERSION == "1.0.0"

    def test_positive_vector_is_oracle_conformant(self) -> None:
        """The shared positive vector is labeled conformant by the
        independent oracle, which derives PERMIT from ordered-history state —
        never from an arm or engine model — so every expected ADMIT below is
        anchored outside the code under test."""
        case = _conformant_delegated_consent_case("SACMAT-BF-POS-ORACLE")
        assert oracle_decision(_validated(case)) == "PERMIT"

    def test_negative_vectors_are_oracle_or_skew_divergent(self) -> None:
        """The expiry-race vector is oracle-DENY (lapsed grant); the
        healed-skew vector is oracle-PERMIT at decision time yet carries a
        policy version bump AFTER it — the skew B3 alone flags."""
        assert oracle_decision(_validated(_expiry_race_divergence_case("O1"))) == "DENY"
        healed = _history_healed_skew_divergence_case("O2")
        assert oracle_decision(_validated(healed)) == "PERMIT"
        assert "bump_at=2500" in run_baseline(BASELINE_B3, healed, _ctx()).detail


# ---------------------------------------------------------------------------
# Per-arm positive vectors: correct conformance decision on a conformant case.
# ---------------------------------------------------------------------------


class TestPositiveVectors:
    @pytest.mark.parametrize("arm", ALL_ARMS)
    def test_each_arm_admits_conformant_delegated_consent(self, arm: str) -> None:
        case = _conformant_delegated_consent_case(f"SACMAT-BF-POS-ARM-{arm}")
        outcome = run_baseline(arm, case, _ctx(arm_id=arm))
        assert outcome.observed_outcome == ADMIT, (arm, outcome.detail)
        assert outcome.counted_as_success is True
        assert outcome.retriable is False
        assert RC_NO_DIVERGENCE in outcome.detail


# ---------------------------------------------------------------------------
# Per-arm adversarial negative vectors: expiry/skew divergences where B3
# detects and the weaker arms miss — the contrast is the fidelity evidence.
# ---------------------------------------------------------------------------


class TestAdversarialNegativeVectors:
    def test_b3_detects_history_healed_version_skew(self) -> None:
        case = _history_healed_skew_divergence_case("SACMAT-BF-NEG-B3-SKEW")
        outcome = run_baseline(BASELINE_B3, case, _ctx(arm_id=BASELINE_B3))
        assert outcome.observed_outcome == REJECT, outcome.detail
        assert outcome.counted_as_success is True
        assert outcome.retriable is False
        assert RC_B3_TEMPORAL_CONFORMANCE in outcome.detail
        assert RC_B3_VERSION_SKEW in outcome.detail

    def test_b3_detects_delegation_expiry_race(self) -> None:
        case = _expiry_race_divergence_case("SACMAT-BF-NEG-B3-EXPIRY")
        outcome = run_baseline(BASELINE_B3, case, _ctx(arm_id=BASELINE_B3))
        assert outcome.observed_outcome == REJECT, outcome.detail
        assert "oracle_decision" in outcome.detail
        assert "DENY" in outcome.detail

    @pytest.mark.parametrize("arm", [BASELINE_B0, BASELINE_B1, BASELINE_B2])
    def test_weaker_arms_miss_skew_divergence_b3_detects(self, arm: str) -> None:
        """Each weaker arm really evaluated the SAME healed-skew divergence
        case through its own semantics and returned a clean verdict while B3
        rejects it: the miss is a recorded scientific result, not an error
        and not a stub."""
        case = _history_healed_skew_divergence_case(f"SACMAT-BF-NEG-ARM-{arm}")
        weaker = run_baseline(arm, case, _ctx(arm_id=arm))
        candidate = run_baseline(BASELINE_B3, case, _ctx(arm_id=BASELINE_B3))
        assert weaker.observed_outcome == ADMIT, (arm, weaker.detail)
        assert weaker.counted_as_success is True
        assert RC_NO_DIVERGENCE in weaker.detail
        assert candidate.observed_outcome == REJECT

    @pytest.mark.parametrize("arm", [BASELINE_B0, BASELINE_B1])
    def test_b0_b1_also_miss_expiry_race_b3_detects(self, arm: str) -> None:
        """The compiled final-state engines (XACML/Cedar) still PERMIT the
        lapsed grant pointwise, so the static/pointwise arms B0 and B1 miss
        the expiry race while B3 detects it via the oracle's temporal DENY."""
        case = _expiry_race_divergence_case(f"SACMAT-BF-NEG-EXPIRY-ARM-{arm}")
        weaker = run_baseline(arm, case, _ctx(arm_id=arm))
        candidate = run_baseline(BASELINE_B3, case, _ctx(arm_id=BASELINE_B3))
        assert weaker.observed_outcome == ADMIT, (arm, weaker.detail)
        assert candidate.observed_outcome == REJECT

    def test_fidelity_contrast_is_complete_on_skew_divergence(self) -> None:
        """The contrast itself: same healed-skew case, four arms, exactly B3
        differs — and each miss is real arm output carrying its own reason
        code path (no divergence reason recorded by the missing arms)."""
        case = _history_healed_skew_divergence_case("SACMAT-BF-NEG-CONTRAST")
        verdicts = {arm: run_baseline(arm, case, _ctx(arm_id=arm)) for arm in ALL_ARMS}
        assert verdicts[BASELINE_B3].observed_outcome == REJECT
        assert verdicts[BASELINE_B0].observed_outcome == ADMIT
        assert verdicts[BASELINE_B1].observed_outcome == ADMIT
        assert verdicts[BASELINE_B2].observed_outcome == ADMIT
        assert RC_B0_STRUCTURAL_DIFF not in verdicts[BASELINE_B0].detail
        assert RC_B1_ENGINE_SELF_TEST not in verdicts[BASELINE_B1].detail
        assert RC_B2_CROSS_ENGINE_DISAGREEMENT not in verdicts[BASELINE_B2].detail
        assert RC_B3_TEMPORAL_CONFORMANCE in verdicts[BASELINE_B3].detail


# ---------------------------------------------------------------------------
# Unavailable upstream binaries: transparent NOT_RUN_EXTERNAL, never a toy.
# ---------------------------------------------------------------------------


class TestUnavailableUpstreamBinaries:
    @pytest.mark.parametrize("arm", [BASELINE_B1, BASELINE_B2, BASELINE_B3])
    def test_unavailable_upstream_flag_yields_not_run_external(self, arm: str) -> None:
        """With the pinned upstream binaries declared unavailable on the
        injected context, the engine-replay arms report NOT_RUN_EXTERNAL /
        BASELINE_UNAVAILABLE: a first-class, retriable, never-counted
        outcome — not a silent skip and not a safe rejection."""
        case = _conformant_delegated_consent_case(f"SACMAT-BF-EXT-{arm}")
        outcome = run_baseline(arm, case, _ctx(arm_id=arm, simulate_unavailable_upstream=True))
        assert outcome.observed_outcome == NOT_RUN_EXTERNAL, (arm, outcome.detail)
        assert outcome.counted_as_success is False
        assert outcome.retriable is True
        assert RC_BASELINE_UNAVAILABLE in outcome.detail

    def test_b0_pure_structural_diff_still_runs_without_upstreams(self) -> None:
        """B0 is a pure in-process structural diff requiring no engine
        replay, so it still executes when upstreams are unavailable."""
        case = _conformant_delegated_consent_case("SACMAT-BF-EXT-B0")
        outcome = run_baseline(
            BASELINE_B0, case, _ctx(arm_id=BASELINE_B0, simulate_unavailable_upstream=True)
        )
        assert outcome.observed_outcome == ADMIT, outcome.detail


# ---------------------------------------------------------------------------
# Determinism: identical inputs give identical outcomes.
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.parametrize("arm", ALL_ARMS)
    def test_identical_inputs_give_identical_outcomes(self, arm: str) -> None:
        cases = (
            _conformant_delegated_consent_case("SACMAT-BF-DET-POS"),
            _history_healed_skew_divergence_case("SACMAT-BF-DET-NEG"),
        )
        for case in cases:
            first = run_baseline(arm, case, _ctx(arm_id=arm))
            second = run_baseline(arm, case, _ctx(arm_id=arm))
            assert (first.observed_outcome, first.detail) == (
                second.observed_outcome,
                second.detail,
            )
