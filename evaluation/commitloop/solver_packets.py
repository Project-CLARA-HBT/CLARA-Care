"""Condition-specific solver packets; construction gold is deliberately absent."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Protocol

from evaluation.commitloop.oracle import grace_end_for_case
from evaluation.commitloop.production_context import compile_glhs_v2_full_context
from evaluation.commitloop.schema import ConstructedCase, TimelineEvent
from evaluation.comparator_studies.bitemporal_state_arbitration.adapter import (
    btsa_context,
)
from evaluation.comparator_studies.commitloop_baselines import (
    last_write_wins,
    long_context,
    naive_rag,
    temporal_bm25,
)

CONDITIONS = (
    "full_authorized_history",
    "long_context_chronological",
    "naive_rag",
    "lww",
    "btsa",
    "glhs_no_predicate_engine",
    "glhs_no_bitemporal_knowledge_time",
    "glhs_hybrid",
    "glhs_hybrid_thss_strict",
)

# V21/V22 and all V5/V6 validators intentionally retain ``CONDITIONS`` above.
# A future exploratory protocol may opt into this stronger retrieval comparator
# only through its own frozen inventory; it cannot silently alter past runs.
EXPLORATORY_V7_CONDITIONS = (*CONDITIONS, "temporal_bm25", "glhs_v2_full")


def _event(event: TimelineEvent) -> dict[str, Any]:
    return {
        "evidence_id": event.evidence_id,
        "resource_type": event.resource_type,
        "status": event.status,
        "codes": [list(item) for item in event.codes],
        "valid_at": event.valid_at.isoformat() if event.valid_at else None,
        "known_at": event.known_at.isoformat(),
        "encounter_reference": event.encounter_reference,
        "relation": event.source.get("relation"),
    }


def _event_without_knowledge_time(event: TimelineEvent) -> dict[str, Any]:
    """Project only already-visible evidence while ablating its known-time field."""

    projected = _event(event)
    projected.pop("known_at")
    return projected


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class ProductionStrictContextBuilder(Protocol):
    def __call__(
        self,
        case: ConstructedCase,
        events: tuple[TimelineEvent, ...],
        *,
        valid_cutoff: datetime,
        known_cutoff: datetime,
    ) -> dict[str, Any]: ...


def build_solver_packets(
    case: ConstructedCase,
    events: tuple[TimelineEvent, ...],
    *,
    valid_cutoff: datetime,
    known_cutoff: datetime,
    production_strict_context: ProductionStrictContextBuilder | None = None,
    conditions: tuple[str, ...] = CONDITIONS,
) -> dict[str, dict[str, Any]]:
    if case.status != "ELIGIBLE" or case.target is None:
        return {}
    if not conditions or len(conditions) != len(set(conditions)) or not set(conditions).issubset(
        EXPLORATORY_V7_CONDITIONS
    ):
        raise ValueError("solver_packet_condition_inventory_invalid")
    valid_visible = [
        item
        for item in events
        if item.valid_at is not None and item.valid_at <= valid_cutoff
    ]
    visible = [item for item in valid_visible if item.known_at <= known_cutoff]
    chronological = sorted(
        visible, key=lambda item: (item.valid_at or item.known_at, item.evidence_id)
    )
    target_pair = (case.target["system"], case.target["code"])
    relevant = [item for item in visible if target_pair in item.codes]
    retrieved = sorted(
        relevant,
        key=lambda item: (
            item.valid_at or item.known_at,
            item.known_at,
            item.evidence_id,
        ),
        reverse=True,
    )[:5]
    serialized_visible = [_event(item) for item in visible]
    serialized_chronological = [_event(item) for item in chronological]
    conflicts = [
        item.evidence_id
        for item in visible
        if item.source.get("relation") == "contradicts"
    ]
    serialized_retrieved = [_event(item) for item in retrieved]
    assertion_hashes = [
        {"assertion_id": item["evidence_id"], "sha256": _hash(item)}
        for item in serialized_retrieved
    ]
    strict_sufficiency = (
        "CONFLICTED"
        if conflicts
        else ("INSUFFICIENT_EVIDENCE" if not retrieved else "CLEAR")
    )
    strict_thss = {
        "representation": "strict_task_purpose_thss",
        "subject_scope_token": case.subject_token,
        "state_version": 1,
        "policy_version": "commitloop.v1",
        "consent_version": "synthetic-protocol-consent.v1",
        "actor": "evaluation_solver",
        "purpose": "synthetic_protocol_evaluation",
        "task": "reconcile_future_oriented_commitment",
        "valid_cutoff": valid_cutoff.isoformat(),
        "known_cutoff": known_cutoff.isoformat(),
        "included_commitment_ids": [case.case_id],
        "included_evidence_ids": [item.evidence_id for item in retrieved],
        "included_assertion_ids": [item.evidence_id for item in retrieved],
        "assertion_hashes": assertion_hashes,
        "events": serialized_retrieved,
        "exclusion_summary": {
            "not_selected_for_task_count": len(visible) - len(retrieved)
        },
        "conflicts": conflicts,
        "critical_fact_coverage": {
            "covered": int(bool(retrieved)),
            "required": 1,
        },
        "authority_classes": sorted({item.resource_type for item in retrieved}),
        "missing_fields": [] if retrieved else ["fulfillment_evidence"],
        "evidence_sufficiency": strict_sufficiency,
        "decision": (
            "ESCALATE" if conflicts else ("ABSTAIN" if not retrieved else "DISCLOSE")
        ),
        "expires_at": (known_cutoff + timedelta(minutes=5)).isoformat(),
    }
    strict_thss["snapshot_sha256"] = _hash(strict_thss)
    grace_end = grace_end_for_case(case)
    common = {
        "case_id": case.case_id,
        "task": "reconcile_future_oriented_commitment",
        "anchor_evidence_id": case.anchor_evidence_id,
        "anchor_valid_time": (
            case.anchor_valid_time.isoformat() if case.anchor_valid_time else None
        ),
        "domain": case.domain,
        "action": case.action,
        "target": case.target,
        "due_time": case.due_time.isoformat() if case.due_time else None,
        "grace_end": grace_end.isoformat() if grace_end is not None else None,
        "valid_cutoff": valid_cutoff.isoformat(),
        "known_cutoff": known_cutoff.isoformat(),
    }
    strict_context = (
        production_strict_context(
            case,
            events,
            valid_cutoff=valid_cutoff,
            known_cutoff=known_cutoff,
        )
        if production_strict_context is not None
        else strict_thss
    )
    if production_strict_context is not None and not isinstance(
        strict_context.get("production_path"), dict
    ):
        raise ValueError("production_strict_context_provenance_required")
    packets = {}
    for condition in conditions:
        ctx: dict[str, Any]
        if condition == "full_authorized_history":
            ctx = {
                "representation": "chronological_full_authorized",
                "events": serialized_chronological,
            }
        elif condition == "long_context_chronological":
            ctx = {**long_context(serialized_visible)}
        elif condition == "naive_rag":
            ctx = {
                **naive_rag(
                    serialized_visible,
                    system=case.target["system"],
                    code=case.target["code"],
                )
            }
        elif condition == "temporal_bm25":
            ctx = {
                **temporal_bm25(
                    serialized_visible,
                    query_terms=[case.target["system"], case.target["code"], case.action or ""],
                    valid_cutoff=valid_cutoff.isoformat(),
                )
            }
        elif condition == "lww":
            ctx = {**last_write_wins(serialized_visible)}
        elif condition == "btsa":
            ctx = {
                **btsa_context(
                    serialized_chronological,
                    valid_at=valid_cutoff,
                    known_at=known_cutoff,
                )
            }
        elif condition == "glhs_no_predicate_engine":
            ctx = {
                "representation": "glhs_bitemporal_without_predicate",
                "events": [_event(item) for item in chronological],
                "provenance_closed": True,
            }
        elif condition == "glhs_no_bitemporal_knowledge_time":
            ctx = {
                "representation": "glhs_valid_time_only",
                "events": [_event_without_knowledge_time(item) for item in visible],
                "predicate": case.fulfillment_predicate,
            }
        elif condition == "glhs_hybrid":
            ctx = {
                "representation": "glhs_bitemporal_predicate_hybrid",
                "events": [_event(item) for item in chronological],
                "predicate": case.fulfillment_predicate,
                "provenance_closed": True,
            }
        elif condition == "glhs_hybrid_thss_strict":
            ctx = {
                **strict_context,
                "predicate": case.fulfillment_predicate,
            }
        elif condition == "glhs_v2_full":
            ctx = {
                **compile_glhs_v2_full_context(
                    case,
                    events,
                    valid_cutoff=valid_cutoff,
                    known_cutoff=known_cutoff,
                )
            }
        else:
            raise ValueError(f"unsupported condition: {condition}")
        payload = {**common, "condition": condition, "context": ctx}
        packets[condition] = {**payload, "packet_sha256": _hash(payload)}
    return packets
