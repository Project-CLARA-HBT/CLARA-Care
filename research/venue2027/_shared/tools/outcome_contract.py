"""CLARA-Care 2027 shared task SH-outcome_contract — outcome contract validator.

Purpose
-------
Program-level per-unit outcome contract (shared by all nine venue studies).
One record per (independent unit, arm) carries an INDEPENDENT
``expected_outcome`` (frozen oracle expectation) and an INDEPENDENT
``observed_outcome`` (what the arm actually did, decided from persisted
state/evidence) so an expectation can never be collapsed into an observation
(``GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rules 4 and 8,
``GATES/SCIENTIFIC_METRICS_CONTRACT.md`` item 6).

Failure semantics
-----------------
Fail closed. :func:`validate_outcome` returns False (with stable reason codes
from the shared stdlib JSON Schema validator) for any record that is not a
valid ``outcome.v1`` document — including the schema-encoded false-zero ban:
``observed_outcome`` in {INDETERMINATE, NOT_RUN_EXTERNAL, EXECUTION_ERROR,
TIMEOUT} with ``counted_as_success=true`` is rejected by the schema's oneOf
constraint pair itself. :func:`assert_no_false_zero` additionally refuses any
record set in which a NOT_RUN/INDETERMINATE/TIMEOUT/EXECUTION_ERROR outcome is
counted as success OR serialized as a numeric zero outcome (a numeric outcome
is legal only for counted ADMIT/REJECT results), so an incomplete or externally
blocked execution can never silently shrink a denominator.

Allowed input
-------------
A JSON-compatible outcome record (``dict``) or record set (``list``/``tuple``),
each matching ``research/venue2027/_shared/schemas/outcome.v1.schema.json``.

Version
-------
``OUTCOME_CONTRACT_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

OUTCOME_CONTRACT_VERSION = "1.0.0"

#: Observed outcome values that must never be tallied as success or serialized
#: as a numeric zero outcome.
NEVER_SUCCESS_OUTCOMES: frozenset[str] = frozenset(
    {"INDETERMINATE", "NOT_RUN_EXTERNAL", "EXECUTION_ERROR", "TIMEOUT"}
)

#: Outcomes that may legitimately carry counted_as_success=True.
COUNTABLE_OUTCOMES: frozenset[str] = frozenset({"ADMIT", "REJECT"})

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "outcome.v1.schema.json"


class FalseZeroOutcomeError(ValueError):
    """A NOT_RUN/INDETERMINATE/TIMEOUT/EXECUTION_ERROR outcome was presented as success/zero."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


def _load_schema() -> dict[str, Any]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import schema_validator as sv

    return sv.load_schema(SCHEMA_PATH)


