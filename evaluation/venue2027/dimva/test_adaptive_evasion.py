"""Tests for DIMVA-X07_adaptive_evasion — Adaptive evasion and low-and-slow probing.

Positive controls:
- Generates evasive campaigns across tactical strategies:
  * pacing (inter-arrival delay manipulation);
  * benign interleaving (padding with legitimate allowed tool calls);
  * field scrambling (verifying schema permutation invariance);
  * missing optional fields (minimal schema projection);
  * composite evasion (pacing + interleaving + scrambling).
- Evasion impact proven against baseline arms:
  * Pacing evades B0 (sliding-window count alarm drops below threshold);
  * Benign interleaving evades simple rate detectors (denial ratio diluted);
  * Candidate detector maintains detection under evasion (structural linkage,
    cross-tool spread, and continuity signals remain robust).
- Target contract: ``evaluate_adaptation(model, campaigns) -> Metrics`` produces
  strictly typed, schema-valid, reproducible metrics.
- Comprehensive cross-arm comparison: ``evaluate_arms_evasion`` measures evasion
  rates across B0, B1, B2, and candidate.
- Deterministic fixed test campaign families.

Adversarial controls:
- Privileged attacker assumptions refused:
  * Tampering with backend logs / overwriting signed server audit logs is refused
    with PRIVILEGED_LOG_TAMPERING_REFUSED (:class:`PrivilegedTamperingError`);
  * Injecting privileged backend fields (server_signature, audit_log_id, oracle_truth)
    is refused;
  * Accessing or injecting forbidden rejection reason codes (RQ1 masking) fails
    closed with EVENT_REASON_CODE_FIELD_FORBIDDEN.
- Non-permitted events refused:
  * Events with unpermitted extra fields fail closed (UNPERMITTED_EVENT_FIELD_REFUSED);
  * Events from multiple actors (session impersonation) fail closed (SESSION_MIXED_ACTORS);
  * Non-monotonic timestamps fail closed (EVENT_TS_NOT_MONOTONIC);
  * Empty event streams or malformed cases fail closed;
  * Unknown evasion strategies or malformed configs fail closed.
"""

from __future__ import annotations

import pytest

from evaluation.venue2027.dimva import adaptive_evasion as ae
from evaluation.venue2027.dimva import baselines, candidate


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers.
# ---------------------------------------------------------------------------
def _make_burst_campaign(actor_id: str = "actor-adv-burst") -> dict[str, object]:
    """Base un-paced burst campaign (6 denials in 500 s across 6 distinct tools)."""
    events = [
        baselines.event(actor_id, f"probe_tool_{i:02d}", "self_care", False, 100 + 80 * i)
        for i in range(6)
    ]
    return {
        "case_id": "TEST-BURST-01",
        "family": "burst_probe",
        "campaign_label": "ATTACK",
        "events": events,
    }


def _make_low_slow_campaign(actor_id: str = "actor-adv-slow") -> dict[str, object]:
    """Base low-and-slow campaign (6 denials spaced by 1800 s across 6 tools)."""
    events = [
        baselines.event(actor_id, f"probe_tool_{i:02d}", "self_care", False, 1000 + 1800 * i)
        for i in range(6)
    ]
    return {
        "case_id": "TEST-SLOW-01",
        "family": "low_and_slow",
        "campaign_label": "ATTACK",
        "events": events,
    }


# ===========================================================================
# Positive Tests: Evasive Campaign Generation.
# ===========================================================================
def test_generate_evasive_campaign_pacing() -> None:
    base = _make_burst_campaign()
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_PACING)

    assert isinstance(evasive, ae.EvasiveCampaign)
    assert evasive.strategy == ae.STRATEGY_PACING
    assert evasive.base_campaign_id == "TEST-BURST-01"
    assert len(evasive.events) == 6

    # Verify inter-arrival delays are stretched
    ts_list = [e["ts"] for e in evasive.events]
    assert all(b > a for a, b in zip(ts_list, ts_list[1:]))

    # Inter-denial gap must be at least pacing_delay_seconds (default 1800 s)
    gaps = [b - a for a, b in zip(ts_list, ts_list[1:])]
    assert all(g >= 1800 for g in gaps)

    # Span must be extended
    span = ts_list[-1] - ts_list[0]
    assert span >= 7200

    # JSON-serializable
    d = evasive.to_dict()
    assert d["strategy"] == ae.STRATEGY_PACING
    assert len(d["events"]) == 6


