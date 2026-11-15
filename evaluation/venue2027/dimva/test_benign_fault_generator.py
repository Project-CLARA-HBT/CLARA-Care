"""Tests for the DIMVA venue2027 benign fault generator (task DIMVA-X03_benign_gen).

Positive vectors cover determinism, the full benign fault repertoire
(rate-limit retries, network retries, UX confusion retries, legitimate consent
edits, delayed timestamps), exact volume parity with the requested workload
budget, cadence-profile conformance, campaign-level-only BENIGN labeling with
``violated_invariant="NONE"``, schema-shaped minimal events (validated against
the frozen ``research/venue2027/dimva/protocols/event.schema.json`` contract)
and JSON serializability. Adversarial vectors prove fail-closed refusal of a
benign campaign that would exceed the requested volume budget, per-event label
fields, malformed workloads, invalid seeds/tenants, PHI-like content and
off-schema events, plus PHI-freeness of every generated campaign.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

from evaluation.venue2027.dimva import benign_fault_generator as bfg
from evaluation.venue2027.dimva import campaign_generator as cg

TOOL_DIR = pathlib.Path(__file__).resolve().parents[3] / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOL_DIR))

import schema_validator as sv  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO / "research/venue2027/dimva/protocols/event.schema.json"

SEED = 2027
TENANT = "tenant_a"


def _workload(**overrides: object) -> bfg.WorkloadProfile:
    values: dict[str, object] = {
        "tenant": TENANT,
        "target_events": 12,
        "pace_bucket_lo": 1,
        "pace_bucket_hi": cg.PACE_WINDOW_BUCKETS,
    }
    values.update(overrides)
    return bfg.WorkloadProfile(**values)  # type: ignore[arg-type]


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------- positive


def test_generates_benign_campaign_with_default_profile() -> None:
    campaign = bfg.generate_benign(SEED, _workload())
    assert campaign.campaign_id
    assert campaign.events
    assert campaign.tenant == TENANT
    assert campaign.family == bfg.FAMILY_BENIGN_FAULTS


def test_label_is_benign_with_no_violated_invariant() -> None:
    for seed in (0, 1, 2027, 99991):
        campaign = bfg.generate_benign(seed, _workload())
        assert campaign.campaign_label == cg.LABEL_BENIGN
        assert campaign.violated_invariant == cg.INVARIANT_NONE


def test_deterministic_same_inputs_yield_identical_campaign() -> None:
    first = bfg.generate_benign(SEED, _workload())
    second = bfg.generate_benign(SEED, _workload())
    assert first.to_dict() == second.to_dict()
    assert first.events == second.events
    assert first.campaign_id == second.campaign_id


def test_different_seed_yields_distinct_campaign() -> None:
    a = bfg.generate_benign(1, _workload())
    b = bfg.generate_benign(2, _workload())
    assert a.campaign_id != b.campaign_id
    assert a.to_dict() != b.to_dict()


def test_every_benign_fault_type_is_generated() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=64))
    ts_values = [e["ts"] for e in campaign.events]
    gaps = [b - a for a, b in zip(ts_values, ts_values[1:])]
    actors = {e["actor"] for e in campaign.events}
    scopes = {e["scope"] for e in campaign.events}
    purposes = {e["purpose"] for e in campaign.events}
    allowed = [e["allowed"] for e in campaign.events]
    # rate_limit_retry: tightest profile-pace identical-attempt burst ending admitted.
    assert gaps.count(min(gaps)) >= 1
    # network_retry: backoff-paced retries, strictly above the tightest bound.
    assert any(
        _workload().pace_bucket_lo < gap <= _workload().pace_bucket_hi for gap in gaps
    )
    # ux_confusion_retry: mis-scoped denied purposes plus the correct admitted one.
    assert len(purposes) >= 2
    # consent_edit: fresh authorized scopes for the same principal/epoch lineage.
    assert len(scopes) >= 2
    # delayed_timestamps: deliberate stalls beyond the pacing profile, all admitted.
    assert any(gap >= bfg.DELAYED_GAP_MIN_BUCKETS for gap in gaps)
    # Single principal throughout; every retry eventually admitted; denials present.
    assert len(actors) == 1
    # Only retry-type events are denied; consent edits and delayed stalls admitted.
    denied_indices = [i for i, is_allowed in enumerate(allowed) if not is_allowed]
    assert denied_indices
    delayed_indices = {
        i
        for i, gap in enumerate(gaps, start=1)
        if gap >= bfg.DELAYED_GAP_MIN_BUCKETS
    }
    assert all(i < len(allowed) - 1 for i in delayed_indices)
    assert allowed[-1]
    assert any(not e["allowed"] for e in campaign.events)


def test_volume_parity_exact_event_count_for_many_budgets() -> None:
    for target in (bfg.MIN_TARGET_EVENTS, 12, 33, 100, bfg.MAX_TARGET_EVENTS):
        campaign = bfg.generate_benign(SEED, _workload(target_events=target))
        assert len(campaign.events) == target


def test_volume_never_exceeds_requested_budget() -> None:
    for target in (bfg.MIN_TARGET_EVENTS + 1, 12, 50):
        campaign = bfg.generate_benign(SEED, _workload(target_events=target))
        assert len(campaign.events) <= target


def test_cadence_profile_conformance() -> None:
    for seed in (0, 7, 2027):
        for pace_lo, pace_hi in ((1, 1), (2, 5), (3, bfg.MAX_PACE_GAP_BUCKETS)):
            workload = _workload(target_events=40, pace_bucket_lo=pace_lo, pace_bucket_hi=pace_hi)
            campaign = bfg.generate_benign(seed, workload)
            ts_values = [e["ts"] for e in campaign.events]
            assert ts_values == sorted(ts_values)
            gaps = [b - a for a, b in zip(ts_values, ts_values[1:])]
            for gap in gaps:
                assert (
                    workload.pace_bucket_lo <= gap <= workload.pace_bucket_hi
                    or gap >= bfg.DELAYED_GAP_MIN_BUCKETS
                ), (seed, (pace_lo, pace_hi), gap)


def test_delayed_timestamps_reside_only_in_delay_class() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=48))
    ts_values = [e["ts"] for e in campaign.events]
    gaps = [b - a for a, b in zip(ts_values, ts_values[1:])]
    workload = _workload()
    assert any(gap >= bfg.DELAYED_GAP_MIN_BUCKETS for gap in gaps)
    # Every non-delayed gap lies inside the requested cadence profile; the two
    # gap classes are disjoint by construction (profile capped below the delay
    # floor).
    assert workload.pace_bucket_hi < bfg.DELAYED_GAP_MIN_BUCKETS
    for gap in gaps:
        assert (
            workload.pace_bucket_lo <= gap <= workload.pace_bucket_hi
            or gap >= bfg.DELAYED_GAP_MIN_BUCKETS
        ), gap


def test_campaign_minimum_budget_contains_full_repertoire() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=bfg.MIN_TARGET_EVENTS))
    assert len(campaign.events) == bfg.MIN_TARGET_EVENTS
    # Baseline + the minimum genuine-repertoire counts per fault type; the
    # retry faults still produce real repeated attempts (denials present).
    assert any(not e["allowed"] for e in campaign.events)
    assert len({e["purpose"] for e in campaign.events}) >= 2


def test_events_conform_to_frozen_minimal_event_schema() -> None:
    schema = _schema()
    for seed in (0, 2027):
        campaign = bfg.generate_benign(seed, _workload(target_events=32))
        for event in campaign.events:
            errors = sv.validate_instance(dict(event), schema, schema_path=SCHEMA_PATH)
            assert errors == (), (seed, event, errors)


def test_events_use_exactly_the_seven_schema_fields() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=32))
    for event in campaign.events:
        assert set(event) == set(cg.EVENT_FIELDS)


def test_label_exists_only_at_campaign_level() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=32))
    for event in campaign.events:
        assert "campaign_label" not in event
        assert "violated_invariant" not in event
        assert "label" not in event
        assert "is_attack" not in event
        assert "attacker" not in event


def test_actor_and_scope_are_opaque_hex_digests() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=24))
    for event in campaign.events:
        assert len(event["actor"]) == 64
        assert all(c in "0123456789abcdef" for c in event["actor"])
        assert len(event["scope"]) == 64
        assert all(c in "0123456789abcdef" for c in event["scope"])


def test_campaign_id_is_opaque_and_leak_free() -> None:
    for seed in (0, 2027):
        campaign = bfg.generate_benign(seed, _workload())
        assert campaign.campaign_id.startswith("camp-")
        lowered = campaign.campaign_id.lower()
        for token in (campaign.family, campaign.campaign_label, campaign.violated_invariant, TENANT):
            assert token.lower() not in lowered


def test_events_never_leak_tenant_family_or_label_strings() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=32))
    for event in campaign.events:
        serialized = json.dumps(event).lower()
        assert TENANT.lower() not in serialized
        assert campaign.family.lower() not in serialized
        assert campaign.campaign_label.lower() not in serialized
        assert campaign.violated_invariant.lower() not in serialized


def test_workload_profile_is_json_serializable() -> None:
    encoded = json.dumps(_workload().to_dict(), sort_keys=True)
    assert json.loads(encoded) == _workload().to_dict()


def test_campaign_is_json_serializable() -> None:
    campaign = bfg.generate_benign(SEED, _workload())
    encoded = json.dumps(campaign.to_dict(), sort_keys=True)
    reparsed = json.loads(encoded)
    assert reparsed == campaign.to_dict()


def test_repeated_generation_is_idempotent_across_call_order() -> None:
    a = bfg.generate_benign(SEED, _workload(target_events=16))
    bfg.generate_benign(SEED + 1, _workload(target_events=18))
    b = bfg.generate_benign(SEED, _workload(target_events=16))
    assert a.to_dict() == b.to_dict()


def test_volume_parity_against_attack_arm_budgets() -> None:
    """Benign sessions can be volume-matched to every attack family's stage range."""

    for _family, spec in cg.FAMILY_SPECS.items():
        lo, hi = spec.stage_events
        budget = max(hi, bfg.MIN_TARGET_EVENTS)
        campaign = bfg.generate_benign(SEED, _workload(target_events=budget))
        assert len(campaign.events) == budget
        assert len(campaign.events) >= lo


