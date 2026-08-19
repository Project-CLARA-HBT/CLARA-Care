"""Precision-requirement sizing for the CareGuard-VN primary endpoint (CG-03).

Computes the positive-reference case count n such that the two-sided 95%
(Wald) interval around a plausible false-reassurance rate p has half-width
<= h percentage points:

    n = ceil( z^2 * p * (1 - p) / h^2 )

with z = 1.96 for a 95% two-sided interval. This is the planning target for
the positive-reference denominator only; it says nothing about negative or
specificity cases, which CareGuard-VN does not claim.

Usage (no DAV data required):

    python research/careguard_vn/precision_requirement.py
    python research/careguard_vn/precision_requirement.py --p 0.05 --h 0.03
"""

from __future__ import annotations

import argparse
import math

Z_95 = 1.959963984540054


def required_n(p: float, half_width: float, z: float = Z_95) -> int:
    """Smallest positive-reference case count meeting the half-width target."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must lie strictly between 0 and 1")
    if half_width <= 0.0:
        raise ValueError("half_width must be positive")
    numerator = z * z * p * (1.0 - p)
    denominator = half_width * half_width
    return math.ceil(numerator / denominator)


def half_width_at(n: int, p: float, z: float = Z_95) -> float:
    """Achieved half-width (percentage points) at count n for plausible rate p."""
    if n <= 0:
        raise ValueError("n must be positive")
    return z * math.sqrt(p * (1.0 - p) / n)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p", type=float, default=None, help="plausible false-reassurance rate")
    parser.add_argument("--h", type=float, default=0.03, help="max half-width in pp (0.03 = 3pp)")
    parser.add_argument("--z", type=float, default=Z_95, help="critical value (default 1.96)")
    args = parser.parse_args()

    half_width = args.h
    if args.p is not None:
        n = required_n(args.p, half_width, args.z)
        print(
            f"p={args.p:.3f} half_width<={half_width:.3f}: required_n={n} "
            f"(achieved_half_width={half_width_at(n, args.p, args.z):.4f})"
        )
        return 0

    for p in (0.05, 0.10):
        n = required_n(p, half_width, args.z)
        print(
            f"p={p:.3f} half_width<={half_width:.3f}: required_n={n} "
            f"(achieved_half_width={half_width_at(n, p, args.z):.4f})"
        )
    print(
        "planning_target_n="
        f"{max(required_n(0.05, half_width, args.z), required_n(0.10, half_width, args.z))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
