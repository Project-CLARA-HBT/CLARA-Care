"""DSN-X03_fault_windows — deterministic fault-injection controller.

Purpose
-------
Enumerates the named crash cut points across a commit lifecycle for the DSN
2027 study "Recoverable Safety Journals for Crash-Consistent AI-Mediated
Health-State Mutations" (RQ1; CASE_MATRIX DSN-CASE-02..04 adversarial
controls). A *fault window* is a named synchronization barrier between two
durable pipeline stages. Injection works by arming a barrier on a
:class:`LifecycleRun` recorder: when the lifecycle under test attempts to
cross the armed barrier, :class:`CrashInjected` is raised at that exact
point — a named synchronization barrier, never a sleep-based causal guess,
never a random cut.

Canonical commit lifecycle (mapped onto the CASE_MATRIX / state_machine
channels; the manifest barriers "SQL flush, commit ACK, outbox enqueue,
broker publish, consumer ack" sit at these stages):

- ``INTENT``          — governed write intent received (pre-flush).
- ``WAL_WRITE``       — WAL record written (after SQL flush).
- ``APPLY``           — change applied/committed to durable storage (commit ACK).
- ``PERSIST_RECEIPT`` — versioned decision receipt + outbox record persisted
                        (outbox enqueue; one atomic transaction).
- ``OUTBOX_DELIVER``  — partial-effect delivery receipt recorded (broker
                        publish / consumer ack).

The five enumerated windows (crash fires immediately *before* the anchor
stage executes, so the anchor stage never happens):

- ``BEFORE_WAL``                 — anchor ``WAL_WRITE``; nothing durable
                                   anywhere (DSN-CASE-02 atomicity).
- ``AFTER_WAL_BEFORE_APPLY``     — anchor ``APPLY``; WAL record written, not
                                   applied (torn visibility; unapplied WAL is
                                   not a committed mutation).
- ``AFTER_APPLY_BEFORE_RECEIPT`` — anchor ``PERSIST_RECEIPT``; row applied,
                                   ledger receipt missing (DSN-CASE-03
                                   unknown-response reconciliation).
- ``AFTER_RECEIPT``              — anchor ``OUTBOX_DELIVER``; row + receipt
                                   durable, delivery pending (DSN-CASE-03/07).
- ``DOUBLE_FAULT``               — two crashes in one lifecycle: first crash
                                   at the earliest reachable single-window
                                   barrier, recovery/restart recorded, second
                                   crash at the same barrier; the second
                                   :class:`CrashInjected` (``crash_number=2``)
                                   propagates to the caller (repeated
                                   kill/restart adversarial control).

Allowed input
-------------
:func:`enumerate_fault_windows` takes an ordered sequence of canonical stage
names (a lifecycle map). :func:`run_with_window` takes a window (name or
:class:`FaultWindow`), the callable under test ``fn(run, *args, **kwargs)``
and optionally the explicit ``lifecycle`` the callable is expected to
execute. All inputs are JSON-serializable dataclasses/strings; no I/O, no
hidden clock, no randomness, no provider calls.

Failure semantics
-----------------
Every failure raises a :class:`FaultWindowError` subclass carrying a stable
``reason_code``: ``UNKNOWN_STAGE``, ``DUPLICATE_STAGE``,
``DUPLICATE_WINDOW``, ``WINDOW_CATALOG_MISMATCH``, ``WINDOW_NOT_REACHABLE``,
``UNORDERED_LIFECYCLE``, ``DOUBLE_FAULT_UNREACHABLE``,
``EMPTY_LIFECYCLE``, ``LIFECYCLE_REQUIRED``, ``MALFORMED_CRASH_RECORD``.
A window whose anchor barrier cannot occur on the given lifecycle is
*refused* (:class:`WindowNotReachableError`) — never silently skipped and
never replaced by a partial enumeration. A crash, once fired inside an
attempt, is sticky: the attempt cannot record further stages or swallow the
crash (a SIGKILLed process cannot continue). :func:`run_with_window` never
returns normally: it either injects (raising :class:`CrashInjected` carrying
the run transcript) or refuses with a stable reason code. Enumeration is a
pure function of the lifecycle: identical inputs always yield an equal,
deduplicated window list in canonical order.

Version
-------
``FAULT_WINDOWS_VERSION = "clara.dsn.fault-windows-v1"`` (additive-only
evolution within v1; the window catalog is version-pinned for the oracle).
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import json
from collections.abc import Callable, Sequence
from typing import Any, Final, NoReturn

FAULT_WINDOWS_VERSION: Final[str] = "clara.dsn.fault-windows-v1"

REASON_UNKNOWN_STAGE: Final[str] = "UNKNOWN_STAGE"
REASON_DUPLICATE_STAGE: Final[str] = "DUPLICATE_STAGE"
REASON_DUPLICATE_WINDOW: Final[str] = "DUPLICATE_WINDOW"
REASON_WINDOW_CATALOG_MISMATCH: Final[str] = "WINDOW_CATALOG_MISMATCH"
REASON_WINDOW_NOT_REACHABLE: Final[str] = "WINDOW_NOT_REACHABLE"
REASON_UNORDERED_LIFECYCLE: Final[str] = "UNORDERED_LIFECYCLE"
REASON_DOUBLE_FAULT_UNREACHABLE: Final[str] = "DOUBLE_FAULT_UNREACHABLE"
REASON_EMPTY_LIFECYCLE: Final[str] = "EMPTY_LIFECYCLE"
REASON_LIFECYCLE_REQUIRED: Final[str] = "LIFECYCLE_REQUIRED"
REASON_MALFORMED_CRASH_RECORD: Final[str] = "MALFORMED_CRASH_RECORD"

REASON_CODES: Final[tuple[str, ...]] = (
    REASON_UNKNOWN_STAGE,
    REASON_DUPLICATE_STAGE,
    REASON_DUPLICATE_WINDOW,
    REASON_WINDOW_CATALOG_MISMATCH,
    REASON_WINDOW_NOT_REACHABLE,
    REASON_UNORDERED_LIFECYCLE,
    REASON_DOUBLE_FAULT_UNREACHABLE,
    REASON_EMPTY_LIFECYCLE,
    REASON_LIFECYCLE_REQUIRED,
    REASON_MALFORMED_CRASH_RECORD,
)

STAGE_INTENT: Final[str] = "INTENT"
STAGE_WAL: Final[str] = "WAL_WRITE"
STAGE_APPLY: Final[str] = "APPLY"
STAGE_RECEIPT: Final[str] = "PERSIST_RECEIPT"
STAGE_DELIVER: Final[str] = "OUTBOX_DELIVER"

CANONICAL_LIFECYCLE: Final[tuple[str, ...]] = (
    STAGE_INTENT,
    STAGE_WAL,
    STAGE_APPLY,
    STAGE_RECEIPT,
    STAGE_DELIVER,
)


class WindowName(enum.StrEnum):
    """Named crash windows across the commit lifecycle (canonical order)."""

    BEFORE_WAL = "BEFORE_WAL"
    AFTER_WAL_BEFORE_APPLY = "AFTER_WAL_BEFORE_APPLY"
    AFTER_APPLY_BEFORE_RECEIPT = "AFTER_APPLY_BEFORE_RECEIPT"
    AFTER_RECEIPT = "AFTER_RECEIPT"
    DOUBLE_FAULT = "DOUBLE_FAULT"


SINGLE_WINDOW_NAMES: Final[tuple[str, ...]] = (
    WindowName.BEFORE_WAL,
    WindowName.AFTER_WAL_BEFORE_APPLY,
    WindowName.AFTER_APPLY_BEFORE_RECEIPT,
    WindowName.AFTER_RECEIPT,
)

WINDOW_ORDER: Final[tuple[str, ...]] = SINGLE_WINDOW_NAMES + (WindowName.DOUBLE_FAULT,)

# Anchor barrier of each single-crash window: the crash fires immediately
# before this stage executes, so the anchor stage never happens in that run.
WINDOW_ANCHOR: Final[dict[str, str]] = {
    WindowName.BEFORE_WAL: STAGE_WAL,
    WindowName.AFTER_WAL_BEFORE_APPLY: STAGE_APPLY,
    WindowName.AFTER_APPLY_BEFORE_RECEIPT: STAGE_RECEIPT,
    WindowName.AFTER_RECEIPT: STAGE_DELIVER,
}


class FaultWindowError(Exception):
    """Base class: every failure carries a stable ``reason_code``."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


