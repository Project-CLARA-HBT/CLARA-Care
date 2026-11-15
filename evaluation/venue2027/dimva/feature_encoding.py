"""DIMVA venue2027 leak-safe sequence feature encoder (task DIMVA-X04_feature_encoder, phase P04).

Purpose
-------
Encode minimal agent events into a fixed-length numeric feature matrix for the
DIMVA 2027 study "GovernanceTrace: Detecting Adaptive Authorization-Boundary
Probing from Minimal Agent Events"
(``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``, task contract
``research/venue2027/VENUES/dimva/TASKS/DIMVA-X04_feature_encoder.md``). Each
input sequence is one session/campaign of minimal, leak-safe events —
``(tool, scope, allowed, ts)`` required, plus the optional minimal-schema
fields ``actor``/``actor_id``/``purpose``/``campaign_id`` — carrying NO raw
content, NO rejection reason codes and NO label-bearing field. Five feature
families are derived (RQ1 mechanism, blueprint candidate arm B4 inputs):

- time gaps: inter-arrival statistics (mean/median/std/max/min/gap after
  denials) over consecutive events and over the denial subsequence;
- scope transitions: distinct scopes, switch rate, cross-scope denials and
  denial->different-scope follow-ups (the B1-style signature, softer);
- denial-transition signatures: denied fraction, denial run lengths,
  allowed-after-denied and denied-after-denied transition rates;
- entropy: Shannon entropy over the tool distribution and the scope
  distribution, in bits (campaign-linkage signal for cross-tool
  obfuscation);
- rate-adjusted counts: counts normalized by the encoder's session span
  (denials/hour, events/hour, distinct tools/hour) so campaign arms with
  different horizons remain comparable.

NO-LEAKAGE FIT DISCIPLINE (the core contract)
---------------------------------------------
ALL data-derived transforms — per-feature normalization statistics (median
and IQR scaling) and the training reference denial rate — are FIT ON
TRAINING DATA ONLY by :meth:`FeatureEncoder.fit` and then stored on the
fitted encoder. :meth:`FeatureEncoder.transform` applies the stored
statistics read-only: dev/test encodings NEVER alter the stored train stats
(verified by an internal consistency digest and re-assertable via
:meth:`stats_digest`). ``transform`` before ``fit`` raises
:class:`FeatureEncodingError` with ``NOT_FITTED``; fitting on data tagged as
holdout (an event/campaign-level ``split``/``partition`` tag of ``dev``,
``test`` or ``holdout``, or a per-sequence ``split_tag`` mapping entry, or
the ``split_tag`` argument) raises ``HOLDOUT_LEAK``. Entropy definitions,
window edges and the feature ordering are code constants — the only learned
parameters are the training normalization statistics and the training
denial-rate reference, and nothing else is ever data-dependent. Robust
scaling convention: a training column with zero IQR falls back to
centering-only scaling (scale 1.0: ``normalized = raw - train_median``),
documented in the lineage, instead of dividing by zero or refusing ordinary
uniformly-paced training data.

Determinism
-----------
Pure functions over the input; sorted iteration everywhere; no ``random``
module, no clock, no environment reads, no network, no live provider, no
real PHI/PII. The same ``(events, window)`` against the same fitted state
always yields byte-identical feature values (floats rounded to 12 decimal
places for stable serialization).

Allowed input
-------------
``fit(train_events)`` / ``transform(events)`` accept a list of sequences;
each sequence is either (a) a JSON-serializable mapping
``{"events": [...]}`` (optionally with ``case_id`` and a ``split`` /
``partition`` tag) or (b) a bare list of event mappings. An event mapping
requires exactly the minimal-schema fields: ``tool`` (non-empty str), ``scope``
(non-empty str), ``allowed`` (bool), ``ts`` (non-negative int, non-decreasing
across the sequence); optional ``actor``/``actor_id`` (non-empty str, one
distinct actor per sequence), ``purpose`` (coarse enum token) and
``campaign_id`` (opaque token). Any extra event key fails closed — a
reason-code-like or label-like key is refused as a leak-surface violation.
``window`` (the ``encode(events, window)`` contract argument) is the fixed
pacing window in seconds (positive int) used for rate adjustment and the
short-gap indicator; it is a code-level constant supplied by the caller, not
a learned statistic.

Failure semantics
-----------------
Every error is a :class:`FeatureEncodingError` carrying a stable uppercase
``reason_code``: ``NOT_FITTED`` (transform before fit), ``HOLDOUT_LEAK``
(fit called on holdout-tagged data — the holdout is never allowed to shape
stored statistics), ``EVENTS_NOT_A_LIST``, ``SEQUENCE_NOT_A_MAPPING_OR_LIST``,
``EVENT_SEQUENCE_EMPTY`` (fit requires at least one non-empty training
sequence), ``EVENT_NOT_AN_OBJECT``, ``EVENT_MISSING_FIELD``,
``EVENT_BAD_TYPE``, ``EVENT_TS_NOT_MONOTONIC``, ``EVENT_UNKNOWN_FIELD``,
``EVENT_REASON_CODE_FIELD_FORBIDDEN`` (RQ1 leak-safe masking),
``EVENT_LABEL_FIELD_FORBIDDEN``, ``SESSION_MIXED_ACTORS`` and
``INVALID_WINDOW``.

Feature lineage
---------------
:func:`FeatureEncoder.feature_lineage` returns one lineage record per output
feature: ``name``, ``family``, ``source_fields``, ``transform`` (the exact
formula) and ``fit_dependent`` (whether the feature's value depends on
stored training statistics). The lineage is complete by construction — it is
generated from the same feature-name registry the encoder iterates — and
tests assert the mapping covers every matrix column.

Version
-------
``FEATURE_ENCODING_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

FEATURE_ENCODING_VERSION = "1.0.0"

VENUE = "dimva"

# ---------------------------------------------------------------------------
# Stable reason codes (uppercase, machine-checkable).
# ---------------------------------------------------------------------------
RC_NOT_FITTED = "NOT_FITTED"
RC_HOLDOUT_LEAK = "HOLDOUT_LEAK"
RC_EVENTS_NOT_A_LIST = "EVENTS_NOT_A_LIST"
RC_SEQUENCE_NOT_A_MAPPING_OR_LIST = "SEQUENCE_NOT_A_MAPPING_OR_LIST"
RC_EVENT_SEQUENCE_EMPTY = "EVENT_SEQUENCE_EMPTY"
RC_EVENT_NOT_AN_OBJECT = "EVENT_NOT_AN_OBJECT"
RC_EVENT_MISSING_FIELD = "EVENT_MISSING_FIELD"
RC_EVENT_BAD_TYPE = "EVENT_BAD_TYPE"
RC_EVENT_TS_NOT_MONOTONIC = "EVENT_TS_NOT_MONOTONIC"
RC_EVENT_UNKNOWN_FIELD = "EVENT_UNKNOWN_FIELD"
RC_EVENT_REASON_CODE_FORBIDDEN = "EVENT_REASON_CODE_FIELD_FORBIDDEN"
RC_EVENT_LABEL_FIELD_FORBIDDEN = "EVENT_LABEL_FIELD_FORBIDDEN"
RC_SESSION_MIXED_ACTORS = "SESSION_MIXED_ACTORS"
RC_INVALID_WINDOW = "INVALID_WINDOW"

#: Required minimal-schema event fields (leak-safe surface, shared with
#: evaluation/venue2027/dimva/baselines.py's five-field surface plus the
#: optional frozen X01 schema fields).
REQUIRED_EVENT_KEYS: frozenset[str] = frozenset({"tool", "scope", "allowed", "ts"})

#: Optional frozen X01 telemetry-contract fields accepted on an event.
OPTIONAL_EVENT_KEYS: frozenset[str] = frozenset({"actor", "actor_id", "purpose", "campaign_id"})

#: Full legal event surface.
EVENT_KEYS: frozenset[str] = REQUIRED_EVENT_KEYS | OPTIONAL_EVENT_KEYS

#: Keys whose presence constitutes rejection-reason leakage (RQ1 masking
#: contract; mirrored from baselines.py so both surfaces refuse the same leak).
REASON_CODE_LEAK_KEYS: frozenset[str] = frozenset(
    {"reason_code", "reject_reason", "denial_reason", "rejection_code", "why"}
)

#: Campaign-level label fields that must never ride on an event (labels exist
#: only on the Campaign object / oracle adjudication, never on features).
EVENT_LABEL_FIELDS: frozenset[str] = frozenset(
    {"label", "campaign_label", "violated_invariant", "attacker_label", "is_attack"}
)

#: Holdout split tags that must never be fitted on.
HOLDOUT_SPLIT_TAGS: frozenset[str] = frozenset({"dev", "test", "holdout"})

#: Sequence-mapping keys holding a holdout tag.
SPLIT_TAG_KEYS: tuple[str, ...] = ("split", "partition", "split_tag")

#: Feature value rounding (stable serialization / byte-identical determinism).
VALUE_PRECISION = 12

# ---------------------------------------------------------------------------
# Feature registry — the single source of truth for feature names, families
# and lineage. ``fit_dependent`` marks features whose value depends on stored
# TRAINING statistics (true only for the IQR/median-normalized block and the
# rate-reference ratio).
# ---------------------------------------------------------------------------
FAMILY_TIME_GAPS = "time_gaps"
FAMILY_SCOPE_TRANSITIONS = "scope_transitions"
FAMILY_DENIAL_TRANSITIONS = "denial_transitions"
FAMILY_ENTROPY = "entropy"
FAMILY_RATE_ADJUSTED = "rate_adjusted"

_FEATURE_SPECS: tuple[tuple[str, str, bool], ...] = (
    # -- time gaps ---------------------------------------------------------
    ("gap_mean_seconds", FAMILY_TIME_GAPS, False),
    ("gap_median_seconds", FAMILY_TIME_GAPS, False),
    ("gap_std_seconds", FAMILY_TIME_GAPS, False),
    ("gap_max_seconds", FAMILY_TIME_GAPS, False),
    ("gap_min_seconds", FAMILY_TIME_GAPS, False),
    ("gap_after_denial_mean_seconds", FAMILY_TIME_GAPS, False),
    ("gap_short_fraction", FAMILY_TIME_GAPS, False),
    # -- scope transitions ---------------------------------------------------
    ("distinct_scopes", FAMILY_SCOPE_TRANSITIONS, False),
    ("scope_switch_rate", FAMILY_SCOPE_TRANSITIONS, False),
    ("cross_scope_denials", FAMILY_SCOPE_TRANSITIONS, False),
    ("denial_followed_by_other_scope", FAMILY_SCOPE_TRANSITIONS, False),
    # -- denial-transition signatures ----------------------------------------
    ("denied_fraction", FAMILY_DENIAL_TRANSITIONS, False),
    ("denial_run_max", FAMILY_DENIAL_TRANSITIONS, False),
    ("denial_run_mean", FAMILY_DENIAL_TRANSITIONS, False),
    ("allowed_after_denied_rate", FAMILY_DENIAL_TRANSITIONS, False),
    ("denied_after_denied_rate", FAMILY_DENIAL_TRANSITIONS, False),
    # -- entropy -------------------------------------------------------------
    ("tool_entropy_bits", FAMILY_ENTROPY, False),
    ("scope_entropy_bits", FAMILY_ENTROPY, False),
    # -- rate-adjusted counts -------------------------------------------------
    ("denials_per_hour", FAMILY_RATE_ADJUSTED, False),
    ("events_per_hour", FAMILY_RATE_ADJUSTED, False),
    ("distinct_tools_per_hour", FAMILY_RATE_ADJUSTED, False),
    ("denial_rate_ratio_to_train", FAMILY_RATE_ADJUSTED, True),
)

FEATURE_NAMES: tuple[str, ...] = tuple(name for name, _, _ in _FEATURE_SPECS)

_FEATURE_FAMILY: dict[str, str] = {name: family for name, family, _ in _FEATURE_SPECS}
_FEATURE_FIT_DEPENDENT: dict[str, bool] = {name: dep for name, _, dep in _FEATURE_SPECS}

#: Normalized (fit-dependent) block: every raw feature is robustly scaled by
#: the TRAINING median and IQR: normalized = (raw - train_median) / train_iqr.
NORMALIZED_FEATURE_NAMES: tuple[str, ...] = tuple(f"{name}_norm" for name in FEATURE_NAMES)

OUTPUT_FEATURE_NAMES: tuple[str, ...] = FEATURE_NAMES + NORMALIZED_FEATURE_NAMES

#: Feature count (44 = 22 raw + 22 normalized).
FEATURE_COUNT: int = len(OUTPUT_FEATURE_NAMES)


class FeatureEncodingError(ValueError):
    """Fail-closed encoder error with a stable, machine-checkable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


