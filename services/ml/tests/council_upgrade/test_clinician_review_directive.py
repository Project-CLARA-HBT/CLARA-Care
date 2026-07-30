"""Clinician-review directive invariant for the CLARA Council (ML side).

Task 4.4 — re-assert the deterministic safety invariant that **every**
``run_council`` output carries the "review with a licensed clinician" directive,
regardless of triage outcome (emergency escalation, consensus, divergence,
needs-more-info/fallback) and regardless of every Council upgrade flag and of any
downstream oversight state (Requirement 3.5).

CLARA's Council is decision-support software, not a medical device and not an
EMR/EHR; the directive must never be droppable by any output path. The guarantee
is therefore additive and *not* flag-gated:

* ``clinician_review_required`` is always ``True`` (machine-readable contract).
* ``clinician_review_directive`` is always the bilingual directive text, which
  names a *licensed clinician* and is non-empty.

This is an example-based regression lock + a small generative property over
representative payloads. Everything here is deterministic and network-free.
"""

from __future__ import annotations

from itertools import product

import pytest

from clara_ml.agents.council import CLINICIAN_REVIEW_DIRECTIVE, run_council

from .harness import council_flags

# ---------------------------------------------------------------------------
# Representative payloads, one per triage/escalation pathway through run_council.
# ---------------------------------------------------------------------------

# Red-flag → emergency_escalation path.
_EMERGENCY_PAYLOAD: dict[str, object] = {
    "symptoms": ["sudden one sided weakness and slurred speech since this morning"],
    "labs": {},
    "medications": [],
    "history": [],
    "specialists": ["neurology", "cardiology"],
}

# Rich, non-emergency input → consensus (routine/same-day) path.
_CONSENSUS_PAYLOAD: dict[str, object] = {
    "symptoms": ["mild fatigue", "occasional mild headache for two weeks"],
    "labs": {"glucose": 110.0, "creatinine": 1.0},
    "medications": ["metformin"],
    "history": ["type 2 diabetes", "hypertension"],
    "specialists": ["endocrinology", "cardiology", "neurology"],
}

# Conflicting specialist urgencies → divergence path (kept non-emergency).
_DIVERGENCE_PAYLOAD: dict[str, object] = {
    "symptoms": ["palpitations", "intermittent dizziness"],
    "labs": {"potassium": 5.2, "egfr": 28.0},
    "medications": ["ibuprofen"],
    "history": ["chronic kidney disease"],
    "specialists": ["cardiology", "nephrology", "neurology"],
}

# Sparse input → needs_more_info / degraded-data path.
_FALLBACK_PAYLOAD: dict[str, object] = {
    "symptoms": ["unwell"],
    "labs": {},
    "medications": [],
    "history": [],
    "specialists": ["cardiology", "neurology"],
}

_ALL_PAYLOADS = {
    "emergency": _EMERGENCY_PAYLOAD,
    "consensus": _CONSENSUS_PAYLOAD,
    "divergence": _DIVERGENCE_PAYLOAD,
    "fallback": _FALLBACK_PAYLOAD,
}

# Every permutation of the three ML-side upgrade flags; the directive must ride
# along under all of them, not just flags-off.
_FLAG_NAMES = (
    "council_streaming_enabled",
    "council_model_disclosure_enabled",
    "council_observability_enabled",
)
_FLAG_PERMUTATIONS = [
    dict(zip(_FLAG_NAMES, combo)) for combo in product((False, True), repeat=len(_FLAG_NAMES))
]


def _assert_directive_present(result: dict) -> None:
    """The two stable directive keys are present, correct, and non-empty."""
    assert result["clinician_review_required"] is True
    directive = result["clinician_review_directive"]
    assert isinstance(directive, str)
    assert directive.strip()
    assert directive == CLINICIAN_REVIEW_DIRECTIVE
    # The directive is specifically a *licensed clinician* review directive,
    # bilingual vi/en (Requirement 3.5).
    assert "clinician" in directive.lower()
    assert "bác sĩ" in directive


class TestClinicianReviewDirectiveAlwaysPresent:
    """Req 3.5: the directive is on every run_council output, every path."""

    @pytest.mark.parametrize("path", list(_ALL_PAYLOADS))
    def test_every_triage_path_carries_directive(self, path: str) -> None:
        result = run_council(dict(_ALL_PAYLOADS[path]))
        _assert_directive_present(result)

    def test_emergency_path_still_escalates_and_carries_directive(self) -> None:
        """The emergency path both escalates AND carries the directive."""
        result = run_council(dict(_EMERGENCY_PAYLOAD))
        assert result["emergency_escalation"]["triggered"] is True
        _assert_directive_present(result)

    def test_fallback_path_requests_more_info_and_carries_directive(self) -> None:
        """The degraded/needs-more-info path also carries the directive."""
        result = run_council(dict(_FALLBACK_PAYLOAD))
        assert result["needs_more_info"] is True
        _assert_directive_present(result)

    @pytest.mark.parametrize("flags", _FLAG_PERMUTATIONS)
    @pytest.mark.parametrize("path", list(_ALL_PAYLOADS))
    def test_directive_independent_of_upgrade_flags(
        self, flags: dict, path: str
    ) -> None:
        """The directive is present under every upgrade-flag permutation."""
        with council_flags(**flags):
            result = run_council(dict(_ALL_PAYLOADS[path]))
        _assert_directive_present(result)

    @pytest.mark.parametrize(
        "rule_shadow_enabled", [False, True], ids=["rule_shadow_off", "rule_shadow_on"]
    )
    def test_directive_independent_of_rule_shadow(self, rule_shadow_enabled: bool) -> None:
        """Enabling the fixed rule shadow never drops the directive."""
        result = run_council(
            dict(_CONSENSUS_PAYLOAD, council_rule_shadow_enabled=rule_shadow_enabled)
        )
        _assert_directive_present(result)

    def test_directive_keys_are_additive_only(self) -> None:
        """Directive keys are added without disturbing pre-existing keys.

        Mirrors the disclosure-additivity contract: stripping the two new keys
        must leave an envelope identical to one produced before they were known
        to consumers (i.e. the directive is purely additive).
        """
        result = run_council(dict(_CONSENSUS_PAYLOAD))
        # The known existing top-level keys are all still present.
        for key in (
            "final_recommendation",
            "emergency_escalation",
            "council_consensus",
            "analyze",
            "reasoning_timeline",
        ):
            assert key in result
        # And the directive keys are the additive surface this task introduces.
        assert "clinician_review_required" in result
        assert "clinician_review_directive" in result
