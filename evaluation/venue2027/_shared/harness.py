"""CLARA-Care 2027 shared task SH-run_harness — deterministic multi-arm execution harness.

Purpose
-------
Execute a *preregistered* campaign (frozen case set, arm set, seed set, source
commit) across injected arm adapters and record EVERY planned arm x case pair
in raw JSONL, including failures, timeouts and indeterminate outcomes. Nothing
is ever silently dropped: an arm adapter that raises is recorded as
``EXECUTION_ERROR`` with the exception class; an adapter that exceeds its
per-pair budget is recorded as ``TIMEOUT``; an adapter that returns a
non-outcome is recorded as ``INVALID_RESULT`` (all first-class outcomes that
can never be tallied as success per
``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rule 4).

Execution is resumable and idempotent: the harness persists one JSONL line per
completed pair into a journal file. Re-running the same campaign against the
same journal executes only the missing pairs (never duplicates), because the
logical operation ID ``<arm_id>::<case_id>`` is stable. The final
:class:`RunBundle` aggregates mutually exclusive outcome counts and refuses
seed drift between arms (``SEED_DRIFT``) so no arm can silently run under a
different randomization.

Allowed input
-------------
- A :class:`Campaign` preregistration: ``campaign_id``, ``case_ids``,
  ``arm_ids``, ``seeds``, ``source_commit`` (all frozen before execution).
- Arm adapters: callables ``run(case, ctx) -> Outcome`` (or plain ``dict``
  matching ``outcome.v1``). Adapters must be injected; the harness performs no
  hidden provider/network/model calls. ``ctx`` carries the case id, the
  frozen per-arm seed, ``source_commit`` and the adapter's deadline.
- An oracle: injected callable ``adjudicate(case_id, arm_id, observed,
  detail) -> dict`` returning the independent oracle verdict (at minimum an
  ``expected_outcome``). The harness never derives expectations itself.

Failure semantics
-----------------
Fail closed with stable reason codes:
- ``SEED_DRIFT`` — seeds are not identical across all arms.
- ``EMPTY_SCOPE`` / ``DUPLICATE_ID`` / ``MISSING_ARM`` / ``UNKNOWN_ARM`` /
  ``MISSING_CASE`` — preregistration is incomplete or inconsistent.
- ``ORACLE_NOT_CALLABLE`` / ``ARM_NOT_CALLABLE`` — wiring errors.
- ``JOURNAL_CORRUPT`` — journal line is not valid JSON of a known record kind.
- ``JOURNAL_SOURCE_MISMATCH`` — journal was written by a different campaign or
  source commit (never resumed across a moving code SHA).

No exception from an arm adapter ever escapes as an uncounted crash; every
exception becomes a recorded outcome row. Only harness-level configuration
errors raise.

Version
-------
``HARNESS_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import platform
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

HARNESS_VERSION = "1.0.0"

#: Observed outcome buckets; mutually exclusive per
#: GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4.
OUTCOME_BUCKETS: tuple[str, ...] = (
    "ADMIT",
    "REJECT",
    "INDETERMINATE",
    "TIMEOUT",
    "EXECUTION_ERROR",
    "NOT_RUN_EXTERNAL",
    "INVALID_RESULT",
)

#: Outcomes that may carry counted_as_success=True (false-zero ban).
COUNTABLE_OUTCOMES: frozenset[str] = frozenset({"ADMIT", "REJECT"})

#: Outcomes produced by the harness itself when the adapter misbehaves.
HARNESS_SYNTHETIC_OUTCOMES: frozenset[str] = frozenset(
    {"TIMEOUT", "EXECUTION_ERROR", "INVALID_RESULT", "NOT_RUN_EXTERNAL"}
)

RECORD_KIND_PAIR = "pair_result"
RECORD_KIND_MANIFEST = "run_manifest"


class HarnessError(ValueError):
    """Stable, machine-readable harness configuration/wiring failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class Campaign:
    """Preregistered campaign: frozen before any arm executes."""

    campaign_id: str
    case_ids: tuple[str, ...]
    arm_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    source_commit: str
    per_pair_timeout_seconds: float = 60.0

    def validate(self) -> None:
        if not self.campaign_id:
            raise HarnessError("EMPTY_SCOPE", "campaign_id must be non-empty")
        if not self.case_ids:
            raise HarnessError("EMPTY_SCOPE", "at least one case_id is required")
        if not self.arm_ids:
            raise HarnessError("EMPTY_SCOPE", "at least one arm_id is required")
        if len(set(self.case_ids)) != len(self.case_ids):
            raise HarnessError("DUPLICATE_ID", "case_ids must be unique")
        if len(set(self.arm_ids)) != len(self.arm_ids):
            raise HarnessError("DUPLICATE_ID", "arm_ids must be unique")
        if len(self.seeds) != len(self.arm_ids):
            raise HarnessError(
                "SEED_DRIFT",
                f"seeds count {len(self.seeds)} != arm count {len(self.arm_ids)}",
            )
        if len(set(self.seeds)) != 1:
            # Rule 4/7: every arm of a paired comparison runs under the same
            # frozen seed; any drift is refused before execution starts.
            raise HarnessError(
                "SEED_DRIFT", f"seeds differ across arms: {sorted(set(self.seeds))}"
            )
        if len(self.source_commit) != 40 or any(c not in "0123456789abcdef" for c in self.source_commit):
            raise HarnessError("MISSING_SOURCE_SHA", "source_commit must be a 40-hex git SHA")
        if self.per_pair_timeout_seconds <= 0:
            raise HarnessError(
                "INVALID_TIMEOUT", "per_pair_timeout_seconds must be positive"
            )

    @property
    def seed(self) -> int:
        return self.seeds[0]

    @property
    def planned_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple((arm_id, case_id) for arm_id in self.arm_ids for case_id in self.case_ids)


