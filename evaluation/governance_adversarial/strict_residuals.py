"""W1-T02/T03: localize and root-cause the GLHS_STRICT residual failures.

Reads the immutable GLHS_STRICT ``raw_results.csv`` and the frozen locked
manifest, and emits ``research/govred_rivf/strict_residual_failure_manifest.jsonl``
with one structural line per failed logical case, plus a root-cause taxonomy
summary.

Established findings encoded here (regression-locked):

- all 30 GLHS_STRICT mandatory-primary residuals are in family
  ``concurrent_stale_state_write``;
- every serial authorization-drift family (consent/policy/role/stale-state/
  digest/cross-subject/cache-revoke) has zero invalid commits in the strict arm;
- the secondary ``audit_reconstruction_failure`` family commits by design (30)
  and is NOT a primary failure (excluded from the residual manifest);
- primary denominator = 210, all-executed = 270, NOT_RUN = 180 per arm.

Root causes come from the prespecified W1-T03 taxonomy:
IMPLEMENTATION_DEFECT, MISSING_CONTRACT_COORDINATE, NON_ATOMIC_GOVERNANCE_READ,
CACHE_ONLY_FAILURE, OBSERVER_CLASSIFICATION_ERROR, PROTOCOL_EXPECTATION_ERROR,
EXPECTED_VALID_OPERATION, INDETERMINATE_ORDERING, OTHER_EXPLAINED.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.governance_adversarial.protocol import family_scope

DEFAULT_RAW = Path("artifacts/govred/2026-08-17-rivf-final-003/GLHS_STRICT/raw_results.csv")
DEFAULT_MANIFEST = Path(
    "artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json"
)
DEFAULT_OUTPUT = Path("research/govred_rivf/strict_residual_failure_manifest.jsonl")
DEFAULT_TAXONOMY_OUTPUT = Path("research/govred_rivf/strict_residual_root_cause_taxonomy.json")

ROOT_CAUSES = frozenset(
    {
        "IMPLEMENTATION_DEFECT",
        "MISSING_CONTRACT_COORDINATE",
        "NON_ATOMIC_GOVERNANCE_READ",
        "CACHE_ONLY_FAILURE",
        "OBSERVER_CLASSIFICATION_ERROR",
        "PROTOCOL_EXPECTATION_ERROR",
        "EXPECTED_VALID_OPERATION",
        "INDETERMINATE_ORDERING",
        "OTHER_EXPLAINED",
    }
)

# Mandatory-primary families retained for the strict endpoint denominator.
PRIMARY_ENDPOINT_FAMILIES = frozenset(
    {
        "authorization_consent_toctou",
        "concurrent_stale_state_write",
        "cross_subject_proposal_write",
        "revoked_consent_cache_index_reuse",
        "role_mismatch",
        "stale_thss_replay",
        "audit_reconstruction_failure",
    }
)

# Prespecified established facts (regression-locked W1 findings).
PRIMARY_DENOMINATOR = 210
ALL_EXECUTED = 270
NOT_RUN_PER_ARM = 180
EXPECTED_STRICT_RESIDUALS = 30

# Per-family mutation classes (drift axis being mutated) for the residual lines.
MUTATION_CLASS_BY_FAMILY: dict[str, str] = {
    "concurrent_stale_state_write": "concurrent_stale_state_write",
    "authorization_consent_toctou": "consent_toctou",
    "role_mismatch": "actor_role_mismatch",
    "stale_thss_replay": "stale_state_replay",
    "digest_expiry_tamper_replay": "digest_corruption_replay",
    "cross_subject_proposal_write": "cross_subject_proposal_write",
    "revoked_consent_cache_index_reuse": "consent_revoke_cache_index_reuse",
    "policy_version_change": "policy_version_change",
    "derived_cache_persistence_after_revocation": "derived_cache_persistence_after_revocation",
    "audit_reconstruction_failure": "audit_reconstruction_failure",
}

# Serial authorization-drift families expected to show zero invalid commits in
# the strict arm. Each maps to the drift axis used in the positive-control schema.
SERIAL_DRIFT_FAMILIES: dict[str, str] = {
    "authorization_consent_toctou": "consent_revoke",
    "revoked_consent_cache_index_reuse": "consent_revoke",
    "policy_version_change": "policy_change",
    "role_mismatch": "actor_change",
    "stale_thss_replay": "stale_state",
    "digest_expiry_tamper_replay": "digest_corrupt",
    "cross_subject_proposal_write": "cross_subject",
    "derived_cache_persistence_after_revocation": "cache_revoke",
}


def _flag(row: dict[str, str], name: str) -> bool:
    return row[name] == "true"


def _is_failure(row: dict[str, str]) -> bool:
    """A mandatory-primary failure: an invalid commit outside the by-design control."""
    if row["family"] == "audit_reconstruction_failure":
        return False
    return _flag(row, "stale_or_unauthorized_commit") or _flag(row, "successful_bypass")


def root_cause_for(row: dict[str, str]) -> tuple[str, list[str]]:
    """Return (primary_root_cause, secondary_tags) for a strict residual row.

    All mandatory-primary residuals are concurrent stale-state writes; per the
    frozen GLHS TOCTOU analysis these are classified as INDETERMINATE_ORDERING
    (a concurrency/ordering family, not a serial authorization drift defect).
    """
    family = row["family"]
    if family == "concurrent_stale_state_write":
        return "INDETERMINATE_ORDERING", [
            "concurrent_stale_state_write",
            "concurrency",
            "ordering",
            "toctou",
        ]
    if family == "audit_reconstruction_failure":
        return "EXPECTED_VALID_OPERATION", ["audit_reconstruction_failure", "by_design_commit"]
    return "OTHER_EXPLAINED", [family]


def load_manifest(manifest: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise TypeError("govred_manifest_cases_missing")
    return {str(case["case_id"]): case for case in cases if isinstance(case, dict)}


def build_residuals(raw: Path, manifest: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (residual_lines, taxonomy) derived from the immutable strict arm.

    One line per failed mandatory-primary logical case; the by-design
    audit_reconstruction_failure control is excluded from the manifest.
    """
    cases = load_manifest(manifest)
    with raw.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    residuals: list[dict[str, Any]] = []
    by_design: Counter[str] = Counter()
    for row in rows:
        if row["run_status"] != "EXECUTED":
            continue
        family = row["family"]
        if family == "audit_reconstruction_failure":
            if row["normalized_outcome"] == "committed":
                by_design["audit_reconstruction_failure"] += 1
            continue
        if not _is_failure(row):
            continue
        if family not in PRIMARY_ENDPOINT_FAMILIES:
            raise ValueError(f"govred_unexpected_strict_residual_family:{family}")
        case = cases[row["case_id"]]
        primary_root_cause, secondary_tags = root_cause_for(row)
        residuals.append(
            {
                "case_id": row["case_id"],
                "family": family,
                "reporting_scope": family_scope(family),
                "mutation_class": MUTATION_CLASS_BY_FAMILY.get(family, family),
                "expected_invariant": case["expected_invariant"],
                "normalized_observed_outcome": row["normalized_outcome"],
                "observation_artifact_sha256": row["observation_artifact_sha256"],
                "primary_root_cause": primary_root_cause,
                "secondary_tags": secondary_tags,
            }
        )

    # Serial drift families must have zero invalid commits in the strict arm.
    strict_executed = [row for row in rows if row["run_status"] == "EXECUTED"]
    serial_invalid = {
        family: sum(
            _flag(row, "stale_or_unauthorized_commit") or _flag(row, "successful_bypass")
            for row in strict_executed
            if row["family"] == family
        )
        for family in SERIAL_DRIFT_FAMILIES
    }
    taxonomy = {
        "schema_version": "govred-strict-residual-taxonomy-v1",
        "run_id": "2026-08-17-rivf-final-003",
        "arm": "GLHS_STRICT",
        "total_residuals": len(residuals),
        "by_primary_root_cause": dict(
            Counter(str(item["primary_root_cause"]) for item in residuals)
        ),
        "by_family": dict(Counter(str(item["family"]) for item in residuals)),
        "secondary_tags": sorted({tag for item in residuals for tag in item["secondary_tags"]}),
        "by_design_commits_excluded": dict(by_design),
        "serial_drift_invalid_commits": serial_invalid,
        "established_facts": {
            "primary_denominator": PRIMARY_DENOMINATOR,
            "all_executed": ALL_EXECUTED,
            "not_run_per_arm": NOT_RUN_PER_ARM,
            "expected_strict_residuals": EXPECTED_STRICT_RESIDUALS,
        },
    }
    return residuals, taxonomy


def write_residuals(
    raw: Path, manifest: Path, output: Path, taxonomy_output: Path
) -> dict[str, object]:
    residuals, taxonomy = build_residuals(raw, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for item in residuals:
            stream.write(json.dumps(item, sort_keys=True) + "\n")
    taxonomy_output.parent.mkdir(parents=True, exist_ok=True)
    taxonomy_output.write_text(
        json.dumps(taxonomy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return taxonomy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--taxonomy-output", type=Path, default=DEFAULT_TAXONOMY_OUTPUT)
    args = parser.parse_args()
    taxonomy = write_residuals(args.raw, args.manifest, args.output, args.taxonomy_output)
    print(json.dumps(taxonomy, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