class UnknownStageError(FaultWindowError):
    def __init__(self, stage: str) -> None:
        super().__init__(
            REASON_UNKNOWN_STAGE,
            f"stage {stage!r} is not part of the canonical lifecycle "
            f"{list(CANONICAL_LIFECYCLE)}",
        )
        self.stage = stage


class DuplicateStageError(FaultWindowError):
    def __init__(self, stage: str) -> None:
        super().__init__(REASON_DUPLICATE_STAGE, f"stage {stage!r} appears more than once")
        self.stage = stage


class DuplicateWindowError(FaultWindowError):
    def __init__(self, message: str) -> None:
        super().__init__(REASON_DUPLICATE_WINDOW, message)


class WindowCatalogError(FaultWindowError):
    def __init__(self, message: str) -> None:
        super().__init__(REASON_WINDOW_CATALOG_MISMATCH, message)


class WindowNotReachableError(FaultWindowError):
    """A window cannot occur on the given lifecycle/execution: refused."""

    def __init__(self, window: str, anchor: str, *, static: bool = False) -> None:
        if static:
            message = (
                f"window {window!r} cannot be reached: its anchor barrier {anchor!r} "
                "is absent from the lifecycle (refused, not silently skipped)"
            )
        else:
            message = (
                f"window {window!r} was not injected: the lifecycle completed without "
                f"reaching its anchor barrier {anchor!r} (refused, not silently skipped)"
            )
        super().__init__(REASON_WINDOW_NOT_REACHABLE, message)
        self.window = window
        self.anchor = anchor
        self.static = static


