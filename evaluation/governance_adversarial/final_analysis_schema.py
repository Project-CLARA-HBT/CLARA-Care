"""E-001: explicit three-state primary schema for the GovRed RIVF analysis.

GRD-01 requires final scientific tables to distinguish ``CONFIRMED_INVALID``,
``INDETERMINATE`` and ``CONFIRMED_SAFE_OR_REJECTED``, plus the operational
failure state. The historical binary non-safe composite
(``primary_failures`` in the sealed analysis) remains a **secondary frozen
endpoint only** and is never relabelled.

This module derives the three-state primary table from the sealed
``research/govred_rivf/results/final-003-analysis-v2.json`` (read-only, never
modified). It emits a **new** derived artifact. Derivation rules are explicit:

- every ``concurrent_stale_state_write`` residual is ``INDETERMINATE`` per the
  frozen GLHS TOCTOU wording (ordering unresolvable from the final-003
  observer); it is never relabelled as a confirmed violation;
- residuals in weaker arms (``authorization_consent_toctou``,
  ``role_mismatch``, ``stale_thss_replay``) are ``CONFIRMED_INVALID`` with
  attribution ``arm_omitted_coordinate`` (the arm design removes the guarding
  coordinate); they are controlled ablation outcomes, not production defects;
- ``OPERATIONAL_FAILURE`` is taken from the availability endpoint split;
- ``CONFIRMED_SAFE_OR_REJECTED`` is the remainder of the primary denominator.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.governance_adversarial.protocol import ARMS

SCHEMA_VERSION = "govred-three-state-primary-v1"

STATE_CONFIRMED_INVALID = "CONFIRMED_INVALID"
STATE_INDETERMINATE = "INDETERMINATE"
STATE_CONFIRMED_SAFE_OR_REJECTED = "CONFIRMED_SAFE_OR_REJECTED"
STATE_OPERATIONAL_FAILURE = "OPERATIONAL_FAILURE"

THREE_STATE_ORDER = (
    STATE_CONFIRMED_INVALID,
    STATE_INDETERMINATE,
    STATE_CONFIRMED_SAFE_OR_REJECTED,
    STATE_OPERATIONAL_FAILURE,
)

#: Residual families whose outcomes stay INDETERMINATE under the frozen
#: wording. Final-003 residual localization (strict_residuals.py) classifies
#: the concurrency/ordering family as INDETERMINATE_ORDERING; the sealed
#: reconciliation never upgrades these to confirmed violations.
INDETERMINATE_FAMILIES = frozenset({"concurrent_stale_state_write"})

#: Drift-axis -> guarded coordinate omitted by the weaker arm designs. Only
#: used to annotate CONFIRMED_INVALID residuals in arms that omit the
#: coordinate; the strict arm guards all coordinates and contributes zero.
_OMITTED_COORDINATE = {
    "authorization_consent_toctou": "governance_revalidation",
    "role_mismatch": "governance_revalidation",
    "stale_thss_replay": "state_revalidation",
}

#: Which arm designs omit which coordinate (from the prespecified ablation).
_ARM_OMITS = {
    "UNBOUND": frozenset({"governance_revalidation", "state_revalidation"}),
    "STATE_VERSION_ONLY": frozenset({"governance_revalidation"}),
    "SNAPSHOT_BOUND_STATE_ONLY": frozenset({"governance_revalidation"}),
    "GLHS_STRICT": frozenset(),
}


@dataclass(frozen=True)
class ThreeStateRow:
    """One arm's three-state primary breakdown."""

    arm: str
    primary_endpoint_n: int
    confirmed_invalid: int
    indeterminate: int
    confirmed_safe_or_rejected: int
    operational_failure: int
    invalid_breakdown: tuple[dict[str, object], ...]
    indeterminate_breakdown: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "arm": self.arm,
            "primary_endpoint_n": self.primary_endpoint_n,
            STATE_CONFIRMED_INVALID: self.confirmed_invalid,
            STATE_INDETERMINATE: self.indeterminate,
            STATE_CONFIRMED_SAFE_OR_REJECTED: self.confirmed_safe_or_rejected,
            STATE_OPERATIONAL_FAILURE: self.operational_failure,
            "invalid_breakdown": list(self.invalid_breakdown),
            "indeterminate_breakdown": list(self.indeterminate_breakdown),
        }


def _breakdown(residuals: dict[str, int], *, arm: str) -> tuple[dict[str, object], ...]:
    """Split residual families into INDETERMINATE vs CONFIRMED_INVALID lines."""
    indeterminate: list[dict[str, object]] = []
    invalid: list[dict[str, object]] = []
    for family, count in sorted(residuals.items()):
        if count <= 0:
            continue
        if family in INDETERMINATE_FAMILIES:
            indeterminate.append({
                "family": family,
                "n": count,
                "state": STATE_INDETERMINATE,
                "reason": "concurrency/ordering residual; ordering not resolvable "
                "from the frozen final-003 observer (never relabelled as a "
                "confirmed violation)",
            })
            continue
        omitted = _OMITTED_COORDINATE.get(family, "unknown")
        invalid.append({
            "family": family,
            "n": count,
            "state": STATE_CONFIRMED_INVALID,
            "attribution": "arm_omitted_coordinate",
            "omitted_coordinate": omitted,
            "note": "controlled ablation outcome: the arm design removes the "
            f"{omitted} coordinate; not a production defect",
            "arm_omits_coordinate": omitted in _ARM_OMITS[arm],
        })
    return tuple(invalid), tuple(indeterminate)