def test_generate_evasive_campaign_benign_interleaving() -> None:
    base = _make_burst_campaign()
    config = ae.EvasionConfig(interleave_ratio=2)
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_BENIGN_INTERLEAVING, config=config)

    assert evasive.strategy == ae.STRATEGY_BENIGN_INTERLEAVING
    # 6 base events + (6 * 2) interleaved benign events = 18 events
    assert len(evasive.events) == 18

    denied = [e for e in evasive.events if not e["allowed"]]
    allowed = [e for e in evasive.events if e["allowed"]]

    assert len(denied) == 6
    assert len(allowed) == 12

    # Verify timestamps are strictly monotonic
    ts_list = [e["ts"] for e in evasive.events]
    assert all(b > a for a, b in zip(ts_list, ts_list[1:]))

    # Denial rate diluted from 100% down to 33.3%
    rate = ae.compute_denial_rate(evasive.events)
    assert abs(rate - (6 / 18)) < 1e-6


def test_generate_evasive_campaign_field_scrambling() -> None:
    base = _make_burst_campaign()
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_FIELD_SCRAMBLING)

    assert evasive.strategy == ae.STRATEGY_FIELD_SCRAMBLING
    assert len(evasive.events) == 6

    # Every event must retain all 5 minimal keys despite reordering
    for ev in evasive.events:
        assert set(ev.keys()) == ae.EVENT_KEYS
        # The first key is scrambled to 'ts' per default config
        assert list(ev.keys())[0] == "ts"


def test_generate_evasive_campaign_missing_optional_fields() -> None:
    # Base event has extra optional fields (e.g. from 7-field schema)
    events_with_optional = [
        {
            "actor": "actor-adv-01",
            "actor_id": "actor-adv-01",
            "tool": f"tool_{i}",
            "scope": "self_care",
            "allowed": False,
            "ts": 100 + 50 * i,
            "purpose": "self_care",
            "campaign_id": "camp-opt-01",
        }
        for i in range(5)
    ]
    base = {"case_id": "CASE-OPT-01", "events": events_with_optional}
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_MISSING_OPTIONAL_FIELDS)

    # Optional fields stripped, only minimal 5 keys remain
    for ev in evasive.events:
        assert set(ev.keys()) == ae.EVENT_KEYS


def test_generate_evasive_campaign_composite() -> None:
    base = _make_burst_campaign()
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_COMPOSITE)

    assert evasive.strategy == ae.STRATEGY_COMPOSITE
    assert len(evasive.events) > 6
    # Both paced and interleaved
    ts_list = [e["ts"] for e in evasive.events]
    assert all(b > a for a, b in zip(ts_list, ts_list[1:]))
    assert ts_list[-1] - ts_list[0] >= 7200


