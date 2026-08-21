"""Frozen-protocol validation, Gate C arm-diff, and no-production-flag checks.

``validate_schedules`` freezes the 320-schedule inventory invariants
(GLHS-A05): 8 binding-specific families x 32 adversarial schedules plus 64
valid controls, per-family expected admissibility matching the family
definition, and ``current_coordinates_ok`` for every adversarial schedule
(C-007: current state/governance valid while changing only the disclosure
dependency).

``validate_arm_diff`` implements Gate C: for every logical schedule the two
arm executions must be byte-identical on all non-binding governance
coordinates; the only permitted differences are the admission outcome and the
rejection reason, driven by whether the exact disclosure dependency check was
applied (``binding_check_applied``).

``validate_no_production_flag`` scans ``services/**`` for the feature-flag
vocabulary (``disable_binding`` / ``no_exact_binding``): the no-binding arm is
evaluation-only (GLHS-A02) and must never be reachable through production
code.  ``validate_import_boundary`` verifies no ``services/**`` file references
the evaluation-only package (GR-03, C-004).
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.glhs_binding_only_ablation.adapter import (
    FULL_GOVERNANCE_NO_EXACT_BINDING,
    GLHS_EXACT_BINDING,
)
from evaluation.glhs_binding_only_ablation.build_schedules import (
    ADVERSARIAL_PER_FAMILY,
    CONTROLS_PER_FAMILY,
    FAMILY_COUNT,
    FAMILY_NAMES,
    FAMILY_VARIANT_KINDS,
    TOTAL_SCHEDULES,
)

FLAG_VOCABULARY = ("disable_binding", "no_exact_binding")
FORBIDDEN_REFERENCES = ("glhs_binding_only_ablation",)

PROTOCOL_SCHEMA_VERSION = "glhs-binding-ablation-protocol.v1"
FROZEN_PROTOCOL_STATUS = "FROZEN"


def validate_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    """Validate the frozen protocol document; raise ``ValueError`` on violation."""
    if not isinstance(protocol, dict):
        raise TypeError("protocol_not_object")
    if protocol.get("schema_version") != PROTOCOL_SCHEMA_VERSION:
        raise ValueError(f"protocol_schema_invalid:{protocol.get('schema_version')}")
    if protocol.get("status") != FROZEN_PROTOCOL_STATUS:
        raise ValueError(f"protocol_not_frozen:{protocol.get('status')}")
    freeze_id = protocol.get("freeze_id")
    if not isinstance(freeze_id, str) or not freeze_id:
        raise ValueError("protocol_freeze_id_missing")
    arms = protocol.get("arms")
    if not isinstance(arms, list) or set(arms) != {
        FULL_GOVERNANCE_NO_EXACT_BINDING,
        GLHS_EXACT_BINDING,
    }:
        raise ValueError("protocol_arms_invalid")
    inventory = protocol.get("schedule_inventory") or {}
    if inventory.get("total") != TOTAL_SCHEDULES:
        raise ValueError("protocol_schedule_total_invalid")
    if inventory.get("adversarial") != FAMILY_COUNT * ADVERSARIAL_PER_FAMILY:
        raise ValueError("protocol_adversarial_count_invalid")
    if inventory.get("controls") != FAMILY_COUNT * CONTROLS_PER_FAMILY:
        raise ValueError("protocol_control_count_invalid")
    analysis = protocol.get("primary_analysis") or {}
    if analysis.get("adaptive_sample_size") is not False:
        raise ValueError("protocol_adaptive_sample_size_not_forbidden")
    analysis_hash = _sha256_canonical(analysis)
    if protocol.get("analysis_plan_hash") != analysis_hash:
        raise ValueError("protocol_analysis_plan_hash_mismatch")
    protocol_without_hash = {
        key: value for key, value in protocol.items() if key != "protocol_hash"
    }
    if protocol.get("protocol_hash") != _sha256_canonical(protocol_without_hash):
        raise ValueError("protocol_hash_mismatch")
    return {
        "freeze_id": freeze_id,
        "status": FROZEN_PROTOCOL_STATUS,
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "total_schedules": TOTAL_SCHEDULES,
        "valid": True,
    }


def _sha256_canonical(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_schedule_hash(schedule_bytes: bytes, expected_hash: str) -> None:
    """Verify the byte hash of the frozen schedule artifact."""
    actual = hashlib.sha256(schedule_bytes).hexdigest()
    if actual != expected_hash:
        raise ValueError("schedules_hash_mismatch")


def validate_schedules(document: dict[str, Any]) -> dict[str, Any]:
    """Validate the frozen 320-schedule inventory; raise ``ValueError`` on violation."""
    if not isinstance(document, dict):
        raise TypeError("schedules_not_object")
    schedules = document.get("schedules")
    if not isinstance(schedules, list):
        raise TypeError("schedules_missing")
    if len(schedules) != TOTAL_SCHEDULES:
        raise ValueError(f"schedules_count_invalid:{len(schedules)}")
    counts = Counter((int(schedule["family_id"]), str(schedule["kind"])) for schedule in schedules)
    for family_id in range(1, FAMILY_COUNT + 1):
        if counts[(family_id, "adversarial")] != ADVERSARIAL_PER_FAMILY:
            raise ValueError(f"family_adversarial_count_invalid:{family_id}")
        if counts[(family_id, "control")] != CONTROLS_PER_FAMILY:
            raise ValueError(f"family_control_count_invalid:{family_id}")
    seen_ids: set[str] = set()
    for schedule in schedules:
        schedule_id = str(schedule["schedule_id"])
        if schedule_id in seen_ids:
            raise ValueError(f"duplicate_schedule_id:{schedule_id}")
        seen_ids.add(schedule_id)
        family_id = int(schedule["family_id"])
        if family_id not in FAMILY_NAMES:
            raise ValueError(f"unknown_family_id:{family_id}")
        if str(schedule["family_name"]) != FAMILY_NAMES[family_id]:
            raise ValueError(f"family_name_mismatch:{schedule_id}")
        if schedule.get("arm") != "BOTH":
            raise ValueError(f"schedule_arm_not_both:{schedule_id}")
        kind = str(schedule["kind"])
        expected = schedule.get("expected_admissibility")
        if kind == "adversarial":
            if expected != "invalid_commit_rejected":
                raise ValueError(f"adversarial_expected_invalid:{schedule_id}")
            if schedule.get("current_coordinates_ok") is not True:
                raise ValueError(f"adversarial_coordinates_not_valid:{schedule_id}")
            variant = dict(schedule.get("variant") or {})
            if family_id == 1 and str(variant.get("wrong_id_kind")) not in FAMILY_VARIANT_KINDS[1]:
                raise ValueError(f"family1_variant_invalid:{schedule_id}")
            if (
                family_id == 2
                and str(variant.get("wrong_digest_kind")) not in FAMILY_VARIANT_KINDS[2]
            ):
                raise ValueError(f"family2_variant_invalid:{schedule_id}")
            if (
                family_id == 3
                and str(variant.get("payload_mutation_target")) not in FAMILY_VARIANT_KINDS[3]
            ):
                raise ValueError(f"family3_variant_invalid:{schedule_id}")
            if (
                family_id == 4
                and str(variant.get("extra_evidence_kind")) not in FAMILY_VARIANT_KINDS[4]
            ):
                raise ValueError(f"family4_variant_invalid:{schedule_id}")
            if (
                family_id == 5
                and str(variant.get("substitution_kind")) not in FAMILY_VARIANT_KINDS[5]
            ):
                raise ValueError(f"family5_variant_invalid:{schedule_id}")
            if (
                family_id == 6
                and int(variant.get("expiry_offset_seconds")) not in FAMILY_VARIANT_KINDS[6]
            ):
                raise ValueError(f"family6_variant_invalid:{schedule_id}")
            if family_id == 7 and str(variant.get("swap_kind")) not in FAMILY_VARIANT_KINDS[7]:
                raise ValueError(f"family7_variant_invalid:{schedule_id}")
            if (
                family_id == 8
                and str(variant.get("substitution_kind")) not in FAMILY_VARIANT_KINDS[8]
            ):
                raise ValueError(f"family8_variant_invalid:{schedule_id}")
            if not isinstance(schedule.get("snapshot_fields"), dict) or not schedule.get("reason"):
                raise ValueError(f"adversarial_schedule_incomplete:{schedule_id}")
        elif kind == "control":
            if expected != "valid_commit":
                raise ValueError(f"control_expected_invalid:{schedule_id}")
        else:
            raise ValueError(f"unknown_schedule_kind:{schedule_id}")
    return {
        "total_schedules": len(schedules),
        "adversarial": FAMILY_COUNT * ADVERSARIAL_PER_FAMILY,
        "controls": FAMILY_COUNT * CONTROLS_PER_FAMILY,
        "valid": True,
    }


def _coordinate_block(record: dict[str, Any]) -> str:
    return json.dumps(record.get("governance_coordinates") or {}, sort_keys=True)


def validate_arm_diff(
    records: list[dict[str, Any]], *, expected_schedule_ids: set[str] | None = None
) -> dict[str, Any]:
    """Gate C: non-binding governance coordinates must be byte-identical across arms."""
    by_schedule: dict[str, dict[str, dict[str, Any]]] = {}
    duplicate_pairs: list[str] = []
    for record in records:
        schedule_id = str(record["schedule_id"])
        arm = str(record["arm"])
        if arm not in {FULL_GOVERNANCE_NO_EXACT_BINDING, GLHS_EXACT_BINDING}:
            duplicate_pairs.append(f"{schedule_id}:{arm}")
            continue
        if arm in by_schedule.setdefault(schedule_id, {}):
            duplicate_pairs.append(f"{schedule_id}:{arm}")
            continue
        by_schedule.setdefault(schedule_id, {})[arm] = record
    mismatches: list[dict[str, Any]] = []
    missing_arm: list[str] = []
    unexpected_schedule_ids: list[str] = []
    if expected_schedule_ids is not None:
        unexpected_schedule_ids = sorted(set(by_schedule).difference(expected_schedule_ids))
        missing_arm.extend(sorted(expected_schedule_ids.difference(by_schedule)))
    for schedule_id, arms in sorted(by_schedule.items()):
        if set(arms) != {FULL_GOVERNANCE_NO_EXACT_BINDING, GLHS_EXACT_BINDING}:
            missing_arm.append(schedule_id)
            continue
        no_binding = arms[FULL_GOVERNANCE_NO_EXACT_BINDING]
        exact_binding = arms[GLHS_EXACT_BINDING]
        if _coordinate_block(no_binding) != _coordinate_block(exact_binding):
            mismatches.append(
                {
                    "schedule_id": schedule_id,
                    "reason": "governance_coordinates_differ",
                }
            )
        if bool(no_binding.get("binding_check_applied")) is not False:
            mismatches.append(
                {
                    "schedule_id": schedule_id,
                    "reason": "no_binding_arm_applied_binding_check",
                }
            )
        if bool(exact_binding.get("binding_check_applied")) is not True:
            mismatches.append(
                {
                    "schedule_id": schedule_id,
                    "reason": "exact_binding_arm_missing_binding_check",
                }
            )
    return {
        "valid": not mismatches
        and not missing_arm
        and not duplicate_pairs
        and not unexpected_schedule_ids,
        "checked_schedules": len(by_schedule),
        "missing_arm_schedule_ids": missing_arm,
        "unexpected_schedule_ids": unexpected_schedule_ids,
        "duplicate_or_unknown_pairs": duplicate_pairs,
        "mismatches": mismatches,
    }


def _python_flag_present(content: str) -> bool:
    """Find flag identifiers/usages while ignoring explanatory docstrings."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return any(token in content.lower() for token in FLAG_VOCABULARY)
    docstring_nodes: set[int] = set()
    containers = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if isinstance(node, containers) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstring_nodes.add(id(first.value))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstring_nodes
            and any(token in node.value.lower() for token in FLAG_VOCABULARY)
        ):
            return True
        if isinstance(node, ast.Name) and node.id.lower() in FLAG_VOCABULARY:
            return True
        if isinstance(node, ast.Attribute) and node.attr.lower() in FLAG_VOCABULARY:
            return True
        if isinstance(node, ast.arg) and node.arg.lower() in FLAG_VOCABULARY:
            return True
    return False