class UnorderedLifecycleError(FaultWindowError):
    def __init__(self, ops: Sequence[str], first_bad_index: int) -> None:
        super().__init__(
            REASON_UNORDERED_LIFECYCLE,
            f"lifecycle {list(ops)} violates canonical stage order "
            f"{list(CANONICAL_LIFECYCLE)} at index {first_bad_index}",
        )
        self.first_bad_index = first_bad_index


class DoubleFaultUnreachableError(FaultWindowError):
    def __init__(self, message: str = "") -> None:
        super().__init__(
            REASON_DOUBLE_FAULT_UNREACHABLE,
            message
            or "DOUBLE_FAULT requires at least one single-crash barrier reachable on "
            "the lifecycle; none is",
        )


class EmptyLifecycleError(FaultWindowError):
    def __init__(self) -> None:
        super().__init__(REASON_EMPTY_LIFECYCLE, "lifecycle has no stages")


class LifecycleRequiredError(FaultWindowError):
    def __init__(self) -> None:
        super().__init__(
            REASON_LIFECYCLE_REQUIRED,
            "DOUBLE_FAULT requires an explicit lifecycle to locate the earliest "
            "reachable barrier deterministically",
        )


@dataclasses.dataclass(frozen=True)
class FaultWindow:
    """One named crash cut point (JSON-serializable, deterministic)."""

    name: str
    anchor_stage: str
    description: str
    case_matrix_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "anchor_stage": self.anchor_stage,
            "description": self.description,
            "case_matrix_ref": self.case_matrix_ref,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FaultWindow:
        try:
            window = cls(
                name=payload["name"],
                anchor_stage=payload["anchor_stage"],
                description=payload["description"],
                case_matrix_ref=payload["case_matrix_ref"],
            )
        except (KeyError, TypeError) as exc:
            raise FaultWindowError(
                REASON_WINDOW_CATALOG_MISMATCH, f"malformed FaultWindow payload: {exc}"
            ) from exc
        if window.name not in WINDOW_ORDER:
            raise UnknownStageError(window.name)
        return window


