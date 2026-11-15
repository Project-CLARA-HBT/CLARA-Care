"""Tests for the DIMVA venue2027 campaign generator (task DIMVA-X02_campaign_gen).

Positive vectors cover determinism, every registered family, campaign-level-only
labeling, schema-shaped minimal events (validated against the frozen
``research/venue2027/dimva/protocols/event.schema.json`` contract), the stage
semantics of each family and the harmless control. Adversarial vectors prove
fail-closed refusal of per-event labels, unknown families, invalid seeds/tenants,
PHI-like content, off-schema events and label leakage through the campaign
identifier or the event surface.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

from evaluation.venue2027.dimva import campaign_generator as cg

TOOL_DIR = pathlib.Path(__file__).resolve().parents[3] / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOL_DIR))

import schema_validator as sv  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO / "research/venue2027/dimva/protocols/event.schema.json"

SEED = 2027
TENANT = "tenant_a"

_ALL_FAMILIES = (
    "purpose_probe",
    "cross_principal_retry",
    "expired_token_replay",
    "cadence_shift",
    "harmless_control",
)
_ATTACK_FAMILIES = tuple(f for f in _ALL_FAMILIES if f != "harmless_control")


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------- positive


@pytest.mark.parametrize("family", _ALL_FAMILIES)
def test_generate_covers_each_registered_family(family: str) -> None:
    campaign = cg.generate(SEED, family, TENANT)
    assert campaign.family == family
    assert campaign.campaign_id
    assert campaign.events


def test_deterministic_same_inputs_yield_identical_campaign() -> None:
    first = cg.generate(SEED, "purpose_probe", TENANT)
    second = cg.generate(SEED, "purpose_probe", TENANT)
    assert first.to_dict() == second.to_dict()
    assert first.events == second.events
    assert first.campaign_id == second.campaign_id


def test_different_seed_yields_distinct_campaign() -> None:
    a = cg.generate(1, "purpose_probe", TENANT)
    b = cg.generate(2, "purpose_probe", TENANT)
    assert a.campaign_id != b.campaign_id
    assert a.to_dict() != b.to_dict()


def test_campaign_carries_required_top_level_fields() -> None:
    campaign = cg.generate(SEED, "cross_principal_retry", TENANT)
    payload = campaign.to_dict()
    assert set(payload) >= {
        "campaign_id",
        "tenant",
        "family",
        "events",
        "campaign_label",
        "violated_invariant",
    }
    assert payload["tenant"] == TENANT
    assert payload["family"] == "cross_principal_retry"


def test_label_exists_only_at_campaign_level() -> None:
    for family in _ALL_FAMILIES:
        campaign = cg.generate(SEED, family, TENANT)
        for event in campaign.events:
            assert "campaign_label" not in event
            assert "violated_invariant" not in event
            assert "label" not in event
            assert "is_attack" not in event
            assert "attacker" not in event


def test_events_conform_to_frozen_minimal_event_schema() -> None:
    schema = _schema()
    for family in _ALL_FAMILIES:
        campaign = cg.generate(SEED, family, TENANT)
        for event in campaign.events:
            errors = sv.validate_instance(dict(event), schema, schema_path=SCHEMA_PATH)
            assert errors == (), (family, event, errors)


def test_events_use_exactly_the_seven_schema_fields() -> None:
    for family in _ALL_FAMILIES:
        campaign = cg.generate(SEED, family, TENANT)
        for event in campaign.events:
            assert set(event) == set(cg.EVENT_FIELDS)


def test_campaign_id_is_opaque_and_leak_free() -> None:
    for family in _ALL_FAMILIES:
        campaign = cg.generate(SEED, family, TENANT)
        assert campaign.campaign_id.startswith("camp-")
        lowered = campaign.campaign_id.lower()
        for token in (family, campaign.campaign_label, campaign.violated_invariant, TENANT):
            assert token.lower() not in lowered


def test_events_never_leak_tenant_family_or_invariant_strings() -> None:
    for family in _ALL_FAMILIES:
        campaign = cg.generate(SEED, family, TENANT)
        for event in campaign.events:
            serialized = json.dumps(event).lower()
            assert TENANT.lower() not in serialized
            assert family.lower() not in serialized
            assert campaign.violated_invariant.lower() not in serialized
            assert campaign.campaign_label.lower() not in serialized


def test_actor_and_scope_are_opaque_hex_digests() -> None:
    campaign = cg.generate(SEED, "expired_token_replay", TENANT)
    for event in campaign.events:
        assert len(event["actor"]) == 64
        assert all(c in "0123456789abcdef" for c in event["actor"])
        assert len(event["scope"]) == 64
        assert all(c in "0123456789abcdef" for c in event["scope"])


def test_purpose_probe_reuses_principal_and_rotates_purpose() -> None:
    campaign = cg.generate(SEED, "purpose_probe", TENANT)
    assert campaign.violated_invariant == cg.INVARIANT_PURPOSE_SCOPE_AUTHORIZATION
    actors = {e["actor"] for e in campaign.events}
    scopes = {e["scope"] for e in campaign.events}
    purposes = {e["purpose"] for e in campaign.events}
    assert len(actors) == 1
    assert len(purposes) >= 2
    assert len(scopes) >= 2
    assert any(not e["allowed"] for e in campaign.events)


def test_cross_principal_retry_rotates_principals() -> None:
    campaign = cg.generate(SEED, "cross_principal_retry", TENANT)
    assert campaign.violated_invariant == cg.INVARIANT_PRINCIPAL_SCOPE_BINDING
    actors = [e["actor"] for e in campaign.events]
    assert len(set(actors)) >= 3
    assert all(not e["allowed"] for e in campaign.events[1:])


def test_expired_token_replay_resumes_beyond_freshness_horizon() -> None:
    campaign = cg.generate(SEED, "expired_token_replay", TENANT)
    assert campaign.violated_invariant == cg.INVARIANT_CREDENTIAL_EPOCH_FRESHNESS
    ts_values = [e["ts"] for e in campaign.events]
    replay_gaps = [b - a for a, b in zip(ts_values, ts_values[1:])]
    assert ts_values[1] - ts_values[0] >= cg.TOKEN_EXPIRY_HORIZON_BUCKETS
    assert all(gap >= 1 for gap in replay_gaps)
    assert all(not e["allowed"] for e in campaign.events[1:])


def test_cadence_shift_gaps_exceed_pacing_window() -> None:
    campaign = cg.generate(SEED, "cadence_shift", TENANT)
    assert campaign.violated_invariant == cg.INVARIANT_PACING_BASELINE_STABILITY
    ts_values = [e["ts"] for e in campaign.events]
    gaps = [b - a for a, b in zip(ts_values, ts_values[1:])]
    assert gaps
    assert all(gap > cg.PACE_WINDOW_BUCKETS for gap in gaps)
    assert ts_values == sorted(ts_values)


def test_harmless_control_is_benign_with_no_violated_invariant() -> None:
    campaign = cg.generate(SEED, "harmless_control", TENANT)
    assert campaign.campaign_label == cg.LABEL_BENIGN
    assert campaign.violated_invariant == cg.INVARIANT_NONE
    ts_values = [e["ts"] for e in campaign.events]
    gaps = [b - a for a, b in zip(ts_values, ts_values[1:])]
    assert all(1 <= gap <= cg.PACE_WINDOW_BUCKETS for gap in gaps)
    actors = {e["actor"] for e in campaign.events}
    assert len(actors) == 1


def test_attack_campaigns_are_labeled_attack_with_invariant() -> None:
    for family in _ATTACK_FAMILIES:
        campaign = cg.generate(SEED, family, TENANT)
        assert campaign.campaign_label == cg.LABEL_ATTACK
        assert campaign.violated_invariant != cg.INVARIANT_NONE


def test_campaign_is_json_serializable() -> None:
    campaign = cg.generate(SEED, "cadence_shift", TENANT)
    encoded = json.dumps(campaign.to_dict(), sort_keys=True)
    assert isinstance(encoded, str)
    reparsed = json.loads(encoded)
    assert reparsed == campaign.to_dict()


def test_distinct_tenants_yield_distinct_campaigns() -> None:
    a = cg.generate(SEED, "purpose_probe", "tenant_a")
    b = cg.generate(SEED, "purpose_probe", "tenant_b")
    assert a.campaign_id != b.campaign_id
    assert b.tenant == "tenant_b"


# ------------------------------------------------------------ adversarial


def test_unknown_family_refused() -> None:
    with pytest.raises(cg.CampaignError) as exc:
        cg.generate(SEED, "not_a_family", TENANT)
    assert exc.value.reason_code == "UNKNOWN_FAMILY"


def test_per_event_label_fields_refused() -> None:
    for field in ("label", "campaign_label", "violated_invariant", "attacker_label", "is_attack"):
        with pytest.raises(cg.CampaignError) as exc:
            cg._make_event(
                actor="a" * 64,
                tool="record_read",
                scope="c" * 64,
                allowed=True,
                purpose="self_care",
                ts=1,
                campaign_id="camp-0123456789abcdef",
                **{field: "ATTACK"},
            )
        assert exc.value.reason_code == "EVENT_LABEL_FIELD_FORBIDDEN"


def test_off_schema_event_field_refused() -> None:
    with pytest.raises(cg.CampaignError) as exc:
        cg._make_event(
            actor="a" * 64,
            tool="record_read",
            scope="c" * 64,
            allowed=True,
            purpose="self_care",
            ts=1,
            campaign_id="camp-0123456789abcdef",
            tenant="tenant_a",
        )
    assert exc.value.reason_code == "EVENT_FIELD_MISMATCH"


def test_tampered_event_fails_schema_shape_gate() -> None:
    campaign = cg.generate(SEED, "purpose_probe", TENANT)
    tampered = list(campaign.events)
    broken = dict(tampered[0])
    broken["allowed"] = "yes"
    tampered[0] = broken
    with pytest.raises(cg.CampaignError) as exc:
        cg._assert_schema_shaped(campaign.__class__(**{**campaign.to_dict(), "events": tuple(tampered)}))
    assert exc.value.reason_code == "EVENT_FIELD_MISMATCH"


def test_tampered_event_with_extra_field_fails_schema_shape_gate() -> None:
    campaign = cg.generate(SEED, "harmless_control", TENANT)
    tampered = list(campaign.events)
    broken = dict(tampered[0])
    broken["campaign_label"] = cg.LABEL_ATTACK
    tampered[0] = broken
    with pytest.raises(cg.CampaignError) as exc:
        cg._assert_schema_shaped(
            campaign.__class__(**{**campaign.to_dict(), "events": tuple(tampered)})
        )
    assert exc.value.reason_code == "EVENT_FIELD_MISMATCH"


@pytest.mark.parametrize("bad_seed", (-1, "7", 1.5, None, True))
def test_invalid_seed_refused(bad_seed: object) -> None:
    with pytest.raises(cg.CampaignError) as exc:
        cg.generate(bad_seed, "purpose_probe", TENANT)  # type: ignore[arg-type]
    assert exc.value.reason_code == "INVALID_SEED"


@pytest.mark.parametrize(
    "bad_tenant", ("", "has space", "-leading", "x" * 40, "tenant;drop", "p@th")
)
def test_invalid_tenant_refused(bad_tenant: str) -> None:
    with pytest.raises(cg.CampaignError) as exc:
        cg.generate(SEED, "purpose_probe", bad_tenant)
    assert exc.value.reason_code == "INVALID_TENANT"


def test_phi_like_tenant_refused() -> None:
    with pytest.raises(cg.CampaignError) as exc:
        cg.generate(SEED, "purpose_probe", "patient_1")
    assert exc.value.reason_code == "PHI_FIELD_PRESENT"


def test_generated_campaigns_are_phi_free() -> None:
    for family in _ALL_FAMILIES:
        for tenant in ("tenant_a", "tenant_b"):
            campaign = cg.generate(SEED, family, tenant)
            lowered = json.dumps(campaign.to_dict(), sort_keys=True).lower()
            for marker in cg.PHI_SCAN_MARKERS:
                assert marker not in lowered, (family, tenant, marker)


def test_no_reason_code_field_anywhere_on_event_surface() -> None:
    for family in _ALL_FAMILIES:
        campaign = cg.generate(SEED, family, TENANT)
        for event in campaign.events:
            assert "reason_code" not in event
            assert "reason" not in event


def test_repeated_generation_is_idempotent_across_call_order() -> None:
    a = cg.generate(SEED, "expired_token_replay", TENANT)
    cg.generate(SEED, "cadence_shift", TENANT)
    b = cg.generate(SEED, "expired_token_replay", TENANT)
    assert a.to_dict() == b.to_dict()


def test_family_specs_guard_against_label_drift() -> None:
    assert cg.FAMILY_SPECS["harmless_control"].violated_invariant == cg.INVARIANT_NONE
    assert cg.FAMILY_SPECS["harmless_control"].campaign_label == cg.LABEL_BENIGN
    for family in _ATTACK_FAMILIES:
        spec = cg.FAMILY_SPECS[family]
        assert spec.campaign_label == cg.LABEL_ATTACK
        assert spec.violated_invariant != cg.INVARIANT_NONE
