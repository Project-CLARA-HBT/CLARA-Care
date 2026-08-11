from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.commitloop.power import (
    exact_two_sided_sign_p_value,
    exact_unconditional_power,
    verify_power_plan,
)


def test_exact_sign_test_and_tie_aware_power_are_locked() -> None:
    assert exact_two_sided_sign_p_value(wins=13, losses=1) == pytest.approx(
        0.0018310546875
    )
    assert exact_two_sided_sign_p_value(wins=0, losses=0) == 1.0
    assert exact_unconditional_power(
        subjects=384,
        non_tie_probability=0.15,
        win_probability_given_non_tie=0.7,
    ) == pytest.approx(0.8445713130700195)


def test_tracked_power_plan_recomputes_exactly() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "protocols"
        / "commitloop"
        / "v5-confirmatory"
        / "power_analysis.json"
    )
    result = verify_power_plan(json.loads(path.read_text(encoding="utf-8")))
    assert result["status"] == "VALID"
    assert result["subjects"] == 384
