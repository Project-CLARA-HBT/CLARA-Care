from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

REQUIRED = frozenset(
    {
        "version",
        "status",
        "primary_cluster",
        "external_primary_endpoints",
        "comparisons",
        "uncertainty",
        "agreement",
        "multiplicity",
        "stratification",
        "negative_results_visible",
        "clinical_inference",
    }
)


def validate(path: Path, *, final: bool = False) -> None:
    plan = load_frozen_json(path)
    missing = REQUIRED.difference(plan)
    if missing:
        raise FreezeError("statistics_plan_fields_missing:" + ",".join(sorted(missing)))
    if final and plan["status"] != "frozen":
        raise FreezeError("statistics_plan_not_frozen")
    if plan["primary_cluster"] != "subject_token":
        raise FreezeError("subject_cluster_required")
    if plan["clinical_inference"] is not False or plan["negative_results_visible"] is not True:
        raise FreezeError("statistics_claim_boundary_invalid")
    if not plan["external_primary_endpoints"] or not plan["uncertainty"]:
        raise FreezeError("statistics_endpoints_or_uncertainty_missing")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        validate(args.plan, final=args.final)
    except FreezeError as exc:
        parser.error(str(exc))
