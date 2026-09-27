"""Frozen-protocol validation, Gate C arm-diff, and no-production-flag checks.

``validate_schedules`` freezes the 352-schedule inventory invariants:
9 families x (32 adversarial per 8 negative families + 96 clean controls),
per-family expected admissibility matching the family definition, and
``current_coordinates_ok`` for every schedule.

``validate_no_production_flag`` scans ``services/**`` for the forbidden
feature-flag vocabulary (``disable_exact_binding``, ``binding_mask``,
``skip_snapshot_digest``, ``no_evidence_binding``, ``component_ablation``):
all ablation masks must exist under ``evaluation/`` only (GLHS-A02).
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.glhs_binding_component_ablation.binding_mask import (
    ALL_ARMS,
    ARMS,
    B000,
    B001,
    B010,
    B011,
    B100,
    B101,
    B110,
    B111,
)
from evaluation.glhs_binding_component_ablation.build_schedules import (
    FAMILY_IDS,
    SCHEDULES_PER_FAMILY,
    TOTAL_SCHEDULES,
)

FORBIDDEN_FLAG_VOCABULARY = (
    "disable_exact_binding",
    "binding_mask",
    "skip_snapshot_digest",
    "no_evidence_binding",
    "component_ablation",
    "disable_binding",
    "no_exact_binding",
)
FORBIDDEN_REFERENCES = ("glhs_binding_component_ablation",)

PROTOCOL_SCHEMA_VERSION = "glhs-binding-component-ablation-protocol.v1"
FROZEN_PROTOCOL_STATUS = "FROZEN"


def _sha256_canonical(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
    if not isinstance(arms, list) or set(arms) != set(ALL_ARMS):
        raise ValueError("protocol_arms_invalid")
    inventory = protocol.get("schedule_inventory") or {}
    if inventory.get("total") != TOTAL_SCHEDULES:
        raise ValueError(f"protocol_schedule_total_invalid:{inventory.get('total')}")
    if inventory.get("adversarial") != 256:
        raise ValueError(f"protocol_adversarial_count_invalid:{inventory.get('adversarial')}")
    if inventory.get("controls") != 96:
        raise ValueError(f"protocol_control_count_invalid:{inventory.get('controls')}")
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


def validate_schedule_hash(raw_bytes: bytes, expected_sha256: str) -> bool:
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if digest != expected_sha256:
        raise ValueError(
            f"schedule_hash_mismatch:expected={expected_sha256}:computed={digest}"
        )
    return True


def validate_schedules(schedules_doc: dict[str, Any]) -> dict[str, Any]:
    """Validate frozen schedule inventory structure and invariants."""
    schedules = schedules_doc.get("schedules")
    if not isinstance(schedules, list):
        raise TypeError("schedules_not_list")
    if len(schedules) != TOTAL_SCHEDULES:
        raise ValueError(f"schedule_count_mismatch:expected={TOTAL_SCHEDULES}:found={len(schedules)}")

    seen_ids: set[str] = set()
    family_counts: Counter[str] = Counter()

    for schedule in schedules:
        schedule_id = schedule.get("schedule_id")
        if not schedule_id or schedule_id in seen_ids:
            raise ValueError(f"duplicate_or_empty_schedule_id:{schedule_id}")
        seen_ids.add(schedule_id)

        family_name = schedule.get("family_name")
        if family_name not in FAMILY_IDS:
            raise ValueError(f"unknown_family_name:{family_name}")
        family_counts[family_name] += 1

        if schedule.get("kind") == "control":
            if schedule.get("expected_admissibility") != "valid_commit":
                raise ValueError(f"control_expected_admissibility_invalid:{schedule_id}")
        else:
            if schedule.get("expected_admissibility") != "invalid_commit_rejected":
                raise ValueError(f"adversarial_expected_admissibility_invalid:{schedule_id}")

        if not schedule.get("current_coordinates_ok"):
            raise ValueError(f"current_coordinates_not_ok:{schedule_id}")

    for family, expected_count in SCHEDULES_PER_FAMILY.items():
        if family_counts[family] != expected_count:
            raise ValueError(
                f"family_count_mismatch:{family}:expected={expected_count}:found={family_counts[family]}"
            )

    return {
        "total_schedules": len(schedules),
        "family_counts": dict(family_counts),
        "valid": True,
    }


def _python_flag_present(content: str) -> bool:
    """Find flag identifiers/usages while ignoring explanatory docstrings."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return any(token in content.lower() for token in FORBIDDEN_FLAG_VOCABULARY)
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
            and any(token in node.value.lower() for token in FORBIDDEN_FLAG_VOCABULARY)
        ):
            return True
        if isinstance(node, ast.Name) and node.id.lower() in FORBIDDEN_FLAG_VOCABULARY:
            return True
        if isinstance(node, ast.Attribute) and node.attr.lower() in FORBIDDEN_FLAG_VOCABULARY:
            return True
        if isinstance(node, ast.arg) and node.arg.lower() in FORBIDDEN_FLAG_VOCABULARY:
            return True
    return False


def validate_no_production_flag(services_root: Path) -> dict[str, Any]:
    """Scan services/** to ensure no ablation flag or bypass exists in production code."""
    offenders: list[dict[str, Any]] = []
    for path in services_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _python_flag_present(text):
            offenders.append({"path": str(path)})
    if offenders:
        raise RuntimeError(f"forbidden_production_flag_detected:{offenders}")
    return {"clean": True, "scanned_root": str(services_root)}


def validate_import_boundary(services_root: Path) -> dict[str, Any]:
    """Verify that services/** contains no imports of glhs_binding_component_ablation."""
    offenders: list[str] = []
    for path in services_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for ref in FORBIDDEN_REFERENCES:
            if ref in text:
                offenders.append(str(path))
    if offenders:
        raise RuntimeError(f"forbidden_evaluation_import_in_services:{offenders}")
    return {"clean": True, "scanned_root": str(services_root)}


def validate_execution_against_expected(
    records: list[dict[str, Any]],
    schedules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit arm executions against frozen schedule expected outcomes."""
    sched_map = {s["schedule_id"]: s for s in schedules}
    violations: list[str] = []

    for r in records:
        sid = r["schedule_id"]
        sched = sched_map.get(sid)
        if not sched:
            violations.append(f"unknown_schedule:{sid}")
            continue
        # Clean controls MUST always be admitted across ALL arms
        if sched["kind"] == "control" and not r["admitted"]:
            violations.append(
                f"clean_control_rejected:{sid}:arm={r['arm']}:reason={r.get('rejection_reason_code')}"
            )
        # B111 MUST reject all adversarial schedules
        if r["arm"] == B111 and sched["kind"] == "adversarial" and r["admitted"]:
            violations.append(f"full_binding_admitted_adversarial:{sid}")

    if violations:
        raise ValueError(f"execution_audit_failed:{violations[:5]}")
    return {"valid": True, "records_audited": len(records)}
