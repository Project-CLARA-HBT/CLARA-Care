"""W1-T05: matched positive-control schema for the primary drift families.

Defines authority-preserving clean controls for every primary drift family so a
system that "rejects everything" cannot look safe (AUD-016).  For each invalid
mutation a matched valid control keeps authority valid, state current, digest
intact, unexpired, and subject-matched; the expected outcome is a legitimate
commit (positive control) versus rejection (invalid mutation).

This is a static schema module: it emits the matched positive-control schema
JSON and validation helpers.  It performs no boundary execution and imports no
production code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Prespecified W1-T05 matched pairs: invalid mutation vs matched valid control.
POSITIVE_CONTROLS: dict[str, dict[str, str]] = {
    "consent_revoke_invalid": {
        "valid_control": "consent_unchanged_valid",
        "family": "revoked_consent_cache_index_reuse",
        "mutation_class": "consent_revoke",
        "mutation": "revoke consent before repeat governed disclosure",
        "expected_invalid_outcome": "rejected",
        "expected_valid_outcome": "committed",
    },
    "policy_change_invalid": {
        "valid_control": "policy_unchanged_valid",
        "family": "policy_version_change",
        "mutation_class": "policy_change",
        "mutation": "advance policy version before commit admission",
        "expected_invalid_outcome": "rejected",
        "expected_valid_outcome": "committed",
    },
    "actor_change_invalid": {
        "valid_control": "actor_stable_valid",
        "family": "role_mismatch",
        "mutation_class": "actor_role_mismatch",
        "mutation": "change actor/role between disclosure and commit",
        "expected_invalid_outcome": "rejected",
        "expected_valid_outcome": "committed",
    },
    "state_advance_invalid": {
        "valid_control": "same_state_valid",
        "family": "concurrent_stale_state_write",
        "mutation_class": "concurrent_stale_state_write",
        "mutation": "advance state concurrently between disclosure and write admission",
        "expected_invalid_outcome": "rejected",
        "expected_valid_outcome": "committed",
    },
    "digest_corrupt_invalid": {
        "valid_control": "digest_intact_valid",
        "family": "digest_expiry_tamper_replay",
        "mutation_class": "digest_corruption_replay",
        "mutation": "corrupt the proposal/snapshot digest before commit",
        "expected_invalid_outcome": "rejected",
        "expected_valid_outcome": "committed",
    },
    "expired_invalid": {
        "valid_control": "unexpired_valid",
        "family": "stale_thss_replay",
        "mutation_class": "stale_state_replay",
        "mutation": "replay an expired THSS token/state before commit",
        "expected_invalid_outcome": "rejected",
        "expected_valid_outcome": "committed",
    },
    "cross_subject_invalid": {
        "valid_control": "same_subject_valid",
        "family": "cross_subject_proposal_write",
        "mutation_class": "cross_subject_proposal_write",
        "mutation": "propose a persistent write for a different subject",
        "expected_invalid_outcome": "rejected",
        "expected_valid_outcome": "committed",
    },
}

# Authority-preserving coordinates that must remain unchanged in the matched
# valid control (same subject/task/evidence, authority valid, state current).
PRESERVED_COORDINATES = (
    "subject",
    "actor",
    "purpose",
    "task_binding",
    "evidence",
    "consent_granted",
    "policy_version_current",
    "state_version_current",
    "digest_intact",
    "token_unexpired",
)

# Per-drift axis mapping used by the strict residual taxonomy.
DRIFT_AXIS_BY_FAMILY: dict[str, str] = {
    "revoked_consent_cache_index_reuse": "consent_revoke",
    "policy_version_change": "policy_change",
    "role_mismatch": "actor_change",
    "concurrent_stale_state_write": "state_advance",
    "digest_expiry_tamper_replay": "digest_corrupt",
    "stale_thss_replay": "expired",
    "cross_subject_proposal_write": "cross_subject",
}


def positive_control_schema() -> dict[str, Any]:
    """Return the full matched positive-control schema (JSON-serializable)."""
    return {
        "schema_version": "govred-positive-control-schema-v1",
        "purpose": (
            "Matched authority-preserving controls per primary drift family so "
            "valid-transition rejection is separated from invalid-transition "
            "acceptance (AUD-016)."
        ),
        "preserved_coordinates": list(PRESERVED_COORDINATES),
        "drift_axis_by_family": dict(sorted(DRIFT_AXIS_BY_FAMILY.items())),
        "controls": {
            name: {
                **spec,
                "valid_control": spec["valid_control"],
            }
            for name, spec in POSITIVE_CONTROLS.items()
        },
    }


def write_controls_schema(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(positive_control_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/govred_rivf/positive_control_schema.json"),
    )
    args = parser.parse_args()
    write_controls_schema(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