# ===========================================================================
# Positive Tests: Evasion Impact (B0, Rates, and Candidate).
# ===========================================================================
def test_pacing_evades_b0_while_candidate_detects() -> None:
    """Pacing evades fixed-window count B0 while Candidate maintains detection."""
    base = _make_burst_campaign()
    ctx = baselines.DetectorContext(b0_window_seconds=3600, b0_denied_threshold=5)

    # 1. Base un-paced burst: all 6 denials happen in 500 s (< 3600 s window).
    b0_base = baselines.run_baseline_detection("B0", base, ctx)
    assert b0_base.decision == baselines.DETECT
    assert b0_base.reason_code == baselines.RC_B0_THRESHOLD_EXCEEDED

    # 2. Paced campaign: 6 denials spaced by 1800 s.
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_PACING)
    evasive_case = evasive.to_dict()

    # B0 is EVADED: max denials in any 3600 s window drops to 2 (< 5 threshold).
    b0_evasive = baselines.run_baseline_detection("B0", evasive_case, ctx)
    assert b0_evasive.decision == baselines.NO_DETECT
    assert b0_evasive.reason_code == baselines.RC_NO_ALARM

    # 3. Candidate RESILIENCE: Candidate DETECTS the paced campaign!
    # Candidate specifically links low-and-slow campaigns across long spans
    # and satisfies all 5 structural criteria.
    cand_detection = candidate.detect(evasive_case["events"])
    assert cand_detection.decision == candidate.DETECT
    assert cand_detection.reason == candidate.RC_CAMPAIGN_STRUCTURE_DETECTED
    assert cand_detection.evidence["criteria"]["evades_fixed_window"] is True
    assert cand_detection.evidence["criteria"]["enough_denials"] is True
    assert cand_detection.evidence["criteria"]["long_horizon_span"] is True


def test_benign_interleaving_evades_simple_rates_while_candidate_detects() -> None:
    """Benign interleaving evades simple rate anomaly while Candidate maintains detection."""
    base = _make_low_slow_campaign()

    # 1. Base campaign: 6 denials, 0 allowed. Denial rate = 1.0 (100%).
    base_rate = ae.evaluate_simple_rate_detector(base["events"], threshold=0.5)
    assert base_rate["detected"] is True
    assert base_rate["decision"] == "DETECT"

    # 2. Benign interleaved campaign: padding with 18 allowed requests (ratio=3).
    # 6 denials / 24 total requests = 25% denial rate.
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_BENIGN_INTERLEAVING)
    evasive_case = evasive.to_dict()

    evasive_rate = ae.evaluate_simple_rate_detector(evasive_case["events"], threshold=0.5)
    assert evasive_rate["detected"] is False
    assert evasive_rate["decision"] == "NO_DETECT"  # Evaded simple rate!

    # 3. Candidate RESILIENCE: Candidate filters to denials and still DETECTS!
    cand_detection = candidate.detect(evasive_case["events"])
    assert cand_detection.decision == candidate.DETECT
    assert cand_detection.reason == candidate.RC_CAMPAIGN_STRUCTURE_DETECTED


def test_candidate_maintains_detection_under_scrambling() -> None:
    """Candidate produces identical score and verdict when event keys are scrambled."""
    base = _make_low_slow_campaign()
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_FIELD_SCRAMBLING)

    det_base = candidate.detect(base["events"])
    det_scrambled = candidate.detect(evasive.to_dict()["events"])

    assert det_base.decision == candidate.DETECT
    assert det_scrambled.decision == candidate.DETECT
    assert det_base.score == det_scrambled.score
    assert det_base.reason == det_scrambled.reason


def test_candidate_maintains_detection_under_composite_evasion() -> None:
    """Candidate detector detects the composite evasive campaign."""
    base = _make_burst_campaign()
    evasive = ae.generate_evasive_campaign(base, ae.STRATEGY_COMPOSITE)

    det = candidate.detect(evasive.to_dict()["events"])
    assert det.decision == candidate.DETECT
    assert det.reason == candidate.RC_CAMPAIGN_STRUCTURE_DETECTED


