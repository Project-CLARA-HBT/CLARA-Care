"""Deterministic schedule generator for E03 Downgrade and Anti-Laundering Assurance.

Generates 300 schedules across 11 families:
- 10 Negative/Adversarial Laundering Families (25 schedules each = 250 schedules)
- 1 Clean Control Family (50 schedules)
Total = 300 schedules.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "glhs-downgrade-assurance-schedules.v1"

LAUNDERING_PATTERNS = [
    {
        "pattern_id": 1,
        "code": "P01_MISSING_SNAPSHOT_BINDING",
        "name": "Missing Snapshot Binding",
        "threat_vector": "Proposal consumed THSS but omitted snapshot binding",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "proposal_snapshot_binding_required",
        "count": 25,
    },
    {
        "pattern_id": 2,
        "code": "P02_DOWNGRADE_TO_BASE_VERSION",
        "name": "Downgrade To Base Version Only",
        "threat_vector": "Snapshot-bound parent attempting transition to base-version-only child",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "commitment_lineage_base_only_forbidden",
        "count": 25,
    },
    {
        "pattern_id": 3,
        "code": "P03_PARENT_BOUND_CHANGED_SNAPSHOT",
        "name": "Changed Snapshot in Reviewed Proposal",
        "threat_vector": "Snapshot-bound parent followed by reviewed proposal with mutated snapshot identity",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "commitment_lineage_snapshot_mismatch",
        "count": 25,
    },
    {
        "pattern_id": 4,
        "code": "P04_MISSING_ROOT_LINEAGE",
        "name": "Missing Root Lineage Reference",
        "threat_vector": "Reviewed proposal stripped of root lineage reference to evade binding verification",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "commitment_lineage_binding_required",
        "count": 25,
    },
    {
        "pattern_id": 5,
        "code": "P05_ROOT_CHILD_SNAPSHOT_MISMATCH",
        "name": "Root-Child Snapshot Digest Mismatch",
        "threat_vector": "Root snapshot digest tampered or mismatched in child proposal",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "commitment_lineage_manifest_digest_mismatch",
        "count": 25,
    },
    {
        "pattern_id": 6,
        "code": "P06_DIRECT_WRITE_ESCAPE",
        "name": "Direct Write Escape",
        "threat_vector": "Direct model-originated generic assertion write bypassing GLHS proposal layer",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "model_cannot_write_assertion",
        "count": 25,
    },
    {
        "pattern_id": 7,
        "code": "P07_UNBOUND_USER_REVIEW_ADAPTER",
        "name": "Unbound User Review Adapter Escape",
        "threat_vector": "Model output passed through user-review adapter attempting to drop snapshot binding",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "commitment_lineage_binding_required",
        "count": 25,
    },
    {
        "pattern_id": 8,
        "code": "P08_CROSS_PROFILE_LAUNDERING",
        "name": "Cross-Profile Snapshot Laundering",
        "threat_vector": "Using snapshot from Profile X for a proposal modifying Profile Y",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "cross_profile_snapshot_forbidden",
        "count": 25,
    },
    {
        "pattern_id": 9,
        "code": "P09_EXPIRED_PARENT_REUSE",
        "name": "Expired Parent Reuse",
        "threat_vector": "Attempting to chain child proposal to an expired parent snapshot lease",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "lease_expired",
        "count": 25,
    },
    {
        "pattern_id": 10,
        "code": "P10_DEPENDENCY_OVERRIDE_AFTER_SEAL",
        "name": "Dependency Vector Override After Seal",
        "threat_vector": "Attempting to alter dependency vector post-seal to bypass read-set dependencies",
        "expected_outcome": "REJECT",
        "rejection_reason_code": "dependency_vector_seal_mismatch",
        "count": 25,
    },
    {
        "pattern_id": 11,
        "code": "P11_CLEAN_VALID_LINEAGE",
        "name": "Clean Valid Bound Lineage Control",
        "threat_vector": "None (valid positive control schedule with full snapshot binding)",
        "expected_outcome": "ADMIT",
        "rejection_reason_code": "valid_commit",
        "count": 50,
    },
]

DOMAINS = ["medications", "conditions", "observations", "allergies"]
TASKS = ["monitoring_repeat", "medication_review", "device_sync_review", "adherence_check"]
ACTORS = ["clinician", "owner", "system"]


def generate_schedules() -> list[dict[str, Any]]:
    """Deterministically generate the 300 schedules for E03."""
    schedules: list[dict[str, Any]] = []
    global_id = 0

    for pat in LAUNDERING_PATTERNS:
        count = pat["count"]
        for idx in range(count):
            global_id += 1
            schedule_id = f"SCHED-E03-{pat['pattern_id']:02d}-{idx+1:03d}"
            domain = DOMAINS[idx % len(DOMAINS)]
            task = TASKS[idx % len(TASKS)]
            actor = ACTORS[idx % len(ACTORS)]

            schedules.append({
                "schedule_id": schedule_id,
                "global_sequence": global_id,
                "pattern_id": pat["pattern_id"],
                "pattern_code": pat["code"],
                "pattern_name": pat["name"],
                "threat_vector": pat["threat_vector"],
                "expected_outcome": pat["expected_outcome"],
                "rejection_reason_code": pat["rejection_reason_code"],
                "is_clean_control": pat["code"] == "P11_CLEAN_VALID_LINEAGE",
                "is_adversarial": pat["code"] != "P11_CLEAN_VALID_LINEAGE",
                "profile_index": (idx % 10) + 1,
                "domain": domain,
                "task": task,
                "actor_role": actor,
                "purpose": "clinical_review" if actor == "clinician" else "self_care",
                "semantic_key": f"{domain}:patient-{(idx % 10) + 1:03d}:item-{idx+1}",
                "simulated_params": {
                    "seed": 20260928 + global_id,
                    "lease_duration_sec": 300 if pat["code"] != "P09_EXPIRED_PARENT_REUSE" else -60,
                    "tamper_digest": pat["code"] == "P05_ROOT_CHILD_SNAPSHOT_MISMATCH",
                    "tamper_dependency": pat["code"] == "P10_DEPENDENCY_OVERRIDE_AFTER_SEAL",
                    "cross_profile": pat["code"] == "P08_CROSS_PROFILE_LAUNDERING",
                },
            })

    return schedules


def build_schedules_document() -> dict[str, Any]:
    schedules = generate_schedules()
    return {
        "schema_version": SCHEMA_VERSION,
        "total_schedules": len(schedules),
        "adversarial_negative": sum(1 for s in schedules if s["is_adversarial"]),
        "clean_controls": sum(1 for s in schedules if s["is_clean_control"]),
        "laundering_patterns": LAUNDERING_PATTERNS,
        "schedules": schedules,
    }


def write_schedules(output_path: Path) -> dict[str, Any]:
    doc = build_schedules_document()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("protocols/E03_downgrade/schedules.json")
    write_schedules(out)
    print(f"Generated {out}")
