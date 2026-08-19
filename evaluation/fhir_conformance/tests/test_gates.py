"""Gate and freeze tests for the FHIR conformance package."""

from __future__ import annotations

import json

import pytest

from evaluation.fhir_conformance import app_semantic, validator_wrapper
from evaluation.fhir_conformance.freeze import PACKAGE_DIR, build_manifest
from evaluation.fhir_conformance.run import _run_gate
from evaluation.fhir_conformance.validator_wrapper import sha256_file

GOLDEN = PACKAGE_DIR / "fixtures/positive/r4/lifemap-summary-r4.json"
DUPLICATE = PACKAGE_DIR / "fixtures/negative/duplicate-replay.json"


def test_manifest_covers_every_fixture_on_disk() -> None:
    manifest = build_manifest()
    on_disk = sorted(
        str(path.relative_to(PACKAGE_DIR))
        for path in (PACKAGE_DIR / "fixtures").rglob("*.json")
        if path.name != "manifest.json"
    )
    declared = [f["path"] for f in manifest["fixtures"]]
    assert on_disk == declared


def test_duplicate_replay_is_byte_identical_to_golden() -> None:
    assert sha256_file(GOLDEN) == sha256_file(DUPLICATE)


def test_pin_matches_toolchain_lock() -> None:
    pin = validator_wrapper.load_pin()
    assert pin.version == "6.9.12"
    assert pin.sha256 == ("0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6")


@pytest.mark.parametrize("fixture", build_manifest()["fixtures"])
def test_app_gates_match_declared_expected(fixture: dict) -> None:
    bundle = json.loads((PACKAGE_DIR / fixture["path"]).read_text(encoding="utf-8"))
    for gate in fixture["gates"]:
        if not gate.startswith(("api_", "bench_")):
            continue
        result = _run_gate(gate, bundle)
        assert result.available, f"{fixture['id']} {gate}: oracle unavailable"
        expected = fixture["expected"][gate]["accepted"]
        assert result.accepted is expected, (
            f"{fixture['id']} {gate}: expected accepted={expected} "
            f"got accepted={result.accepted} errors={result.errors}"
        )


def test_wrapper_reports_pending_when_jar_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(validator_wrapper, "resolve_jar", lambda *a, **k: None)
    monkeypatch.setattr(validator_wrapper, "java_available", lambda: False)
    record = validator_wrapper.validate_file(GOLDEN, "r4", allow_download=False)
    assert record["execution"] == "PENDING"
    assert record["structural"] == "not_executed"
    assert record["payload_sha256"] == sha256_file(GOLDEN)


def test_unsupported_version_mode_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported mode"):
        validator_wrapper.validate_file(GOLDEN, "r5")


def test_sha256_of_fixtures_is_stable() -> None:
    manifest = build_manifest()
    for fixture in manifest["fixtures"]:
        assert fixture["sha256"] == sha256_file(PACKAGE_DIR / fixture["path"])


def test_snapshot_input_has_no_fhir_gates() -> None:
    manifest = build_manifest()
    snapshot = next(f for f in manifest["fixtures"] if f["id"] == "snapshot_input")
    assert snapshot["gates"] == []
    assert snapshot["mode"] == "n/a"


def test_invalid_temporal_is_app_gap_not_rejection() -> None:
    bundle = json.loads(
        (PACKAGE_DIR / "fixtures/negative/invalid-temporal.json").read_text(encoding="utf-8")
    )
    result = app_semantic.api_r4_gate(bundle)
    assert result.accepted is True
    assert result.errors == []


def test_validator_severity_matches_pinned_cli_output() -> None:
    invalid = validator_wrapper._summarize(
        "Observation.effective: Error - Not a valid date/time format\n"
        "Patient: Warning - Best Practice Recommendation"
    )
    assert invalid == {"fatal": 0, "error": 1, "warning": 1, "info": 0, "hint": 0}
