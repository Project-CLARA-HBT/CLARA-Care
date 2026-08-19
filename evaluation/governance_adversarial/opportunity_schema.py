"""E-007/E-008: audit opportunity schemas and conditional denominators.

GRD-04: define separate denominators for (a) rejected operations where a
rejection decision record is required, (b) committed operations requiring
exact reconstruction, and (c) governance mutations requiring trace linkage.
Completeness is reported **only within its eligible opportunity set**; raw
cross-arm counts are never implied to be completeness.

This module computes, per family/arm from the immutable final-003 raw rows:

- the **eligible opportunity set** for each of the three kinds;
- how many of those eligible operations carry the required record;
- the completeness fraction **within that eligible set only**;
- whether the frozen final-003 observer emitted the required field at all
  (``not_emitted`` is reported honestly, never as a zero-failure result).

It emits ``research/govred_rivf/audit_opportunity_denominators.md`` plus a
structured JSON artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluation.governance_adversarial.family_contracts import family_contract
from evaluation.governance_adversarial.protocol import ARMS

SCHEMA_VERSION = "govred-audit-opportunity-denominators-v1"

REJECTED_OPERATION_DECISION_RECORD = "rejected_operation_decision_record"
COMMITTED_OPERATION_EXACT_RECONSTRUCTION = "committed_operation_exact_reconstruction"
GOVERNANCE_MUTATION_TRACE_LINKAGE = "governance_mutation_trace_linkage"

OPPORTUNITY_KINDS = (
    REJECTED_OPERATION_DECISION_RECORD,
    COMMITTED_OPERATION_EXACT_RECONSTRUCTION,
    GOVERNANCE_MUTATION_TRACE_LINKAGE,
)

#: Required record fields per opportunity kind. The frozen final-003 observer
#: emits only the single ``audit_reconstruction_complete`` boolean; the
#: structured rejection record and transaction trace are defined by the newer
#: observer schema (``glhs-postgres-governance-toctou-final-v2.1``) and are
#: ``not_emitted`` in the final-003 raw rows.
_REQUIRED_FIELDS = {
    REJECTED_OPERATION_DECISION_RECORD: (
        "rejection_reason_code",
        "rejection_coordinates",
        "zero_transition_rows",
    ),
    COMMITTED_OPERATION_EXACT_RECONSTRUCTION: ("audit_reconstruction_complete",),
    GOVERNANCE_MUTATION_TRACE_LINKAGE: ("transaction_trace", "commit_order_evidence"),
}

#: Families exercising a persisted governance mutation (writer type neither
#: ``none`` nor the prompt-attempt stub). These form the governance-mutation
#: trace-linkage opportunity set.
def _is_governance_mutation_family(family: str) -> bool:
    writer = family_contract(family).governance_writer_type
    return writer not in {"none", "prompt_attempt"}


DEFAULT_RAW_ROOT = Path("artifacts/govred/2026-08-17-rivf-final-003")
DEFAULT_OUTPUT_JSON = Path("research/govred_rivf/audit_opportunity_denominators.json")
DEFAULT_OUTPUT_MD = Path("research/govred_rivf/audit_opportunity_denominators.md")


def _load_raw(raw_root: Path) -> dict[str, list[dict[str, str]]]:
    rows: dict[str, list[dict[str, str]]] = {}
    for arm in ARMS:
        path = raw_root / arm / "raw_results.csv"
        if not path.is_file():
            raise FileNotFoundError(f"govred_raw_missing:{path}")
        with path.open(encoding="utf-8", newline="") as stream:
            rows[arm] = list(csv.DictReader(stream))
    return rows


def _record_status(row: dict[str, str], required: tuple[str, ...]) -> tuple[bool, list[str]]:
    """Return ``(complete, problems)`` for a row against the required fields.

    Problems distinguish ``<field>:not_emitted`` (column absent from the
    frozen observer) from ``<field>:missing`` (column present but the record
    value is falsy/``false``).
    """
    problems: list[str] = []
    complete = True
    for field in required:
        if field not in row:
            complete = False
            problems.append(f"{field}:not_emitted")
            continue
        value = row[field]
        present = value not in {"", "false", "False"}
        if field == "audit_reconstruction_complete":
            present = value == "true"
        if not present:
            complete = False
            problems.append(f"{field}:missing")
    return complete, problems


def _eligible_rows(
    rows: dict[str, list[dict[str, str]]],
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Split executed rows per arm/family by opportunity eligibility."""
    eligible: dict[str, dict[str, list[dict[str, str]]]] = {
        kind: defaultdict(list) for kind in OPPORTUNITY_KINDS
    }
    for arm in ARMS:
        for row in rows[arm]:
            if row["run_status"] != "EXECUTED":
                continue
            family = row["family"]
            outcome = row["normalized_outcome"]
            if outcome == "rejected":
                eligible[REJECTED_OPERATION_DECISION_RECORD][(arm, family)].append(row)
            if outcome == "committed":
                eligible[COMMITTED_OPERATION_EXACT_RECONSTRUCTION][(arm, family)].append(row)
            if _is_governance_mutation_family(family):
                eligible[GOVERNANCE_MUTATION_TRACE_LINKAGE][(arm, family)].append(row)
    return eligible


