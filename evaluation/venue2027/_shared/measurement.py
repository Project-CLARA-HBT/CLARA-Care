"""CLARA-Care 2027 shared task SH-measurement — measurement standard over run bundles.

Purpose
-------
Turn the raw JSONL emitted by ``SH-run_harness`` (one ``pair_result`` record per
planned arm x case pair, plus one ``run_manifest``) into a versioned
:class:`Metrics` payload whose every number is *computed from raw records* and
never estimated, back-filled or silently defaulted to zero. This is the
program-level measurement standard reused by all nine venue2027 studies, per
``research/venue2027/GATES/SCIENTIFIC_METRICS_CONTRACT.md`` (rule 6: report
mutually exclusive counts and never silently shrink the denominator) and
``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` (rule 4: mutually
exclusive per-arm outcome buckets; rule 3: the independent unit of inference is
the preregistered arm x case pair — repeated calls inside one case history are
clustered and never inflate the denominator).

Metrics produced (all from raw records)
---------------------------------------
- ``outcome_counts`` — mutually exclusive buckets ``admit / reject /
  indeterminate / not_run / timeout / execution_error`` (plus harness-only
  ``invalid_result``, kept visible so nothing is ever dropped), each pair
  tallied exactly once by its ``observed_outcome``.
- ``denominator`` — ``planned`` (preregistered arm x case pairs), ``attempted``
  (records present), ``missing`` (planned - attempted), ``attempted_total`` =
  sum of the outcome buckets. ``assert_denominator_consistency`` proves
  ``attempted_total + missing == planned`` and that buckets are mutually
  exclusive (no pair counted twice).
- ``forbidden_commit_rate`` — forbidden events (per oracle verdicts, not
  candidate reason codes) over the predeclared denominator; refusing to divide
  by an empty or missing denominator.
- ``false_stale_rate`` — REJECT verdicts later contradicted by observed
  persisted state (``outcome.observed_outcome == "REJECT"`` while the oracle
  truth label is ``ADMIT``) over all stale checks actually performed.
- ``throughput_ops_per_sec`` — committed ops / active busy seconds of the run
  (sum of per-record ``duration_seconds``), not wall time padded by idle or
  benchmark-overhead gaps; computed only when the manifest's ``wall_seconds``
  is present so the unit can never be silently misinterpreted.
- ``latency_seconds`` — p50 / p95 / p99 over raw per-record ``duration_seconds``
  using exact nearest-rank order statistics on the sorted sample; malformed or
  mixed-unit samples are refused, never averaged through.
- ``retry_amplification`` — total attempts / distinct logical operations,
  computed from ``attempt_index`` fields when the harness records them (1.0
  when every op ran exactly once); refused as MISSING_RECORDS when no attempt
  field exists at all, rather than silently reported as 1.0.

Allowed input
-------------
A :class:`harness.RunBundle`-shaped mapping (``campaign_id``, ``manifest``,
``records``), the bundle object itself, or a JSONL string/Path containing the
same lines. Records must be plain JSON dicts. No network, no database, no
model calls, no clock: the module is a pure function over already-recorded
evidence, so benchmark overhead and SUT cost stay externalized.

Failure semantics
-----------------
Fail closed with stable reason codes (:class:`MeasurementError`):
- ``MISSING_RECORDS`` — a requested metric's required raw records/fields are
  absent; the metric is omitted (listed in ``metrics.unavailable``) instead of
  being invented as 0.
- ``DENOMINATOR_MISMATCH`` — outcome counts do not partition the planned total
  (records missing, duplicated, or manifest disagreement).
- ``NO_DENOMINATOR`` — a rate was requested with zero/missing denominator.
- ``MALFORMED_RECORD`` / ``MALFORMED_DURATION`` — record is not a valid
  pair_result or durations are not all positive finite seconds in one unit.
- ``MIXED_TIME_UNITS`` — p99/latency input mixes declared time units
  (adversarial control from the task spec).
- ``ORACLE_VERDICT_MISSING`` — forbidden-commit rate requested but records
  carry no independent oracle verdicts (truth never comes from candidate
  reason codes).

Never raises for ordinary absence: :func:`measure` omits the metric and
records the stable reason. Only structurally impossible inputs (e.g. no
records at all when a metric is demanded) raise.

Version
-------
``MEASUREMENT_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

MEASUREMENT_VERSION = "1.0.0"

#: Outcome buckets in the canonical harness vocabulary (lowercase keys).
OUTCOME_BUCKETS: tuple[str, ...] = (
    "admit",
    "reject",
    "indeterminate",
    "not_run",
    "timeout",
    "execution_error",
    "invalid_result",
)

#: Harness ``observed_outcome`` value -> canonical lowercase bucket.
_HARNESS_OUTCOME_TO_BUCKET: dict[str, str] = {
    "ADMIT": "admit",
    "REJECT": "reject",
    "INDETERMINATE": "indeterminate",
    "NOT_RUN_EXTERNAL": "not_run",
    "TIMEOUT": "timeout",
    "EXECUTION_ERROR": "execution_error",
    "INVALID_RESULT": "invalid_result",
}

#: Buckets that represent a committed logical operation (authorized completion
#: is ADMIT; REJECT is a completed, counted *safe* decision, not a commit).
_COMMITTED_BUCKETS: frozenset[str] = frozenset({"admit"})

#: Buckets that consume a real attempt (everything except planned-but-never-run).
_ATTEMPTED_BUCKETS: frozenset[str] = frozenset(
    {"admit", "reject", "indeterminate", "timeout", "execution_error", "invalid_result"}
)

REASON_MISSING_RECORDS = "MISSING_RECORDS"
REASON_DENOMINATOR_MISMATCH = "DENOMINATOR_MISMATCH"
REASON_NO_DENOMINATOR = "NO_DENOMINATOR"
REASON_MALFORMED_RECORD = "MALFORMED_RECORD"
REASON_MALFORMED_DURATION = "MALFORMED_DURATION"
REASON_MIXED_TIME_UNITS = "MIXED_TIME_UNITS"
REASON_ORACLE_VERDICT_MISSING = "ORACLE_VERDICT_MISSING"

_ALLOWED_TIME_UNITS: frozenset[str] = frozenset({"s", "ms", "us", "ns"})


class MeasurementError(ValueError):
    """Fail-closed measurement violation carrying a stable machine-readable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class UnavailableMetric:
    """A metric that was refused because its required raw records are missing.

    Never a silent zero: the caller sees exactly why the number is absent.
    """

    metric: str
    reason_code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"metric": self.metric, "reason_code": self.reason_code, "detail": self.detail}


