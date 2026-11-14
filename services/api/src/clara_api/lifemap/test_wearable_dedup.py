"""Unit tests for deterministic wearable dedup and multi-source version mapping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clara_api.connected_health.schemas import CanonicalHealthRecord
from clara_api.core.config import Settings
from clara_api.lifemap.wearable_dedup import (
    DEDUP_POLICY_VERSION,
    DedupOutcome,
    SourceClass,
    WearableDedupDisabledError,
    WearableDeduplicationEngine,
    record_dedup_key,
    record_metric_key,
    record_revision_key,
    wearable_dedup_enabled,
)

START = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)
END = datetime(2026, 11, 14, 2, 0, tzinfo=UTC)
HASH_A = "sha256:" + ("a" * 64)
HASH_B = "sha256:" + ("b" * 64)


def _record(**overrides: object) -> CanonicalHealthRecord:
    payload: dict[str, object] = {
        "profile_id": "prof_1",
        "connector_id": "con_1",
        "provider": "health_connect",
        "provider_record_id": "record-1",
        "record_type": "steps",
        "value": {"scalar": 1200, "unit": "count"},
        "observed_start": START,
        "observed_end": END,
        "zone_offset_start": "+07:00",
        "zone_offset_end": "+07:00",
        "data_origin": "com.vendor.health",
        "device": {"manufacturer": "Vendor", "model": "Watch 1", "type": "watch"},
        "recording_method": "automatic",
        "provider_updated_at": END,
        "quality": {"state": "source_asserted", "flags": []},
        "provenance": {"adapter_version": "android-1.0.0", "raw_hash": HASH_A},
    }
    payload.update(overrides)
    return CanonicalHealthRecord.model_validate(payload)


def _enabled_engine(**kwargs: object) -> WearableDeduplicationEngine:
    return WearableDeduplicationEngine(
        settings=Settings(LIFEMAP_WEARABLE_DEDUP_ENABLED=True), **kwargs
    )


def _cloud_record(**overrides: object) -> CanonicalHealthRecord:
    payload: dict[str, object] = {
        "connector_id": "con-2",
        "provider": "fitbit",
        "provider_record_id": "fitbit-9",
        "data_origin": "com.fitbit.cloud",
        "provenance": {"adapter_version": "fitbit-1.0.0", "raw_hash": HASH_B},
    }
    payload.update(overrides)
    return _record(**payload)


def test_flag_defaults_to_disabled_and_fails_closed() -> None:
    assert Settings().lifemap_wearable_dedup_enabled is False
    assert wearable_dedup_enabled(Settings()) is False
    engine = WearableDeduplicationEngine(settings=Settings())
    with pytest.raises(WearableDedupDisabledError):
        engine.evaluate(_record())
    with pytest.raises(WearableDedupDisabledError):
        engine.map_versions([_record()])


def test_flag_can_be_read_from_explicit_settings() -> None:
    settings = Settings(LIFEMAP_WEARABLE_DEDUP_ENABLED=True)
    assert wearable_dedup_enabled(settings) is True
    assert wearable_dedup_enabled(Settings()) is False


def test_dedup_key_is_deterministic_and_ignores_observed_order() -> None:
    first = _record()
    second = _record()
    assert record_dedup_key(first) == record_dedup_key(second)
    changed_value = _record(value={"scalar": 1201, "unit": "count"})
    changed_id = _record(provider_record_id="record-2")
    assert record_dedup_key(first) != record_dedup_key(changed_value)
    assert record_dedup_key(first) != record_dedup_key(changed_id)
    assert record_revision_key(first) == record_revision_key(changed_value)
    assert record_metric_key(first) == record_metric_key(changed_value)


def test_exact_duplicate_is_skipped() -> None:
    engine = _enabled_engine()
    decision = engine.evaluate(_record(), [_record()])
    assert decision.outcome is DedupOutcome.DUPLICATE_SKIPPED
    assert decision.reason == "same_revision_identical_value"
    assert decision.policy_version == DEDUP_POLICY_VERSION


def test_new_record_is_accepted() -> None:
    engine = _enabled_engine()
    decision = engine.evaluate(_record())
    assert decision.outcome is DedupOutcome.ACCEPTED
    assert decision.preferred_key == decision.dedup_key


def test_newer_revision_supersedes_older_one() -> None:
    engine = _enabled_engine()
    older = _record(value={"scalar": 1100, "unit": "count"}, provider_updated_at=END)
    newer = _record(
        value={"scalar": 1500, "unit": "count"},
        provider_updated_at=END + timedelta(minutes=5),
    )
    decision = engine.evaluate(newer, [older])
    assert decision.outcome is DedupOutcome.ACCEPTED
    assert decision.reason == "same_revision_newer"
    assert decision.preferred_key == decision.dedup_key
    assert decision.superseded_keys == (record_dedup_key(older),)


def test_older_revision_is_superseded_by_existing() -> None:
    engine = _enabled_engine()
    newest = _record(
        value={"scalar": 1500, "unit": "count"},
        provider_updated_at=END + timedelta(minutes=5),
    )
    stale = _record(value={"scalar": 900, "unit": "count"}, provider_updated_at=END)
    decision = engine.evaluate(stale, [newest])
    assert decision.outcome is DedupOutcome.SUPERSEDED
    assert decision.reason == "same_revision_older_or_equal"
    assert decision.preferred_key == record_dedup_key(newest)


def test_device_source_beats_cloud_on_conflict() -> None:
    engine = _enabled_engine()
    cloud = _cloud_record(value={"scalar": 800, "unit": "count"})
    device = _record(value={"scalar": 1000, "unit": "count"})
    assert engine.source_class(device) is SourceClass.DEVICE
    assert engine.source_class(cloud) is SourceClass.CLOUD

    decision = engine.evaluate(device, [cloud])
    assert decision.outcome is DedupOutcome.ACCEPTED
    assert decision.reason == "conflict_preferred_not_overwritten"
    assert decision.conflicting_keys == (record_dedup_key(cloud),)
    assert decision.preferred_key == decision.dedup_key


def test_lower_precedence_source_conflict_is_preserved_not_overwritten() -> None:
    engine = _enabled_engine()
    device = _record(value={"scalar": 1000, "unit": "count"})
    cloud = _cloud_record(value={"scalar": 800, "unit": "count"})
    decision = engine.evaluate(cloud, [device])
    assert decision.outcome is DedupOutcome.CONFLICT_PRESERVED
    assert decision.reason == "conflict_lower_precedence_or_tie"
    assert decision.preferred_key == record_dedup_key(device)
    assert decision.conflicting_keys == (record_dedup_key(device),)


def test_cross_source_identical_value_is_duplicate_skipped() -> None:
    engine = _enabled_engine()
    device = _record(value={"scalar": 1000, "unit": "count"})
    cloud = _cloud_record(value={"scalar": 1000, "unit": "count"})
    decision = engine.evaluate(cloud, [device])
    assert decision.outcome is DedupOutcome.DUPLICATE_SKIPPED
    assert decision.reason == "cross_source_identical_value"
    assert decision.preferred_key == record_dedup_key(device)


def test_freshness_breaks_ties_within_same_source_class() -> None:
    engine = _enabled_engine()
    stale = _record(
        value={"scalar": 1000, "unit": "count"},
        provider_updated_at=END,
    )
    fresh = _record(
        value={"scalar": 1400, "unit": "count"},
        connector_id="con-3",
        data_origin="com.vendor.health.2",
        provider_record_id="record-2",
        provider_updated_at=END + timedelta(minutes=30),
    )
    decision = engine.evaluate(fresh, [stale])
    assert decision.outcome is DedupOutcome.ACCEPTED
    assert decision.preferred_key == decision.dedup_key


def test_batch_mapping_is_order_independent_and_preserves_conflicts() -> None:
    engine = _enabled_engine()
    cloud = _cloud_record(value={"scalar": 800, "unit": "count"})
    device = _record(value={"scalar": 1000, "unit": "count"})

    forward = engine.map_versions([cloud, device, device])
    reverse = engine.map_versions([device, cloud])

    assert forward.to_dict() == reverse.to_dict()
    decisions = {decision.dedup_key: decision for decision in forward.decisions}
    assert decisions[record_dedup_key(device)].outcome is DedupOutcome.ACCEPTED
    assert decisions[record_dedup_key(cloud)].outcome is DedupOutcome.CONFLICT_PRESERVED
    assert decisions[record_dedup_key(cloud)].preferred_key == record_dedup_key(device)
    assert len(decisions) == 2
    metric_key = record_metric_key(device)
    assert forward.preferred_by_metric[metric_key] == record_dedup_key(device)


def test_batch_mapping_marks_cross_source_echo_as_duplicate() -> None:
    engine = _enabled_engine()
    device = _record(value={"scalar": 1000, "unit": "count"})
    echo = _cloud_record(value={"scalar": 1000, "unit": "count"})
    version_map = engine.map_versions([echo, device])
    decisions = {decision.dedup_key: decision for decision in version_map.decisions}
    assert decisions[record_dedup_key(device)].outcome is DedupOutcome.ACCEPTED
    assert decisions[record_dedup_key(echo)].outcome is DedupOutcome.DUPLICATE_SKIPPED
    assert decisions[record_dedup_key(echo)].preferred_key == record_dedup_key(device)


def test_batch_mapping_collapses_revisions_to_newest() -> None:
    engine = _enabled_engine()
    older = _record(value={"scalar": 1100, "unit": "count"}, provider_updated_at=END)
    newer = _record(
        value={"scalar": 1500, "unit": "count"},
        provider_updated_at=END + timedelta(minutes=5),
    )
    version_map = engine.map_versions([older, newer])
    decisions = {decision.dedup_key: decision for decision in version_map.decisions}
    assert decisions[record_dedup_key(newer)].outcome is DedupOutcome.ACCEPTED
    assert decisions[record_dedup_key(older)].outcome is DedupOutcome.SUPERSEDED
    assert decisions[record_dedup_key(older)].preferred_key == record_dedup_key(newer)
    assert version_map.preferred_by_metric[record_metric_key(newer)] == record_dedup_key(newer)


def test_source_class_override_is_honoured() -> None:
    engine = _enabled_engine(source_classes={"fitbit": SourceClass.DEVICE})
    cloud = _cloud_record()
    assert engine.source_class(cloud) is SourceClass.DEVICE


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError):
        record_dedup_key(_record(observed_start=datetime(2026, 11, 14, 1, 0)))