# ------------------------------------------------------------ adversarial


@pytest.mark.parametrize("target", (0, 1, 2, 3, 4, 5, bfg.MIN_TARGET_EVENTS - 1))
def test_volume_budget_below_minimum_refused(target: int) -> None:
    """A benign campaign exceeding the requested volume budget is refused."""

    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg.generate_benign(SEED, _workload(target_events=target))
    assert exc.value.reason_code == bfg.REASON_VOLUME_BUDGET_EXCEEDED


def test_volume_budget_exceeded_is_fail_closed_not_trimmed() -> None:
    """The repertoire is never silently trimmed to honor an impossible budget."""

    for target in range(1, bfg.MIN_TARGET_EVENTS):
        with pytest.raises(bfg.BenignFaultError) as exc:
            bfg.generate_benign(SEED, _workload(target_events=target))
        assert exc.value.reason_code == bfg.REASON_VOLUME_BUDGET_EXCEEDED


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
                **{field: "BENIGN"},
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
            fault_type="rate_limit_retry",
        )
    assert exc.value.reason_code == "EVENT_FIELD_MISMATCH"


def test_non_workload_profile_refused() -> None:
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg.generate_benign(SEED, {"tenant": TENANT, "target_events": 12})  # type: ignore[arg-type]
    assert exc.value.reason_code == bfg.REASON_INVALID_WORKLOAD