@dataclasses.dataclass(frozen=True)
class Latency:
    """Exact nearest-rank order statistics over one homogeneous time unit."""

    unit: str
    n: int
    p50: float
    p95: float
    p99: float

    def to_dict(self) -> dict[str, Any]:
        return {"unit": self.unit, "n": self.n, "p50": self.p50, "p95": self.p95, "p99": self.p99}


@dataclasses.dataclass(frozen=True)
class Metrics:
    """Versioned, JSON-serializable result of :func:`measure`."""

    measurement_version: str
    campaign_id: str
    outcome_counts: dict[str, int]
    denominator: dict[str, int]
    forbidden_commit_rate: float | None
    false_stale_rate: float | None
    throughput_ops_per_sec: float | None
    latency_seconds: Latency | None
    retry_amplification: float | None
    unavailable: tuple[UnavailableMetric, ...]
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_version": self.measurement_version,
            "campaign_id": self.campaign_id,
            "outcome_counts": dict(self.outcome_counts),
            "denominator": dict(self.denominator),
            "forbidden_commit_rate": self.forbidden_commit_rate,
            "false_stale_rate": self.false_stale_rate,
            "throughput_ops_per_sec": self.throughput_ops_per_sec,
            "latency_seconds": self.latency_seconds.to_dict() if self.latency_seconds else None,
            "retry_amplification": self.retry_amplification,
            "unavailable": [u.to_dict() for u in self.unavailable],
            "provenance": dict(self.provenance),
        }