# ===========================================================================
# Target Contract & Evaluation Metrics Tests.
# ===========================================================================
def test_evaluate_adaptation_contract() -> None:
    """Test exact contract evaluate_adaptation(model, campaigns) -> Metrics."""
    base = _make_burst_campaign()
    paced = ae.generate_evasive_campaign(base, ae.STRATEGY_PACING)

    # Test under B0: base detected, evasive not detected (evasion_success_rate = 1.0)
    metrics_b0 = ae.evaluate_adaptation("B0", [paced])
    assert isinstance(metrics_b0, ae.Metrics)
    assert metrics_b0.total_campaigns == 1
    assert metrics_b0.base_detections == 1
    assert metrics_b0.evasive_detections == 0
    assert metrics_b0.evasion_success_count == 1
    assert metrics_b0.evasion_success_rate == 1.0
    assert metrics_b0.detection_retention_rate == 0.0

    # Test under Candidate on low-and-slow: both base and evasive detected
    slow_base = _make_low_slow_campaign()
    interleaved = ae.generate_evasive_campaign(slow_base, ae.STRATEGY_BENIGN_INTERLEAVING)

    metrics_cand = ae.evaluate_adaptation("candidate", [interleaved])
    assert metrics_cand.total_campaigns == 1
    assert metrics_cand.base_detections == 1
    assert metrics_cand.evasive_detections == 1
    assert metrics_cand.evasion_success_count == 0
    assert metrics_cand.evasion_success_rate == 0.0
    assert metrics_cand.detection_retention_rate == 1.0

    # Serialization check
    d = metrics_cand.to_dict()
    assert d["total_campaigns"] == 1
    assert d["detection_retention_rate"] == 1.0


def test_evaluate_arms_evasion_comprehensive() -> None:
    """Test comprehensive cross-arm evasion evaluation across B0, B1, B2, and candidate."""
    report = ae.evaluate_arms_evasion()

    assert isinstance(report, ae.CrossArmEvasionReport)
    assert report.total_cases > 0
    summary = report.summary

    # B0 must register successful evasions (specifically from pacing)
    assert summary["B0"]["evaded"] >= 1

    # Candidate must maintain detections under pacing and benign interleaving
    assert summary["candidate"]["detected_evasive"] >= 1

    d = report.to_dict()
    assert "summary" in d
    assert len(d["results"]) == report.total_cases


def test_fixed_test_campaign_families() -> None:
    families = ae.fixed_test_campaign_families()
    assert "rapid_denial_burst" in families
    assert "cross_tool_probe" in families
    assert "single_scope_probe" in families
    assert "low_and_slow_probe" in families

    for _name, camp in families.items():
        assert "case_id" in camp
        assert "events" in camp
        assert len(camp["events"]) >= 6
        # Validate events schema
        for e in camp["events"]:
            assert set(e.keys()) == ae.EVENT_KEYS


# ===========================================================================
# Adversarial Tests: Privileged Attacker Assumptions Refused.
# ===========================================================================
def test_refuse_backend_log_tampering() -> None:
    """Privileged attacker attempting to overwrite backend logs is refused."""
    with pytest.raises(ae.PrivilegedTamperingError) as exc_info:
        ae.tamper_backend_logs("overwrite_signed_server_logs")
    assert exc_info.value.reason_code == ae.RC_PRIVILEGED_LOG_TAMPERING

    with pytest.raises(ae.PrivilegedTamperingError) as exc_info2:
        ae.refuse_privileged_tampering("tamper_backend_database_audit_log")
    assert exc_info2.value.reason_code == ae.RC_PRIVILEGED_LOG_TAMPERING

    # Attempting to request a log-tampering evasion strategy
    base = _make_burst_campaign()
    with pytest.raises(ae.PrivilegedTamperingError):
        ae.generate_evasive_campaign(base, "tamper_backend_logs")


def test_refuse_privileged_event_fields() -> None:
    """Events carrying backend audit signatures or oracle truth are refused."""
    privileged_events = [
        {
            "actor_id": "actor-adv",
            "tool": "probe_tool",
            "scope": "self_care",
            "allowed": False,
            "ts": 100,
            "server_signature": "sig-0xdeadbeef",
        }
    ]
    base = {"case_id": "TAMPER-01", "events": privileged_events}

    with pytest.raises(ae.PrivilegedTamperingError) as exc_info:
        ae.generate_evasive_campaign(base, ae.STRATEGY_PACING)
    assert exc_info.value.reason_code == ae.RC_PRIVILEGED_LOG_TAMPERING


