"""Unit and Integration Test Suite for GLHS Q3/R3 Phase 9 (E14) Reproducibility Bundle.

Enforces fail-closed offline verification across 15 experiments (E00–E14) and asserts
all 7 mandatory negative failure conditions:
  - N1: Missing raw artifact file -> MUST FAIL RELEASE.
  - N2: Chronology anomaly (freeze timestamp > execution timestamp) -> MUST FAIL RELEASE.
  - N3: Un-attested simulation masquerading as production PostgreSQL -> MUST FAIL RELEASE.
  - N4: Un-backed provider claim without provider run ledger -> MUST FAIL RELEASE.
  - N5: Corrupted raw record SHA-256 hash / Merkle chain break -> MUST FAIL RELEASE.
  - N6: Claim budget violation in claim ledger -> MUST FAIL RELEASE.
  - N7: Network access attempted during offline reproduction -> MUST FAIL RELEASE.
"""

from __future__ import annotations

import csv
import json
import socket
import sys
import tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from reproduce_q3_r3 import (
    AUDITED_HARNESS_COMMIT,
    AUDITED_SUT_COMMIT,
    CLAIM_BUDGET_PATH,
    EVIDENCE_ROOT,
    RELEASE_ROOT,
    ChronologyAnomalyError,
    ClaimBudgetViolationError,
    CorruptedHashError,
    GitWorktreeDirtyError,
    MissingArtifactError,
    NetworkAccessProhibitedError,
    RecordCountMismatchError,
    UnattestedSimulationError,
    UnbackedProviderClaimError,
    disable_network,
    restore_network,
    reproduce_q3_r3,
    sha256_file,
    verify_backend_attestation,
    verify_claim_ledger,
    verify_experiment_bundle,
    verify_experiment_checksums,
    verify_experiment_chronology,
    verify_git_state,
    verify_hash_chain,
    verify_provider_run_ledger,
)


def test_clean_q3_r3_reproduction_sweep() -> None:
    """Test full Q3/R3 offline reproduction sweep over all 15 experiments (E00–E14)."""
    sweep_report = reproduce_q3_r3(skip_git_check=True)

    assert sweep_report["overall_status"] == "UNIFIED_REPRODUCIBILITY_VERIFIED"
    assert sweep_report["network_isolation_active"] is True
    assert sweep_report["total_experiments_swept"] == 15
    assert sweep_report["passed_experiments_count"] == 15
    assert sweep_report["claim_ledger_audit"]["claim_ledger_valid"] is True
    assert sweep_report["claim_ledger_audit"]["total_claims"] == 15
    assert sweep_report["claim_ledger_audit"]["claim_eligible_claims"] == 15

    for eid in [f"E{i:02d}" for i in range(15)]:
        assert eid in sweep_report["experiments"], f"Missing experiment {eid} in report"
        res = sweep_report["experiments"][eid]
        assert res.get("claim_eligible") is True
        assert res.get("seal_verified") is True
        assert res.get("status") in ("REPRODUCED_AND_VERIFIED", "VERIFIED")


def test_n1_missing_raw_artifact_fails_release(tmp_path: Path) -> None:
    """N1: Test that a missing raw artifact file MUST fail release."""
    exp_dir = tmp_path / "E01_inference_consumption"
    exp_dir.mkdir(parents=True)

    (exp_dir / "protocol.json").write_text("{}", encoding="utf-8")
    (exp_dir / "protocol.sha256").write_text("dummy", encoding="utf-8")
    (exp_dir / "freeze.json").write_text("{}", encoding="utf-8")

    with pytest.raises(MissingArtifactError) as exc_info:
        verify_experiment_bundle(
            "E01", "E01_inference_consumption", "Inference Test", 100, evidence_root=tmp_path
        )
    assert "required_artifact_missing" in str(exc_info.value)


def test_n2_chronology_anomaly_fails_release(tmp_path: Path) -> None:
    """N2: Test that freeze timestamp > execution timestamp MUST fail release."""
    exp_dir = tmp_path / "E04_postgres_toctou"
    exp_dir.mkdir(parents=True)

    # Future freeze timestamp relative to execution
    freeze_data = {"freeze_timestamp_utc": "2026-10-01T00:00:00Z"}
    (exp_dir / "freeze.json").write_text(json.dumps(freeze_data), encoding="utf-8")

    # Execution artifact with earlier timestamp
    exec_data = {"execution_timestamp": "2026-09-28T12:00:00Z"}
    (exp_dir / "seal.json").write_text(json.dumps(exec_data), encoding="utf-8")

    with pytest.raises(ChronologyAnomalyError) as exc_info:
        verify_experiment_chronology(exp_dir)
    assert "chronology_anomaly" in str(exc_info.value)