@dataclasses.dataclass(frozen=True)
class RunContext:
    """Injected per-pair execution context handed to arm adapters."""

    campaign_id: str
    case_id: str
    arm_id: str
    seed: int
    source_commit: str
    deadline_seconds: float


@dataclasses.dataclass(frozen=True)
class Outcome:
    """Observed outcome of one arm x case pair (JSON-serializable view via to_dict)."""

    observed_outcome: str
    counted_as_success: bool = False
    retriable: bool = False
    detail: str = ""

    def __post_init__(self) -> None:
        if self.observed_outcome not in OUTCOME_BUCKETS:
            raise HarnessError(
                "OBSERVED_OUTCOME_UNKNOWN",
                f"observed_outcome {self.observed_outcome!r} not in {OUTCOME_BUCKETS}",
            )
        if self.observed_outcome in HARNESS_SYNTHETIC_OUTCOMES and self.counted_as_success:
            raise HarnessError(
                "FALSE_ZERO_OUTCOME",
                f"observed_outcome {self.observed_outcome!r} can never be counted as success",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_outcome": self.observed_outcome,
            "counted_as_success": self.counted_as_success,
            "retriable": self.retriable,
            "detail": self.detail,
        }


ArmAdapter = Callable[[Mapping[str, Any], RunContext], "Outcome | dict[str, Any] | str"]
Oracle = Callable[[str, str, str, str], Mapping[str, Any]]