_SINGLE_WINDOW_CATALOG: Final[dict[str, FaultWindow]] = {
    WindowName.BEFORE_WAL: FaultWindow(
        name=WindowName.BEFORE_WAL,
        anchor_stage=STAGE_WAL,
        description=(
            "Crash before the WAL record is written: no durable evidence in any "
            "channel; recovery re-runs the operation under the same immutable ID."
        ),
        case_matrix_ref="DSN-CASE-02",
    ),
    WindowName.AFTER_WAL_BEFORE_APPLY: FaultWindow(
        name=WindowName.AFTER_WAL_BEFORE_APPLY,
        anchor_stage=STAGE_APPLY,
        description=(
            "Crash after the WAL record is written but before the change is applied "
            "to durable storage: an unapplied WAL record is not a committed mutation."
        ),
        case_matrix_ref="DSN-CASE-02",
    ),
    WindowName.AFTER_APPLY_BEFORE_RECEIPT: FaultWindow(
        name=WindowName.AFTER_APPLY_BEFORE_RECEIPT,
        anchor_stage=STAGE_RECEIPT,
        description=(
            "Crash after the row is applied but before the versioned decision "
            "receipt is persisted: unknown-response reconciliation cut."
        ),
        case_matrix_ref="DSN-CASE-03",
    ),
    WindowName.AFTER_RECEIPT: FaultWindow(
        name=WindowName.AFTER_RECEIPT,
        anchor_stage=STAGE_DELIVER,
        description=(
            "Crash after the decision receipt is durable but before the outbox "
            "delivery receipt is recorded: pending-delivery cut."
        ),
        case_matrix_ref="DSN-CASE-03",
    ),
}


def double_fault_window(anchor_stage: str) -> FaultWindow:
    """Build the compound two-crash window for a concrete anchor barrier."""

    if anchor_stage not in CANONICAL_LIFECYCLE:
        raise UnknownStageError(anchor_stage)
    return FaultWindow(
        name=WindowName.DOUBLE_FAULT,
        anchor_stage=anchor_stage,
        description=(
            "Two crashes in one lifecycle: the first crash fires at the earliest "
            f"reachable single-window barrier ({anchor_stage}), the run restarts "
            "deterministically and a second crash fires at the same barrier; the "
            "second CrashInjected (crash_number=2) is observed by the caller."
        ),
        case_matrix_ref="DSN-CASE-02",
    )


def _check_catalog_integrity() -> None:
    """Refuse a corrupted window catalog before enumerating from it."""

    if len(WINDOW_ORDER) != len(set(WINDOW_ORDER)):
        raise DuplicateWindowError(f"WINDOW_ORDER contains duplicates: {list(WINDOW_ORDER)}")
    if set(WINDOW_ORDER) != set(SINGLE_WINDOW_NAMES) | {WindowName.DOUBLE_FAULT}:
        raise WindowCatalogError(
            f"WINDOW_ORDER {list(WINDOW_ORDER)} does not match the single-window "
            f"catalog plus DOUBLE_FAULT: {list(SINGLE_WINDOW_NAMES)}"
        )
    if set(WINDOW_ANCHOR) != set(SINGLE_WINDOW_NAMES):
        raise WindowCatalogError(
            f"WINDOW_ANCHOR keys {sorted(WINDOW_ANCHOR)} do not match "
            f"SINGLE_WINDOW_NAMES {list(SINGLE_WINDOW_NAMES)}"
        )
    for name, anchor in WINDOW_ANCHOR.items():
        if anchor not in CANONICAL_LIFECYCLE:
            raise UnknownStageError(anchor)
        if name not in _SINGLE_WINDOW_CATALOG:
            raise WindowCatalogError(f"window {name!r} missing from the catalog")
        if _SINGLE_WINDOW_CATALOG[name].anchor_stage != anchor:
            raise WindowCatalogError(
                f"window {name!r} catalog anchor "
                f"{_SINGLE_WINDOW_CATALOG[name].anchor_stage!r} != barrier map {anchor!r}"
            )