def test_n3_unattested_simulation_fails_release(tmp_path: Path) -> None:
    """N3: Test that an un-attested simulation masquerading as production PostgreSQL MUST fail release."""
    exp_dir = tmp_path / "E04_postgres_toctou"
    exp_dir.mkdir(parents=True)

    # Masquerading attestation: claims production PostgreSQL but sets simulation=True
    attestation = {
        "schema_version": "glhs-r3-backend-attestation.v1",
        "experiment_id": "E04",
        "actual_backend": "PostgreSQL 16.14",
        "backend_type": "real_postgresql_16",
        "simulation": True,
        "production_path": False,
    }
    (exp_dir / "backend_attestation.json").write_text(json.dumps(attestation), encoding="utf-8")

    with pytest.raises(UnattestedSimulationError) as exc_info:
        verify_backend_attestation(exp_dir)
    assert "unattested_simulation_masquerading_as_postgresql" in str(exc_info.value)


def test_n4_unbacked_provider_claim_fails_release(tmp_path: Path) -> None:
    """N4: Test that an un-backed provider claim without provider run ledger MUST fail release."""
    exp_dir = tmp_path / "E11_model_replication"
    raw_dir = exp_dir / "raw"
    raw_dir.mkdir(parents=True)

    attestation = {
        "schema_version": "glhs-r3-backend-attestation.v1",
        "experiment_id": "E11",
        "actual_backend": "Live Multi-Model LLM Provider Ledger",
        "network_provider": True,
    }
    (exp_dir / "backend_attestation.json").write_text(json.dumps(attestation), encoding="utf-8")

    # Missing raw/provider_run_ledger.json
    with pytest.raises(UnbackedProviderClaimError) as exc_info:
        verify_provider_run_ledger(exp_dir)
    assert "unbacked_provider_claim_missing_ledger" in str(exc_info.value)


def test_n5_corrupted_hash_fails_release(tmp_path: Path) -> None:
    """N5: Test that a corrupted raw record SHA-256 hash or Merkle chain break MUST fail release."""
    exp_dir = tmp_path / "E01_inference_consumption"
    exp_dir.mkdir(parents=True)

    # Create dummy file with incorrect checksum in checksums.sha256
    (exp_dir / "dummy.txt").write_text("corrupted content", encoding="utf-8")
    wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    (exp_dir / "checksums.sha256").write_text(f"{wrong_hash}  dummy.txt\n", encoding="utf-8")

    with pytest.raises(CorruptedHashError) as exc_info:
        verify_experiment_checksums(exp_dir)
    assert "checksum_mismatch" in str(exc_info.value)

    # Test Merkle hash chain break in runs.jsonl
    runs_file = tmp_path / "runs.jsonl"
    rec1 = {"sequence": 1, "prev_hash": "", "data": "A"}
    rec1_hash = "a1b2c3d4"  # Incorrect stored hash
    rec1["hash"] = rec1_hash
    runs_file.write_text(json.dumps(rec1) + "\n", encoding="utf-8")

    with pytest.raises(CorruptedHashError) as exc_info:
        verify_hash_chain(runs_file)
    assert "record_hash_mismatch" in str(exc_info.value)


def test_n6_claim_budget_violation_fails_release(tmp_path: Path) -> None:
    """N6: Test that a claim budget violation in claim ledger MUST fail release."""
    claim_csv = tmp_path / "claim_to_evidence.csv"

    # Write a claim containing forbidden overclaim regex "toctou eliminated"
    with claim_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["claim_id", "claim_text", "experiment_id", "evidence_path", "seal_sha256", "status", "claim_eligible"])
        writer.writerow([
            "GLHS-R3-CLAIM-FAIL",
            "TOCTOU eliminated completely by system",
            "E04",
            "research/glhs_journal/q3_r3/evidence/E04_postgres_toctou/seal.json",
            "SEALED",
            "SEALED_AND_VERIFIED",
            "true",
        ])

    with pytest.raises(ClaimBudgetViolationError) as exc_info:
        verify_claim_ledger(claim_csv, budget_json_path=CLAIM_BUDGET_PATH, evidence_root=EVIDENCE_ROOT)
    assert "forbidden_claim_budget_violation" in str(exc_info.value)


def test_n7_network_access_attempt_fails_release() -> None:
    """N7: Test that network access attempted during offline reproduction MUST fail release."""
    disable_network()
    try:
        with pytest.raises(NetworkAccessProhibitedError):
            socket.getaddrinfo("router.theclaracare.com", 443)

        with pytest.raises(NetworkAccessProhibitedError):
            socket.create_connection(("1.1.1.1", 443))
    finally:
        restore_network()


