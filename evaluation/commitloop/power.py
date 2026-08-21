"""Exact tie-aware power calculations for one paired sign-test contrast."""

from __future__ import annotations

import argparse
import json
from functools import cache
from math import comb
from pathlib import Path
from typing import Any


def exact_two_sided_sign_p_value(*, wins: int, losses: int) -> float:
    if wins < 0 or losses < 0:
        raise ValueError("negative_sign_count")
    non_ties = wins + losses
    if non_ties == 0:
        return 1.0
    tail = min(wins, losses)
    return min(
        1.0,
        2.0 * sum(comb(non_ties, value) for value in range(tail + 1)) / (2**non_ties),
    )


@cache
def _critical_wins(non_ties: int, alpha: float) -> int:
    for wins in range(non_ties // 2 + 1, non_ties + 1):
        if exact_two_sided_sign_p_value(wins=wins, losses=non_ties - wins) <= alpha:
            return wins
    return non_ties + 1


def _conditional_rejection_probability(
    *, non_ties: int, win_probability: float, alpha: float
) -> float:
    critical = _critical_wins(non_ties, alpha)
    return sum(
        comb(non_ties, wins) * win_probability**wins * (1.0 - win_probability) ** (non_ties - wins)
        for wins in range(critical, non_ties + 1)
    )


def exact_unconditional_power(
    *,
    subjects: int,
    non_tie_probability: float,
    win_probability_given_non_tie: float,
    alpha: float = 0.05,
) -> float:
    if subjects < 1:
        raise ValueError("subjects_must_be_positive")
    for name, value in (
        ("non_tie_probability", non_tie_probability),
        ("win_probability_given_non_tie", win_probability_given_non_tie),
        ("alpha", alpha),
    ):
        if not 0.0 < value < 1.0:
            raise ValueError(f"invalid_{name}")
    return sum(
        comb(subjects, non_ties)
        * non_tie_probability**non_ties
        * (1.0 - non_tie_probability) ** (subjects - non_ties)
        * _conditional_rejection_probability(
            non_ties=non_ties,
            win_probability=win_probability_given_non_tie,
            alpha=alpha,
        )
        for non_ties in range(subjects + 1)
    )


def verify_power_plan(plan: dict[str, Any]) -> dict[str, object]:
    assumptions = plan["assumptions"]
    calculation = plan["calculation"]
    actual = exact_unconditional_power(
        subjects=int(calculation["enrolled_subjects"]),
        non_tie_probability=float(assumptions["non_tie_probability"]),
        win_probability_given_non_tie=float(
            assumptions["reference_win_probability_conditional_on_non_tie"]
        ),
        alpha=float(plan["alpha"]),
    )
    declared = float(calculation["calculated_power"])
    if abs(actual - declared) > 1e-12:
        raise ValueError("power_plan_calculation_mismatch")
    floor = float(plan["target_power_floor"])
    return {
        "status": "VALID" if actual >= floor else "UNDERPOWERED",
        "subjects": int(calculation["enrolled_subjects"]),
        "calculated_power": actual,
        "target_power_floor": floor,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise TypeError("power_plan_must_be_object")
    print(json.dumps(verify_power_plan(plan), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