def validate_lifecycle(ops: Sequence[str]) -> list[str]:
    """Validate a lifecycle map, returning it as a stage list.

    Raises (in order): :class:`EmptyLifecycleError`, :class:`UnknownStageError`,
    :class:`DuplicateStageError`, :class:`UnorderedLifecycleError`. Order is
    checked as a subsequence of :data:`CANONICAL_LIFECYCLE`: a lifecycle may
    skip stages (e.g. an arm without a receipt stage) but never reorder them.
    """

    ops_list = [str(stage) for stage in ops]
    if not ops_list:
        raise EmptyLifecycleError()
    seen: set[str] = set()
    for stage in ops_list:
        if stage not in CANONICAL_LIFECYCLE:
            raise UnknownStageError(stage)
        if stage in seen:
            raise DuplicateStageError(stage)
        seen.add(stage)
    canonical_index = {stage: i for i, stage in enumerate(CANONICAL_LIFECYCLE)}
    indices = [canonical_index[stage] for stage in ops_list]
    for i in range(1, len(indices)):
        if indices[i] < indices[i - 1]:
            raise UnorderedLifecycleError(ops_list, i)
    return ops_list


def _reachable_single_anchors(ops_list: Sequence[str]) -> list[str]:
    return [
        WINDOW_ANCHOR[name] for name in SINGLE_WINDOW_NAMES if WINDOW_ANCHOR[name] in set(ops_list)
    ]


def enumerate_fault_windows(ops: Sequence[str]) -> list[FaultWindow]:
    """Enumerate the named crash windows for one commit lifecycle map.

    Deterministic and total over valid inputs: returns exactly one entry per
    named window, in canonical :data:`WINDOW_ORDER`, with no duplicates. The
    ``DOUBLE_FAULT`` anchor is the earliest reachable single-window barrier.
    A window whose anchor barrier is absent from ``ops`` cannot physically
    occur there and is *refused* via :class:`WindowNotReachableError` rather
    than silently skipped — enumeration never under-reports reachable cut
    points, so callers can never mistake a missing window for a passed one.
    """

    _check_catalog_integrity()
    ops_list = validate_lifecycle(ops)
    reachable = _reachable_single_anchors(ops_list)
    if not reachable:
        raise DoubleFaultUnreachableError()
    windows: list[FaultWindow] = []
    for name in SINGLE_WINDOW_NAMES:
        anchor = WINDOW_ANCHOR[name]
        if anchor in set(ops_list):
            windows.append(_SINGLE_WINDOW_CATALOG[name])
        else:
            raise WindowNotReachableError(name, anchor, static=True)
    windows.append(double_fault_window(reachable[0]))
    return windows


def enumerate_windows(ops: Sequence[str]) -> list[FaultWindow]:
    """Manifest-name alias for :func:`enumerate_fault_windows` (same contract)."""

    return enumerate_fault_windows(ops)


@dataclasses.dataclass(frozen=True)
class _Arm:
    """Armed barrier: the window name plus the anchor stage that trips it."""

    window: str
    anchor: str


class CrashInjected(Exception):
    """Raised at the exact injected cut point; never swallowed internally.

    ``transcript`` carries the ordered lifecycle events observed up to and
    including the crash, so the caller can reconstruct the exact durable
    prefix (which stages completed, which never ran) without introspecting
    the candidate's internals.
    """

    def __init__(
        self,
        *,
        window: str,
        stage: str,
        crash_number: int,
        transcript: tuple[tuple[str, ...], ...] = (),
    ) -> None:
        if not isinstance(window, str) or not window:
            raise FaultWindowError(
                REASON_MALFORMED_CRASH_RECORD, "CrashInjected.window must be a non-empty str"
            )
        if not isinstance(stage, str) or not stage:
            raise FaultWindowError(
                REASON_MALFORMED_CRASH_RECORD, "CrashInjected.stage must be a non-empty str"
            )
        if not isinstance(crash_number, int) or isinstance(crash_number, bool) or crash_number < 1:
            raise FaultWindowError(
                REASON_MALFORMED_CRASH_RECORD, "CrashInjected.crash_number must be a positive int"
            )
        super().__init__(
            f"crash #{crash_number} injected at window {window} (barrier before {stage})"
        )
        self.window = window
        self.stage = stage
        self.crash_number = crash_number
        self.transcript = tuple(tuple(event) for event in transcript)

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "stage": self.stage,
            "crash_number": self.crash_number,
            "transcript": [list(event) for event in self.transcript],
        }


