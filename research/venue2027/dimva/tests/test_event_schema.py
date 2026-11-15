"""Tests for the DIMVA-X01 minimal agent-event schema (P02).

Purpose
-------
Verify that ``research/venue2027/dimva/protocols/event.schema.json`` implements
the minimized authorized telemetry contract for GovernanceTrace: exactly seven
metadata fields (actor, tool, scope, allowed, purpose, ts, campaign_id) with
``additionalProperties: false``, no PHI/health-text/reason-code surface, and
fail-closed rejection of adversarial events (missing required fields, PHI-like
and free-text fields, non-boolean authorization outcome, extra properties).

Allowed input
-------------
The schema file and synthetic in-memory event fixtures. Read-only; no network,
no randomness, no clock, no PHI.

Failure semantics
-----------------
Each violation is an ordinary pytest assertion failure with a stable test name;
nothing is silently skipped. Version: 1.0.0.
"""

from __future__ import annotations

import json
import pathlib
import sys

TOOL_DIR = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOL_DIR))

import schema_validator as sv  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPO / "research/venue2027/dimva/protocols/event.schema.json"

_ACTOR = "a" * 64
_ACTOR_ALT = "b" * 64
_SCOPE = "c" * 64
_SCOPE_ALT = "d" * 64


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _valid_event(**overrides: object) -> dict:
    event: dict[str, object] = {
        "actor": _ACTOR,
        "tool": "record_read",
        "scope": _SCOPE,
        "allowed": False,
        "purpose": "self_care",
        "ts": 2937840,
        "campaign_id": "synthetic-campaign-0001",
    }
    event.update(overrides)
    return event


# ------------------------------------------------------------- schema shape
def test_schema_is_minimal_seven_field_contract() -> None:
    schema = _load_schema()
    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "actor",
        "tool",
        "scope",
        "allowed",
        "purpose",
        "ts",
        "campaign_id",
    ]
    assert set(schema["properties"]) == {
        "actor",
        "tool",
        "scope",
        "allowed",
        "purpose",
        "ts",
        "campaign_id",
    }


def test_schema_declares_minimality_note() -> None:
    description = _load_schema()["description"]
    assert "MINIMALITY NOTE" in description
    assert "additionalProperties" in description


def test_schema_has_no_phi_like_property_names() -> None:
    forbidden = (
        "patient",
        "name",
        "email",
        "phone",
        "address",
        "diagnosis",
        "note",
        "prompt",
        "reason_code",
        "reason",
        "dob",
        "mrn",
        "ssn",
    )
    schema = _load_schema()
    lowered = json.dumps(schema).lower()
    for token in forbidden:
        assert f'"{token}"' not in lowered, f"schema retains PHI-like field {token!r}"


def test_schema_has_no_explicit_attacker_label_field() -> None:
    schema = _load_schema()
    assert "label" not in schema["properties"]
    assert "attacker" not in schema["properties"]
    assert "is_attack" not in schema["properties"]


def test_schema_uses_only_shared_validator_keywords() -> None:
    schema = _load_schema()
    for keyword in schema:
        assert keyword in sv.SUPPORTED_KEYWORDS, keyword


# ----------------------------------------------------------- positive cases
def test_positive_benign_retry_event_valid() -> None:
    errors = sv.validate_instance(_valid_event(), _load_schema(), schema_path=SCHEMA_PATH)
    assert not errors, errors


def test_positive_denied_probe_event_valid() -> None:
    event = _valid_event(
        actor=_ACTOR_ALT,
        scope=_SCOPE_ALT,
        tool="record_export",
        allowed=False,
        purpose="care_delivery",
        campaign_id="synthetic-campaign-0002",
    )
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert not errors, errors


def test_positive_allowed_delegation_event_valid() -> None:
    event = _valid_event(
        actor=_ACTOR_ALT,
        tool="record_write",
        allowed=True,
        purpose="care_team_handoff",
        campaign_id="synthetic-campaign-0003",
    )
    schema = _load_schema()
    assert sv.validate_instance(event, schema, schema_path=SCHEMA_PATH) == ()
    assert sv.is_valid(event, schema, schema_path=SCHEMA_PATH)


def test_positive_events_form_reproducible_batch() -> None:
    schema = _load_schema()
    batch = [
        _valid_event(),
        _valid_event(actor=_ACTOR_ALT, scope=_SCOPE_ALT, allowed=True),
        _valid_event(tool="record_export", purpose="audit", allowed=False),
    ]
    assert len(batch) >= 3
    expected = [sv.validate_instance(e, schema, schema_path=SCHEMA_PATH) for e in batch]
    assert expected == [(), (), ()], expected
    repeat = [sv.validate_instance(e, schema, schema_path=SCHEMA_PATH) for e in batch]
    assert repeat == expected, "validation must be deterministic"


# -------------------------------------------------------- adversarial cases
def test_adversarial_missing_tool_rejected() -> None:
    event = _valid_event()
    del event["tool"]
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert "REQUIRED_MISSING" in errors, errors


def test_adversarial_missing_scope_rejected() -> None:
    event = _valid_event()
    del event["scope"]
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert "REQUIRED_MISSING" in errors, errors


def test_adversarial_phi_like_field_rejected() -> None:
    event = _valid_event()
    event["patient_name"] = "Nguyen Van A"
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert "ADDITIONAL_PROPERTY" in errors, errors


def test_adversarial_free_text_reason_field_rejected() -> None:
    event = _valid_event()
    event["reason"] = "cần xem hồ sơ bệnh án của bệnh nhân"
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert "ADDITIONAL_PROPERTY" in errors, errors


def test_adversarial_rejection_reason_code_field_rejected() -> None:
    """Leak-safe RQ1 control: reason codes must never enter the event surface."""
    event = _valid_event()
    event["reason_code"] = "CROSS_SCOPE_DENIAL_RULE"
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert "ADDITIONAL_PROPERTY" in errors, errors


def test_adversarial_clear_text_principal_rejected() -> None:
    event = _valid_event(actor="dr.sinh-123")
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert "PATTERN_MISMATCH" in errors, errors


def test_adversarial_non_bool_allowed_rejected() -> None:
    schema = _load_schema()
    for bad in ("false", 0, None, 1):
        event = _valid_event(allowed=bad)
        errors = sv.validate_instance(event, schema, schema_path=SCHEMA_PATH)
        assert "TYPE_MISMATCH" in errors, (bad, errors)


def test_adversarial_extra_field_rejected() -> None:
    event = _valid_event()
    event["attacker_label"] = "probe"
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert "ADDITIONAL_PROPERTY" in errors, errors


def test_adversarial_unknown_purpose_rejected() -> None:
    event = _valid_event(purpose="curiosity")
    errors = sv.validate_instance(event, _load_schema(), schema_path=SCHEMA_PATH)
    assert "ENUM_MISMATCH" in errors, errors


def test_adversarial_bad_timestamp_rejected() -> None:
    schema = _load_schema()
    for bad in (-1, "2026-11-15T00:00:00Z", None):
        event = _valid_event(ts=bad)
        errors = sv.validate_instance(event, schema, schema_path=SCHEMA_PATH)
        assert errors, (bad, errors)


def test_adversarial_missing_actor_and_campaign_rejected() -> None:
    schema = _load_schema()
    for key in ("actor", "campaign_id"):
        event = _valid_event()
        del event[key]
        errors = sv.validate_instance(event, schema, schema_path=SCHEMA_PATH)
        assert "REQUIRED_MISSING" in errors, (key, errors)
