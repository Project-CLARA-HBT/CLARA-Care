"""W1-T01: recover family-level rows from immutable RIVF final-003 raw results.

Reads the four sealed ``raw_results.csv`` arms under
``artifacts/govred/2026-08-17-rivf-final-003/{ARM}/`` together with the frozen
locked manifest (for ``reporting_scope`` and per-family eligible case counts)
and emits ``research/govred_rivf/family_arm_matrix.csv``.

The matrix is AUD-018 localization input: one row per family x arm with
executed/NOT_RUN counts, the five separated AUD-012 endpoints
(invalid-commit acceptance, unintended disclosure, wrong-subject exposure,
cache revocation failure, availability failure), committed/rejected counts,
rejection auditability, committed reconstructability, and latency.

Raw rows are treated as immutable; this module never modifies them.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from evaluation.governance_adversarial.protocol import ARMS, FAMILIES, family_scope

# Immutable final-003 artifact locations relative to the repository root.
DEFAULT_RAW_ROOT = Path("artifacts/govred/2026-08-17-rivf-final-003")
DEFAULT_MANIFEST = Path(
    "artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json"
)
DEFAULT_OUTPUT = Path("research/govred_rivf/family_arm_matrix.csv")

# Established endpoint facts encoded as constants (W1 findings; regression-locked).
PRIMARY_DENOMINATOR = 210
ALL_EXECUTED = 270
NOT_RUN_PER_ARM = 180

# Mandatory-primary endpoint families: the six executable primary authorization
# drift schedules plus the audit-reconstruction control that commits by design.
# Sum of executed cases over these families is the primary endpoint denominator
# (210); audit_reconstruction_failure commits by design and is never counted as
# a primary failure.
PRIMARY_ENDPOINT_FAMILIES = frozenset({
    "authorization_consent_toctou",
    "concurrent_stale_state_write",
    "cross_subject_proposal_write",
    "revoked_consent_cache_index_reuse",
    "role_mismatch",
    "stale_thss_replay",
    "audit_reconstruction_failure",
})

# Serial authorization-drift families that show zero invalid commits in the
# strict arm (GLHS_STRICT) -- the residual is exclusively a concurrency/ordering
# family (concurrent_stale_state_write).
SERIAL_DRIFT_FAMILIES = frozenset({
    "consent_revoke",
    "policy_change",
    "role_mismatch",
    "stale_state",
    "digest_corrupt",
    "cross_subject",
    "cache_revoke",
})


def _flag(row: dict[str, str], name: str) -> bool:
    return row[name] == "true"


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[index]
    return (ordered[index - 1] + ordered[index]) / 2.0


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * 0.95))
    return ordered[index]


def _latency_format(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def load_eligible_counts(manifest: Path) -> dict[str, int]:
    """Return per-family eligible logical-case counts from the frozen manifest."""
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise TypeError("govred_manifest_cases_missing")
    counts: dict[str, int] = defaultdict(int)
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("family"), str):
            raise TypeError("govred_manifest_case_invalid")
        counts[case["family"]] += 1
    return dict(counts)


def build_family_arm_matrix(
    raw_root: Path, manifest: Path
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Build one row per family x arm from the immutable raw results.

    Returns ``(rows, endpoint_checks)`` where ``rows`` are CSV-ready rows and
    ``endpoint_checks`` aggregates the established endpoint facts derived from
    the strict arm.
    """
    eligible = load_eligible_counts(manifest)
    rows: list[dict[str, str]] = []
    for arm in ARMS:
        raw_path = raw_root / arm / "raw_results.csv"
        if not raw_path.is_file():
            raise FileNotFoundError(f"govred_raw_missing:{raw_path}")
        with raw_path.open(encoding="utf-8", newline="") as stream:
            raw = list(csv.DictReader(stream))
        for family in FAMILIES:
            family_rows = [row for row in raw if row["family"] == family]
            executed = [row for row in family_rows if row["run_status"] == "EXECUTED"]
            not_run = [row for row in family_rows if row["run_status"] == "NOT_RUN"]
            latencies = [
                float(row["latency_ms"]) for row in executed if row["latency_ms"]
            ]
            scope = family_scope(family)
            rows.append({
                "family": family,
                "reporting_scope": "primary" if scope == "primary_authorization_drift" else "secondary",
                "arm": arm,
                "eligible_n": str(eligible[family]),
                "executed_n": str(len(executed)),
                "not_run_n": str(len(not_run)),
                "invalid_commit_acceptance": str(
                    sum(_flag(row, "stale_or_unauthorized_commit") for row in executed)
                ),
                "unintended_disclosure": str(
                    sum(_flag(row, "unauthorized_disclosure") for row in executed)
                ),
                "wrong_subject_exposure": str(
                    sum(_flag(row, "wrong_subject_exposure") for row in executed)
                ),
                "cache_revocation_failure": str(
                    sum(_flag(row, "cache_index_revocation_failure") for row in executed)
                ),
                "availability_error": str(
                    sum(_flag(row, "availability_error") for row in executed)
                ),
                "committed_count": str(
                    sum(row["normalized_outcome"] == "committed" for row in executed)
                ),
                "rejected_count": str(
                    sum(row["normalized_outcome"] == "rejected" for row in executed)
                ),
                # AUD-012 split: rejection auditability = rejected operations
                # whose rejection decision is reconstructable; committed
                # reconstructability = committed operations whose transition is
                # reconstructable. The final-003 observer records the single
                # audit_reconstruction_complete boolean (AUD-021: no persisted
                # audit row is expected for rejected operations).
                "rejection_auditability": str(
                    sum(
                        row["normalized_outcome"] == "rejected"
                        and _flag(row, "audit_reconstruction_complete")
                        for row in executed
                    )
                ),
                "committed_reconstructability": str(
                    sum(
                        row["normalized_outcome"] == "committed"
                        and _flag(row, "audit_reconstruction_complete")
                        for row in executed
                    )
                ),
                "latency_ms": _latency_format(_median(latencies)),
                "latency_p95_ms": _latency_format(_p95(latencies)),
            })
    checks = _endpoint_checks(raw_root)
    return rows, checks


