"""No-content post-pilot stop/recall evaluation without automatic retraining."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Literal

_SAFE_REF = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:@/-]{2,127}")


class MonitoringError(ValueError):
    pass


@dataclass(frozen=True)
class StopThresholds:
    threshold_version: str
    use_case_id: str
    artifact_ref: str
    maximum_drift_score: float
    maximum_correction_rate: float
    maximum_override_rate: float
    maximum_abstention_rate: float
    maximum_adverse_event_rate: float
    maximum_provider_change_count: int
    minimum_sample_count: int
    owner_approval_id: str


@dataclass(frozen=True)
class MonitoringSnapshot:
    window_id: str
    use_case_id: str
    artifact_ref: str
    expected_provider_ref: str
    observed_provider_ref: str
    sample_count: int
    drift_score: float
    correction_rate: float
    override_rate: float
    abstention_rate: float
    adverse_event_rate: float
    provider_change_count: int


@dataclass(frozen=True)
class MonitoringDecision:
    action: Literal["continue", "pause_expansion", "recall"]
    breached: tuple[str, ...]
    threshold_manifest_sha256: str
    window_id: str
    use_case_id: str
    artifact_ref: str
    automatic_retraining: bool = False


def _threshold_manifest_sha256(thresholds: StopThresholds) -> str:
    payload = {
        "threshold_version": thresholds.threshold_version,
        "use_case_id": thresholds.use_case_id,
        "artifact_ref": thresholds.artifact_ref,
        "maximum_drift_score": thresholds.maximum_drift_score,
        "maximum_correction_rate": thresholds.maximum_correction_rate,
        "maximum_override_rate": thresholds.maximum_override_rate,
        "maximum_abstention_rate": thresholds.maximum_abstention_rate,
        "maximum_adverse_event_rate": thresholds.maximum_adverse_event_rate,
        "maximum_provider_change_count": thresholds.maximum_provider_change_count,
        "minimum_sample_count": thresholds.minimum_sample_count,
        "owner_approval_id": thresholds.owner_approval_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def evaluate_stop_thresholds(
    snapshot: MonitoringSnapshot,
    thresholds: StopThresholds,
) -> MonitoringDecision:
    maximum_rates = (
        thresholds.maximum_drift_score,
        thresholds.maximum_correction_rate,
        thresholds.maximum_override_rate,
        thresholds.maximum_abstention_rate,
        thresholds.maximum_adverse_event_rate,
    )
    if (
        not all(
            _SAFE_REF.fullmatch(value)
            for value in (
                thresholds.threshold_version,
                thresholds.use_case_id,
                thresholds.artifact_ref,
                thresholds.owner_approval_id,
            )
        )
        or thresholds.minimum_sample_count <= 0
        or thresholds.maximum_provider_change_count < 0
        or any(
            not math.isfinite(value) or not 0 <= value <= 1
            for value in maximum_rates
        )
    ):
        raise MonitoringError("stop_thresholds_not_approved")
    if (
        not all(
            _SAFE_REF.fullmatch(value)
            for value in (
                snapshot.window_id,
                snapshot.use_case_id,
                snapshot.artifact_ref,
                snapshot.expected_provider_ref,
                snapshot.observed_provider_ref,
            )
        )
        or snapshot.use_case_id != thresholds.use_case_id
        or snapshot.artifact_ref != thresholds.artifact_ref
    ):
        raise MonitoringError("monitoring_scope_mismatch")
    rates = (
        snapshot.drift_score,
        snapshot.correction_rate,
        snapshot.override_rate,
        snapshot.abstention_rate,
        snapshot.adverse_event_rate,
    )
    if (
        snapshot.sample_count < 0
        or snapshot.provider_change_count < 0
        or any(not math.isfinite(value) or not 0 <= value <= 1 for value in rates)
    ):
        raise MonitoringError("monitoring_snapshot_invalid")
    breached: list[str] = []
    checks = (
        ("drift", snapshot.drift_score, thresholds.maximum_drift_score),
        ("correction", snapshot.correction_rate, thresholds.maximum_correction_rate),
        ("override", snapshot.override_rate, thresholds.maximum_override_rate),
        ("abstention", snapshot.abstention_rate, thresholds.maximum_abstention_rate),
        (
            "adverse_event",
            snapshot.adverse_event_rate,
            thresholds.maximum_adverse_event_rate,
        ),
    )
    breached.extend(name for name, value, maximum in checks if value > maximum)
    provider_identity_changed = (
        snapshot.observed_provider_ref != snapshot.expected_provider_ref
    )
    if (
        provider_identity_changed
        or snapshot.provider_change_count > thresholds.maximum_provider_change_count
    ):
        breached.append("provider_change")
    if snapshot.sample_count < thresholds.minimum_sample_count:
        breached.append("sample_insufficient")
    action: Literal["continue", "pause_expansion", "recall"]
    if "adverse_event" in breached or "provider_change" in breached:
        action = "recall"
    elif breached:
        action = "pause_expansion"
    else:
        action = "continue"
    return MonitoringDecision(
        action=action,
        breached=tuple(breached),
        threshold_manifest_sha256=_threshold_manifest_sha256(thresholds),
        window_id=snapshot.window_id,
        use_case_id=snapshot.use_case_id,
        artifact_ref=snapshot.artifact_ref,
    )
