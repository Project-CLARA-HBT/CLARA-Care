"""E-004: Not Run capability audit for the GovRed RIVF final-003 matrix.

GRD-03: every family/arm currently Not Run gets a capability decision:

- ``IMPLEMENTABLE_FAITHFULLY`` — implement and test before a new freeze;
- ``TASK_OR_ARM_SEMANTICS_UNSUPPORTED`` — retain Not Run with a technical
  reason;
- ``REQUIRES_LLM_ATTACK_STUDY`` — keep outside the core authorization-drift
  endpoint rather than fake a model attack (E-006).

This module reads the frozen family-arm matrix
(``research/govred_rivf/family_arm_matrix.csv``) plus the family contracts and
the isolated adapter's mutation map, classifies every Not Run family, and
emits ``research/govred_rivf/not_run_capability_audit.md`` plus a structured
JSON artifact. The three mandatory-primary families completed since final-003
(commit ``bd0d7d65``: ``cross_subject_retrieval`` -> ``subject_cross_replay``,
``purpose_mismatch`` -> ``purpose_switch_replay``, ``policy_version_change``
two-phase) are noted; completion in the adapter is not a result.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from evaluation.governance_adversarial.family_contracts import family_contract
from evaluation.governance_adversarial.isolated_boundary_adapter import _MUTATIONS
from evaluation.governance_adversarial.protocol import ARMS, family_scope

SCHEMA_VERSION = "govred-not-run-capability-audit-v1"

IMPLEMENTABLE_FAITHFULLY = "IMPLEMENTABLE_FAITHFULLY"
TASK_OR_ARM_SEMANTICS_UNSUPPORTED = "TASK_OR_ARM_SEMANTICS_UNSUPPORTED"
REQUIRES_LLM_ATTACK_STUDY = "REQUIRES_LLM_ATTACK_STUDY"

CAPABILITY_CATEGORIES = (
    IMPLEMENTABLE_FAITHFULLY,
    TASK_OR_ARM_SEMANTICS_UNSUPPORTED,
    REQUIRES_LLM_ATTACK_STUDY,
)

#: Commit that eliminated the three mandatory-primary NOT_RUN families by
#: adding two-phase adapter schedules plus persisted-writer scenarios.
COMPLETION_COMMIT = "bd0d7d65"

#: Per-family capability decision with the technical reason required by GRD-03.
#: The family's governance-writer type comes from ``family_contracts``.
_CAPABILITY: dict[str, tuple[str, str]] = {
    "cross_subject_retrieval": (
        IMPLEMENTABLE_FAITHFULLY,
        (
            "Two-phase subject_cross_replay schedule is implemented in the "
            f"isolated adapter (commit {COMPLETION_COMMIT}); faithful disclosure "
            "retrieval for a foreign subject is an HTTP scope-enforcement probe "
            "with a persisted-writer scenario."
        ),
    ),
    "purpose_mismatch": (
        IMPLEMENTABLE_FAITHFULLY,
        (
            "Narrow synthetic purpose_switch_replay grant mutation (two-phase "
            "create/commit) is implemented in the isolated adapter "
            f"(commit {COMPLETION_COMMIT}) and maps to the persisted "
            "purpose_or_authorization_change governance writer."
        ),
    ),
    "policy_version_change": (
        IMPLEMENTABLE_FAITHFULLY,
        (
            "Two-phase deployment-level GOVRED_RESEARCH_POLICY_VERSION override "
            f"plus the persisted advance_governance_policy_epoch writer (commit "
            f"{COMPLETION_COMMIT}); policy epochs are real persisted rows."
        ),
    ),
    "gst_bypass_prompt": (
        REQUIRES_LLM_ATTACK_STUDY,
        (
            "Prompt-injection bypass of GST requires a real model-mediated "
            "security protocol (E-006). No frozen LLM-attack protocol exists; a "
            "synthetic request label would fake the attack and must not enter the "
            "core authorization-drift endpoint."
        ),
    ),
    "patient_evidence_prompt_injection": (
        REQUIRES_LLM_ATTACK_STUDY,
        (
            "Prompt-injection into patient evidence requires a real model-mediated "
            "security protocol (E-006). Kept outside the core authorization-drift "
            "endpoint until one is frozen."
        ),
    ),
    "unrelated_disclosure_request": (
        IMPLEMENTABLE_FAITHFULLY,
        (
            "Request-time scope enforcement: an HTTP disclosure request for an "
            "out-of-scope subject/purpose is denied at the scope resolver "
            "(documented 404 scope_forbidden development probes). Requires a "
            "disclosure-probe mutation in the adapter; no governance writer or LLM "
            "is involved."
        ),
    ),
}

DEFAULT_MATRIX = Path("research/govred_rivf/family_arm_matrix.csv")
DEFAULT_OUTPUT_JSON = Path("research/govred_rivf/not_run_capability_audit.json")
DEFAULT_OUTPUT_MD = Path("research/govred_rivf/not_run_capability_audit.md")


def _load_matrix_rows(matrix_path: Path) -> list[dict[str, str]]:
    with matrix_path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _not_run_families(rows: list[dict[str, str]]) -> tuple[str, ...]:
    families = {row["family"] for row in rows if int(row["not_run_n"]) > 0 and row["arm"] in ARMS}
    return tuple(sorted(families))


def build_capability_audit(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Classify every Not Run family/arm into a GRD-03 capability category."""
    not_run_families = _not_run_families(rows)
    missing = set(not_run_families) - set(_CAPABILITY)
    if missing:
        raise ValueError("govred_not_run_capability_unclassified:" + ",".join(sorted(missing)))
    rows_out: list[dict[str, object]] = []
    for family in not_run_families:
        for arm in ARMS:
            matrix = next(
                (row for row in rows if row["family"] == family and row["arm"] == arm),
                None,
            )
            not_run_n = int(matrix["not_run_n"]) if matrix else 30
            contract = family_contract(family)
            capability, reason = _CAPABILITY[family]
            rows_out.append(
                {
                    "family": family,
                    "reporting_scope": family_scope(family),
                    "arm": arm,
                    "not_run_n": not_run_n,
                    "capability": capability,
                    "technical_reason": reason,
                    "governance_writer_type": contract.governance_writer_type,
                    "adapter_mutation": _MUTATIONS.get(family),
                    "completed_since_final_003": family
                    in {
                        "cross_subject_retrieval",
                        "purpose_mismatch",
                        "policy_version_change",
                    },
                    "completion_commit": COMPLETION_COMMIT
                    if family
                    in {
                        "cross_subject_retrieval",
                        "purpose_mismatch",
                        "policy_version_change",
                    }
                    else None,
                    "in_core_authorization_drift_endpoint": family_scope(family)
                    == "primary_authorization_drift",
                }
            )
    counts = {category: 0 for category in CAPABILITY_CATEGORIES}
    for item in rows_out:
        counts[str(item["capability"])] += 1
    families_by_category = {
        category: sorted({str(i["family"]) for i in rows_out if i["capability"] == category})
        for category in CAPABILITY_CATEGORIES
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "final-003 family-arm matrix (research/govred_rivf/family_arm_matrix.csv)",
        "gr_requirement": "GRD-03 Not Run completion",
        "classification_counts": counts,
        "families_by_category": families_by_category,
        "rows": rows_out,
        "completion_notes": [
            (
                f"The three mandatory-primary NOT_RUN families were completed in "
                f"the adapter (commit {COMPLETION_COMMIT}): cross_subject_retrieval "
                "-> subject_cross_replay, purpose_mismatch -> purpose_switch_replay, "
                "policy_version_change two-phase. Completion is capability, not result."
            ),
            (
                "Prompt-injection families stay REQUIRES_LLM_ATTACK_STUDY (E-006): "
                "no real model-mediated security protocol is frozen, so they are "
                "not faked with synthetic request labels."
            ),
        ],
    }