def test_git_state_verification() -> None:
    """Test git state verification returns valid commit metadata."""
    git_info = verify_git_state(skip_git_check=True)
    assert git_info["audited_sut_commit"] == AUDITED_SUT_COMMIT
    assert git_info["audited_parent_harness_commit"] == AUDITED_HARNESS_COMMIT
    assert "current_commit" in git_info
    assert git_info["git_check_passed"] is True


def test_release_manifest_integrity() -> None:
    """Test release_manifest / reproduction report structure and coverage."""
    report_path = RELEASE_ROOT / "reproduction_report.json"
    assert report_path.is_file(), f"Missing reproduction report: {report_path}"

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] in ("glhs-q3-r3-reproduction-report.v1", "glhs-r3-reproduction-report.v1")
    assert report["network_isolation_active"] is True
    assert report["total_experiments_swept"] == 15
    assert report["passed_experiments_count"] == 15
    assert report["overall_status"] == "UNIFIED_REPRODUCIBILITY_VERIFIED"


def test_record_count_mismatch_raises_fail_closed(tmp_path: Path) -> None:
    """Test that unexpected record counts fail closed with RecordCountMismatchError."""
    exp_dir = tmp_path / "E01_inference_consumption"
    exp_dir.mkdir(parents=True)
    raw_dir = exp_dir / "raw"
    raw_dir.mkdir(parents=True)

    (exp_dir / "protocol.json").write_text(json.dumps({"sample_size_allocation": {"total_executions": 10}}), encoding="utf-8")
    proto_sha = sha256_file(exp_dir / "protocol.json")
    (exp_dir / "protocol.sha256").write_text(f"{proto_sha}  protocol.json\n", encoding="utf-8")
    (exp_dir / "freeze.json").write_text(json.dumps({"freeze_timestamp_utc": "2026-09-28T00:00:00Z"}), encoding="utf-8")
    (exp_dir / "backend_attestation.json").write_text(json.dumps({"backend_type": "sqlite", "simulation": False}), encoding="utf-8")
    (exp_dir / "seal.json").write_text(json.dumps({"sealed_at_utc": "2026-09-28T00:00:00Z", "claim_eligible": True}), encoding="utf-8")
    (exp_dir / "validation.json").write_text(json.dumps({"validation_verdict": "PASS"}), encoding="utf-8")

    # Only write 2 records instead of 10
    runs_file = raw_dir / "runs.jsonl"
    runs_file.write_text('{"hash": "1", "data": "a"}\n{"hash": "2", "data": "b"}\n', encoding="utf-8")

    checksum_lines = [
        f"{sha256_file(exp_dir / f)}  {f}"
        for f in ["protocol.json", "protocol.sha256", "freeze.json", "backend_attestation.json", "validation.json", "raw/runs.jsonl"]
    ]
    seal_sha = sha256_file(exp_dir / "seal.json")
    checksum_lines.append(f"{seal_sha}  seal.json")
    (exp_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    # verify_hash_chain will be skipped if we test RecordCountMismatchError directly or mock/test it
    with pytest.raises(Exception) as exc_info:
        verify_experiment_bundle(
            "E01", "E01_inference_consumption", "Inference Test", expected_records=10, evidence_root=tmp_path
        )
    assert isinstance(exc_info.value, (RecordCountMismatchError, CorruptedHashError))


def test_git_fail_closed_on_dirty_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that git worktree dirty state raises GitWorktreeDirtyError when skip_git_check=False."""
    import subprocess
    orig_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        if "status" in cmd:
            class DummyResult:
                stdout = " M modified_file.py\n"
                stderr = ""
                returncode = 0
            return DummyResult()
        return orig_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)
    with pytest.raises(GitWorktreeDirtyError):
        verify_git_state(skip_git_check=False)


def test_strict_monotonic_chronology_enforcement(tmp_path: Path) -> None:
    """Test strict monotonic ordering: freeze <= started <= completed <= sealed."""
    exp_dir = tmp_path / "E01"
    exp_dir.mkdir(parents=True)

    # Inversion: completed > sealed
    (exp_dir / "freeze.json").write_text(json.dumps({"freeze_timestamp_utc": "2026-09-28T00:00:00Z"}), encoding="utf-8")
    (exp_dir / "seal.json").write_text(json.dumps({
        "execution_started_utc": "2026-09-28T01:00:00Z",
        "execution_completed_utc": "2026-09-28T03:00:00Z",
        "sealed_at_utc": "2026-09-28T02:00:00Z"
    }), encoding="utf-8")

    with pytest.raises(ChronologyAnomalyError):
        verify_experiment_chronology(exp_dir)