@dataclasses.dataclass
class LifecycleRun:
    """Ordered, deterministic transcript of one lifecycle execution.

    The recorder *is* the named synchronization barrier set: stages are
    recorded via :meth:`record_stage`, and a crash armed on this run fires
    inside that call at the exact barrier — never on a timer.
    """

    events: list[tuple[str, ...]] = dataclasses.field(default_factory=list)
    _arm: _Arm | None = None
    _crash_count: int = 0
    _attempt_seen: set[str] = dataclasses.field(default_factory=set)
    _crashed_this_attempt: bool = False
    _sticky: CrashInjected | None = None

    def arm(self, window: str, anchor: str) -> None:
        if window not in WINDOW_ORDER:
            raise WindowNotReachableError(str(window), anchor, static=True)
        if anchor not in CANONICAL_LIFECYCLE:
            raise UnknownStageError(anchor)
        self._arm = _Arm(window=window, anchor=anchor)

    def begin_attempt(self) -> None:
        """Start one process attempt (restarts reset per-attempt barriers)."""

        self._attempt_seen = set()
        self._crashed_this_attempt = False
        self._sticky = None

    def record_stage(self, stage: str) -> int:
        """Cross the barrier before ``stage``; returns the stage ordinal.

        If the armed window anchors on ``stage``, the crash fires here and
        the stage is never recorded (it did not happen). Once a crash has
        fired in the current attempt it is sticky: every further
        :meth:`record_stage` re-raises it, because a SIGKILLed attempt cannot
        record anything else.
        """

        if stage not in CANONICAL_LIFECYCLE:
            raise UnknownStageError(stage)
        if self._sticky is not None:
            raise self._sticky
        if stage in self._attempt_seen:
            raise DuplicateStageError(stage)
        arm = self._arm
        if arm is not None and stage == arm.anchor:
            self._crashed_this_attempt = True
            self._crash_count += 1
            self.events.append(("crash", arm.window, stage, self._crash_count))
            injected = CrashInjected(
                window=arm.window,
                stage=stage,
                crash_number=self._crash_count,
                transcript=tuple(self.events),
            )
            self._sticky = injected
            raise injected
        self._attempt_seen.add(stage)
        ordinal = sum(1 for event in self.events if event[0] == "stage" and event[1] == stage) + 1
        self.events.append(("stage", stage, ordinal))
        return ordinal

    def record_recovery(self, stage: str) -> None:
        """Record a recovery/restart after a caught crash (double-fault only)."""

        self.events.append(("recovery", stage))

    def stage_events(self) -> list[str]:
        return [event[1] for event in self.events if event[0] == "stage"]

    def crash_events(self) -> list[tuple[str, str, int]]:
        return [(event[1], event[2], event[3]) for event in self.events if event[0] == "crash"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [list(event) for event in self.events],
            "crashes": [
                {"window": event[1], "stage": event[2], "crash_number": event[3]}
                for event in self.events
                if event[0] == "crash"
            ],
        }


def _resolve_window(window: FaultWindow | str) -> str:
    if isinstance(window, FaultWindow):
        return str(window.name)
    if isinstance(window, WindowName):
        return window.value
    if isinstance(window, str):
        return window
    raise WindowNotReachableError(str(window), "<unknown>", static=True)


def _arm_for(window_name: str, lifecycle: Sequence[str] | None) -> _Arm:
    """Compute the armed barrier for ``window_name`` (static refusal here)."""

    if window_name == WindowName.DOUBLE_FAULT:
        if lifecycle is None:
            raise LifecycleRequiredError()
        ops_list = validate_lifecycle(lifecycle)
        reachable = _reachable_single_anchors(ops_list)
        if not reachable:
            raise DoubleFaultUnreachableError()
        return _Arm(window=window_name, anchor=reachable[0])
    if window_name not in WINDOW_ANCHOR:
        raise WindowNotReachableError(window_name, "<not-a-window>", static=True)
    anchor = WINDOW_ANCHOR[window_name]
    if lifecycle is not None:
        ops_list = validate_lifecycle(lifecycle)
        if anchor not in set(ops_list):
            raise WindowNotReachableError(window_name, anchor, static=True)
    return _Arm(window=window_name, anchor=anchor)


