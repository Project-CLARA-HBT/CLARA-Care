from __future__ import annotations

from datetime import UTC, datetime

from evaluation.commitloop.fixtures import DeterministicFakeTransport, synthetic_bundle
from evaluation.commitloop.provider import REVIEWER_MODEL, EvaluationClient, RunLimits
from evaluation.commitloop.run_local import run_local_e2e
from evaluation.commitloop.v5_reproduce import reproduce, verify_seal


def test_v5_zero_call_reproduction_is_byte_identical(tmp_path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "reproduced"
    limits = RunLimits(max_subjects=1, max_cases=1, max_requests=2)
    transport = DeterministicFakeTransport()
    client = EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-secret-not-real",
        transport=transport,
        limits=limits,
    )
    run_local_e2e(
        bundles=[(synthetic_bundle("v5-reproduce", "v5"), "R4")],
        output_dir=source,
        clients={REVIEWER_MODEL: client},
        valid_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
        known_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
        limits=limits,
        conditions=("full_authorized_history", "glhs_hybrid_thss_strict"),
        primary_model=REVIEWER_MODEL,
    )
    calls_before = transport.call_count
    report = reproduce(source, output)
    assert transport.call_count == calls_before
    assert report["status"] == "PASS"
    assert report["provider_calls"] == 0
    assert all(item["identical"] for item in report["derived_files"].values())
    verify_seal(output)
