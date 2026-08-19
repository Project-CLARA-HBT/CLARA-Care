"""E-009: fresh holdout freeze with a mandatory independent-human authorship gate.

GRD-05: freeze 30-60 new logical schedules after current results remain
sealed, preferably independently authored; report separately; never merge into
final-003.

The authorship gate is **manual**: schedules must be authored by independent
human authors. LLM-generated or LLM-simulated authorship is explicitly
forbidden — a holdout whose schedules were written by the same model that
observed the results would not be independent. This module therefore:

- builds a **skeleton** of 30-60 logical schedules (structure only, no oracle
  expectations);
- refuses to mark any skeleton as frozen/executed until every schedule carries
  an independent-human authorship record (author id + authored date);
- never executes anything: execution requires real independent authors and a
  separate, later freeze.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from evaluation.governance_adversarial.protocol import ARMS, FAMILIES, family_scope

SCHEMA_VERSION = "govred-holdout-protocol-v1"
AUTHORSHIP_MODE = "INDEPENDENT_HUMAN_REQUIRED"
FORBIDDEN_AUTHORSHIP_MODES = frozenset({"llm_simulated", "llm_authored"})

MIN_SCHEDULES = 30
MAX_SCHEDULES = 60

#: Families whose invariant a holdout schedule may exercise. The skeleton keeps
#: primary authorization-drift families weighted (3 per family) and adds the
#: implementable secondary families; prompt-injection families are excluded
#: (E-006).
_HOLDOUT_FAMILIES = tuple(
    family
    for family in FAMILIES
    if family not in {"gst_bypass_prompt", "patient_evidence_prompt_injection"}
)


@dataclass(frozen=True)
class HoldoutScheduleSkeleton:
    """One holdout schedule skeleton (structure only, authorship pending)."""

    schedule_id: str
    family: str
    reporting_scope: str
    invariant: str
    arm_applicability: tuple[str, ...]
    authorship: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "family": self.family,
            "reporting_scope": self.reporting_scope,
            "invariant": self.invariant,
            "arm_applicability": list(self.arm_applicability),
            "authorship": self.authorship,
        }


def _skeleton_ids() -> tuple[str, ...]:
    ids: list[str] = []
    for family in _HOLDOUT_FAMILIES:
        for index in range(1, 4):
            ids.append(f"holdout-v1-{family}-{index:03d}")
    return tuple(ids)


def build_holdout_schedules(count: int | None = None) -> list[dict[str, object]]:
    """Build the holdout schedule skeleton.

    The default skeleton yields 3 schedules per eligible family. ``count`` may
    trim to a requested size between ``MIN_SCHEDULES`` and ``MAX_SCHEDULES``
    (always a multiple of the eligible family count, trimming the last
    families' final schedules so the set stays balanced).
    """
    ids = list(_skeleton_ids())
    if count is not None:
        if count < MIN_SCHEDULES or count > MAX_SCHEDULES:
            raise ValueError(
                f"govred_holdout_count_out_of_range:{count} (required 30-60)"
            )
        if count > len(ids):
            raise ValueError(f"govred_holdout_count_exceeds_skeleton:{count}")
        ids = ids[:count]
    schedules: list[dict[str, object]] = []
    for schedule_id in ids:
        family = schedule_id.split("-", 3)[2]
        schedules.append(
            HoldoutScheduleSkeleton(
                schedule_id=schedule_id,
                family=family,
                reporting_scope=family_scope(family),
                invariant="prohibited_disclosure_or_unauthorized_commit_rejected",
                arm_applicability=tuple(ARMS),
            ).to_dict()
        )
    return schedules


def build_holdout_freeze(
    schedules: list[dict[str, object]],
    *,
    authors: dict[str, str],
) -> dict[str, object]:
    """Validate authorship and build the frozen (unexecuted) holdout manifest.

    ``authors`` maps each schedule id to an independent-human author id. The
    freeze fails closed if any schedule lacks authorship, if the mode is not
    independent human, or if the schedule count is out of range.
    """
    if not MIN_SCHEDULES <= len(schedules) <= MAX_SCHEDULES:
        raise ValueError(
            f"govred_holdout_count_out_of_range:{len(schedules)} (required 30-60)"
        )
    for schedule in schedules:
        schedule_id = str(schedule["schedule_id"])
        author_id = authors.get(schedule_id)
        if not isinstance(author_id, str) or not author_id:
            raise ValueError(f"govred_holdout_missing_independent_human_author:{schedule_id}")
        if not author_id.startswith("human-author:"):
            raise ValueError(f"govred_holdout_author_must_be_independent_human:{schedule_id}")
        schedule["authorship"] = {
            "mode": AUTHORSHIP_MODE,
            "author_id": author_id,
            "authored_at": datetime.now(UTC).isoformat(),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "FROZEN_UNEXECUTED_MANUAL_AUTHORSHIP_GATE",
        "execution_status": "NOT_EXECUTED",
        "authorship_gate": {
            "required_mode": AUTHORSHIP_MODE,
            "forbidden_modes": sorted(FORBIDDEN_AUTHORSHIP_MODES),
            "note": "independent human authorship required; never simulated "
            "with an LLM; do not execute without real independent authors",
        },
        "reporting": "separate from final-003; never merged",
        "schedule_count": len(schedules),
        "frozen_at": datetime.now(UTC).isoformat(),
        "schedules": schedules,
    }


def validate_holdout_freeze(value: object) -> dict[str, object]:
    """Fail closed on a non-frozen, LLM-authored, or executed holdout."""
    if not isinstance(value, dict):
        raise TypeError("govred_holdout_freeze_not_object")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("govred_holdout_schema_invalid")
    if value.get("status") != "FROZEN_UNEXECUTED_MANUAL_AUTHORSHIP_GATE":
        raise ValueError("govred_holdout_not_frozen_unexecuted")
    if value.get("execution_status") != "NOT_EXECUTED":
        raise ValueError("govred_holdout_must_not_be_executed")
    schedules = value.get("schedules")
    if not isinstance(schedules, list):
        raise TypeError("govred_holdout_schedules_missing")
    if not MIN_SCHEDULES <= len(schedules) <= MAX_SCHEDULES:
        raise ValueError(f"govred_holdout_count_out_of_range:{len(schedules)}")
    for schedule in schedules:
        authorship = schedule.get("authorship")
        if not isinstance(authorship, dict):
            raise TypeError(f"govred_holdout_missing_authorship:{schedule.get('schedule_id')}")
        mode = authorship.get("mode")
        if mode != AUTHORSHIP_MODE:
            raise ValueError(f"govred_holdout_authorship_mode_forbidden:{mode}")
        if not str(authorship.get("author_id", "")).startswith("human-author:"):
            raise ValueError("govred_holdout_author_not_independent_human")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "VALIDATED_FROZEN_HOLDOUT_NOT_EXECUTED",
        "database_executed": False,
        "result_emitted": False,
        "schedule_count": len(schedules),
    }


DEFAULT_OUTPUT_DIR = Path("research/govred_rivf/holdout_v1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--count", type=int, default=None, help="Optional schedule count in [30, 60].")
    parser.add_argument("--freeze", action="store_true", help="Write the frozen (authorship-gated) manifest.")
    args = parser.parse_args()

    schedules = build_holdout_schedules(args.count)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.freeze:
        raise SystemExit(
            "govred_holdout_freeze_is_manual: populate independent human "
            "authors and call build_holdout_freeze() yourself; the CLI never "
            "simulates authorship"
        )

    skeleton = {
        "schema_version": SCHEMA_VERSION,
        "status": "SKELETON_NOT_AUTHORED",
        "authorship_gate": {
            "required_mode": AUTHORSHIP_MODE,
            "forbidden_modes": sorted(FORBIDDEN_AUTHORSHIP_MODES),
            "note": "independent human authorship required; never simulated "
            "with an LLM; do not execute without real independent authors",
        },
        "schedule_count": len(schedules),
        "created_at": datetime.now(UTC).isoformat(),
        "schedules": schedules,
    }
    (args.output_dir / "schedules_skeleton.json").write_text(
        json.dumps(skeleton, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "SKELETON_NOT_AUTHORED", "schedule_count": len(schedules)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())