def run_with_window(
    window: FaultWindow | str,
    fn: Callable[..., Any],
    *args: Any,
    lifecycle: Sequence[str] | None = None,
    **kwargs: Any,
) -> NoReturn:
    """Run ``fn`` under one fault window; inject the crash at the exact point.

    ``fn(run, *args, **kwargs)`` receives the :class:`LifecycleRun` recorder
    and must cross its stage barriers through ``run.record_stage(...)``.
    When the armed anchor barrier is crossed, :class:`CrashInjected` is
    raised inside that call — the exact named cut point — and the anchor
    stage is never recorded. The crash is sticky for the attempt.

    ``DOUBLE_FAULT`` requires the explicit ``lifecycle``: the first crash at
    the earliest reachable single-window barrier is caught by the harness
    (recorded as recovery/restart), ``fn`` re-executes deterministically and
    the second :class:`CrashInjected` (``crash_number=2``) propagates to the
    caller — modeling repeated kill/restart.

    Refusal contract: if the lifecycle completes without reaching the armed
    barrier, or the window cannot exist on the given lifecycle, a
    :class:`FaultWindowError` with a stable ``reason_code`` is raised — the
    window is never silently skipped. This function therefore never returns
    normally: it injects, or it refuses.
    """

    window_name = _resolve_window(window)
    arm = _arm_for(window_name, lifecycle)
    run = LifecycleRun()
    run.arm(arm.window, arm.anchor)
    if window_name == WindowName.DOUBLE_FAULT:
        run.begin_attempt()
        try:
            fn(run, *args, **kwargs)
        except CrashInjected as first:
            if first.window != window_name or first.crash_number != 1:
                raise
            run.record_recovery(first.stage)
            run.begin_attempt()
            fn(run, *args, **kwargs)
        raise WindowNotReachableError(window_name, arm.anchor)
    run.begin_attempt()
    fn(run, *args, **kwargs)
    raise WindowNotReachableError(window_name, arm.anchor)


def demo_transcript() -> dict[str, Any]:
    """Deterministic self-check: inject every window on the full lifecycle.

    Returns the canonical enumeration plus one transcript per window — a
    worked example, not a research result.
    """

    full_lifecycle = list(CANONICAL_LIFECYCLE)
    windows = enumerate_fault_windows(full_lifecycle)

    def lifecycle(run: LifecycleRun) -> str:
        run.record_stage(STAGE_INTENT)
        run.record_stage(STAGE_WAL)
        run.record_stage(STAGE_APPLY)
        run.record_stage(STAGE_RECEIPT)
        run.record_stage(STAGE_DELIVER)
        return "committed"

    transcripts: dict[str, Any] = {}
    for window in windows:
        try:
            run_with_window(window, lifecycle, lifecycle=full_lifecycle)
            transcripts[window.name]: dict[str, Any] = {"injected": False}
        except CrashInjected as injected:
            transcripts[window.name] = {
                "injected": True,
                "crash": injected.to_dict(),
            }
    return {
        "version": FAULT_WINDOWS_VERSION,
        "lifecycle": full_lifecycle,
        "windows": [window.to_dict() for window in windows],
        "transcripts": transcripts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DSN-X03 fault window controller self-check")
    parser.add_argument("--json", action="store_true", help="emit the demo transcript as JSON")
    args = parser.parse_args(argv)
    payload = demo_transcript()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    for window in payload["windows"]:
        transcript = payload["transcripts"][window["name"]]
        crash = transcript.get("crash", {})
        print(
            f"{window['name']:28s} case={window['case_matrix_ref']:12s} "
            f"injected={transcript['injected']} barrier_before={crash.get('stage', '-')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