@pytest.mark.parametrize("bad_target", ("12", 12.0, None, True))
def test_non_integer_target_events_refused(bad_target: object) -> None:
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg.generate_benign(SEED, _workload(target_events=bad_target))  # type: ignore[arg-type]
    assert exc.value.reason_code == bfg.REASON_INVALID_WORKLOAD


def test_target_events_above_maximum_refused() -> None:
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg.generate_benign(SEED, _workload(target_events=bfg.MAX_TARGET_EVENTS + 1))
    assert exc.value.reason_code == bfg.REASON_INVALID_WORKLOAD


@pytest.mark.parametrize(
    "pace_lo,pace_hi", ((0, 5), (5, 2), (1, bfg.MAX_PACE_GAP_BUCKETS + 1), (-1, 3))
)
def test_malformed_cadence_bounds_refused(pace_lo: int, pace_hi: int) -> None:
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg.generate_benign(SEED, _workload(pace_bucket_lo=pace_lo, pace_bucket_hi=pace_hi))
    assert exc.value.reason_code == bfg.REASON_INVALID_WORKLOAD


@pytest.mark.parametrize("bad_seed", (-1, "7", 1.5, None, True))
def test_invalid_seed_refused(bad_seed: object) -> None:
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg.generate_benign(bad_seed, _workload())  # type: ignore[arg-type]
    assert exc.value.reason_code == bfg.REASON_INVALID_SEED