def outcome_errors(record: dict[str, Any]) -> tuple[str, ...]:
    """Stable reason codes for ``record`` against ``outcome.v1``; empty iff valid.

    Raises only for a malformed schema (never for a bad instance — fail closed
    on the instance side means a False return, not an exception).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import schema_validator as sv

    return sv.validate_instance(record, _load_schema(), schema_path=SCHEMA_PATH)


def validate_outcome(outcome: dict[str, Any]) -> bool:
    """Task-contract signature ``validate_outcome(outcome) -> bool``.

    True iff ``outcome`` is a valid ``outcome.v1`` record: independent
    ``expected_outcome`` and ``observed_outcome`` fields both present, retriable
    flag present, at least one observation evidence pointer, and
    ``counted_as_success`` consistent with the observed outcome (the schema's
    oneOf pair rejects INDETERMINATE / NOT_RUN_EXTERNAL / EXECUTION_ERROR /
    TIMEOUT counted as success).
    """
    if not isinstance(outcome, dict):
        return False
    return not outcome_errors(outcome)


def _false_zero_reasons(record: Any, index: int | None = None) -> list[str]:
    where = f"record[{index}]" if index is not None else "record"
    reasons: list[str] = []
    if not isinstance(record, dict):
        return [f"{where}: not an object"]
    observed = record.get("observed_outcome")
    counted = record.get("counted_as_success")
    retriable = record.get("retriable")
    if observed in NEVER_SUCCESS_OUTCOMES:
        if counted is True:
            reasons.append(
                f"{where}: FALSE_ZERO_COUNTED_AS_SUCCESS observed={observed!r}"
                f" counted_as_success=true"
            )
        elif counted is not False:
            reasons.append(
                f"{where}: FALSE_ZERO_COUNT_UNSET observed={observed!r} counted_as_success missing"
            )
        if "numeric_outcome" in record and record["numeric_outcome"] == 0:
            reasons.append(
                f"{where}: FALSE_ZERO_NUMERIC outcome={observed!r} serialized as numeric 0"
            )
    elif observed in COUNTABLE_OUTCOMES:
        if "numeric_outcome" in record and not isinstance(record["numeric_outcome"], int | float):
            reasons.append(f"{where}: NUMERIC_OUTCOME_NOT_NUMERIC")
    else:
        reasons.append(f"{where}: OBSERVED_OUTCOME_UNKNOWN {observed!r}")
    if observed in {"NOT_RUN_EXTERNAL", "TIMEOUT"} and retriable is not True:
        reasons.append(
            f"{where}: RETRIABLE_FLAG_REQUIRED observed={observed!r} must declare retriable=true"
            f" (bounded predeclared retry) or reclassify the outcome"
        )
    return reasons


def assert_no_false_zero(records: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> None:
    """Refuse any false zero in a record set; raise :class:`FalseZeroOutcomeError`.

    Refused (never silently accepted, never invented as 0):
    - NOT_RUN_EXTERNAL / INDETERMINATE / EXECUTION_ERROR / TIMEOUT with
      ``counted_as_success=true`` or an unset count flag;
    - any of those outcomes serialized as a numeric zero outcome
      (``numeric_outcome == 0``);
    - NOT_RUN_EXTERNAL / TIMEOUT without an explicit retriable flag.

    Valid outcome.v1 records pass silently; malformed records raise with the
    schema reason codes embedded.
    """
    if not isinstance(records, list | tuple):
        raise FalseZeroOutcomeError(
            "FALSE_ZERO_CONTAINER", f"expected a list of records, got {type(records).__name__}"
        )
    reasons: list[str] = []
    for index, record in enumerate(records):
        reasons.extend(_false_zero_reasons(record, index))
        if isinstance(record, dict) and not validate_outcome(record):
            reasons.append(f"record[{index}]: SCHEMA_INVALID ({', '.join(outcome_errors(record))})")
    if reasons:
        raise FalseZeroOutcomeError("FALSE_ZERO_OUTCOME", "; ".join(reasons))


def outcome_denominator(
    records: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[str, int]:
    """Mutually exclusive per-arm outcome counts (no invented zeros for real events).

    Every observed record lands in exactly one bucket; buckets with zero
    members are reported as 0 explicitly (an explicit 0 is an honest count, an
    invented 0 for an unrecorded event is not).
    """
    counts: dict[str, int] = {
        "admit": 0,
        "reject": 0,
        "indeterminate": 0,
        "not_run_external": 0,
        "execution_error": 0,
        "timeout": 0,
    }
    for record in records:
        if not isinstance(record, dict):
            raise FalseZeroOutcomeError(
                "FALSE_ZERO_CONTAINER", "denominator input must be outcome records"
            )
        observed = record.get("observed_outcome")
        if observed == "ADMIT":
            counts["admit"] += 1
        elif observed == "REJECT":
            counts["reject"] += 1
        elif observed in NEVER_SUCCESS_OUTCOMES:
            counts[observed.lower()] += 1
        else:
            raise FalseZeroOutcomeError(
                "OBSERVED_OUTCOME_UNKNOWN",
                f"observed_outcome {observed!r} has no denominator bucket",
            )
    counts["success"] = counts["admit"] if _success_is_admit(records) else counts["reject"]
    return counts


def _success_is_admit(records: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> bool:
    counted = [r for r in records if isinstance(r, dict) and r.get("counted_as_success") is True]
    if not counted:
        return True
    return counted[0].get("observed_outcome") == "ADMIT"


def _load_records(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise FalseZeroOutcomeError("FALSE_ZERO_CONTAINER", f"{path}: expected a JSON array")
    return data


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 outcome contract validator")
    parser.add_argument("path", help="JSON array of outcome.v1 records")
    args = parser.parse_args(argv)
    try:
        records = _load_records(args.path)
        assert_no_false_zero(records)
    except FalseZeroOutcomeError as exc:
        print(json.dumps({"ok": False, "reason_code": exc.reason_code, "detail": exc.detail}))
        return 1
    bad = [i for i, r in enumerate(records) if not validate_outcome(r)]
    print(
        json.dumps(
            {
                "ok": not bad,
                "record_count": len(records),
                "invalid_record_indices": bad,
                "denominator": outcome_denominator(records),
                "version": OUTCOME_CONTRACT_VERSION,
            }
        )
    )
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