# ---------------------------------------------------------------------------
# Typed outputs (JSON-serializable).
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class FeatureMatrix:
    """One encoded sequence: ordered feature vector + provenance.

    ``values`` is a list of floats in exactly :data:`OUTPUT_FEATURE_NAMES`
    order. ``window_seconds`` echoes the caller's pacing window. ``stats_sha256``
    binds the row to the exact training statistics used (changes whenever the
    stored stats change, so leakage into a frozen matrix is detectable).
    """

    feature_names: tuple[str, ...]
    values: list[float]
    window_seconds: int
    n_events: int
    encoder_version: str = FEATURE_ENCODING_VERSION
    stats_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_names": list(self.feature_names),
            "values": [round(float(v), VALUE_PRECISION) for v in self.values],
            "window_seconds": self.window_seconds,
            "n_events": self.n_events,
            "encoder_version": self.encoder_version,
            "stats_sha256": self.stats_sha256,
        }


@dataclasses.dataclass(frozen=True)
class FeatureLineage:
    """Lineage record for one output feature (feature lineage/ablation audit)."""

    name: str
    family: str
    source_fields: tuple[str, ...]
    transform: str
    fit_dependent: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "source_fields": list(self.source_fields),
            "transform": self.transform,
            "fit_dependent": self.fit_dependent,
        }