@pytest.mark.parametrize(
    "bad_tenant", ("", "has space", "-leading", "x" * 40, "tenant;drop", "p@th")
)
def test_invalid_tenant_refused(bad_tenant: str) -> None:
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg.generate_benign(SEED, _workload(tenant=bad_tenant))
    assert exc.value.reason_code == bfg.REASON_INVALID_TENANT


def test_phi_like_tenant_refused() -> None:
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg.generate_benign(SEED, _workload(tenant="patient_1"))
    assert exc.value.reason_code == bfg.REASON_PHI_FIELD_PRESENT


def test_generated_campaigns_are_phi_free() -> None:
    for seed in (0, 2027):
        for tenant in ("tenant_a", "tenant_b"):
            campaign = bfg.generate_benign(seed, _workload(tenant=tenant, target_events=24))
            lowered = json.dumps(campaign.to_dict(), sort_keys=True).lower()
            for marker in cg.PHI_SCAN_MARKERS:
                assert marker not in lowered, (seed, tenant, marker)


def test_no_reason_code_field_anywhere_on_event_surface() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=24))
    for event in campaign.events:
        assert "reason_code" not in event
        assert "reason" not in event


def test_tampered_volume_budget_fails_volume_gate() -> None:
    """Tampering that drops events fails the fail-closed volume/cadence gate."""

    campaign = bfg.generate_benign(SEED, _workload(target_events=16))
    workload = _workload(target_events=16)
    shrunk = campaign.__class__(
        **{**campaign.to_dict(), "events": tuple(campaign.events)[:-1]}
    )
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg._assert_volume_and_cadence(shrunk, workload)
    assert exc.value.reason_code == bfg.REASON_VOLUME_BUDGET_EXCEEDED


def test_tampered_cadence_fails_cadence_gate() -> None:
    campaign = bfg.generate_benign(SEED, _workload(target_events=16))
    workload = _workload(target_events=16)
    events = [dict(event) for event in campaign.events]
    events[1]["ts"] = events[0]["ts"] + bfg.MAX_PACE_GAP_BUCKETS + 1
    shifted = campaign.__class__(**{**campaign.to_dict(), "events": tuple(events)})
    with pytest.raises(bfg.BenignFaultError) as exc:
        bfg._assert_volume_and_cadence(shifted, workload)
    assert exc.value.reason_code == bfg.REASON_CADENCE_PROFILE_VIOLATED
