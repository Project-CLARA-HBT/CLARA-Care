"""Deterministic builder for the frozen 320-schedule exact-binding protocol.

Freeze: 8 binding-specific families x 32 adversarial schedules = 256
adversarial schedules plus 64 valid controls (8 per family) = 320 logical
schedules (GLHS-A05).  Every schedule is executed under both arms (640
executions); the scientific unit is the logical schedule.

Every adversarial schedule holds current state/governance coordinates valid
(``current_coordinates_ok=true``) and changes ONLY the disclosure dependency
(C-007, GLHS-A03): the proposal's referenced snapshot identity/digest, the
persisted snapshot payload, the disclosed/observed evidence membership, the
snapshot expiry, or the post-review lineage binding.

This builder is deterministic: it enumerates fixed variant tables (no random
number generator), so ``schedules.json`` is reproducible byte-for-byte.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "glhs-binding-ablation-schedules.v1"
FAMILY_COUNT = 8
ADVERSARIAL_PER_FAMILY = 32
CONTROLS_PER_FAMILY = 8
TOTAL_SCHEDULES = FAMILY_COUNT * (ADVERSARIAL_PER_FAMILY + CONTROLS_PER_FAMILY)

FAMILY_NAMES = {
    1: "wrong_snapshot_id",
    2: "wrong_snapshot_digest",
    3: "mutated_snapshot_payload",
    4: "evidence_not_disclosed",
    5: "valid_snapshot_substitution",
    6: "expired_snapshot",
    7: "minimized_evidence_swap",
    8: "lineage_root_substitution",
}

FAMILY_REASONS = {
    1: "proposal references a snapshot id that is not its own manifest (absent, "
    "malformed, or another profile's) while profile/state/governance coordinates "
    "are current; only the persisted exact THSS identity dependency differs",
    2: "proposal carries a snapshot digest that does not match the referenced "
    "manifest; only the exact digest dependency differs",
    3: "the persisted snapshot payload is mutated while current state/governance "
    "columns are unchanged; only the exact payload digest dependency differs",
    4: "proposal evidence includes ids absent from the disclosed snapshot "
    "provenance; only the evidence-membership dependency differs",
    5: "the proposal is re-pointed to another valid snapshot of the same profile "
    "and state version whose disclosure does not contain the proposal evidence; "
    "only the exact manifest identity/evidence dependency differs",
    6: "the original snapshot is expired while state/policy/consent remain "
    "unchanged; only the expiry dependency differs",
    7: "the minimized observed evidence set is swapped for a different set "
    "containing at least one id outside the disclosed provenance; only the "
    "evidence-membership dependency differs",
    8: "after human review the reviewed proposal's lineage root snapshot is "
    "substituted by another valid snapshot whose disclosure does not contain the "
    "proposal evidence; only the post-review exact binding dependency differs",
}

DISCLOSURE_DELTA_TYPES = {
    1: "wrong_snapshot_id",
    2: "wrong_snapshot_digest",
    3: "mutated_snapshot_payload",
    4: "evidence_not_disclosed",
    5: "valid_snapshot_substitution",
    6: "expired_snapshot",
    7: "minimized_evidence_swap",
    8: "lineage_root_substitution",
}

CONTEXTS = [
    {
        "task": "monitoring_repeat",
        "domain": "observations",
        "action": "repeat_measurement",
        "evidence_count": 1,
    },
    {
        "task": "monitoring_repeat",
        "domain": "observations",
        "action": "repeat_measurement",
        "evidence_count": 2,
    },
    {
        "task": "monitoring_repeat",
        "domain": "observations",
        "action": "repeat_measurement",
        "evidence_count": 3,
    },
    {
        "task": "device_sync_review",
        "domain": "observations",
        "action": "monitor_observation",
        "evidence_count": 1,
    },
    {
        "task": "medication_review",
        "domain": "medications",
        "action": "medication_review",
        "evidence_count": 1,
    },
    {
        "task": "medication_review",
        "domain": "medications",
        "action": "medication_review",
        "evidence_count": 2,
    },
    {
        "task": "medication_adherence",
        "domain": "medications",
        "action": "take_medication",
        "evidence_count": 1,
    },
    {
        "task": "medication_adherence",
        "domain": "medications",
        "action": "take_medication",
        "evidence_count": 3,
    },
]

WRONG_ID_KINDS = [
    "absent_well_formed",
    "other_profile_manifest",
    "non_uuid_string",
    "empty_string",
]

WRONG_DIGEST_KINDS = [
    "zero_hex_64",
    "digest_of_unrelated_payload",
    "truncated_hex",
    "uppercase_hex_64",
]

PAYLOAD_MUTATION_TARGETS = [
    "selection",
    "visible_conflicts_irrelevant",
    "recency",
    "exclusions",
    "fact_coverage",
    "minimal_evidence",
    "sufficiency",
    "authority",
]

EXTRA_EVIDENCE_KINDS = [
    "one_extra_same_profile",
    "two_extra_same_profile",
    "three_extra_same_profile",
    "different_same_profile",
]

SUBSTITUTION_KINDS = [
    "opening_flow_no_disclosure",
    "opening_flow_disclosed_other",
    "opening_flow_disclosed_extra",
    "declared_target_mismatch",
]

EXPIRY_OFFSETS_SECONDS = [1, 60, 3600, 86400]

SWAP_KINDS = [
    "swap_all_to_fresh_evidence",
    "swap_all_to_same_profile_fresh_evidence",
    "swap_mix_disclosed_and_fresh",
    "swap_to_other_commitment_evidence",
]

FAMILY_VARIANT_KINDS = {
    1: WRONG_ID_KINDS,
    2: WRONG_DIGEST_KINDS,
    3: PAYLOAD_MUTATION_TARGETS,
    4: EXTRA_EVIDENCE_KINDS,
    5: SUBSTITUTION_KINDS,
    6: EXPIRY_OFFSETS_SECONDS,
    7: SWAP_KINDS,
    8: SUBSTITUTION_KINDS,
}


def _evidence_set(context: dict[str, Any], *, count: int) -> dict[str, Any]:
    return {
        "observed_evidence_ids": [f"E{i}" for i in range(1, count + 1)],
        "disclosed_provenance_ids": [f"E{i}" for i in range(1, count + 1)],
        "extra_undisclosed_ids": [],
    }


def _schedule(
    family_id: int,
    index: int,
    *,
    kind: str,
    context: dict[str, Any],
    variant: dict[str, Any],
    adversarial: bool,
) -> dict[str, Any]:
    schedule_id = (
        f"GLHS-BA-F{family_id:02d}-A{index:02d}"
        if adversarial
        else f"GLHS-BA-F{family_id:02d}-C{index:02d}"
    )
    if adversarial:
        expected = "invalid_commit_rejected"
        delta_type = DISCLOSURE_DELTA_TYPES[family_id]
        evidence_set = _evidence_set(context, count=int(context["evidence_count"]))
        if variant.get("extra_undisclosed"):
            evidence_set["extra_undisclosed_ids"] = variant["extra_undisclosed"]
        if variant.get("swap"):
            evidence_set["observed_evidence_ids"] = variant["swap"]
        reason = FAMILY_REASONS[family_id]
    else:
        expected = "valid_commit"
        delta_type = "none_control"
        evidence_set = _evidence_set(context, count=int(context["evidence_count"]))
        reason = "control: all fields preserved; valid commit expected under both arms"
    return {
        "schedule_id": schedule_id,
        "family_id": family_id,
        "family_name": FAMILY_NAMES[family_id],
        "kind": "adversarial" if adversarial else "control",
        "arm": "BOTH",
        "disclosure_delta_type": delta_type,
        "current_coordinates_ok": True,
        "expected_admissibility": expected,
        "context": dict(context),
        "variant": dict(variant),
        "snapshot_fields": dict(variant.get("snapshot_fields", {})),
        "evidence_set": evidence_set,
        "reason": reason,
    }


def _adversarial_variant_params(
    family_id: int, kind_index: int, context: dict[str, Any]
) -> dict[str, Any]:
    family = FAMILY_NAMES[family_id]
    kind = FAMILY_VARIANT_KINDS[family_id][kind_index]
    evidence_count = int(context["evidence_count"])
    if family == "wrong_snapshot_id":
        return {
            "wrong_id_kind": kind,
            "snapshot_fields": {
                "source_snapshot_id": kind,
                "source_snapshot_digest": "own-manifest-digest",
                "manifest_payload": "unmodified",
            },
        }
    if family == "wrong_snapshot_digest":
        return {
            "wrong_digest_kind": kind,
            "snapshot_fields": {
                "source_snapshot_id": "own-manifest",
                "source_snapshot_digest": kind,
                "manifest_payload": "unmodified",
            },
        }
    if family == "mutated_snapshot_payload":
        return {
            "payload_mutation_target": kind,
            "snapshot_fields": {
                "source_snapshot_id": "own-manifest",
                "source_snapshot_digest": "own-manifest-digest",
                "manifest_payload": f"mutated:{kind}",
            },
        }
    if family == "evidence_not_disclosed":
        extra = _extra_evidence_ids(kind, evidence_count)
        return {
            "extra_evidence_kind": kind,
            "extra_undisclosed": extra,
            "snapshot_fields": {
                "source_snapshot_id": "own-manifest",
                "source_snapshot_digest": "own-manifest-digest",
                "manifest_payload": "unmodified",
            },
        }
    if family == "valid_snapshot_substitution":
        return {
            "substitution_kind": kind,
            "snapshot_fields": {
                "source_snapshot_id": f"substituted-valid-snapshot:{kind}",
                "source_snapshot_digest": "substituted-manifest-digest",
                "manifest_payload": "unmodified",
            },
        }
    if family == "expired_snapshot":
        return {
            "expiry_offset_seconds": kind,
            "snapshot_fields": {
                "source_snapshot_id": "own-manifest",
                "source_snapshot_digest": "own-manifest-digest",
                "manifest_payload": "unmodified",
                "expires_at": f"now-{kind}s",
            },
        }
    if family == "minimized_evidence_swap":
        swap = _swap_evidence_ids(kind, evidence_count)
        return {
            "swap_kind": kind,
            "swap": swap,
            "snapshot_fields": {
                "source_snapshot_id": "own-manifest",
                "source_snapshot_digest": "own-manifest-digest",
                "manifest_payload": "unmodified",
            },
        }
    if family == "lineage_root_substitution":
        return {
            "substitution_kind": kind,
            "reviewed_lineage": True,
            "snapshot_fields": {
                "source_snapshot_id": f"substituted-valid-snapshot:{kind}",
                "source_snapshot_digest": "substituted-manifest-digest",
                "manifest_payload": "unmodified",
            },
        }
    raise ValueError(f"unknown_family:{family_id}")


def _extra_evidence_ids(kind: str, evidence_count: int) -> list[str]:
    if kind == "one_extra_same_profile":
        return ["X1"]
    if kind == "two_extra_same_profile":
        return ["X1", "X2"]
    if kind == "three_extra_same_profile":
        return ["X1", "X2", "X3"]
    if kind == "different_same_profile":
        return ["X2"]
    raise ValueError(f"unknown_extra_evidence_kind:{kind}")


def _swap_evidence_ids(kind: str, evidence_count: int) -> list[str]:
    if kind == "swap_all_to_fresh_evidence":
        return ["X1"]
    if kind == "swap_all_to_same_profile_fresh_evidence":
        return ["X1"]
    if kind == "swap_mix_disclosed_and_fresh":
        return ["E1", "X1"]
    if kind == "swap_to_other_commitment_evidence":
        return ["Z1"]
    raise ValueError(f"unknown_swap_kind:{kind}")


def build_schedules() -> list[dict[str, Any]]:
    """Return the frozen 320 logical schedules (256 adversarial + 64 controls)."""
    schedules: list[dict[str, Any]] = []
    for family_id in range(1, FAMILY_COUNT + 1):
        for adversarial_index in range(1, ADVERSARIAL_PER_FAMILY + 1):
            variant_index = (adversarial_index - 1) // len(CONTEXTS)
            context_index = (adversarial_index - 1) % len(CONTEXTS)
            context = CONTEXTS[context_index]
            variant = _adversarial_variant_params(family_id, variant_index, context)
            schedules.append(
                _schedule(
                    family_id,
                    adversarial_index,
                    kind="adversarial",
                    context=context,
                    variant=variant,
                    adversarial=True,
                )
            )
        for control_index in range(1, CONTROLS_PER_FAMILY + 1):
            context = CONTEXTS[(control_index - 1) % len(CONTEXTS)]
            schedules.append(
                _schedule(
                    family_id,
                    control_index,
                    kind="control",
                    context=context,
                    variant={"control": True},
                    adversarial=False,
                )
            )
    return schedules


def write_schedules(path: Path) -> None:
    schedules = build_schedules()
    document = {
        "schema_version": SCHEMA_VERSION,
        "freeze_note": (
            "Frozen 320 logical schedules: 8 families x 32 adversarial + 64 "
            "valid controls. Every schedule executes under both arms "
            "(FULL_GOVERNANCE_NO_EXACT_BINDING and GLHS_EXACT_BINDING)."
        ),
        "total_schedules": TOTAL_SCHEDULES,
        "adversarial_schedules": FAMILY_COUNT * ADVERSARIAL_PER_FAMILY,
        "control_schedules": FAMILY_COUNT * CONTROLS_PER_FAMILY,
        "schedules": schedules,
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_schedules(Path(__file__).resolve().parent / "schedules.json")
    print(f"wrote {TOTAL_SCHEDULES} schedules")
