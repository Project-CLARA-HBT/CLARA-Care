"""Deterministic builder for the E01 component-wise exact-binding ablation corpus.

Design:
- 9 Distinct schedule families (8 adversarial/control families + 1 clean family)
- 32 schedules per adversarial/negative family (8 x 32 = 256 schedules)
- 96 clean positive control schedules (CLEAN)
- Total: 352 unique logical schedules (evaluated over 8 factorial arms = 2,816 executions)

Schedule Families:
1. ID-SUB: Replaces snapshot ID with another valid snapshot ID for the same patient.
2. DIGEST-MUT: Mutates snapshot digest bytes while keeping snapshot ID intact.
3. EVIDENCE-OUTSIDE: Injects evidence ID that was NOT part of the THSS snapshot disclosure.
4. MIN-SET-SWAP: Swaps evidence subset for a different subset.
5. CROSS-SNAPSHOT-SAME-VERSION: Reuses snapshot from another patient or session at the same state version.
6. COORD-SUB: Mutates actor/purpose/task coordinates.
7. LINEAGE-ROOT-SUB: Substitutes root proposal binding in reviewed proposals.
8. EXPIRY-CONTROL: Negative control with expired snapshot lease.
9. CLEAN: Valid positive control schedules that MUST be accepted across all arms.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "glhs-binding-component-ablation-schedules.v1"

FAMILY_IDS = {
    "ID-SUB": 1,
    "DIGEST-MUT": 2,
    "EVIDENCE-OUTSIDE": 3,
    "MIN-SET-SWAP": 4,
    "CROSS-SNAPSHOT-SAME-VERSION": 5,
    "COORD-SUB": 6,
    "LINEAGE-ROOT-SUB": 7,
    "EXPIRY-CONTROL": 8,
    "CLEAN": 9,
}

FAMILY_NAMES = {v: k for k, v in FAMILY_IDS.items()}

FAMILY_DESCRIPTIONS = {
    "ID-SUB": "Replaces snapshot ID with another valid snapshot ID for the same patient",
    "DIGEST-MUT": "Mutates snapshot digest bytes while keeping snapshot ID intact",
    "EVIDENCE-OUTSIDE": "Injects evidence ID that was NOT part of the THSS snapshot disclosure",
    "MIN-SET-SWAP": "Swaps evidence subset for a different subset under matching state version",
    "CROSS-SNAPSHOT-SAME-VERSION": "Reuses snapshot from another patient or session at the same state version",
    "COORD-SUB": "Mutates actor/purpose/task coordinates while authorization is otherwise admissible",
    "LINEAGE-ROOT-SUB": "Substitutes root proposal binding in reviewed proposals",
    "EXPIRY-CONTROL": "Negative control with expired snapshot lease",
    "CLEAN": "Valid positive control schedules that MUST be accepted across all arms",
}

SCHEDULES_PER_FAMILY = {
    "ID-SUB": 32,
    "DIGEST-MUT": 32,
    "EVIDENCE-OUTSIDE": 32,
    "MIN-SET-SWAP": 32,
    "CROSS-SNAPSHOT-SAME-VERSION": 32,
    "COORD-SUB": 32,
    "LINEAGE-ROOT-SUB": 32,
    "EXPIRY-CONTROL": 32,
    "CLEAN": 96,
}

TOTAL_SCHEDULES = sum(SCHEDULES_PER_FAMILY.values())  # 352

CLINICAL_CONTEXTS = [
    {"task": "monitoring_repeat", "domain": "observations", "action": "repeat_measurement", "evidence_count": 1, "actor_role": "owner", "purpose": "self_care"},
    {"task": "monitoring_repeat", "domain": "observations", "action": "repeat_measurement", "evidence_count": 2, "actor_role": "clinician", "purpose": "clinical_review"},
    {"task": "monitoring_repeat", "domain": "observations", "action": "repeat_measurement", "evidence_count": 3, "actor_role": "owner", "purpose": "self_care"},
    {"task": "device_sync_review", "domain": "observations", "action": "monitor_observation", "evidence_count": 1, "actor_role": "owner", "purpose": "self_care"},
    {"task": "device_sync_review", "domain": "observations", "action": "monitor_observation", "evidence_count": 2, "actor_role": "clinician", "purpose": "clinical_review"},
    {"task": "medication_review", "domain": "medications", "action": "medication_review", "evidence_count": 1, "actor_role": "clinician", "purpose": "clinical_review"},
    {"task": "medication_review", "domain": "medications", "action": "medication_review", "evidence_count": 2, "actor_role": "clinician", "purpose": "clinical_review"},
    {"task": "medication_adherence", "domain": "medications", "action": "take_medication", "evidence_count": 1, "actor_role": "owner", "purpose": "self_care"},
    {"task": "medication_adherence", "domain": "medications", "action": "take_medication", "evidence_count": 2, "actor_role": "owner", "purpose": "self_care"},
    {"task": "medication_adherence", "domain": "medications", "action": "take_medication", "evidence_count": 3, "actor_role": "owner", "purpose": "self_care"},
    {"task": "condition_monitoring", "domain": "conditions", "action": "monitor_condition", "evidence_count": 2, "actor_role": "clinician", "purpose": "clinical_review"},
    {"task": "allergy_verification", "domain": "allergies", "action": "verify_allergy", "evidence_count": 1, "actor_role": "clinician", "purpose": "clinical_review"},
]

ID_SUB_KINDS = [
    "prior_version_snapshot_id",
    "alternate_session_snapshot_id",
    "synthetic_foreign_snapshot_id",
    "parallel_subtask_snapshot_id",
]

DIGEST_MUT_KINDS = [
    "bit_flip_payload_digest",
    "truncated_digest_bytes",
    "zero_digest_padding",
    "inverted_merkle_digest",
]

EVIDENCE_OUTSIDE_KINDS = [
    "single_external_evidence_id",
    "multiple_external_evidence_ids",
    "cross_patient_evidence_id",
    "fabricated_future_evidence_id",
]

MIN_SET_SWAP_KINDS = [
    "swap_to_disjoint_evidence_subset",
    "swap_to_expanded_unpruned_subset",
    "swap_to_stale_evidence_subset",
    "swap_to_correlated_alternative_subset",
]

CROSS_SNAPSHOT_KINDS = [
    "cross_patient_same_state_version",
    "cross_session_same_profile_version",
    "cross_tenant_cloned_snapshot",
    "shadow_profile_same_epoch",
]

COORD_SUB_KINDS = [
    "substituted_actor_role",
    "substituted_purpose_code",
    "substituted_task_identifier",
    "mutated_composite_coordinates",
]

LINEAGE_ROOT_SUB_KINDS = [
    "substituted_root_snapshot_id",
    "mutated_root_proposal_digest",
    "disconnected_reviewed_lineage",
    "cross_lineage_transplantation",
]

EXPIRY_CONTROL_OFFSETS = [5, 30, 300, 86400]


def _build_schedule(
    family_name: str,
    index: int,
    context: dict[str, Any],
) -> dict[str, Any]:
    family_id = FAMILY_IDS[family_name]
    is_clean = family_name == "CLEAN"
    schedule_code = f"C{index:03d}" if is_clean else f"A{index:03d}"
    schedule_id = f"GLHS-E01-F{family_id:02d}-{family_name}-{schedule_code}"

    evidence_count = int(context["evidence_count"])
    base_evidence = [f"EVD-{i:03d}" for i in range(1, evidence_count + 1)]
    disclosed_evidence = list(base_evidence)
    observed_evidence = list(base_evidence)
    extra_undisclosed: list[str] = []

    snapshot_fields: dict[str, Any] = {
        "source_snapshot_id": f"SNAP-BASE-{index:03d}",
        "source_snapshot_digest": f"DIGEST-SHA256-ORIG-{index:03d}",
        "manifest_payload_status": "intact",
        "expires_in_seconds": 3600,
        "lineage_root_id": f"SNAP-ROOT-{index:03d}",
    }
    variant_metadata: dict[str, Any] = {"family": family_name, "index": index}

    if family_name == "ID-SUB":
        kind = ID_SUB_KINDS[(index - 1) % len(ID_SUB_KINDS)]
        snapshot_fields["source_snapshot_id"] = f"SNAP-SUB-{kind}-{index:03d}"
        variant_metadata["mutation_kind"] = kind
        expected_admissibility = "invalid_commit_rejected"

    elif family_name == "DIGEST-MUT":
        kind = DIGEST_MUT_KINDS[(index - 1) % len(DIGEST_MUT_KINDS)]
        snapshot_fields["source_snapshot_digest"] = f"DIGEST-MUTATED-{kind}-{index:03d}"
        snapshot_fields["manifest_payload_status"] = f"mutated:{kind}"
        variant_metadata["mutation_kind"] = kind
        expected_admissibility = "invalid_commit_rejected"

    elif family_name == "EVIDENCE-OUTSIDE":
        kind = EVIDENCE_OUTSIDE_KINDS[(index - 1) % len(EVIDENCE_OUTSIDE_KINDS)]
        extra_undisclosed = [f"EVD-OUTSIDE-{index:03d}-X{i}" for i in range(1, 3)]
        observed_evidence = base_evidence + extra_undisclosed
        variant_metadata["mutation_kind"] = kind
        expected_admissibility = "invalid_commit_rejected"

    elif family_name == "MIN-SET-SWAP":
        kind = MIN_SET_SWAP_KINDS[(index - 1) % len(MIN_SET_SWAP_KINDS)]
        swapped_evidence = [f"EVD-SWAP-{index:03d}-S{i}" for i in range(1, evidence_count + 1)]
        observed_evidence = swapped_evidence
        variant_metadata["mutation_kind"] = kind
        expected_admissibility = "invalid_commit_rejected"

    elif family_name == "CROSS-SNAPSHOT-SAME-VERSION":
        kind = CROSS_SNAPSHOT_KINDS[(index - 1) % len(CROSS_SNAPSHOT_KINDS)]
        snapshot_fields["source_snapshot_id"] = f"SNAP-CROSS-{kind}-{index:03d}"
        snapshot_fields["source_snapshot_digest"] = f"DIGEST-CROSS-{kind}-{index:03d}"
        variant_metadata["mutation_kind"] = kind
        expected_admissibility = "invalid_commit_rejected"

    elif family_name == "COORD-SUB":
        kind = COORD_SUB_KINDS[(index - 1) % len(COORD_SUB_KINDS)]
        variant_metadata["mutation_kind"] = kind
        variant_metadata["substituted_coordinates"] = {
            "actor_role": "unauthorized_delegate" if "actor" in kind else context["actor_role"],
            "purpose": "secondary_research" if "purpose" in kind else context["purpose"],
            "task": "arbitrary_write" if "task" in kind else context["task"],
        }
        expected_admissibility = "invalid_commit_rejected"

    elif family_name == "LINEAGE-ROOT-SUB":
        kind = LINEAGE_ROOT_SUB_KINDS[(index - 1) % len(LINEAGE_ROOT_SUB_KINDS)]
        snapshot_fields["lineage_root_id"] = f"SNAP-ROOT-SUBSTITUTED-{kind}-{index:03d}"
        variant_metadata["mutation_kind"] = kind
        expected_admissibility = "invalid_commit_rejected"

    elif family_name == "EXPIRY-CONTROL":
        offset = EXPIRY_CONTROL_OFFSETS[(index - 1) % len(EXPIRY_CONTROL_OFFSETS)]
        snapshot_fields["expires_in_seconds"] = -offset
        snapshot_fields["is_expired"] = True
        variant_metadata["expiry_offset_seconds"] = offset
        expected_admissibility = "invalid_commit_rejected"

    elif family_name == "CLEAN":
        expected_admissibility = "valid_commit"
        variant_metadata["control"] = True

    else:
        raise ValueError(f"unknown_family_name:{family_name}")

    return {
        "schedule_id": schedule_id,
        "family_id": family_id,
        "family_name": family_name,
        "family_description": FAMILY_DESCRIPTIONS[family_name],
        "kind": "control" if is_clean else "adversarial",
        "arm_scope": "FACTORIAL_2X3_ALL_ARMS",
        "current_coordinates_ok": True,
        "expected_admissibility": expected_admissibility,
        "context": dict(context),
        "variant": variant_metadata,
        "snapshot_fields": snapshot_fields,
        "evidence_set": {
            "disclosed_provenance_ids": disclosed_evidence,
            "observed_evidence_ids": observed_evidence,
            "extra_undisclosed_ids": extra_undisclosed,
        },
    }


def build_schedules() -> list[dict[str, Any]]:
    """Deterministically generate the complete corpus of 352 logical schedules."""
    schedules: list[dict[str, Any]] = []

    # Generate 8 adversarial/negative families (32 schedules each)
    for family_name in [
        "ID-SUB",
        "DIGEST-MUT",
        "EVIDENCE-OUTSIDE",
        "MIN-SET-SWAP",
        "CROSS-SNAPSHOT-SAME-VERSION",
        "COORD-SUB",
        "LINEAGE-ROOT-SUB",
        "EXPIRY-CONTROL",
    ]:
        count = SCHEDULES_PER_FAMILY[family_name]
        for idx in range(1, count + 1):
            context = CLINICAL_CONTEXTS[(idx - 1) % len(CLINICAL_CONTEXTS)]
            schedules.append(_build_schedule(family_name, idx, context))

    # Generate CLEAN positive control family (96 schedules)
    clean_count = SCHEDULES_PER_FAMILY["CLEAN"]
    for idx in range(1, clean_count + 1):
        context = CLINICAL_CONTEXTS[(idx - 1) % len(CLINICAL_CONTEXTS)]
        schedules.append(_build_schedule("CLEAN", idx, context))

    return schedules


def write_schedules(path: Path) -> None:
    """Serialize the schedules corpus to JSON format."""
    schedules = build_schedules()
    doc = {
        "schema_version": SCHEMA_VERSION,
        "freeze_note": (
            "Frozen 352 logical schedules for E01 2^3 factorial exact-binding ablation. "
            "Includes 256 adversarial/negative schedules across 8 families (32 per family) "
            "and 96 clean positive controls across 12 clinical contexts. "
            "Evaluated across all 8 factorial arms (B000-B111) yielding 2,816 total executions."
        ),
        "total_schedules": len(schedules),
        "adversarial_schedules": sum(1 for s in schedules if s["kind"] == "adversarial"),
        "control_schedules": sum(1 for s in schedules if s["kind"] == "control"),
        "per_family_counts": {name: SCHEDULES_PER_FAMILY[name] for name in FAMILY_IDS},
        "schedules": schedules,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent / "schedules.json"
    write_schedules(out_path)
    print(f"Successfully generated {TOTAL_SCHEDULES} schedules -> {out_path}")