def derive_three_state_primary(analysis: dict[str, Any]) -> dict[str, object]:
    """Re-derive the three-state primary table from the sealed analysis.

    ``analysis`` must be the parsed ``final-003-analysis-v2.json`` (schema
    ``govred-analysis-v2``). Raises ``ValueError`` on any unrecognised schema
    so an unsupported sealed shape is never silently re-interpreted.
    """
    if analysis.get("schema_version") != "govred-analysis-v2":
        raise ValueError(
            f"govred_three_state_requires_sealed_v2_analysis:{analysis.get('schema_version')}"
        )
    arms = analysis.get("arms")
    if not isinstance(arms, dict):
        raise TypeError("govred_sealed_analysis_arms_missing")
    rows: list[dict[str, object]] = []
    for arm in ARMS:
        payload = arms.get(arm)
        if not isinstance(payload, dict):
            raise TypeError(f"govred_sealed_analysis_arm_missing:{arm}")
        total = int(payload["primary_endpoint_n"])
        residuals = payload.get("primary_family_residual")
        if not isinstance(residuals, dict):
            raise TypeError(f"govred_sealed_residual_missing:{arm}")
        endpoint_split = payload.get("endpoint_split")
        if not isinstance(endpoint_split, dict):
            raise TypeError(f"govred_sealed_endpoint_split_missing:{arm}")
        invalid, indeterminate = _breakdown(residuals, arm=arm)
        invalid_n = sum(int(item["n"]) for item in invalid)
        indeterminate_n = sum(int(item["n"]) for item in indeterminate)
        operational_n = int(endpoint_split.get("availability_failure", 0))
        safe_n = total - invalid_n - indeterminate_n - operational_n
        if safe_n < 0:
            raise ValueError(f"govred_three_state_arithmetic_invalid:{arm}")
        rows.append(
            ThreeStateRow(
                arm=arm,
                primary_endpoint_n=total,
                confirmed_invalid=invalid_n,
                indeterminate=indeterminate_n,
                confirmed_safe_or_rejected=safe_n,
                operational_failure=operational_n,
                invalid_breakdown=invalid,
                indeterminate_breakdown=indeterminate,
            ).to_dict()
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "derived_from": str(analysis.get("run_id")),
        "source_schema_version": str(analysis.get("schema_version")),
        "source_sha": str(analysis.get("source_sha")),
        "derivation_notes": [
            ("CONFIRMED_INVALID counts confirmed invalid-commit acceptances with "
            "attribution arm_omitted_coordinate for weaker-arm residuals; "
            "never presented as production defects."),
            ("INDETERMINATE counts concurrent_stale_state_write residuals per the "
            "frozen GLHS TOCTOU wording; never relabelled as confirmed violations."),
            "OPERATIONAL_FAILURE counts availability failures (zero in final-003).",
            "CONFIRMED_SAFE_OR_REJECTED is the remainder of the primary denominator.",
            ("The historical binary non-safe composite remains a secondary frozen "
            "endpoint and is reported unchanged below."),
        ],
        "rows": rows,
        "secondary_frozen_binary_endpoint": {
            arm: {
                "primary_endpoint_n": int(arms[arm]["primary_endpoint_n"]),
                "primary_failures": int(arms[arm]["primary_failures"]),
                "primary_rate": arms[arm]["primary_rate"],
                "wilson_95_ci": list(arms[arm]["wilson_95_ci"]),
            }
            for arm in ARMS
        },
    }


def write_three_state_primary(
    analysis_path: Path,
    output_path: Path,
    *,
    sealed_analysis: Path | None = None,
) -> dict[str, object]:
    """Read the sealed analysis and write the derived three-state table."""
    if sealed_analysis is not None and analysis_path != sealed_analysis:
        raise ValueError("govred_three_state_analysis_and_sealed_analysis_must_match")
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    table = derive_three_state_primary(analysis)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return table


DEFAULT_ANALYSIS = Path("research/govred_rivf/results/final-003-analysis-v2.json")
DEFAULT_OUTPUT = Path("research/govred_rivf/results/final-003-three-state-primary.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--sealed-analysis",
        type=Path,
        default=None,
        help="Optional alias for --analysis; used by callers to assert the "
        "sealed file is the only source.",
    )
    args = parser.parse_args()
    table = write_three_state_primary(args.analysis, args.output, sealed_analysis=args.sealed_analysis)
    print(json.dumps(table, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())