# ---------------------------------------------------------------------------
# Validation — fail closed, never silently repaired.
# ---------------------------------------------------------------------------


def _extract_split_tag(sequence: Any) -> str | None:
    """Return a holdout tag if the sequence carries one, else None.

    Tag locations: a top-level ``split_tag`` argument (checked by the caller),
    a sequence mapping's ``split`` / ``partition`` key, or — when a sequence is
    a bare event list — the ``split_tag`` entry of its optional wrapper. Only
    the documented holdout tags matter; anything else is ignored here (the
    encoder never consumes labels for fitting).
    """
    if isinstance(sequence, Mapping):
        for key in SPLIT_TAG_KEYS:
            value = sequence.get(key)
            if isinstance(value, str) and value.strip().lower() in HOLDOUT_SPLIT_TAGS:
                return value.strip().lower()
    return None


def _validate_window(window: Any) -> int:
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise FeatureEncodingError(
            RC_INVALID_WINDOW, f"window must be a positive int, got {window!r}"
        )
    return window


def _validate_events(sequence: Any, index: int) -> tuple[list[dict[str, Any]], bool]:
    """Validate one sequence; return (canonical events, is_holdout_tagged).

    Fail-closed on: non-mapping/non-list sequence, empty event list, unknown /
    leak-surface / label fields, missing or mistyped minimal-schema fields,
    non-monotonic ``ts``, mixed actors. Empty event lists are tolerated at
    transform time (an all-zero row) but a fit made ONLY of empty sequences is
    refused later (nothing to fit).
    """
    if isinstance(sequence, Mapping):
        holdout = _extract_split_tag(sequence)
        raw_events = sequence.get("events")
    elif isinstance(sequence, list):
        holdout = False
        raw_events = sequence
    else:
        raise FeatureEncodingError(
            RC_SEQUENCE_NOT_A_MAPPING_OR_LIST,
            f"sequence {index} must be a mapping or a list, got {type(sequence).__name__}",
        )
    if not isinstance(raw_events, list):
        raise FeatureEncodingError(RC_EVENTS_NOT_A_LIST, f"sequence {index} events must be a list")
    if not raw_events:
        return [], bool(holdout)

    events: list[dict[str, Any]] = []
    actors: set[str] = set()
    previous_ts: int | None = None
    for raw in raw_events:
        if not isinstance(raw, Mapping):
            raise FeatureEncodingError(
                RC_EVENT_NOT_AN_OBJECT, f"sequence {index} event is not a mapping"
            )
        unknown = [str(k) for k in raw if k not in EVENT_KEYS]
        leak = [k for k in unknown if k in REASON_CODE_LEAK_KEYS]
        if leak:
            raise FeatureEncodingError(
                RC_EVENT_REASON_CODE_FORBIDDEN,
                f"sequence {index} carries rejection-reason field(s) {sorted(leak)} "
                "(RQ1 leak-safe masking contract)",
            )
        labels = [k for k in unknown if k in EVENT_LABEL_FIELDS]
        if labels:
            raise FeatureEncodingError(
                RC_EVENT_LABEL_FIELD_FORBIDDEN,
                f"sequence {index} carries label field(s) {sorted(labels)}; "
                "labels exist only at campaign/oracle level",
            )
        if unknown:
            raise FeatureEncodingError(
                RC_EVENT_UNKNOWN_FIELD,
                f"sequence {index} event has unknown field(s) {sorted(unknown)}",
            )
        missing = sorted(REQUIRED_EVENT_KEYS - set(raw))
        if missing:
            raise FeatureEncodingError(
                RC_EVENT_MISSING_FIELD, f"sequence {index} event missing {missing}"
            )
        tool = raw["tool"]
        scope = raw["scope"]
        allowed = raw["allowed"]
        ts = raw["ts"]
        if not (isinstance(tool, str) and tool):
            raise FeatureEncodingError(
                RC_EVENT_BAD_TYPE, f"sequence {index} event tool must be a non-empty string"
            )
        if not (isinstance(scope, str) and scope):
            raise FeatureEncodingError(
                RC_EVENT_BAD_TYPE, f"sequence {index} event scope must be a non-empty string"
            )
        if not isinstance(allowed, bool):
            raise FeatureEncodingError(
                RC_EVENT_BAD_TYPE, f"sequence {index} event allowed must be a bool"
            )
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            raise FeatureEncodingError(
                RC_EVENT_BAD_TYPE, f"sequence {index} event ts must be a non-negative int"
            )
        if previous_ts is not None and ts < previous_ts:
            raise FeatureEncodingError(
                RC_EVENT_TS_NOT_MONOTONIC,
                f"sequence {index} event ts {ts} < previous {previous_ts}",
            )
        previous_ts = ts
        actor = raw.get("actor", raw.get("actor_id"))
        if actor is not None:
            if not (isinstance(actor, str) and actor):
                raise FeatureEncodingError(
                    RC_EVENT_BAD_TYPE,
                    f"sequence {index} event actor/actor_id must be a non-empty string",
                )
            actors.add(actor)
        events.append(
            {
                "tool": tool,
                "scope": scope,
                "allowed": allowed,
                "ts": ts,
                **({"actor": actor} if actor is not None else {}),
                **({"purpose": raw["purpose"]} if "purpose" in raw else {}),
                **({"campaign_id": raw["campaign_id"]} if "campaign_id" in raw else {}),
            }
        )
    if len(actors) > 1:
        raise FeatureEncodingError(
            RC_SESSION_MIXED_ACTORS,
            f"sequence {index} mixes {len(actors)} actors; the scientific unit is "
            "one session/campaign for one principal",
        )
    return events, bool(holdout)