def test_refuse_reason_code_leakage() -> None:
    """Events containing forbidden reason_code fields fail closed (RQ1 masking)."""
    leaking_events = [
        {
            "actor_id": "actor-adv",
            "tool": "probe_tool",
            "scope": "self_care",
            "allowed": False,
            "ts": 100,
            "reason_code": "SCOPE_DENIED",
        }
    ]
    base = {"case_id": "LEAK-01", "events": leaking_events}

    with pytest.raises(ae.EvasionError) as exc_info:
        ae.generate_evasive_campaign(base, ae.STRATEGY_PACING)
    assert exc_info.value.reason_code == ae.RC_EVENT_REASON_CODE_FORBIDDEN


# ===========================================================================
# Adversarial Tests: Non-Permitted Events Refused.
# ===========================================================================
def test_refuse_unpermitted_event_fields() -> None:
    """Events carrying unknown fields fail closed."""
    bad_events = [
        {
            "actor_id": "actor-adv",
            "tool": "probe_tool",
            "scope": "self_care",
            "allowed": False,
            "ts": 100,
            "arbitrary_payload": "exploit",
        }
    ]
    base = {"case_id": "BAD-01", "events": bad_events}

    with pytest.raises(ae.EvasionError) as exc_info:
        ae.generate_evasive_campaign(base, ae.STRATEGY_PACING)
    assert exc_info.value.reason_code == ae.RC_UNPERMITTED_EVENT_FIELD


def test_refuse_mixed_actors_tampering() -> None:
    """Session attempting to forge events across multiple actors fails closed."""
    mixed_events = [
        baselines.event("actor-1", "tool_a", "self_care", False, 100),
        baselines.event("actor-2", "tool_b", "self_care", False, 200),
    ]
    base = {"case_id": "MIXED-01", "events": mixed_events}

    with pytest.raises(ae.EvasionError) as exc_info:
        ae.generate_evasive_campaign(base, ae.STRATEGY_PACING)
    assert exc_info.value.reason_code == ae.RC_SESSION_MIXED_ACTORS


def test_refuse_non_monotonic_timestamps() -> None:
    """Events with non-monotonic timestamps fail closed."""
    non_monotonic = [
        baselines.event("actor-1", "tool_a", "self_care", False, 500),
        baselines.event("actor-1", "tool_b", "self_care", False, 300),
    ]
    base = {"case_id": "NON-MONO-01", "events": non_monotonic}

    with pytest.raises(ae.EvasionError) as exc_info:
        ae.generate_evasive_campaign(base, ae.STRATEGY_PACING)
    assert exc_info.value.reason_code == ae.RC_EVENT_TS_NOT_MONOTONIC


def test_refuse_empty_or_non_list_events() -> None:
    """Empty or non-list event payload fails closed."""
    with pytest.raises(ae.EvasionError) as exc1:
        ae.generate_evasive_campaign({"case_id": "EMPTY", "events": []}, ae.STRATEGY_PACING)
    assert exc1.value.reason_code == ae.RC_EMPTY_EVENTS

    with pytest.raises(ae.EvasionError) as exc2:
        ae.generate_evasive_campaign({"case_id": "STR", "events": "not-a-list"}, ae.STRATEGY_PACING)
    assert exc2.value.reason_code == ae.RC_INVALID_BASE_CAMPAIGN


def test_refuse_unknown_strategy() -> None:
    """Requesting an unknown evasion strategy fails closed."""
    base = _make_burst_campaign()
    with pytest.raises(ae.EvasionError) as exc_info:
        ae.generate_evasive_campaign(base, "unsupported_magic_evasion")
    assert exc_info.value.reason_code == ae.RC_UNKNOWN_STRATEGY


def test_refuse_malformed_config() -> None:
    """Invalid non-positive parameters in EvasionConfig raise EvasionError."""
    with pytest.raises(ae.EvasionError) as exc1:
        ae.EvasionConfig(pacing_delay_seconds=0)
    assert exc1.value.reason_code == ae.RC_CONTEXT_MALFORMED

    with pytest.raises(ae.EvasionError) as exc2:
        ae.EvasionConfig(interleave_ratio=-1)
    assert exc2.value.reason_code == ae.RC_CONTEXT_MALFORMED
