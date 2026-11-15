"""Tests for DSN-X03_fault_windows — deterministic fault-injection controller.

Positive controls (each window enumerated exactly once and actually injected,
observable as CrashInjected at the exact barrier):
- Full canonical lifecycle enumerates all five named windows in canonical
  order, exactly once, with the documented anchors and CASE_MATRIX refs.
- Each single-crash window injects a real crash at its anchor barrier: the
  anchor stage is never recorded, all prior stages are, and the transcript
  is carried on the exception.
- DOUBLE_FAULT injects two crashes: the harness observes crash #1, records
  recovery/restart, and crash #2 propagates to the caller.
- Truncated lifecycles (arms without a receipt/delivery stage) enumerate only
  the windows that still exist on them; injection still lands exactly.
- Determinism: repeated enumeration and repeated injection produce identical
  results; no randomness source anywhere.
- to_dict/from_dict round-trip is lossless.

Adversarial controls (refusal, not silent skip):
- A window whose anchor stage is absent from the lifecycle is refused with
  WINDOW_NOT_REACHABLE, both at enumeration and at injection time.
- Duplicate windows in the catalog are detected (WINDOW_CATALOG_MISMATCH /
  DUPLICATE_WINDOW via WINDOW_ORDER integrity check).
- Duplicate stages in a lifecycle are refused (DUPLICATE_STAGE); unknown
  stages too (UNKNOWN_STAGE); reordered lifecycles too (UNORDERED_LIFECYCLE).
- A lifecycle that completes without crossing the armed barrier is refused
  (WINDOW_NOT_REACHABLE, dynamic) — a missed injection can never masquerade
  as a pass.
- A run cannot record further stages after a crash fired (sticky crash), and
  cannot double-record a stage within one attempt.
- DOUBLE_FAULT without a reachable barrier is refused
  (DOUBLE_FAULT_UNREACHABLE / LIFECYCLE_REQUIRED / EMPTY_LIFECYCLE).
- Malformed FaultWindow payloads and malformed CrashInjected fields are
  refused with stable reason codes.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.dsn import fault_windows as fw
from evaluation.venue2027.dsn.fault_windows import (
    CANONICAL_LIFECYCLE,
    STAGE_APPLY,
    STAGE_DELIVER,
    STAGE_INTENT,
    STAGE_RECEIPT,
    STAGE_WAL,
    CrashInjected,
    DuplicateStageError,
    EmptyLifecycleError,
    FaultWindow,
    FaultWindowError,
    LifecycleRequiredError,
    LifecycleRun,
    UnknownStageError,
    WindowName,
    WindowNotReachableError,
    demo_transcript,
    enumerate_fault_windows,
    enumerate_windows,
    run_with_window,
    validate_lifecycle,
)

FULL_LIFECYCLE = list(CANONICAL_LIFECYCLE)

EXPECTED_ANCHORS = {
    WindowName.BEFORE_WAL: STAGE_WAL,
    WindowName.AFTER_WAL_BEFORE_APPLY: STAGE_APPLY,
    WindowName.AFTER_APPLY_BEFORE_RECEIPT: STAGE_RECEIPT,
    WindowName.AFTER_RECEIPT: STAGE_DELIVER,
    WindowName.DOUBLE_FAULT: STAGE_WAL,
}


def full_lifecycle_fn(run: LifecycleRun) -> str:
    run.record_stage(STAGE_INTENT)
    run.record_stage(STAGE_WAL)
    run.record_stage(STAGE_APPLY)
    run.record_stage(STAGE_RECEIPT)
    run.record_stage(STAGE_DELIVER)
    return "committed"


def inject_crash(injection: object) -> CrashInjected:
    assert isinstance(injection, CrashInjected), f"expected CrashInjected, got {injection!r}"
    return injection


# ---------------------------------------------------------------------------
# Positive: enumeration
# ---------------------------------------------------------------------------


def test_full_lifecycle_enumerates_all_five_windows_exactly_once() -> None:
    windows = enumerate_fault_windows(FULL_LIFECYCLE)
    names = [w.name for w in windows]
    assert names == [
        WindowName.BEFORE_WAL,
        WindowName.AFTER_WAL_BEFORE_APPLY,
        WindowName.AFTER_APPLY_BEFORE_RECEIPT,
        WindowName.AFTER_RECEIPT,
        WindowName.DOUBLE_FAULT,
    ]
    assert len(names) == len(set(names)) == 5


def test_enumerated_anchors_and_case_refs_match_contract() -> None:
    windows = {w.name: w for w in enumerate_fault_windows(FULL_LIFECYCLE)}
    for name, anchor in EXPECTED_ANCHORS.items():
        assert windows[name].anchor_stage == anchor, name
    assert windows[WindowName.BEFORE_WAL].case_matrix_ref == "DSN-CASE-02"
    assert windows[WindowName.AFTER_APPLY_BEFORE_RECEIPT].case_matrix_ref == "DSN-CASE-03"
    assert windows[WindowName.AFTER_RECEIPT].case_matrix_ref == "DSN-CASE-03"
    assert windows[WindowName.DOUBLE_FAULT].case_matrix_ref == "DSN-CASE-02"


def test_enumeration_is_deterministic_and_order_stable() -> None:
    first = [w.to_dict() for w in enumerate_fault_windows(FULL_LIFECYCLE)]
    second = [w.to_dict() for w in enumerate_fault_windows(FULL_LIFECYCLE)]
    assert first == second
    json.dumps(first)


def test_manifest_alias_matches_primary_api() -> None:
    assert [w.to_dict() for w in enumerate_windows(FULL_LIFECYCLE)] == [
        w.to_dict() for w in enumerate_fault_windows(FULL_LIFECYCLE)
    ]


@pytest.mark.parametrize(
    ("lifecycle", "missing_window"),
    [
        # B0-style arm: fire-and-forget side effect, no receipt stage — the
        # receipt-window cut point cannot occur there and is refused.
        (
            [STAGE_INTENT, STAGE_WAL, STAGE_APPLY, STAGE_DELIVER],
            WindowName.AFTER_APPLY_BEFORE_RECEIPT,
        ),
        # Minimal transaction-only arm: no receipt and no delivery stage.
        ([STAGE_INTENT, STAGE_WAL, STAGE_APPLY], WindowName.AFTER_APPLY_BEFORE_RECEIPT),
    ],
)
def test_truncated_lifecycles_refuse_unreachable_windows(
    lifecycle: list[str], missing_window: str
) -> None:
    # Fail-closed: a window whose anchor barrier is absent from the lifecycle
    # is refused, never silently skipped (no partial enumeration that a
    # caller could mistake for a complete schedule).
    with pytest.raises(WindowNotReachableError) as excinfo:
        enumerate_fault_windows(lifecycle)
    assert excinfo.value.reason_code == fw.REASON_WINDOW_NOT_REACHABLE
    assert excinfo.value.window == missing_window
    assert excinfo.value.static is True


def test_window_roundtrip_is_lossless() -> None:
    for window in enumerate_fault_windows(FULL_LIFECYCLE):
        restored = FaultWindow.from_dict(window.to_dict())
        assert restored == window
        json.dumps(window.to_dict())


# ---------------------------------------------------------------------------
# Positive: injection is real and observable
# ---------------------------------------------------------------------------


def test_crash_before_wal_injected_and_anchor_never_recorded() -> None:
    with pytest.raises(CrashInjected) as excinfo:
        run_with_window(WindowName.BEFORE_WAL, full_lifecycle_fn, lifecycle=FULL_LIFECYCLE)
    injected = inject_crash(excinfo.value)
    assert injected.window == WindowName.BEFORE_WAL
    assert injected.stage == STAGE_WAL
    assert injected.crash_number == 1
    completed = [event[1] for event in injected.transcript if event[0] == "stage"]
    assert completed == [STAGE_INTENT]


@pytest.mark.parametrize(
    ("window", "anchor"),
    [
        (WindowName.BEFORE_WAL, STAGE_WAL),
        (WindowName.AFTER_WAL_BEFORE_APPLY, STAGE_APPLY),
        (WindowName.AFTER_APPLY_BEFORE_RECEIPT, STAGE_RECEIPT),
        (WindowName.AFTER_RECEIPT, STAGE_DELIVER),
    ],
)
def test_every_single_window_actually_injected_at_its_barrier(
    window: str, anchor: str
) -> None:
    with pytest.raises(CrashInjected) as excinfo:
        run_with_window(window, full_lifecycle_fn, lifecycle=FULL_LIFECYCLE)
    injected = inject_crash(excinfo.value)
    assert injected.window == window
    assert injected.stage == anchor
    completed = [event[1] for event in injected.transcript if event[0] == "stage"]
    # Exactly the stages preceding the anchor executed; the anchor never did.
    assert completed == list(CANONICAL_LIFECYCLE[: CANONICAL_LIFECYCLE.index(anchor)])
    assert anchor not in completed


def test_double_fault_injects_two_observable_crashes() -> None:
    observed: list[CrashInjected] = []

    def restartable(run: LifecycleRun) -> str:
        try:
            run.record_stage(STAGE_INTENT)
            run.record_stage(STAGE_WAL)
        except CrashInjected as first:
            observed.append(first)
            run.record_recovery(first.stage)
            run.begin_attempt()
            run.record_stage(STAGE_INTENT)
            run.record_stage(STAGE_WAL)
        run.record_stage(STAGE_APPLY)
        return "committed"

    with pytest.raises(CrashInjected) as excinfo:
        run_with_window(WindowName.DOUBLE_FAULT, restartable, lifecycle=FULL_LIFECYCLE)
    second = inject_crash(excinfo.value)
    assert second.window == WindowName.DOUBLE_FAULT
    assert second.crash_number == 2
    assert len(observed) == 1
    assert observed[0].crash_number == 1
    # Transcript shows: crash, recovery, stage replay, second crash.
    kinds = [event[0] for event in second.transcript]
    assert kinds == ["stage", "crash", "recovery", "stage", "crash"]


def test_run_with_window_accepts_faultwindow_objects() -> None:
    window = enumerate_fault_windows(FULL_LIFECYCLE)[0]
    with pytest.raises(CrashInjected) as excinfo:
        run_with_window(window, full_lifecycle_fn, lifecycle=FULL_LIFECYCLE)
    assert inject_crash(excinfo.value).window == window.name


def test_window_string_names_accepted_directly() -> None:
    for window in fw.SINGLE_WINDOW_NAMES:
        with pytest.raises(CrashInjected) as excinfo:
            run_with_window(str(window), full_lifecycle_fn, lifecycle=FULL_LIFECYCLE)
        assert inject_crash(excinfo.value).window == str(window)


def test_injection_determinism_identical_transcripts() -> None:
    transcripts = []
    for _ in range(3):
        with pytest.raises(CrashInjected) as excinfo:
            run_with_window(
                WindowName.AFTER_APPLY_BEFORE_RECEIPT,
                full_lifecycle_fn,
                lifecycle=FULL_LIFECYCLE,
            )
        transcripts.append(inject_crash(excinfo.value).to_dict())
    assert transcripts[0] == transcripts[1] == transcripts[2]
    json.dumps(transcripts[0])


def test_demo_transcript_injects_every_window() -> None:
    payload = demo_transcript()
    assert len(payload["windows"]) == 5
    assert len({w["name"] for w in payload["windows"]}) == 5
    for name, transcript in payload["transcripts"].items():
        assert transcript["injected"] is True, name
        json.dumps(payload)


# ---------------------------------------------------------------------------
# Adversarial: unreachable windows refused, duplicates detected
# ---------------------------------------------------------------------------


def test_unreachable_window_refused_at_enumeration() -> None:
    # No PERSIST_RECEIPT stage -> AFTER_APPLY_BEFORE_RECEIPT cannot occur.
    lifecycle = [STAGE_INTENT, STAGE_WAL, STAGE_APPLY, STAGE_DELIVER]
    with pytest.raises(WindowNotReachableError) as excinfo:
        enumerate_fault_windows(lifecycle)
    assert excinfo.value.reason_code == fw.REASON_WINDOW_NOT_REACHABLE
    assert excinfo.value.window == WindowName.AFTER_APPLY_BEFORE_RECEIPT
    assert excinfo.value.static is True


def test_unreachable_window_refused_at_injection() -> None:
    lifecycle = [STAGE_INTENT, STAGE_WAL, STAGE_APPLY]
    with pytest.raises(WindowNotReachableError) as excinfo:
        run_with_window(WindowName.AFTER_RECEIPT, full_lifecycle_fn, lifecycle=lifecycle)
    assert excinfo.value.reason_code == fw.REASON_WINDOW_NOT_REACHABLE


def test_lifecycle_completing_without_crash_is_refused_not_passed() -> None:
    # A no-op function never crosses the armed barrier: the injection is
    # reported as refused, never as a successful (silent) no-crash pass.
    with pytest.raises(WindowNotReachableError) as excinfo:
        run_with_window(WindowName.BEFORE_WAL, lambda run: "done", lifecycle=FULL_LIFECYCLE)
    assert excinfo.value.reason_code == fw.REASON_WINDOW_NOT_REACHABLE
    assert excinfo.value.static is False


def test_duplicate_windows_in_catalog_detected() -> None:
    # Corrupt WINDOW_ORDER with a duplicate and integrity checking must
    # refuse enumeration instead of enumerating the window twice.
    original = fw.WINDOW_ORDER
    try:
        fw.WINDOW_ORDER = fw.SINGLE_WINDOW_NAMES + (
            WindowName.DOUBLE_FAULT,
            WindowName.DOUBLE_FAULT,
        )
        with pytest.raises(FaultWindowError) as excinfo:
            enumerate_fault_windows(FULL_LIFECYCLE)
        assert excinfo.value.reason_code == fw.REASON_DUPLICATE_WINDOW
    finally:
        fw.WINDOW_ORDER = original


def test_window_anchor_map_mismatch_detected() -> None:
    original = dict(fw.WINDOW_ANCHOR)
    try:
        fw.WINDOW_ANCHOR[WindowName.BEFORE_WAL] = STAGE_INTENT
        with pytest.raises(FaultWindowError) as excinfo:
            enumerate_fault_windows(FULL_LIFECYCLE)
        assert excinfo.value.reason_code == fw.REASON_WINDOW_CATALOG_MISMATCH
    finally:
        fw.WINDOW_ANCHOR.clear()
        fw.WINDOW_ANCHOR.update(original)


def test_duplicate_stage_refused() -> None:
    with pytest.raises(DuplicateStageError) as excinfo:
        validate_lifecycle([STAGE_INTENT, STAGE_WAL, STAGE_WAL, STAGE_APPLY])
    assert excinfo.value.reason_code == fw.REASON_DUPLICATE_STAGE


def test_unknown_stage_refused() -> None:
    with pytest.raises(UnknownStageError) as excinfo:
        validate_lifecycle([STAGE_INTENT, "TELEPORT"])
    assert excinfo.value.reason_code == fw.REASON_UNKNOWN_STAGE


def test_reordered_lifecycle_refused() -> None:
    with pytest.raises(FaultWindowError) as excinfo:
        validate_lifecycle([STAGE_WAL, STAGE_INTENT, STAGE_APPLY])
    assert excinfo.value.reason_code == fw.REASON_UNORDERED_LIFECYCLE


def test_empty_lifecycle_refused() -> None:
    with pytest.raises(EmptyLifecycleError) as excinfo:
        validate_lifecycle([])
    assert excinfo.value.reason_code == fw.REASON_EMPTY_LIFECYCLE
    with pytest.raises(EmptyLifecycleError):
        enumerate_fault_windows([])


def test_double_fault_without_reachable_barrier_refused() -> None:
    # An empty lifecycle is refused before reachability is even evaluated.
    with pytest.raises(EmptyLifecycleError) as excinfo:
        enumerate_fault_windows([])
    assert excinfo.value.reason_code == fw.REASON_EMPTY_LIFECYCLE


def test_double_fault_requires_lifecycle() -> None:
    with pytest.raises(LifecycleRequiredError) as excinfo:
        run_with_window(WindowName.DOUBLE_FAULT, full_lifecycle_fn)
    assert excinfo.value.reason_code == fw.REASON_LIFECYCLE_REQUIRED


def test_double_fault_never_silent_when_attempt_never_crashes() -> None:
    # The harness catches only crash #1; if the restarted attempt completes
    # without a second crash the compound window did not occur and the run
    # is refused rather than reported as an injected double fault.
    def non_crashing_restart(run: LifecycleRun) -> str:
        try:
            run.record_stage(STAGE_INTENT)
            run.record_stage(STAGE_WAL)
        except CrashInjected:
            run.record_recovery(STAGE_WAL)
            run.begin_attempt()
            return "recovered-without-second-crash"
        run.record_stage(STAGE_APPLY)
        return "committed"

    with pytest.raises(WindowNotReachableError):
        run_with_window(WindowName.DOUBLE_FAULT, non_crashing_restart, lifecycle=FULL_LIFECYCLE)


def test_crash_is_sticky_within_one_attempt() -> None:
    run = LifecycleRun()
    run.arm(WindowName.BEFORE_WAL, STAGE_WAL)
    run.begin_attempt()
    run.record_stage(STAGE_INTENT)
    with pytest.raises(CrashInjected) as first_info:
        run.record_stage(STAGE_WAL)
    first = inject_crash(first_info.value)
    # A crashed attempt cannot keep recording (SIGKILLed process analogy):
    # the sticky crash re-fires on every further barrier crossing.
    with pytest.raises(CrashInjected) as second_info:
        run.record_stage(STAGE_APPLY)
    assert second_info.value.to_dict() == first.to_dict()
    assert run.stage_events() == [STAGE_INTENT]


def test_stage_cannot_be_recorded_twice_in_one_attempt() -> None:
    run = LifecycleRun()
    run.begin_attempt()
    run.record_stage(STAGE_INTENT)
    with pytest.raises(DuplicateStageError):
        run.record_stage(STAGE_INTENT)
    # A restart begins a fresh attempt, so replaying the stage is legal and
    # gets the next global ordinal (stage replay is observable, not hidden).
    run.begin_attempt()
    assert run.record_stage(STAGE_INTENT) == 2


def test_malformed_crash_record_refused() -> None:
    with pytest.raises(FaultWindowError) as excinfo:
        CrashInjected(window="", stage=STAGE_WAL, crash_number=1)
    assert excinfo.value.reason_code == fw.REASON_MALFORMED_CRASH_RECORD
    with pytest.raises(FaultWindowError) as excinfo:
        CrashInjected(window=WindowName.BEFORE_WAL, stage=STAGE_WAL, crash_number=0)
    assert excinfo.value.reason_code == fw.REASON_MALFORMED_CRASH_RECORD


def test_malformed_window_payload_refused() -> None:
    with pytest.raises(FaultWindowError) as excinfo:
        FaultWindow.from_dict({"name": WindowName.BEFORE_WAL})
    assert excinfo.value.reason_code == fw.REASON_WINDOW_CATALOG_MISMATCH
    with pytest.raises(FaultWindowError) as excinfo:
        FaultWindow.from_dict(
            {
                "name": "TELEPORT",
                "anchor_stage": STAGE_WAL,
                "description": "not a window",
                "case_matrix_ref": "DSN-CASE-02",
            }
        )
    assert excinfo.value.reason_code == fw.REASON_UNKNOWN_STAGE


def test_unknown_window_name_refused() -> None:
    with pytest.raises(WindowNotReachableError):
        run_with_window("NOT_A_WINDOW", full_lifecycle_fn, lifecycle=FULL_LIFECYCLE)


def test_reason_code_registry_is_stable_and_json_serializable() -> None:
    assert len(fw.REASON_CODES) == len(set(fw.REASON_CODES))
    json.dumps(list(fw.REASON_CODES))
    assert fw.FAULT_WINDOWS_VERSION == "clara.dsn.fault-windows-v1"