# ---------------------------------------------------------------------------
# Raw per-sequence feature computation (pure, fit-independent).
# ---------------------------------------------------------------------------


def _shannon_entropy_bits(counter: Mapping[str, int]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in sorted(counter.values()):
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _raw_features(
    events: Sequence[Mapping[str, Any]], window: int, train_denial_rate: float
) -> list[float]:
    """Compute all 22 registry features for one validated sequence.

    The first 21 are fit-independent per-sequence statistics; the 22nd
    (``denial_rate_ratio_to_train``) divides the sequence's denied fraction by
    the TRAINING reference rate stored on the fitted encoder (fit-dependent).
    An empty sequence encodes to the all-zero row.
    """
    n_events = len(events)
    if n_events == 0:
        return [0.0] * len(FEATURE_NAMES)

    span_seconds = events[-1]["ts"] - events[0]["ts"]
    hours = span_seconds / 3600.0

    # -- time gaps ----------------------------------------------------------
    gaps = [float(b["ts"] - a["ts"]) for a, b in zip(events, events[1:])]
    gaps_after_denial = [
        float(b["ts"] - a["ts"]) for a, b in zip(events, events[1:]) if not a["allowed"]
    ]
    gap_mean = sum(gaps) / len(gaps) if gaps else 0.0
    gap_median = _median(gaps) if gaps else 0.0
    gap_std = _std(gaps)
    gap_max = max(gaps) if gaps else 0.0
    gap_min = min(gaps) if gaps else 0.0
    gap_after_denial_mean = (
        sum(gaps_after_denial) / len(gaps_after_denial) if gaps_after_denial else 0.0
    )
    gap_short_fraction = sum(1 for g in gaps if g <= window) / len(gaps) if gaps else 0.0

    # -- scope transitions ----------------------------------------------------
    scopes = [e["scope"] for e in events]
    distinct_scopes = len(set(scopes))
    switches = sum(1 for a, b in zip(scopes, scopes[1:]) if a != b)
    scope_switch_rate = switches / (n_events - 1) if n_events > 1 else 0.0
    cross_scope_denials = 0
    denial_followed_by_other_scope = 0
    for i, e in enumerate(events):
        if not e["allowed"]:
            later_other = [
                f
                for f in events[i + 1 :]
                if f["scope"] != e["scope"] and f["ts"] - e["ts"] <= window
            ]
            if later_other:
                cross_scope_denials += 1
                denial_followed_by_other_scope += 1

    # -- denial-transition signatures -----------------------------------------
    denied_count = sum(1 for e in events if not e["allowed"])
    denied_fraction = denied_count / n_events
    run_lengths: list[int] = []
    run = 0
    for e in events:
        if not e["allowed"]:
            run += 1
        elif run:
            run_lengths.append(run)
            run = 0
    if run:
        run_lengths.append(run)
    denial_run_max = max(run_lengths) if run_lengths else 0
    denial_run_mean = sum(run_lengths) / len(run_lengths) if run_lengths else 0.0
    allowed_after_denied_rate = 0.0
    denied_after_denied_rate = 0.0
    if denied_count:
        allowed_after_denied = sum(
            1 for a, b in zip(events, events[1:]) if not a["allowed"] and b["allowed"]
        )
        denied_after_denied = sum(
            1 for a, b in zip(events, events[1:]) if not a["allowed"] and not b["allowed"]
        )
        allowed_after_denied_rate = allowed_after_denied / denied_count
        denied_after_denied_rate = denied_after_denied / denied_count

    # -- entropy ----------------------------------------------------------------
    tool_counter: dict[str, int] = {}
    scope_counter: dict[str, int] = {}
    for e in events:
        tool_counter[e["tool"]] = tool_counter.get(e["tool"], 0) + 1
        scope_counter[e["scope"]] = scope_counter.get(e["scope"], 0) + 1
    tool_entropy = _shannon_entropy_bits(tool_counter)
    scope_entropy = _shannon_entropy_bits(scope_counter)

    # -- rate-adjusted counts (fixed denominators, no learned statistic) -------
    safe_hours = hours if hours > 0 else 1.0
    denials_per_hour = denied_count / safe_hours
    events_per_hour = n_events / safe_hours
    distinct_tools = len(tool_counter)
    distinct_tools_per_hour = distinct_tools / safe_hours
    # Ratio to the TRAIN reference denial rate (fit-dependent): a session with
    # the training-typical denial mix scores ~1.0, a denial-saturated campaign
    # above it. Degenerate all-allowed train (rate 0): zero-denial sessions
    # score 1.0 (training-typical), any denial scores a large finite constant.
    if train_denial_rate <= 0.0:
        denial_rate_ratio = 1.0 if denied_fraction == 0.0 else 1e12
    else:
        denial_rate_ratio = denied_fraction / train_denial_rate

    return [
        gap_mean,
        gap_median,
        gap_std,
        gap_max,
        gap_min,
        gap_after_denial_mean,
        gap_short_fraction,
        float(distinct_scopes),
        scope_switch_rate,
        float(cross_scope_denials),
        float(denial_followed_by_other_scope),
        denied_fraction,
        float(denial_run_max),
        denial_run_mean,
        allowed_after_denied_rate,
        denied_after_denied_rate,
        tool_entropy,
        scope_entropy,
        denials_per_hour,
        events_per_hour,
        distinct_tools_per_hour,
        denial_rate_ratio,
    ]


# ---------------------------------------------------------------------------
# Stored training statistics.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TrainStats:
    """Statistics FIT ON TRAINING DATA ONLY and stored on the fitted encoder.

    ``median``/``iqr`` are the robust scaling constants for the raw feature
    columns; ``denial_rate`` is the training-set reference denied fraction used
    by the rate-adjusted ratio feature. Frozen after fit; ``transform`` never
    mutates them.
    """

    median: tuple[float, ...]
    iqr: tuple[float, ...]
    denial_rate: float

    def digest(self) -> str:
        payload = json.dumps(
            {
                "median": [round(m, VALUE_PRECISION) for m in self.median],
                "iqr": [round(q, VALUE_PRECISION) for q in self.iqr],
                "denial_rate": round(self.denial_rate, VALUE_PRECISION),
                "version": FEATURE_ENCODING_VERSION,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Encoder.
# ---------------------------------------------------------------------------


class FeatureEncoder:
    """Leak-safe sequence feature encoder.

    Usage contract: :meth:`fit` exactly once on TRAINING sequences, then
    :meth:`transform` on any split. ``transform`` before ``fit`` raises
    ``NOT_FITTED``; ``fit`` on holdout-tagged data raises ``HOLDOUT_LEAK``;
    a second ``fit`` silently replacing statistics is refused (``HOLDOUT_LEAK``
    discipline: refitting could launder holdout statistics through a second
    call) — build a fresh encoder instead.
    """

    def __init__(self, *, window: int = 3600) -> None:
        self._window = _validate_window(window)
        self._stats: TrainStats | None = None
        self._n_train_sequences = 0
        self._n_train_events = 0

    # -- introspection ---------------------------------------------------------

    @property
    def window(self) -> int:
        return self._window

    @property
    def is_fitted(self) -> bool:
        return self._stats is not None

    @property
    def n_train_sequences(self) -> int:
        return self._n_train_sequences

    @property
    def n_train_events(self) -> int:
        return self._n_train_events

    def stats_digest(self) -> str:
        """SHA-256 over the stored training statistics (leakage tripwire)."""
        if self._stats is None:
            raise FeatureEncodingError(RC_NOT_FITTED, "encoder has no stored statistics yet")
        return self._stats.digest()

    @staticmethod
    def feature_lineage() -> tuple[FeatureLineage, ...]:
        """Complete per-feature lineage (name, family, source, transform, fit-dependence).

        Generated from the same registry the encoder iterates, so it is
        complete by construction (asserted by tests).
        """
        lineage: list[FeatureLineage] = []
        for name, family, _fit_dependent in _FEATURE_SPECS:
            if name == "denial_rate_ratio_to_train":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("allowed",),
                        transform=(
                            "denied_fraction(sequence) / train_denial_rate "
                            "(train_denial_rate = mean denied_fraction over TRAIN "
                            "sequences; degenerate all-allowed train -> ratio "
                            "1.0 for zero-denial sessions, 1e12 otherwise)"
                        ),
                        fit_dependent=True,
                    )
                )
            elif name in ("gap_mean_seconds", "gap_median_seconds", "gap_std_seconds"):
                stat = name.split("_")[1]
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("ts",),
                        transform=f"{stat} of consecutive inter-arrival gaps (ts[i+1]-ts[i])",
                        fit_dependent=False,
                    )
                )
            elif name == "gap_max_seconds":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("ts",),
                        transform="max of consecutive inter-arrival gaps",
                        fit_dependent=False,
                    )
                )
            elif name == "gap_min_seconds":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("ts",),
                        transform="min of consecutive inter-arrival gaps",
                        fit_dependent=False,
                    )
                )
            elif name == "gap_after_denial_mean_seconds":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("ts", "allowed"),
                        transform="mean gap following a denied event (a denied, b next)",
                        fit_dependent=False,
                    )
                )
            elif name == "gap_short_fraction":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("ts",),
                        transform="fraction of gaps <= window seconds (caller constant)",
                        fit_dependent=False,
                    )
                )
            elif name == "distinct_scopes":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("scope",),
                        transform="count of distinct scope values in the sequence",
                        fit_dependent=False,
                    )
                )
            elif name == "scope_switch_rate":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("scope",),
                        transform="adjacent scope changes / (n_events - 1)",
                        fit_dependent=False,
                    )
                )
            elif name == "cross_scope_denials":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("scope", "allowed", "ts"),
                        transform=(
                            "denied events with a later event in a different scope "
                            "within window seconds (B1-style signature, softer)"
                        ),
                        fit_dependent=False,
                    )
                )
            elif name == "denial_followed_by_other_scope":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("scope", "allowed", "ts"),
                        transform="same matches as cross_scope_denials (transition count)",
                        fit_dependent=False,
                    )
                )
            elif name == "denied_fraction":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("allowed",),
                        transform="denied events / total events",
                        fit_dependent=False,
                    )
                )
            elif name == "denial_run_max":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("allowed",),
                        transform="longest consecutive denied run",
                        fit_dependent=False,
                    )
                )
            elif name == "denial_run_mean":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("allowed",),
                        transform="mean length of consecutive denied runs",
                        fit_dependent=False,
                    )
                )
            elif name == "allowed_after_denied_rate":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("allowed",),
                        transform="denied->allowed transitions / denied events",
                        fit_dependent=False,
                    )
                )
            elif name == "denied_after_denied_rate":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("allowed",),
                        transform="denied->denied transitions / denied events",
                        fit_dependent=False,
                    )
                )
            elif name == "tool_entropy_bits":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("tool",),
                        transform="Shannon entropy (bits) over the tool distribution",
                        fit_dependent=False,
                    )
                )
            elif name == "scope_entropy_bits":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("scope",),
                        transform="Shannon entropy (bits) over the scope distribution",
                        fit_dependent=False,
                    )
                )
            elif name == "denials_per_hour":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("allowed", "ts"),
                        transform="denied events / (span_seconds/3600); span 0 -> 1h",
                        fit_dependent=False,
                    )
                )
            elif name == "events_per_hour":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("ts",),
                        transform="n_events / (span_seconds/3600); span 0 -> 1h",
                        fit_dependent=False,
                    )
                )
            elif name == "distinct_tools_per_hour":
                lineage.append(
                    FeatureLineage(
                        name=name,
                        family=family,
                        source_fields=("tool", "ts"),
                        transform="distinct tools / (span_seconds/3600); span 0 -> 1h",
                        fit_dependent=False,
                    )
                )
            else:  # pragma: no cover - registry and handler must stay in sync
                raise FeatureEncodingError(
                    RC_EVENT_UNKNOWN_FIELD, f"feature {name!r} has no lineage handler"
                )
        for norm_name in NORMALIZED_FEATURE_NAMES:
            raw_name = norm_name[: -len("_norm")]
            lineage.append(
                FeatureLineage(
                    name=norm_name,
                    family=_FEATURE_FAMILY[raw_name],
                    source_fields=("ts", "tool", "scope", "allowed"),
                    transform=(
                        f"({raw_name} - train_median[{raw_name}]) / train_iqr[{raw_name}] "
                        "(median/IQR FIT ON TRAINING ONLY)"
                    ),
                    fit_dependent=True,
                )
            )
        return tuple(lineage)

    # -- fit -------------------------------------------------------------------

    def fit(self, train_events: Sequence[Any]) -> FeatureEncoder:
        """Fit all data-derived transforms on TRAINING data only.

        Refuses holdout-tagged sequences (``HOLDOUT_LEAK``): dev/test/holdout
        data must never shape the stored statistics. Requires at least one
        non-empty training sequence. Returns ``self``.
        """
        if self._stats is not None:
            raise FeatureEncodingError(
                RC_HOLDOUT_LEAK,
                "encoder is already fitted; refitting could launder non-training "
                "statistics through a second call — build a fresh encoder",
            )
        if not isinstance(train_events, list):
            raise FeatureEncodingError(
                RC_EVENTS_NOT_A_LIST,
                f"train_events must be a list, got {type(train_events).__name__}",
            )
        validated: list[list[dict[str, Any]]] = []
        n_events = 0
        for index, sequence in enumerate(train_events):
            events, holdout = _validate_events(sequence, index)
            if holdout:
                raise FeatureEncodingError(
                    RC_HOLDOUT_LEAK,
                    f"train_events[{index}] is tagged dev/test/holdout; fitting on "
                    "holdout data is refused (train-only transform discipline)",
                )
            validated.append(events)
            n_events += len(events)
        if not any(validated):
            raise FeatureEncodingError(
                RC_EVENT_SEQUENCE_EMPTY,
                "fit requires at least one non-empty training sequence",
            )

        # Training reference denial rate (the one learned rate statistic).
        total_events = sum(len(events) for events in validated if events)
        total_denied = sum(
            sum(1 for e in events if not e["allowed"]) for events in validated if events
        )
        denial_rate = total_denied / total_events

        rows = [_raw_features(events, self._window, denial_rate) for events in validated if events]

        median: list[float] = []
        iqr: list[float] = []
        for col in range(len(FEATURE_NAMES)):
            values = sorted(row[col] for row in rows)
            med = _median(values)
            q1 = _median(values[: len(values) // 2]) if len(values) >= 2 else med
            q3 = _median(values[(len(values) + 1) // 2 :]) if len(values) >= 2 else med
            spread = q3 - q1
            if spread <= 0.0:
                # Centering-only fallback (documented in the module docstring
                # and in the _norm lineage record): a zero-IQR training column
                # is uniformly-paced ordinary data, not an error — scale 1.0
                # avoids dividing by zero and keeps the column defined.
                spread = 1.0
            median.append(med)
            iqr.append(spread)

        self._stats = TrainStats(median=tuple(median), iqr=tuple(iqr), denial_rate=denial_rate)
        self._n_train_sequences = len(validated)
        self._n_train_events = n_events
        return self

    # -- transform -------------------------------------------------------------

    def transform(self, events: Sequence[Any]) -> list[FeatureMatrix]:
        """Encode sequences with the STORED training statistics (read-only).

        Dev/test encodings never alter the stored statistics: the stats digest
        before and after any transform is identical (asserted by tests). Accepts
        the same sequence shapes as :meth:`fit`; holdout-tagged sequences are
        fine here (they are encoded, never fitted on).
        """
        if self._stats is None:
            raise FeatureEncodingError(
                RC_NOT_FITTED,
                "transform called before fit; all normalization statistics must be "
                "fit on training data first",
            )
        if not isinstance(events, list):
            raise FeatureEncodingError(
                RC_EVENTS_NOT_A_LIST, f"events must be a list, got {type(events).__name__}"
            )
        stats = self._stats
        matrices: list[FeatureMatrix] = []
        for index, sequence in enumerate(events):
            if not isinstance(sequence, Mapping | list):
                raise FeatureEncodingError(
                    RC_SEQUENCE_NOT_A_MAPPING_OR_LIST,
                    f"sequence {index} must be a mapping or a list, got "
                    f"{type(sequence).__name__}",
                )
            valid_events, _holdout = _validate_events(sequence, index)
            raw = _raw_features(valid_events, self._window, stats.denial_rate)
            # Output layout: all 22 raw features in FEATURE_NAMES order, then
            # all 22 normalized companions in the same order (exactly
            # OUTPUT_FEATURE_NAMES).
            values: list[float] = [round(raw[col], VALUE_PRECISION) for col in range(len(raw))]
            for col in range(len(raw)):
                med = stats.median[col]
                iqr = stats.iqr[col]
                values.append(round((raw[col] - med) / iqr, VALUE_PRECISION))
            matrices.append(
                FeatureMatrix(
                    feature_names=OUTPUT_FEATURE_NAMES,
                    values=values,
                    window_seconds=self._window,
                    n_events=len(valid_events),
                    stats_sha256=stats.digest(),
                )
            )
        return matrices


#: Module-level convenience mirroring the task-contract signature
#: ``encode(events, window) -> FeatureMatrix`` for a single, already-fitted
#: encoder instance. Prefer the explicit :class:`FeatureEncoder` API in tests
#: and pipelines: this helper fits on the given events first (training-only by
#: construction — the caller asserts the events are training data).
def encode(events: Any, window: int) -> FeatureMatrix:
    """One-shot ``encode(events, window) -> FeatureMatrix``.

    Fits a fresh encoder on ``events`` (the caller guarantees they are
    training data) and returns the first encoded matrix. Holdout-tagged
    sequences are refused with ``HOLDOUT_LEAK`` exactly like
    :meth:`FeatureEncoder.fit`.
    """
    encoder = FeatureEncoder(window=window)
    rows = [events] if isinstance(events, Mapping | list) else events
    encoder.fit(rows)
    return encoder.transform(rows)[0]
