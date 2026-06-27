"""Deterministic-safety regression for the CLARA Council upgrade (ML side).

Task 9.1 — re-assert the two safety invariants that every Council upgrade flag
must leave untouched, exercised directly against the shared ``run_council``
path (Requirements 9.3, 9.4; design Correctness Properties **P11** and **P14**):

* **P11 — Safety preservation.** A *non-negated* red-flag phrase deterministically
  forces ``emergency_escalation`` (``triggered = True``,
  ``action = "immediate_emergency_referral"``, the emergency final
  recommendation, and a ``critical`` escalation priority), while a *negated*
  red-flag phrase never escalates — independent of every upgrade flag and of the
  shadow neural-risk feature.
* **P14 — Neural shadow containment.** Turning the neural risk model on (shadow
  mode) is purely additive: it changes only the ``neural_risk`` block and never
  the deterministic triage / escalation / final recommendation, even when the
  neural model recommends a *higher* triage than the rule engine.

These are example-based regression locks (the optional property-based versions
live in task 9.2). Everything here is deterministic and network-free.
"""

from __future__ import annotations

from itertools import product

import pytest

from clara_ml.agents.council import run_council

from .harness import council_flags

# The deterministic fields that encode the clinical routing decision. None of
# these may ever depend on an upgrade flag or on the shadow neural score.
_DETERMINISTIC_KEYS = (
    "emergency_escalation",
    "final_recommendation",
    "council_consensus",
    "consensus_summary",
    "needs_more_info",
    "analyze",
)

# Every permutation of the three ML-side upgrade flags. The invariant must hold
# across all of them, not just flags-off.
_FLAG_NAMES = (
    "council_streaming_enabled",
    "council_model_disclosure_enabled",
    "council_observability_enabled",
)
_FLAG_PERMUTATIONS = [
    dict(zip(_FLAG_NAMES, combo)) for combo in product((False, True), repeat=len(_FLAG_NAMES))
]

# A non-negated red flag that the *specialist* rules alone would NOT escalate
# (isolated "vomiting blood" without an interacting medication keeps pharmacology
# at routine_follow_up), so a forced ``emergency_escalation`` proves the
# safety gate — not a specialist vote — is doing the forcing.
_RED_FLAG_PAYLOAD: dict[str, object] = {
    "symptoms": ["patient reports vomiting blood since this morning"],
    "labs": {},
    "medications": [],
    "history": [],
    "specialists": ["cardiology", "nephrology"],
}

# The same phrase, locally negated. Negation-aware detection must drop it, so no
# escalation is forced.
_NEGATED_PAYLOAD: dict[str, object] = {
    "symptoms": ["denies vomiting blood", "mild fatigue"],
    "labs": {},
    "medications": [],
    "history": [],
    "specialists": ["cardiology", "nephrology"],
}


def _assert_forced_escalation(result: dict) -> None:
    escalation = result["emergency_escalation"]
    assert escalation["triggered"] is True
    assert escalation["action"] == "immediate_emergency_referral"
    assert len(escalation["red_flags"]) >= 1
    assert escalation["metadata"]["priority"] == "critical"
    assert escalation["metadata"]["requires_human_handoff"] is True
    assert "Emergency escalation triggered" in result["final_recommendation"]
    assert result["analyze"]["emergency_triggered"] is True


class TestRedFlagForcesEscalation:
    """P11: non-negated red flags force emergency_escalation under any flag set."""

    @pytest.mark.parametrize("flags", _FLAG_PERMUTATIONS)
    def test_non_negated_red_flag_forces_emergency(self, flags: dict) -> None:
        with council_flags(**flags):
            result = run_council(dict(_RED_FLAG_PAYLOAD))
        _assert_forced_escalation(result)

    @pytest.mark.parametrize("flags", _FLAG_PERMUTATIONS)
    def test_negated_red_flag_does_not_escalate(self, flags: dict) -> None:
        with council_flags(**flags):
            result = run_council(dict(_NEGATED_PAYLOAD))
        escalation = result["emergency_escalation"]
        assert escalation["triggered"] is False
        assert escalation["red_flags"] == []
        assert escalation["action"] == "standard_multidisciplinary_pathway"
        # The phrase is recorded as negated context, never as a positive trigger.
        assert len(escalation["negated_red_flags"]) >= 1
        assert "Emergency escalation triggered" not in result["final_recommendation"]

    def test_red_flag_escalation_independent_of_neural_flag(self) -> None:
        """The forced escalation is identical whether or not neural risk runs."""
        without_neural = run_council(
            dict(_RED_FLAG_PAYLOAD, council_neural_enabled=False)
        )
        with_neural = run_council(
            dict(_RED_FLAG_PAYLOAD, council_neural_enabled=True)
        )
        _assert_forced_escalation(without_neural)
        _assert_forced_escalation(with_neural)
        for key in _DETERMINISTIC_KEYS:
            assert without_neural[key] == with_neural[key]


class TestNeuralShadowContainment:
    """P14: enabling neural risk never changes the deterministic decision."""

    @pytest.mark.parametrize(
        "payload",
        [_RED_FLAG_PAYLOAD, _NEGATED_PAYLOAD],
        ids=["red_flag", "negated"],
    )
    def test_enabling_neural_only_adds_neural_block(self, payload: dict) -> None:
        baseline = run_council(dict(payload, council_neural_enabled=False))
        shadowed = run_council(dict(payload, council_neural_enabled=True))

        # Every deterministic field is byte-identical.
        for key in _DETERMINISTIC_KEYS:
            assert baseline[key] == shadowed[key], f"neural risk leaked into {key!r}"

        # The neural model actually ran (shadow), so it is observably present...
        assert baseline["neural_risk"]["enabled"] is False
        assert shadowed["neural_risk"]["enabled"] is True
        assert shadowed["neural_risk"]["shadow_mode"] is True

        # ...yet the ONLY difference between the two envelopes is neural_risk.
        baseline_sans = {k: v for k, v in baseline.items() if k != "neural_risk"}
        shadowed_sans = {k: v for k, v in shadowed.items() if k != "neural_risk"}
        assert baseline_sans == shadowed_sans

    def test_neural_higher_recommendation_does_not_override_routine(self) -> None:
        """When neural recommends a higher triage, routing stays deterministic."""
        # Sparse, conflict-prone input keeps the rule engine off emergency while
        # pushing the neural score up; the recommended_triage may diverge.
        payload: dict[str, object] = {
            "symptoms": ["mild intermittent dizziness"],
            "labs": {},
            "medications": [],
            "history": [],
            "specialists": ["cardiology", "neurology"],
        }
        baseline = run_council(dict(payload, council_neural_enabled=False))
        shadowed = run_council(dict(payload, council_neural_enabled=True))

        # No red flag ⇒ deterministic escalation is NOT triggered, regardless of
        # whatever band the shadow model lands on.
        assert baseline["emergency_escalation"]["triggered"] is False
        assert shadowed["emergency_escalation"]["triggered"] is False

        # Neural recommended_triage is reported but never feeds routing.
        assert shadowed["neural_risk"]["recommended_triage"] in {
            "routine_follow_up",
            "same_day_review",
            "emergency_escalation",
        }
        for key in _DETERMINISTIC_KEYS:
            assert baseline[key] == shadowed[key]