def validate_no_production_flag(services_root: Path) -> list[str]:
    """Return services/** files containing the no-binding feature-flag vocabulary.

    An empty list means the no-binding arm is not reachable through any
    production path (GLHS-A02).
    """
    if not services_root.is_dir():
        raise ValueError(f"services_root_missing:{services_root}")
    offenders: list[str] = []
    for path in sorted(services_root.rglob("*")):
        if not path.is_file() or path.suffix not in {
            ".py",
            ".toml",
            ".yaml",
            ".yml",
            ".env.example",
            ".md",
            ".json",
        }:
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if path.suffix == ".py":
            present = _python_flag_present(content)
        else:
            present = any(token in content.lower() for token in FLAG_VOCABULARY)
        if present:
            offenders.append(str(path))
    return offenders


def validate_import_boundary(services_root: Path) -> list[str]:
    """Return services/** files referencing the evaluation-only ablation package."""
    if not services_root.is_dir():
        raise ValueError(f"services_root_missing:{services_root}")
    offenders: list[str] = []
    for path in sorted(services_root.rglob("*.py")):
        if any(part.startswith(".") for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(token in content for token in FORBIDDEN_REFERENCES):
            offenders.append(str(path))
    return offenders


def validate_execution_against_expected(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit observed outcomes against frozen expected admissibility (arm B).

    Arm B (GLHS_EXACT_BINDING) is the production composition: its outcomes must
    match the frozen expectation for every schedule for a run to be
    claim-eligible.  Arm A outcomes are the measured ablation quantity and are
    not pre-judged here.
    """
    mismatches: list[dict[str, Any]] = []
    for record in records:
        if str(record["arm"]) != GLHS_EXACT_BINDING:
            continue
        expected = str(record["expected_admissibility"])
        observed_admitted = bool(record["admitted"])
        expected_admitted = expected == "valid_commit"
        if observed_admitted != expected_admitted:
            mismatches.append(
                {
                    "schedule_id": str(record["schedule_id"]),
                    "expected": expected,
                    "admitted": observed_admitted,
                    "rejection_reason_code": record.get("rejection_reason_code"),
                }
            )
    return {"valid": not mismatches, "mismatches": mismatches}
