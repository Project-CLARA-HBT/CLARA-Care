"""Create reviewable GovRed locked-test freeze candidates without freezing a run."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.governance_adversarial.protocol import build_development_manifest


def _sha256(value: object) -> str:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare(*, seed: int, repetitions: int, statistics_plan: dict[str, object]) -> dict[str, dict[str, object]]:
    """Build artifacts that require an independent reviewer before execution."""

    statistics_plan_sha256 = _sha256(statistics_plan)
    candidate = build_development_manifest(
        seed=seed,
        repetitions=repetitions,
        statistics_plan_sha256=statistics_plan_sha256,
    )
    candidate.update({
        "manifest_id": "govred-rivf-locked-test-candidate",
        "partition": "locked_test_candidate",
        "freeze_state": "candidate_pending_independent_review",
    })
    for case in candidate["cases"]:
        assert isinstance(case, dict)
        case["case_id"] = str(case["case_id"]).replace("dev-", "candidate-locked-", 1)

    final_statistics_plan = dict(statistics_plan)
    final_statistics_plan.update({
        "status": "candidate_pending_independent_review",
        "candidate_source_sha256": statistics_plan_sha256,
        "finalization_requirement": (
            "An independent reviewer must approve this plan, change status to frozen, "
            "and bind its SHA-256 to the final manifest before execution."
        ),
    })
    final_manifest = dict(candidate)
    final_manifest.update({
        "manifest_id": "govred-rivf-final-locked-manifest-template",
        "partition": "locked_test",
        "freeze_state": "final_template_pending_independent_review",
        "final_statistics_plan_sha256": _sha256(final_statistics_plan),
        "independent_curator_attestation": False,
        "finalization_notes": (
            "This is not frozen and must not be passed to execute.py. A separate independent "
            "review must attest the final statistics plan, manifest, adapter revision, and partition."
        ),
    })
    return {
        "locked_test_candidate.json": candidate,
        "final_statistics_plan_candidate.json": final_statistics_plan,
        "final_locked_manifest_template.json": final_manifest,
        "freeze_preparation_receipt.json": {
            "schema_version": "govred-freeze-preparation-receipt-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "status": "candidate_and_template_only_not_frozen_not_executed",
            "candidate_manifest_sha256": _sha256(candidate),
            "final_statistics_plan_candidate_sha256": _sha256(final_statistics_plan),
            "final_manifest_template_sha256": _sha256(final_manifest),
            "required_before_execution": [
                "independent_review_of_locked_partition",
                "independent_review_of_statistics_plan",
                "final_manifest_status_frozen",
                "final_statistics_plan_status_frozen",
                "isolated_stack_adapter_preflight",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--statistics-plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--repetitions", type=int, default=30)
    args = parser.parse_args()
    plan = json.loads(args.statistics_plan.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        parser.error("govred_statistics_plan_must_be_object")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in prepare(seed=args.seed, repetitions=args.repetitions, statistics_plan=plan).items():
        (args.output_dir / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