def render_markdown(audit: dict[str, Any]) -> str:
    lines: list[str] = [
        "# GovRed RIVF — Not Run capability audit (E-004 / GRD-03)",
        "",
        (
            "Capability decision for every family/arm that was `NOT_RUN` in "
            "final-003 (180 per arm). A `NOT_RUN` row contributes to no "
            "denominator and is never a zero-failure result."
        ),
        "",
        "## Classification counts",
        "",
        "| Category | families |",
        "| --- | --- |",
    ]
    for category in CAPABILITY_CATEGORIES:
        families = ", ".join(audit["families_by_category"][category]) or "—"
        lines.append(f"| {category} | {families} |")
    lines += [
        "",
        "## Per family/arm decision",
        "",
        "| family | scope | governance writer | adapter mutation | capability |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in audit["rows"]:
        writer = str(item["governance_writer_type"])
        mutation = str(item["adapter_mutation"]) if item["adapter_mutation"] else "none"
        lines.append(
            f"| {item['family']} | {item['reporting_scope']} | {writer} | "
            f"{mutation} | {item['capability']} |"
        )
    lines += [
        "",
        "## Technical reasons",
        "",
    ]
    seen: set[str] = set()
    for item in audit["rows"]:
        family = str(item["family"])
        if family in seen:
            continue
        seen.add(family)
        lines.append(f"### {family}")
        lines.append("")
        lines.append(str(item["technical_reason"]))
        lines.append("")
    lines += [
        "## Notes",
        "",
        (
            "- The three mandatory-primary families were completed in the adapter "
            f"(`{audit['completion_notes'][0]}`)."
        ),
        f"- {audit['completion_notes'][1]}",
        (
            "- `TASK_OR_ARM_SEMANTICS_UNSUPPORTED` is not forced: no family needed "
            "it, and no family is forced to execute by weakening semantics."
        ),
        "",
    ]
    return "\n".join(lines)


def write_capability_audit(matrix: Path, output_json: Path, output_md: Path) -> dict[str, Any]:
    rows = _load_matrix_rows(matrix)
    audit = build_capability_audit(rows)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(audit), encoding="utf-8")
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()
    audit = write_capability_audit(args.matrix, args.output_json, args.output_md)
    print(json.dumps(audit["classification_counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
