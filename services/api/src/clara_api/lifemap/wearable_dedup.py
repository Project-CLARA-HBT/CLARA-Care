"""Deterministic wearable deduplication and multi-source version mapping.

PH13 / A03. This module is pure domain logic: it never touches the database and
reuses the canonical connected-health contract (``CanonicalHealthRecord``) as
its only input type. It answers one question per incoming record: *what should
the caller do with it?* The answer is an explicit, closed outcome plus the exact
keys needed to retain provenance.

Design invariants
-----------------
1. **Deterministic identity.** A content key is derived from provider, external
   record id, metric type, observed window and canonical value. The same record
   replayed twice yields the same key on every process and platform.
2. **Revision updates are temporal.** Records sharing a provider record id and
   observed window are versions of one source row. The newest provider update
   wins; older or equal replays are ``superseded`` rather than destructively
   overwritten.
3. **Cross-source conflicts are preserved.** Equal metrics arriving from
   different sources with different values are never merged. Precedence only
   names the preferred value; every conflicting key is returned so the caller
   keeps parallel provenance.
4. **Device evidence outranks cloud echoes.** Device transports (Health Connect,
   Wear OS) take precedence over cloud connectors (Fitbit, Huawei Health) when
   two sources disagree; freshness breaks ties inside a source class.
5. **Fail closed.** Every entry point checks ``Settings`` for
   ``LIFEMAP_WEARABLE_DEDUP_ENABLED`` (default ``False``) and raises
   ``WearableDedupDisabledError`` instead of guessing when it cannot prove the
   flag is enabled.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from clara_api.connected_health.schemas import CanonicalHealthRecord, ConnectorProvider
from clara_api.core.config import Settings, get_settings

DEDUP_POLICY_VERSION = "wearable-dedup.v1"


class WearableDedupDisabledError(RuntimeError):
    """Raised when the wearable deduplication feature flag is not enabled."""


class DedupOutcome(StrEnum):
    """Closed set of decisions returned to the ingestion caller."""

    ACCEPTED = "accepted"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    SUPERSEDED = "superseded"
    CONFLICT_PRESERVED = "conflict_preserved"


class SourceClass(StrEnum):
    """Transport class used for precedence ordering."""

    DEVICE = "device"
    CLOUD = "cloud"
    UNKNOWN = "unknown"


_SOURCE_RANK: dict[SourceClass, int] = {
    SourceClass.DEVICE: 2,
    SourceClass.CLOUD: 1,
    SourceClass.UNKNOWN: 0,
}

_METHOD_RANK: dict[str, int] = {
    "manual": 4,
    "active": 3,
    "automatic": 2,
    "unknown": 1,
}

# Health Connect and Wear OS are on-device transports. Fitbit and Huawei Health
# connectors are cloud APIs. Deployments may override this mapping explicitly.
_DEFAULT_SOURCE_CLASSES: dict[str, SourceClass] = {
    ConnectorProvider.HEALTH_CONNECT.value: SourceClass.DEVICE,
    ConnectorProvider.WEAR_OS.value: SourceClass.DEVICE,
    ConnectorProvider.FITBIT.value: SourceClass.CLOUD,
    ConnectorProvider.HUAWEI_HEALTH.value: SourceClass.CLOUD,
}


def wearable_dedup_enabled(settings: Settings | None = None) -> bool:
    """Return the flag, defaulting to False when absent or unreadable."""

    resolved = settings if settings is not None else get_settings()
    return bool(getattr(resolved, "lifemap_wearable_dedup_enabled", False))


@dataclass(frozen=True, order=True)
class Precedence:
    """Total order over competing sources: device class > freshness > method."""

    source_rank: int
    freshness_epoch: float
    method_rank: int
    tiebreak: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_rank": self.source_rank,
            "freshness_epoch": self.freshness_epoch,
            "method_rank": self.method_rank,
            "tiebreak": self.tiebreak,
        }


@dataclass(frozen=True)
class DedupDecision:
    """The caller-facing result of evaluating one incoming record."""

    outcome: DedupOutcome
    dedup_key: str
    revision_key: str
    metric_key: str
    reason: str
    preferred_key: str | None = None
    conflicting_keys: tuple[str, ...] = ()
    superseded_keys: tuple[str, ...] = ()
    incoming_precedence: Precedence | None = None
    policy_version: str = DEDUP_POLICY_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "dedup_key": self.dedup_key,
            "revision_key": self.revision_key,
            "metric_key": self.metric_key,
            "reason": self.reason,
            "preferred_key": self.preferred_key,
            "conflicting_keys": list(self.conflicting_keys),
            "superseded_keys": list(self.superseded_keys),
            "incoming_precedence": (
                self.incoming_precedence.to_dict() if self.incoming_precedence is not None else None
            ),
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True)
class VersionMap:
    """Final decision for every distinct record in a batch."""

    decisions: tuple[DedupDecision, ...]
    preferred_by_metric: dict[str, str]
    policy_version: str = DEDUP_POLICY_VERSION

    def decision_for(self, record: CanonicalHealthRecord) -> DedupDecision | None:
        key = record_dedup_key(record)
        return next((item for item in self.decisions if item.dedup_key == key), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "decisions": [decision.to_dict() for decision in self.decisions],
            "preferred_by_metric": dict(self.preferred_by_metric),
            "policy_version": self.policy_version,
        }


def _canonical_number(value: float) -> float:
    number = float(value)
    return 0.0 if number == 0 else number


def _canonical_value(record: CanonicalHealthRecord) -> dict[str, object]:
    raw = record.value
    if raw.scalar is not None:
        payload: dict[str, object] = {"scalar": _canonical_number(raw.scalar)}
    else:
        components = raw.components or {}
        payload = {
            "components": {
                name: _canonical_number(component) for name, component in sorted(components.items())
            }
        }
    payload["unit"] = raw.unit
    return payload


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("wearable deduplication requires timezone-aware timestamps")
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat()


def _digest(prefix: str, payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(canonical).hexdigest()}"


def record_dedup_key(record: CanonicalHealthRecord) -> str:
    """Stable content key: provider + external id + metric + window + value."""

    return _digest(
        "wearable-dedup",
        {
            "provider": record.provider.value,
            "external_record_id": record.provider_record_id,
            "metric_type": record.record_type.value,
            "start": _iso(record.observed_start),
            "end": _iso(record.observed_end),
            "value": _canonical_value(record),
        },
    )


def record_revision_key(record: CanonicalHealthRecord) -> str:
    """Source-row identity, excluding value so revisions collapse together."""

    return _digest(
        "wearable-revision",
        {
            "provider": record.provider.value,
            "external_record_id": record.provider_record_id,
            "metric_type": record.record_type.value,
            "start": _iso(record.observed_start),
            "end": _iso(record.observed_end),
        },
    )


def record_metric_key(record: CanonicalHealthRecord) -> str:
    """Provider-agnostic metric identity used to detect cross-source echoes."""

    return _digest(
        "wearable-metric",
        {
            "metric_type": record.record_type.value,
            "start": _iso(record.observed_start),
            "end": _iso(record.observed_end),
        },
    )


class WearableDeduplicationEngine:
    """Deterministic, side-effect-free wearable deduplication engine."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        source_classes: Mapping[str, SourceClass] | None = None,
    ) -> None:
        self._settings = settings
        overrides = {
            str(provider): SourceClass(source_class)
            for provider, source_class in (source_classes or {}).items()
        }
        self._source_classes: dict[str, SourceClass] = {
            **_DEFAULT_SOURCE_CLASSES,
            **overrides,
        }

    def _check_enabled(self) -> None:
        if not wearable_dedup_enabled(self._settings):
            raise WearableDedupDisabledError("lifemap_wearable_dedup_disabled")

    def source_class(self, record: CanonicalHealthRecord) -> SourceClass:
        return self._source_classes.get(record.provider.value, SourceClass.UNKNOWN)

    def _precedence(self, record: CanonicalHealthRecord) -> Precedence:
        updated_at = record.provider_updated_at or record.observed_end
        return Precedence(
            source_rank=_SOURCE_RANK[self.source_class(record)],
            freshness_epoch=_utc(updated_at).timestamp(),
            method_rank=_METHOD_RANK.get(record.recording_method.value, 1),
            tiebreak=record_dedup_key(record),
        )

    def _revision_order(self, record: CanonicalHealthRecord) -> tuple[float, int, int, str]:
        precedence = self._precedence(record)
        return (
            precedence.freshness_epoch,
            precedence.method_rank,
            precedence.source_rank,
            precedence.tiebreak,
        )

    @staticmethod
    def _same_value(left: CanonicalHealthRecord, right: CanonicalHealthRecord) -> bool:
        return _canonical_value(left) == _canonical_value(right)

    def evaluate(
        self,
        incoming: CanonicalHealthRecord,
        existing: Sequence[CanonicalHealthRecord] = (),
    ) -> DedupDecision:
        """Decide one record against the currently active records for its metric."""

        self._check_enabled()
        dedup_key = record_dedup_key(incoming)
        revision_key = record_revision_key(incoming)
        metric_key = record_metric_key(incoming)
        precedence = self._precedence(incoming)
        keyed = [(record_dedup_key(record), record) for record in existing]

        same_revision = [
            (key, record) for key, record in keyed if record_revision_key(record) == revision_key
        ]
        exact = next((key for key, _ in same_revision if key == dedup_key), None)
        if exact is not None:
            return DedupDecision(
                outcome=DedupOutcome.DUPLICATE_SKIPPED,
                dedup_key=dedup_key,
                revision_key=revision_key,
                metric_key=metric_key,
                reason="same_revision_identical_value",
                preferred_key=exact,
                incoming_precedence=precedence,
            )
        if same_revision:
            best_key, best_record = max(
                same_revision, key=lambda item: self._revision_order(item[1])
            )
            if self._revision_order(incoming) > self._revision_order(best_record):
                return DedupDecision(
                    outcome=DedupOutcome.ACCEPTED,
                    dedup_key=dedup_key,
                    revision_key=revision_key,
                    metric_key=metric_key,
                    reason="same_revision_newer",
                    preferred_key=dedup_key,
                    superseded_keys=tuple(sorted(key for key, _ in same_revision)),
                    incoming_precedence=precedence,
                )
            return DedupDecision(
                outcome=DedupOutcome.SUPERSEDED,
                dedup_key=dedup_key,
                revision_key=revision_key,
                metric_key=metric_key,
                reason="same_revision_older_or_equal",
                preferred_key=best_key,
                incoming_precedence=precedence,
            )

        cross_source = [
            (key, record) for key, record in keyed if record_metric_key(record) == metric_key
        ]
        if cross_source:
            identical = [
                (key, record) for key, record in cross_source if self._same_value(record, incoming)
            ]
            if identical:
                preferred_key = max(identical, key=lambda item: self._precedence(item[1]))[0]
                return DedupDecision(
                    outcome=DedupOutcome.DUPLICATE_SKIPPED,
                    dedup_key=dedup_key,
                    revision_key=revision_key,
                    metric_key=metric_key,
                    reason="cross_source_identical_value",
                    preferred_key=preferred_key,
                    incoming_precedence=precedence,
                )
            best_key, best_record = max(cross_source, key=lambda item: self._precedence(item[1]))
            conflict_keys = tuple(sorted(key for key, _ in cross_source))
            if precedence > self._precedence(best_record):
                return DedupDecision(
                    outcome=DedupOutcome.ACCEPTED,
                    dedup_key=dedup_key,
                    revision_key=revision_key,
                    metric_key=metric_key,
                    reason="conflict_preferred_not_overwritten",
                    preferred_key=dedup_key,
                    conflicting_keys=conflict_keys,
                    incoming_precedence=precedence,
                )
            return DedupDecision(
                outcome=DedupOutcome.CONFLICT_PRESERVED,
                dedup_key=dedup_key,
                revision_key=revision_key,
                metric_key=metric_key,
                reason="conflict_lower_precedence_or_tie",
                preferred_key=best_key,
                conflicting_keys=conflict_keys,
                incoming_precedence=precedence,
            )

        return DedupDecision(
            outcome=DedupOutcome.ACCEPTED,
            dedup_key=dedup_key,
            revision_key=revision_key,
            metric_key=metric_key,
            reason="new_record",
            preferred_key=dedup_key,
            incoming_precedence=precedence,
        )

    def map_versions(self, records: Sequence[CanonicalHealthRecord]) -> VersionMap:
        """Evaluate a whole batch deterministically, independent of input order."""

        self._check_enabled()
        by_revision: dict[str, dict[str, CanonicalHealthRecord]] = defaultdict(dict)
        for record in records:
            by_revision[record_revision_key(record)][record_dedup_key(record)] = record

        decisions: dict[str, DedupDecision] = {}
        winners_by_metric: dict[str, list[str]] = defaultdict(list)
        winner_records: dict[str, CanonicalHealthRecord] = {}

        for revision_key in sorted(by_revision):
            unique = by_revision[revision_key]
            ordered = sorted(unique.values(), key=self._revision_order, reverse=True)
            winner = ordered[0]
            winner_key = record_dedup_key(winner)
            metric_key = record_metric_key(winner)
            losers = tuple(sorted(key for key in unique if key != winner_key))
            winners_by_metric[metric_key].append(winner_key)
            winner_records[winner_key] = winner
            for key, record in unique.items():
                if key == winner_key:
                    continue
                identical = self._same_value(record, winner)
                decisions[key] = DedupDecision(
                    outcome=(
                        DedupOutcome.DUPLICATE_SKIPPED if identical else DedupOutcome.SUPERSEDED
                    ),
                    dedup_key=key,
                    revision_key=revision_key,
                    metric_key=metric_key,
                    reason=("cross_revision_identical_value" if identical else "older_revision"),
                    preferred_key=winner_key,
                    incoming_precedence=self._precedence(record),
                )
            decisions[winner_key] = DedupDecision(
                outcome=DedupOutcome.ACCEPTED,
                dedup_key=winner_key,
                revision_key=revision_key,
                metric_key=metric_key,
                reason="revision_winner",
                preferred_key=winner_key,
                superseded_keys=tuple(
                    key for key in losers if not self._same_value(unique[key], winner)
                ),
                incoming_precedence=self._precedence(winner),
            )

        preferred_by_metric: dict[str, str] = {}
        for metric_key in sorted(winners_by_metric):
            winner_keys = winners_by_metric[metric_key]
            preferred_key = max(winner_keys, key=lambda key: self._precedence(winner_records[key]))
            preferred_record = winner_records[preferred_key]
            preferred_by_metric[metric_key] = preferred_key
            for key in winner_keys:
                record = winner_records[key]
                if key == preferred_key:
                    conflicts = tuple(
                        sorted(
                            other
                            for other in winner_keys
                            if other != key and not self._same_value(winner_records[other], record)
                        )
                    )
                    decisions[key] = DedupDecision(
                        outcome=DedupOutcome.ACCEPTED,
                        dedup_key=key,
                        revision_key=decisions[key].revision_key,
                        metric_key=metric_key,
                        reason=(
                            "preferred_source_survives_conflict"
                            if conflicts
                            else decisions[key].reason
                        ),
                        preferred_key=preferred_key,
                        conflicting_keys=conflicts,
                        superseded_keys=decisions[key].superseded_keys,
                        incoming_precedence=decisions[key].incoming_precedence,
                    )
                elif self._same_value(record, preferred_record):
                    decisions[key] = DedupDecision(
                        outcome=DedupOutcome.DUPLICATE_SKIPPED,
                        dedup_key=key,
                        revision_key=decisions[key].revision_key,
                        metric_key=metric_key,
                        reason="cross_source_identical_value",
                        preferred_key=preferred_key,
                        incoming_precedence=decisions[key].incoming_precedence,
                    )
                else:
                    decisions[key] = DedupDecision(
                        outcome=DedupOutcome.CONFLICT_PRESERVED,
                        dedup_key=key,
                        revision_key=decisions[key].revision_key,
                        metric_key=metric_key,
                        reason="cross_source_conflict_lower_precedence",
                        preferred_key=preferred_key,
                        conflicting_keys=tuple(
                            sorted(
                                other
                                for other in winner_keys
                                if other != key
                                and not self._same_value(winner_records[other], record)
                            )
                        ),
                        incoming_precedence=decisions[key].incoming_precedence,
                    )

        return VersionMap(
            decisions=tuple(decisions[key] for key in sorted(decisions)),
            preferred_by_metric=preferred_by_metric,
        )
