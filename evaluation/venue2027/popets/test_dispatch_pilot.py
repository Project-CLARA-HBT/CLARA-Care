"""Focused v1 checks of the development IPC boundary, evidence seal and reference semantics."""

import json
from dataclasses import replace

import pytest

from evaluation.venue2027.popets.dispatch_fixture import History, Request, Source
from evaluation.venue2027.popets.dispatch_observer import reconcile
from evaluation.venue2027.popets.dispatch_pilot import collect, reduce, verify
from evaluation.venue2027.popets.dispatch_sender import WarmCache, recompute

A = "a" * 32
B = "b" * 32
HISTORY = History(
    "dev-control",
    "revoked_then_dispatch",
    "dev-tenant",
    (Source(0, "first", A, 10), Source(0, "second", B, None)),
    (
        Request("pre", 0, "first", 9, "prompt"),
        Request("at", 0, "first", 10, "retry"),
        Request("ok", 1, "second", 11, "retained"),
    ),
)
PRE = b"pre\t" + A.encode() + b"\n"
RETAINED = b"ok\t" + B.encode() + b"\n"


def test_forbidden_control_and_authorized_cancellation():
    # Receiver calibration: two whole forbidden attributes in one future frame.
    leak = b"at\t" + A.encode() * 2 + b"\n"
    _, stats = reconcile([HISTORY], PRE + leak, b"ok\n")
    assert stats["post_revocation_forbidden_bytes"] == 64
    assert stats["leaking_post_revocation_subjects"] == stats["post_revocation_subjects"] == 1
    assert stats["authorized_coverage"] == 0.5
    _, stats = reconcile([HISTORY], PRE + RETAINED, b"at\n")
    assert stats["post_revocation_forbidden_bytes"] == 0
    assert stats["authorized_coverage"] == 1


@pytest.mark.parametrize(
    ("data", "journal", "reason"),
    [
        (PRE + RETAINED, b"", "UNRECONCILED_SCHEDULE"),
        (PRE + RETAINED, b"at\nat\n", "UNRECONCILED_SCHEDULE"),
        (PRE + RETAINED, b"at\nok\n", "UNRECONCILED_SCHEDULE"),
        (PRE + RETAINED, b"at\nunknown\n", "UNRECONCILED_SCHEDULE"),
        (RETAINED + PRE, b"at\n", "UNRECONCILED_SCHEDULE"),
        (PRE + PRE + RETAINED, b"at\n", "INVALID_DELIVERY"),
        (PRE + RETAINED[:-1], b"at\n", "TRUNCATED_FRAME"),
        (PRE + b"ok\tb\n", b"at\n", "UNCLASSIFIABLE_BYTES"),
    ],
)
def test_incomplete_capture_invalidates_measurement(data, journal, reason):
    with pytest.raises(ValueError, match=reason):
        reconcile([HISTORY], data, journal)


def test_reference_reprojects_live_source_and_candidate_serves_cached_copy():
    pre, at, ok = HISTORY.requests
    cache = WarmCache(HISTORY)
    assert recompute(HISTORY, pre) == cache.read(pre) == A
    assert recompute(HISTORY, at) is cache.read(at) is None
    assert recompute(HISTORY, ok) == cache.read(ok) == B
    updated = replace(HISTORY, sources=(HISTORY.sources[0], replace(HISTORY.sources[1], value=A)))
    assert recompute(updated, ok) == A
    assert recompute(HISTORY, replace(ok, purpose="first")) is None


def test_isolated_paired_capture_and_replay(tmp_path):
    directory = tmp_path / "paired"
    collect(directory)
    verify(directory)
    report = reduce(directory)
    assert report["paired_rq1_histories"] == 3
    assert report["visits"] == 37
    for arm in ("B2", "B4"):
        stats = report["arms"][arm]
        assert stats["received"] > 0 and stats["cancelled"] > 0
        assert stats["received"] + stats["cancelled"] == stats["scheduled"]
        assert stats["exact_projections"] == stats["scheduled"]
        assert stats["delivered_authorized_bytes"] == stats["requested_authorized_bytes"] > 0
        assert stats["post_revocation_forbidden_bytes"] == 0
    with pytest.raises(FileExistsError):
        collect(directory)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    assert "B4.cancel" in manifest["sha256"]
    (directory / "B4.cancel").write_bytes(b"")
    with pytest.raises(ValueError, match="ARCHIVE_HASH_MISMATCH"):
        verify(directory)