@dataclasses.dataclass
class RunBundle:
    """Aggregated, JSON-serializable result of one campaign execution."""

    campaign_id: str
    source_commit: str
    seed: int
    python_version: str
    harness_version: str
    records: list[dict[str, Any]]
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "source_commit": self.source_commit,
            "seed": self.seed,
            "python_version": self.python_version,
            "harness_version": self.harness_version,
            "manifest": self.manifest,
            "pair_count": len(self.records),
            "records": self.records,
        }

    def to_jsonl(self) -> str:
        lines = [r for r in self.records]
        lines.append(self.manifest)
        return "\n".join(
            json.dumps(line, sort_keys=True, separators=(",", ":")) for line in lines
        ) + "\n"

    def outcome_counts(self) -> dict[str, int]:
        counts = {bucket.lower(): 0 for bucket in OUTCOME_BUCKETS}
        for record in self.records:
            counts[record["outcome"]["observed_outcome"].lower()] += 1
        return counts


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _coerce_outcome(value: Outcome | dict[str, Any] | str, arm_id: str, case_id: str) -> Outcome:
    """Normalize adapter return values into an :class:`Outcome` (fail closed)."""
    if isinstance(value, Outcome):
        return value
    if isinstance(value, str):
        return Outcome(observed_outcome=value, detail="adapter returned bare outcome string")
    if isinstance(value, Mapping):
        observed = value.get("observed_outcome")
        if not isinstance(observed, str):
            raise HarnessError(
                "INVALID_RESULT", f"adapter dict for {arm_id}/{case_id} lacks observed_outcome"
            )
        counted = value.get("counted_as_success", False)
        return Outcome(
            observed_outcome=observed,
            counted_as_success=bool(counted) if isinstance(counted, bool) else False,
            retriable=bool(value.get("retriable", False)),
            detail=str(value.get("detail", "")),
        )
    raise HarnessError(
        "INVALID_RESULT",
        f"adapter for {arm_id}/{case_id} returned unsupported type {type(value).__name__}",
    )