def _endpoint_checks(raw_root: Path) -> dict[str, int]:
    """Derive the established endpoint facts from the GLHS_STRICT raw rows."""
    strict_path = raw_root / "GLHS_STRICT" / "raw_results.csv"
    with strict_path.open(encoding="utf-8", newline="") as stream:
        raw = list(csv.DictReader(stream))
    executed = [row for row in raw if row["run_status"] == "EXECUTED"]
    strict = [row for row in raw if row["run_status"] == "NOT_RUN"]
    residual_families = {
        row["family"]
        for row in executed
        if _flag(row, "stale_or_unauthorized_commit")
        and row["family"] in PRIMARY_ENDPOINT_FAMILIES
        and row["family"] != "audit_reconstruction_failure"
    }
    primary_executed = sum(
        1
        for row in executed
        if row["family"] in PRIMARY_ENDPOINT_FAMILIES
    )
    audit_by_design = sum(
        1
        for row in executed
        if row["family"] == "audit_reconstruction_failure"
        and row["normalized_outcome"] == "committed"
    )
    return {
        "primary_denominator": primary_executed,
        "all_executed": len(executed),
        "not_run_per_arm": len(strict),
        "strict_residual_families": len(residual_families),
        "audit_by_design_commits": audit_by_design,
        "strict_invalid_commit_acceptance": sum(
            _flag(row, "stale_or_unauthorized_commit") for row in executed
        ),
    }


def write_family_arm_matrix(raw_root: Path, manifest: Path, output: Path) -> dict[str, int]:
    rows, checks = build_family_arm_matrix(raw_root, manifest)
    if not rows:
        raise ValueError("govred_family_arm_matrix_empty")
    columns = list(rows[0].keys())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    checks = write_family_arm_matrix(args.raw_root, args.manifest, args.output)
    print(json.dumps({"output": str(args.output), **checks}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