def build_opportunity_denominators(raw_root: Path) -> dict[str, Any]:
    """Compute completeness within each eligible opportunity set only."""
    raw = _load_raw(raw_root)
    eligible = _eligible_rows(raw)
    rows_out: list[dict[str, object]] = []
    for kind in OPPORTUNITY_KINDS:
        required = _REQUIRED_FIELDS[kind]
        for (arm, family) in sorted(eligible[kind]):
            group = eligible[kind][(arm, family)]
            complete_n = 0
            missing_fields: dict[str, int] = defaultdict(int)
            emitted_count = 0
            for row in group:
                complete, problems = _record_status(row, required)
                if complete:
                    complete_n += 1
                for problem in problems:
                    missing_fields[problem] += 1
                if all(field in row for field in required):
                    emitted_count += 1
            reporting_scope = (
                "primary_authorization_drift"
                if family
                in {
                    "authorization_consent_toctou", "concurrent_stale_state_write",
                    "cross_subject_retrieval", "cross_subject_proposal_write",
                    "policy_version_change", "purpose_mismatch",
                    "revoked_consent_cache_index_reuse",
                    "role_mismatch", "stale_thss_replay",
                }
                else "secondary_robustness_stress"
            )
            rows_out.append({
                "opportunity_kind": kind,
                "arm": arm,
                "family": family,
                "reporting_scope": reporting_scope,
                "eligible_opportunity_n": len(group),
                "complete_n": complete_n,
                "completeness_within_eligible_set": (
                    complete_n / len(group) if group else None
                ),
                "required_record": list(required),
                "missing_fields": dict(missing_fields),
                "observer_emitted_required_record": emitted_count == len(group),
            })
    summary: dict[str, dict[str, object]] = {}
    for kind in OPPORTUNITY_KINDS:
        kind_rows = [row for row in rows_out if row["opportunity_kind"] == kind]
        eligible_n = sum(int(row["eligible_opportunity_n"]) for row in kind_rows)
        complete_n = sum(int(row["complete_n"]) for row in kind_rows)
        emitted = all(row["observer_emitted_required_record"] for row in kind_rows)
        summary[kind] = {
            "eligible_opportunity_n": eligible_n,
            "complete_n": complete_n,
            "completeness_within_eligible_set": (complete_n / eligible_n) if eligible_n else None,
            "observer_emitted_required_record": emitted,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "immutable final-003 raw_results.csv (all four arms)",
        "gr_requirement": "GRD-04 audit opportunity denominators",
        "reporting_rule": "completeness is reported ONLY within each eligible "
        "opportunity set; raw cross-arm counts are never completeness",
        "summary": summary,
        "rows": rows_out,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = [
        "# GovRed RIVF — Audit opportunity denominators (E-007/E-008, GRD-04)",
        "",
        ("GRD-04 defines separate denominators and requires completeness to be "
        "reported **only within each eligible opportunity set**. Raw cross-arm "
        "counts (e.g. ``audit_reconstruction_complete`` totals) are never "
        "completeness."),
        "",
        "## Opportunity kinds and eligibility",
        "",
        "| Kind | Eligible set | Required record |",
        "| --- | --- | --- |",
        "| rejected_operation_decision_record | executed **rejected** operations | rejection reason code + coordinates + zero-transition-rows |",
        "| committed_operation_exact_reconstruction | executed **committed** operations | exact reconstruction (transition + state version + snapshot linkage) |",
        "| governance_mutation_trace_linkage | executed governance-mutation families | transaction trace + commit-order evidence |",
        "",
        "## Summary (completeness within eligible sets only)",
        "",
        "| Kind | eligible_n | complete_n | completeness (eligible set only) | observer emitted? |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for kind in OPPORTUNITY_KINDS:
        summary = payload["summary"][kind]
        completeness = summary["completeness_within_eligible_set"]
        completeness_str = "n/a (0 eligible)" if completeness is None else f"{completeness:.3f}"
        emitted = "yes" if summary["observer_emitted_required_record"] else "no"
        lines.append(
            f"| {kind} | {summary['eligible_opportunity_n']} | "
            f"{summary['complete_n']} | {completeness_str} | {emitted} |"
        )
    lines += [
        "",
        "## Per family/arm detail (eligibility only)",
        "",
        "| opportunity_kind | arm | family | eligible_n | complete_n | completeness | observer emitted? |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        completeness = row["completeness_within_eligible_set"]
        completeness_str = "n/a" if completeness is None else f"{completeness:.3f}"
        emitted = "yes" if row["observer_emitted_required_record"] else "no"
        lines.append(
            f"| {row['opportunity_kind']} | {row['arm']} | {row['family']} | "
            f"{row['eligible_opportunity_n']} | {row['complete_n']} | "
            f"{completeness_str} | {emitted} |"
        )
    lines += [
        "",
        "## Honest interpretation",
        "",
        ("- The frozen final-003 observer emits only the single "
        "``audit_reconstruction_complete`` boolean and no persisted rejection "
        "decision row (AUD-021). Its per-kind completeness is therefore "
        "reported as `not_emitted`/0 within the eligible set — this is a "
        "record-format statement, not a completeness claim and not a failure "
        "count."),
        ("- The structured rejection record and transaction trace are defined by "
        "the newer observer schema "
        "(`glhs-postgres-governance-toctou-final-v2.1`); a future freeze can "
        "raise completeness within the same eligible sets."),
        ("- Never divide eligible counts of one kind by the total of another; "
        "each completeness fraction uses its own denominator."),
        "",
    ]
    return "\n".join(lines)


def write_opportunity_denominators(raw_root: Path, output_json: Path, output_md: Path) -> dict[str, Any]:
    payload = build_opportunity_denominators(raw_root)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()
    payload = write_opportunity_denominators(args.raw_root, args.output_json, args.output_md)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())