def _load_journal(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Read the resumable journal: logical op id -> recorded pair result."""
    completed: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.is_file():
        return completed
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HarnessError("JOURNAL_CORRUPT", f"line {line_no}: {exc}") from exc
        if not isinstance(record, dict):
            raise HarnessError("JOURNAL_CORRUPT", f"line {line_no}: record is not an object")
        kind = record.get("record_kind")
        if kind == RECORD_KIND_MANIFEST:
            continue
        if kind != RECORD_KIND_PAIR:
            raise HarnessError(
                "JOURNAL_CORRUPT", f"line {line_no}: unknown record_kind {kind!r}"
            )
        key = (str(record.get("arm_id")), str(record.get("case_id")))
        if key in completed:
            raise HarnessError(
                "JOURNAL_CORRUPT", f"line {line_no}: duplicate pair {key[0]}/{key[1]}"
            )
        completed[key] = record
    return completed


def _check_journal_binding(
    journal: Mapping[tuple[str, str], dict[str, Any]],
    campaign: Campaign,
) -> None:
    """Refuse to resume a journal written by a different campaign/source."""
    for record in journal.values():
        if record.get("campaign_id") != campaign.campaign_id:
            raise HarnessError(
                "JOURNAL_SOURCE_MISMATCH",
                f"journal record campaign_id={record.get('campaign_id')!r}"
                f" != campaign {campaign.campaign_id!r}",
            )
        if record.get("source_commit") != campaign.source_commit:
            raise HarnessError(
                "JOURNAL_SOURCE_MISMATCH",
                f"journal record source_commit={record.get('source_commit')!r}"
                f" != campaign {campaign.source_commit!r}",
            )


def _pair_digest(record: Mapping[str, Any]) -> str:
    payload = json.dumps(
        {
            "campaign_id": record["campaign_id"],
            "arm_id": record["arm_id"],
            "case_id": record["case_id"],
            "seed": record["seed"],
            "source_commit": record["source_commit"],
            "outcome": record["outcome"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_text(payload)


def _execute_pair(
    campaign: Campaign,
    arm_run: ArmAdapter,
    oracle: Oracle,
    arm_id: str,
    case_id: str,
) -> dict[str, Any]:
    """Run one planned pair with per-pair timeout; never drop, never raise for adapter faults."""
    case: dict[str, Any] = {
        "case_id": case_id,
        "campaign_id": campaign.campaign_id,
        "source_commit": campaign.source_commit,
    }
    ctx = RunContext(
        campaign_id=campaign.campaign_id,
        case_id=case_id,
        arm_id=arm_id,
        seed=campaign.seed,
        source_commit=campaign.source_commit,
        deadline_seconds=campaign.per_pair_timeout_seconds,
    )
    started = time.monotonic()
    try:
        raw = arm_run(case, ctx)
    except TimeoutError:
        duration = time.monotonic() - started
        observed = Outcome(
            observed_outcome="TIMEOUT",
            retriable=True,
            detail="adapter raised TimeoutError",
        )
    except Exception as exc:  # noqa: BLE001 - adapter faults become recorded outcomes
        duration = time.monotonic() - started
        observed = Outcome(
            observed_outcome="EXECUTION_ERROR",
            detail=f"{type(exc).__name__}",
        )
    else:
        duration = time.monotonic() - started
        if duration > campaign.per_pair_timeout_seconds:
            observed = Outcome(
                observed_outcome="TIMEOUT",
                retriable=True,
                detail=f"exceeded per_pair_timeout_seconds={campaign.per_pair_timeout_seconds}",
            )
        else:
            try:
                observed = _coerce_outcome(raw, arm_id, case_id)
            except HarnessError as exc:
                if exc.reason_code != "INVALID_RESULT":
                    raise
                observed = Outcome(observed_outcome="INVALID_RESULT", detail=exc.detail)
    verdict: dict[str, Any]
    try:
        verdict = dict(
            oracle(
                case_id,
                arm_id,
                observed.observed_outcome,
                observed.detail,
            )
        )
    except Exception as exc:  # oracle faults are also recorded, never dropped
        verdict = {
            "oracle_error": type(exc).__name__,
            "oracle_detail": str(exc)[:200],
        }
    record: dict[str, Any] = {
        "record_kind": RECORD_KIND_PAIR,
        "logical_op_id": f"{campaign.campaign_id}:{arm_id}::{case_id}",
        "campaign_id": campaign.campaign_id,
        "arm_id": arm_id,
        "case_id": case_id,
        "seed": campaign.seed,
        "source_commit": campaign.source_commit,
        "outcome": observed.to_dict(),
        "oracle": verdict,
        "duration_seconds": round(duration, 6),
        "recorded_at": time.time(),
        "python_version": platform.python_version(),
        "harness_version": HARNESS_VERSION,
    }
    record["pair_digest"] = _pair_digest(record)
    return record


def _build_manifest(
    campaign: Campaign,
    records: Sequence[Mapping[str, Any]],
    wall_seconds: float,
) -> dict[str, Any]:
    counts = {bucket.lower(): 0 for bucket in OUTCOME_BUCKETS}
    for record in records:
        counts[record["outcome"]["observed_outcome"].lower()] += 1
    attempted = len(records)
    planned = len(campaign.planned_pairs)
    manifest: dict[str, Any] = {
        "record_kind": RECORD_KIND_MANIFEST,
        "campaign_id": campaign.campaign_id,
        "source_commit": campaign.source_commit,
        "seed": campaign.seed,
        "python_version": platform.python_version(),
        "harness_version": HARNESS_VERSION,
        "arm_ids": list(campaign.arm_ids),
        "case_ids": list(campaign.case_ids),
        "planned_pairs": planned,
        "attempted_pairs": attempted,
        "missing_pairs": planned - attempted,
        "denominator": counts,
        "denominator_total": sum(counts.values()),
        "wall_seconds": round(wall_seconds, 6),
        "complete": attempted == planned,
    }
    manifest["manifest_digest"] = _sha256_text(
        json.dumps({k: v for k, v in manifest.items() if k != "manifest_digest"},
                   sort_keys=True, separators=(",", ":"))
    )
    return manifest


def execute(
    campaign: Campaign,
    arms: Mapping[str, ArmAdapter],
    oracle: Oracle,
    *,
    workers: int = 1,
    journal_path: str | Path | None = None,
) -> RunBundle:
    """Execute every planned arm x case pair exactly once (resumable, idempotent).

    - ``arms`` maps each preregistered ``arm_id`` to an injected adapter
      ``run(case, ctx)``; adapters run locally, no hidden provider calls.
    - ``oracle`` is the independent adjudicator; its verdict is recorded
      alongside (never replacing) the observed outcome.
    - ``workers`` bounds concurrency; ``workers=1`` is the deterministic
      reference. With ``workers>1`` pairs still execute in preregistration
      order per worker slice, and every pair is recorded exactly once.
    - ``journal_path`` enables resumable idempotent execution: already-completed
      pairs are loaded from the journal and only missing pairs run. Re-running
      a completed campaign performs zero adapter calls and yields identical
      records.
    """
    campaign.validate()
    if workers < 1:
        raise HarnessError("INVALID_WORKERS", "workers must be >= 1")

    missing_arms = [arm_id for arm_id in campaign.arm_ids if arm_id not in arms]
    if missing_arms:
        raise HarnessError("MISSING_ARM", f"arms missing adapters: {missing_arms}")
    unknown_arms = sorted(set(arms) - set(campaign.arm_ids))
    if unknown_arms:
        raise HarnessError("UNKNOWN_ARM", f"adapters not in preregistration: {unknown_arms}")
    for arm_id, adapter in arms.items():
        if not callable(adapter):
            raise HarnessError("ARM_NOT_CALLABLE", f"adapter for {arm_id} is not callable")
    if not callable(oracle):
        raise HarnessError("ORACLE_NOT_CALLABLE", "oracle must be callable")

    journal: dict[tuple[str, str], dict[str, Any]] = {}
    if journal_path is not None:
        journal = _load_journal(Path(journal_path))
        _check_journal_binding(journal, campaign)

    records: list[dict[str, Any]] = []
    resumed = 0
    executed = 0
    started = time.monotonic()
    planned = campaign.planned_pairs

    if workers == 1:
        for arm_id, case_id in planned:
            key = (arm_id, case_id)
            if key in journal:
                records.append(dict(journal[key]))
                resumed += 1
                continue
            record = _execute_pair(campaign, arms[arm_id], oracle, arm_id, case_id)
            records.append(record)
            executed += 1
            if journal_path is not None:
                _append_journal(Path(journal_path), record)
    else:
        # Deterministic worker slicing: pairs are partitioned by index so the
        # union of worker slices equals the preregistered plan with no overlap.
        slices: list[list[tuple[str, str]]] = [[] for _ in range(workers)]
        for index, pair in enumerate(planned):
            slices[index % workers].append(pair)
        for slice_pairs in slices:
            for arm_id, case_id in slice_pairs:
                key = (arm_id, case_id)
                if key in journal:
                    records.append(dict(journal[key]))
                    resumed += 1
                    continue
                record = _execute_pair(campaign, arms[arm_id], oracle, arm_id, case_id)
                records.append(record)
                executed += 1
                if journal_path is not None:
                    _append_journal(Path(journal_path), record)

    # Records are emitted in preregistration order regardless of execution path.
    by_key = {(r["arm_id"], r["case_id"]): r for r in records}
    ordered = [by_key[pair] for pair in planned if pair in by_key]
    wall = time.monotonic() - started
    manifest = _build_manifest(campaign, ordered, wall)
    manifest["resumed_pairs"] = resumed
    manifest["executed_pairs"] = executed
    manifest["journal_path"] = str(journal_path) if journal_path is not None else None

    return RunBundle(
        campaign_id=campaign.campaign_id,
        source_commit=campaign.source_commit,
        seed=campaign.seed,
        python_version=platform.python_version(),
        harness_version=HARNESS_VERSION,
        records=ordered,
        manifest=manifest,
    )


def _append_journal(path: Path, record: Mapping[str, Any]) -> None:
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def completed_pairs(path: str | Path) -> set[tuple[str, str]]:
    """Public helper: the set of (arm_id, case_id) already journaled at ``path``."""
    journal = _load_journal(Path(path))
    return set(journal)


def expected_pair_ids(campaign: Campaign) -> set[tuple[str, str]]:
    """Public helper: the preregistered (arm_id, case_id) plan of a campaign."""
    return set(campaign.planned_pairs)


def summarize_counts(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Mutually exclusive outcome counts over raw pair records."""
    counts = {bucket.lower(): 0 for bucket in OUTCOME_BUCKETS}
    for record in records:
        counts[record["outcome"]["observed_outcome"].lower()] += 1
    return counts
