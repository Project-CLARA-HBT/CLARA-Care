"""Validate that a frozen portability protocol keeps separate domain rules."""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

REQUIRED_DOMAIN_FIELDS = frozenset(
    {
        "semantic_slots",
        "evidence_classes",
        "authority_rule",
        "valid_time",
        "lifecycle",
        "protected_conflict",
        "escalation",
    }
)


def validate(path: Path, *, final: bool = False) -> None:
    policy = load_frozen_json(path)
    domains = policy.get("domains")
    if not isinstance(domains, dict) or len(domains) < 3:
        raise FreezeError("at_least_three_domain_policies_required")
    if "medication" not in domains:
        raise FreezeError("medication_policy_required")
    if final and policy.get("status") != "frozen":
        raise FreezeError("domain_policy_not_frozen")
    for name, rules in domains.items():
        if not isinstance(rules, dict) or REQUIRED_DOMAIN_FIELDS.difference(rules):
            raise FreezeError(f"incomplete_domain_policy:{name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        validate(args.policy, final=args.final)
    except FreezeError as exc:
        parser.error(str(exc))