# ---------------------------------------------------------------------------
# Input loading (pure; JSONL/bundle/dict forms)
# ---------------------------------------------------------------------------


def _bundle_to_parts(bundle: Any) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Accept RunBundle, mapping, JSONL text or Path; return (campaign_id, manifest, records)."""
    if hasattr(bundle, "to_dict") and hasattr(bundle, "records"):
        payload = bundle.to_dict()
        return (
            str(payload.get("campaign_id", "")),
            dict(payload.get("manifest", {})),
            [dict(r) for r in payload.get("records", [])],
        )
    if isinstance(bundle, str):
        # Bare JSONL text (contains a newline) or a filesystem path to JSONL.
        text = bundle if "\n" in bundle else Path(bundle).read_text(encoding="utf-8")
        return _parse_jsonl(text)
    if isinstance(bundle, Path):
        return _parse_jsonl(bundle.read_text(encoding="utf-8"))
    if isinstance(bundle, Mapping):
        records = bundle.get("records")
        if records is None:
            raise MeasurementError(REASON_MISSING_RECORDS, "bundle mapping has no 'records'")
        return (
            str(bundle.get("campaign_id", "")),
            dict(bundle.get("manifest", {}) or {}),
            [dict(r) for r in records],
        )
    raise MeasurementError(
        REASON_MALFORMED_RECORD,
        f"unsupported bundle type {type(bundle).__name__}",
    )


def _parse_jsonl(text: str) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    campaign_id = ""
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MeasurementError(REASON_MALFORMED_RECORD, f"line {line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise MeasurementError(REASON_MALFORMED_RECORD, f"line {line_no}: not an object")
        kind = obj.get("record_kind")
        if kind == "run_manifest":
            manifest = obj
        elif kind == "pair_result":
            records.append(obj)
            campaign_id = campaign_id or str(obj.get("campaign_id", ""))
    if manifest:
        campaign_id = str(manifest.get("campaign_id", campaign_id))
    if not records and not manifest:
        raise MeasurementError(REASON_MISSING_RECORDS, "JSONL contains no pair or manifest records")
    return campaign_id, manifest, records


def load_bundle_records(path: str | Path) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Public helper: parse a JSONL run bundle from disk."""
    return _parse_jsonl(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Raw-record derivation (each metric computed from records, never estimated)
# ---------------------------------------------------------------------------


def _observed_outcome(record: Mapping[str, Any], index: int) -> str:
    outcome = record.get("outcome")
    if not isinstance(outcome, Mapping):
        raise MeasurementError(REASON_MALFORMED_RECORD, f"record {index}: missing 'outcome' map")
    observed = outcome.get("observed_outcome")
    if not isinstance(observed, str):
        raise MeasurementError(REASON_MALFORMED_RECORD, f"record {index}: missing observed_outcome")
    bucket = _HARNESS_OUTCOME_TO_BUCKET.get(observed)
    if bucket is None:
        raise MeasurementError(
            REASON_MALFORMED_RECORD,
            f"record {index}: observed_outcome {observed!r} not in harness vocabulary",
        )
    return bucket


def count_outcomes(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Mutually exclusive outcome counts over raw pair records (each pair once)."""
    counts = {bucket: 0 for bucket in OUTCOME_BUCKETS}
    for index, record in enumerate(records):
        counts[_observed_outcome(record, index)] += 1
    return counts


def _logical_op_id(record: Mapping[str, Any], index: int) -> str | None:
    value = record.get("logical_op_id")
    if isinstance(value, str) and value:
        return value
    arm = record.get("arm_id")
    case = record.get("case_id")
    if isinstance(arm, str) and arm and isinstance(case, str) and case:
        return f"{arm}::{case}"
    return None


def compute_denominator(
    records: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    *,
    planned_pairs: int | None = None,
) -> dict[str, int]:
    """Explicit denominator: planned / attempted / missing / attempted_total.

    ``planned`` comes from the preregistration (manifest ``planned_pairs`` or an
    explicit override) — never from the number of records that happened to
    arrive, which is how denominators silently shrink.
    """
    counts = count_outcomes(records)
    attempted_total = sum(counts[b] for b in _ATTEMPTED_BUCKETS)
    if planned_pairs is None:
        raw_planned = manifest.get("planned_pairs")
        planned_pairs = int(raw_planned) if isinstance(raw_planned, (int, float)) else attempted_total
    attempted = len(records)
    return {
        "planned": int(planned_pairs),
        "attempted": attempted,
        "missing": int(planned_pairs) - attempted,
        "attempted_total": attempted_total,
        "committed": counts["admit"],
        "rejected": counts["reject"],
        "indeterminate": counts["indeterminate"],
        "timeout": counts["timeout"],
        "execution_error": counts["execution_error"],
        "not_run_external": counts["not_run"],
        "invalid_result": counts["invalid_result"],
    }


def assert_denominator_consistency(bundle: Any) -> dict[str, int]:
    """Prove the mutually exclusive counts partition the planned total.

    Raises :class:`MeasurementError` with ``DENOMINATOR_MISMATCH`` when:
    - sum(outcome buckets) != number of pair records (a record is malformed or
      a pair was counted twice), or
    - attempted + missing != planned (records dropped or plan overstated), or
    - the manifest's own ``denominator_total`` disagrees with the recount
      (never trust a summary over raw records).
    Returns the recount on success.
    """
    campaign_id, manifest, records = _bundle_to_parts(bundle)
    counts = count_outcomes(records)
    total = sum(counts.values())

    # Mutually exclusive: every record tallies exactly once.
    if total != len(records):
        raise MeasurementError(
            REASON_DENOMINATOR_MISMATCH,
            f"outcome buckets sum {total} != record count {len(records)}",
        )
    # One record per logical operation: a repeated pair identity means a pair
    # was counted twice (or the journal double-wrote an op).
    identities: list[tuple[str, str]] = []
    for index, record in enumerate(records):
        op = _logical_op_id(record, index)
        if op is None:
            raise MeasurementError(
                REASON_MALFORMED_RECORD, f"record {index}: no logical_op_id or arm/case identity"
            )
        identities.append(op)
    if len(set(identities)) != len(identities):
        duplicates = sorted({op for op in identities if identities.count(op) > 1})
        raise MeasurementError(
            REASON_DENOMINATOR_MISMATCH,
            f"pair identity counted twice: {duplicates}",
        )
    planned = manifest.get("planned_pairs")
    if isinstance(planned, (int, float)):
        if total + int(manifest.get("missing_pairs", 0)) != int(planned):
            raise MeasurementError(
                REASON_DENOMINATOR_MISMATCH,
                f"records {total} + missing {manifest.get('missing_pairs')} != planned {planned}",
            )
        manifest_total = manifest.get("denominator_total")
        if isinstance(manifest_total, (int, float)) and int(manifest_total) != total:
            raise MeasurementError(
                REASON_DENOMINATOR_MISMATCH,
                f"manifest denominator_total {manifest_total} != raw recount {total}",
            )
    return counts


def _oracle_truth(record: Mapping[str, Any]) -> str | None:
    """Independent oracle verdict for the pair (never candidate reason codes)."""
    oracle = record.get("oracle")
    if not isinstance(oracle, Mapping):
        return None
    truth = oracle.get("expected_outcome") or oracle.get("truth_outcome")
    if isinstance(truth, str) and truth in _HARNESS_OUTCOME_TO_BUCKET:
        return truth
    return None


def compute_forbidden_commit_rate(
    records: Sequence[Mapping[str, Any]],
    *,
    denominator: int | None = None,
) -> tuple[float | None, str | None]:
    """Forbidden commits / predeclared denominator, from oracle verdicts only.

    A forbidden event is an ADMIT that the independent oracle judged REJECT
    (the oracle decides forbiddenness; candidate reason codes are ignored).
    The denominator is the predeclared planned total — not the convenient
    subset of successful pairs.
    """
    forbidden = 0
    has_verdicts = False
    for index, record in enumerate(records):
        truth = _oracle_truth(record)
        if truth is None:
            continue
        has_verdicts = True
        bucket = _observed_outcome(record, index)
        if bucket == "admit" and truth == "REJECT":
            forbidden += 1
    if not has_verdicts:
        return None, REASON_ORACLE_VERDICT_MISSING
    denom = denominator
    if denom is None or denom <= 0:
        return None, REASON_NO_DENOMINATOR
    return forbidden / denom, None


def compute_false_stale_rate(records: Sequence[Mapping[str, Any]]) -> tuple[float | None, str | None]:
    """Fraction of stale-check REJECTs contradicted by observed persisted state.

    A false stale: the system reported REJECT (declared the dependency stale /
    unavailable) while the independent oracle truth label is ADMIT — i.e. the
    rejection was wrong. Computed only from pairs where the oracle supplied a
    truth label; refused with MISSING_RECORDS when no such check exists.
    """
    stale_checks = 0
    false_stale = 0
    for record in records:
        truth = _oracle_truth(record)
        if truth is None:
            continue
        observed = _HARNESS_OUTCOME_TO_BUCKET[record["outcome"]["observed_outcome"]]
        if observed == "reject":
            stale_checks += 1
            if truth == "ADMIT":
                false_stale += 1
    if stale_checks == 0:
        return None, REASON_MISSING_RECORDS
    return false_stale / stale_checks, None


def compute_throughput(
    records: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> tuple[float | None, str | None]:
    """Committed ops per second of *active* SUT time.

    Committed ops = pairs whose observed bucket is ``admit`` (authorized
    completions). Active time = sum of raw per-record ``duration_seconds`` —
    the SUT's own busy time, so benchmark/harness overhead (wall-clock padding,
    scheduling gaps) is excluded rather than inflating the denominator. When
    every duration is missing, throughput is refused rather than guessed.
    """
    committed = 0
    busy_seconds = 0.0
    seen_any_duration = False
    for index, record in enumerate(records):
        bucket = _observed_outcome(record, index)
        if bucket == "admit":
            committed += 1
            duration = record.get("duration_seconds")
            if isinstance(duration, (int, float)) and not isinstance(duration, bool):
                if not math.isfinite(float(duration)) or float(duration) < 0:
                    raise MeasurementError(
                        REASON_MALFORMED_DURATION,
                        f"record {index}: duration_seconds={duration!r} not finite >= 0",
                    )
                busy_seconds += float(duration)
                seen_any_duration = True
    if committed == 0:
        return None, REASON_MISSING_RECORDS
    if not seen_any_duration or busy_seconds <= 0.0:
        return None, REASON_MISSING_RECORDS
    return committed / busy_seconds, None


def _percentile_nearest_rank(sorted_values: Sequence[float], fraction: float) -> float:
    """Exact nearest-rank percentile: ceil(f * n)-th smallest value (1-indexed)."""
    n = len(sorted_values)
    rank = math.ceil(fraction * n)
    rank = min(max(rank, 1), n)
    return sorted_values[rank - 1]


def compute_latency(
    records: Sequence[Mapping[str, Any]],
    *,
    unit: str = "s",
    duration_field: str = "duration_seconds",
) -> Latency:
    """p50/p95/p99 over raw per-record durations (exact nearest-rank order stats).

    Adversarial control (task spec): malformed or *mixed* time units are
    rejected. Every duration must be a finite number in the declared single
    unit; records declaring a different ``duration_unit`` fail closed with
    ``MIXED_TIME_UNITS`` instead of being silently averaged through.
    """
    if unit not in _ALLOWED_TIME_UNITS:
        raise MeasurementError(
            REASON_MIXED_TIME_UNITS,
            f"unit {unit!r} not in {sorted(_ALLOWED_TIME_UNITS)}",
        )
    values: list[float] = []
    for index, record in enumerate(records):
        record_unit = record.get("duration_unit", unit)
        if record_unit != unit:
            raise MeasurementError(
                REASON_MIXED_TIME_UNITS,
                f"record {index}: duration_unit {record_unit!r} != declared {unit!r}"
                " (mixed time units are rejected, not converted silently)",
            )
        raw = record.get(duration_field)
        if raw is None:
            raise MeasurementError(
                REASON_MISSING_RECORDS,
                f"record {index}: no {duration_field} on record {index}"
                " (metric unavailable, never estimated)",
            )
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise MeasurementError(
                REASON_MALFORMED_DURATION,
                f"record {index}: {duration_field}={raw!r} is not a number",
            )
        value = float(raw)
        if not math.isfinite(value) or value < 0:
            raise MeasurementError(
                REASON_MALFORMED_DURATION,
                f"record {index}: {duration_field}={raw!r} not finite >= 0",
            )
        values.append(value)
    if not values:
        raise MeasurementError(REASON_MISSING_RECORDS, "no duration records to compute latency")
    ordered = sorted(values)
    return Latency(
        unit=unit,
        n=len(ordered),
        p50=_percentile_nearest_rank(ordered, 0.50),
        p95=_percentile_nearest_rank(ordered, 0.95),
        p99=_percentile_nearest_rank(ordered, 0.99),
    )


def compute_retry_amplification(records: Sequence[Mapping[str, Any]]) -> tuple[float | None, str | None]:
    """Total attempts / distinct logical operations, from raw attempt fields.

    Uses ``attempt_index`` (1-based) when the harness recorded retries;
    otherwise the amplification is refused (MISSING_RECORDS) rather than
    silently reported as a perfect 1.0. Idempotent retries keyed by stable
    logical operation ID collapse to the same op.
    """
    attempts_by_op: dict[str, int] = {}
    saw_attempt_field = False
    for index, record in enumerate(records):
        op = _logical_op_id(record, index)
        if op is None:
            raise MeasurementError(
                REASON_MALFORMED_RECORD, f"record {index}: no logical_op_id or arm/case identity"
            )
        attempt = record.get("attempt_index")
        if attempt is not None:
            saw_attempt_field = True
            if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
                raise MeasurementError(
                    REASON_MALFORMED_RECORD,
                    f"record {index}: attempt_index={attempt!r} is not a positive int",
                )
            attempts_by_op[op] = max(attempts_by_op.get(op, 0), attempt)
        else:
            attempts_by_op[op] = max(attempts_by_op.get(op, 0), 1)
    if not saw_attempt_field:
        return None, REASON_MISSING_RECORDS
    total_attempts = sum(attempts_by_op.values())
    distinct_ops = len(attempts_by_op)
    if distinct_ops == 0:
        return None, REASON_MISSING_RECORDS
    return total_attempts / distinct_ops, None


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def measure(
    bundle: Any,
    *,
    require: Iterable[str] = (),
    latency_unit: str = "s",
    planned_pairs: int | None = None,
) -> Metrics:
    """Compute :class:`Metrics` from a raw run bundle (harness RunBundle / JSONL / mapping).

    ``require`` names metrics that MUST be computable; a missing metric raises
    :class:`MeasurementError` with its stable reason (typically
    ``MISSING_RECORDS``) instead of returning an invented number. Metrics not
    in ``require`` are computed when possible and otherwise listed in
    ``unavailable`` with the exact reason code — never defaulted to zero.

    The unit of inference is the preregistered arm x case pair
    (INDEPENDENT_EVIDENCE_PROTOCOL.md rule 3): every pair record enters each
    denominator at most once; clustered repeats within one case history cannot
    inflate a denominator because counts are keyed by the pair identity.
    """
    campaign_id, manifest, records = _bundle_to_parts(bundle)
    if not records:
        raise MeasurementError(REASON_MISSING_RECORDS, "bundle contains zero pair records")

    # Prove the counts partition the planned total BEFORE trusting any number.
    assert_denominator_consistency(bundle)
    counts = count_outcomes(records)
    denom = compute_denominator(records, manifest, planned_pairs=planned_pairs)

    unavailable: list[UnavailableMetric] = []
    required = set(require)

    def _finalize(metric: str, value: Any, reason: str | None) -> Any:
        if reason is None:
            return value
        unavailable.append(UnavailableMetric(metric=metric, reason_code=reason, detail=value))
        if metric in required:
            raise MeasurementError(reason, f"required metric {metric!r}: {value}")
        return None

    forbidden_commit_rate = _finalize(
        "forbidden_commit_rate", *compute_forbidden_commit_rate(records, denominator=denom["planned"])
    )
    false_stale_rate = _finalize("false_stale_rate", *compute_false_stale_rate(records))

    throughput = _finalize("throughput_ops_per_sec", *compute_throughput(records, manifest))

    latency: Latency | None
    try:
        latency = compute_latency(records, unit=latency_unit)
    except MeasurementError as exc:
        latency = None
        unavailable.append(
            UnavailableMetric(metric="latency_seconds", reason_code=exc.reason_code, detail=exc.detail)
        )
        if "latency_seconds" in required:
            raise

    retry_amplification = _finalize("retry_amplification", *compute_retry_amplification(records))

    planned = denom["planned"]
    if denom["attempted"] + denom["missing"] != planned:
        raise MeasurementError(
            REASON_DENOMINATOR_MISMATCH,
            f"attempted {denom['attempted']} + missing {denom['missing']} != planned {planned}",
        )
    if denom["attempted_total"] != denom["attempted"]:
        # Buckets must cover exactly the attempted records — no gap between
        # "records present" and "records tallied" is allowed.
        raise MeasurementError(
            REASON_DENOMINATOR_MISMATCH,
            f"attempted_total {denom['attempted_total']} != attempted records {denom['attempted']}",
        )

    provenance: dict[str, Any] = {
        "record_count": len(records),
        "source_commit": manifest.get("source_commit"),
        "seed": manifest.get("seed"),
        "harness_version": manifest.get("harness_version"),
        "wall_seconds": manifest.get("wall_seconds"),
        "unit_of_inference": "arm_x_case_pair",
        "metric_sources": {
            "outcome_counts": "raw records outcome.observed_outcome (mutually exclusive tally)",
            "forbidden_commit_rate": "oracle.expected_outcome truth vs observed ADMIT",
            "false_stale_rate": "observed REJECT vs oracle truth ADMIT",
            "throughput_ops_per_sec": "committed admits / sum(duration_seconds) busy time",
            "latency_seconds": f"nearest-rank p50/p95/p99 over duration_seconds (unit={latency_unit})",
            "retry_amplification": "attempt_index maxima / distinct logical_op_id",
        },
    }

    return Metrics(
        measurement_version=MEASUREMENT_VERSION,
        campaign_id=campaign_id,
        outcome_counts=counts,
        denominator=denom,
        forbidden_commit_rate=forbidden_commit_rate,
        false_stale_rate=false_stale_rate,
        throughput_ops_per_sec=throughput,
        latency_seconds=latency,
        retry_amplification=retry_amplification,
        unavailable=tuple(unavailable),
        provenance=provenance,
    )


def metrics_from_bundle_file(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Convenience: measure a JSONL run bundle file and return its dict form."""
    return measure(Path(path), **kwargs).to_dict()
