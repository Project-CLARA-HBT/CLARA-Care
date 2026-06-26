"""Unit tests for the role-gated research telemetry sanitizer + PII serializer.

Covers Requirement 3 (Role-Gated Research Telemetry) and the telemetry half of
Requirement 15.4 (PII-safe personalization): role gating, fail-closed behavior,
alias-only sanitized summaries, and PHR/medicine-cabinet PII exclusion.
"""

from __future__ import annotations

import json

from clara_api.core.research_telemetry import (
    ALLOWED_STAGE_LABELS,
    FLOW_STAGE_ALIAS_MAP,
    build_sanitized_summary,
    sanitize_telemetry,
    strip_pii,
)


def _sample_payload() -> dict:
    return {
        "flow_events": [
            {"stage": "planner", "status": "completed"},
            {"stage": "retrieval_v2", "status": "completed", "label": "RAG mode retrieval"},
            {"stage": "synthesis", "status": "active"},
            # An internal/unknown stage that must never surface in the summary.
            {"stage": "rag_internal_mode", "status": "running", "label": "RAG mode"},
        ],
        "active_stage": "synthesis",
        "search_plan": {"subqueries": ["a", "b"]},
        # PHR/cabinet PII embedded in the raw telemetry.
        "personal_context": {
            "profile": {"full_name": "Nguyen Van Patient", "dob": "1980-01-01"},
            "medications": [{"name": "warfarin-secret"}],
        },
        "medicine_cabinet": {"items": [{"name": "metformin-private"}]},
    }


# --- Role gating (R3.1, R3.3, R3.6) -----------------------------------------


def test_admin_gets_summary_and_detailed() -> None:
    out = sanitize_telemetry(_sample_payload(), role="admin")
    assert "summary" in out
    assert "detailed" in out


def test_non_admin_roles_get_summary_only() -> None:
    for role in ("normal", "researcher", "doctor"):
        out = sanitize_telemetry(_sample_payload(), role=role)
        assert "summary" in out, role
        assert "detailed" not in out, role


def test_unknown_role_is_fail_closed() -> None:
    for role in ("guest", "", "ADMINISTRATOR", None, 123, "superuser"):
        assert sanitize_telemetry(_sample_payload(), role=role) == {}


def test_role_is_case_insensitive() -> None:
    out = sanitize_telemetry(_sample_payload(), role="Admin")
    assert "summary" in out and "detailed" in out


# --- Sanitized summary uses only alias labels (R3.2, R3.5) ------------------


def test_summary_labels_are_alias_only() -> None:
    summary = build_sanitized_summary(_sample_payload())
    assert summary["stages"], "expected at least one resolved stage"
    for stage in summary["stages"]:
        assert stage["label"] in ALLOWED_STAGE_LABELS


def test_summary_strips_internal_labels() -> None:
    out = sanitize_telemetry(_sample_payload(), role="doctor")
    serialized = json.dumps(out, ensure_ascii=False)
    # Raw internal labels and unmapped internal stages never appear.
    assert "RAG mode" not in serialized
    assert "rag_internal_mode" not in serialized


def test_summary_active_stage_is_mapped() -> None:
    summary = build_sanitized_summary(_sample_payload())
    # "synthesis" maps to stage_id "synthesis".
    assert summary["active_stage"] == "synthesis"


def test_summary_dedupes_by_stage_id_keeping_latest_status() -> None:
    payload = {
        "flow_events": [
            {"stage": "synthesis", "status": "active"},
            {"stage": "answer_synthesis", "status": "completed"},  # same stage_id
        ]
    }
    summary = build_sanitized_summary(payload)
    synthesis_stages = [s for s in summary["stages"] if s["stage_id"] == "synthesis"]
    assert len(synthesis_stages) == 1
    assert synthesis_stages[0]["status"] == "completed"


def test_unknown_status_normalized() -> None:
    payload = {"flow_events": [{"stage": "planner", "status": "weird-internal-state"}]}
    summary = build_sanitized_summary(payload)
    assert summary["stages"][0]["status"] == "unknown"


# --- PII exclusion in the detailed rail (R3.4, R15.4) -----------------------


def test_detailed_excludes_phr_and_cabinet_pii() -> None:
    out = sanitize_telemetry(_sample_payload(), role="admin")
    serialized = json.dumps(out, ensure_ascii=False)
    for token in (
        "Nguyen Van Patient",
        "1980-01-01",
        "warfarin-secret",
        "metformin-private",
    ):
        assert token not in serialized, token


def test_detailed_retains_non_pii_diagnostics() -> None:
    out = sanitize_telemetry(_sample_payload(), role="admin")
    detailed = out["detailed"]
    # Non-PII diagnostic telemetry survives the scrub.
    assert detailed.get("search_plan", {}).get("subqueries") == ["a", "b"]


def test_strip_pii_drops_email_and_phone_markers() -> None:
    scrubbed = strip_pii(
        {"note": "contact me at leak@example.com", "ref": "id 0901234567 here", "ok": "fine"}
    )
    assert scrubbed["note"] == ""
    assert scrubbed["ref"] == ""
    assert scrubbed["ok"] == "fine"


def test_strip_pii_drops_nested_pii_subtrees() -> None:
    scrubbed = strip_pii(
        {"outer": {"medicine_cabinet": {"items": ["secretX"]}, "kept": 5}}
    )
    assert "medicine_cabinet" not in scrubbed["outer"]
    assert scrubbed["outer"]["kept"] == 5


# --- Robustness -------------------------------------------------------------


def test_non_dict_payload_yields_empty_summary() -> None:
    out = sanitize_telemetry("not-a-dict", role="admin")
    assert out["summary"] == {"stages": [], "active_stage": ""}
    assert out["detailed"] == {}


def test_alias_map_labels_are_consistent() -> None:
    # Every alias value's label is a member of the allowed-label set (invariant).
    for _stage_id, label in FLOW_STAGE_ALIAS_MAP.values():
        assert label in ALLOWED_STAGE_LABELS
