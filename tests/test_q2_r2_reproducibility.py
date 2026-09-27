"""Unit tests for Phase 14 Unified Reproducibility Bundle (GLHS Q2/R2).

Verifies network isolation, experiment package reproducibility (E00-E13),
release manifest integrity, claim ledger audit completeness, and artifact SHA-256 digests.
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from reproduce_q2_r2 import (
    AUDITED_GIT_COMMIT,
    RELEASE_ROOT,
    NetworkAccessProhibitedError,
    disable_network,
    reproduce_q2_r2,
    sha256_file,
    sweep_all_experiments,
    verify_claim_ledger,
    verify_git_state,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_network_isolation_fail_closed() -> None:
    """Test that network isolation prohibits socket creation and connection."""
    disable_network()
    with pytest.raises(NetworkAccessProhibitedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_git_state_verification() -> None:
    """Test git state verification returns valid commit metadata."""
    git_info = verify_git_state(skip_git_check=True)
    assert git_info["audited_commit"] == AUDITED_GIT_COMMIT
    assert "current_commit" in git_info
    assert git_info["git_check_passed"] is True


def test_sweep_all_experiments_e00_to_e13() -> None:
    """Test that all 14 experiments (E00-E13) reproduce cleanly offline."""
    exp_results = sweep_all_experiments()
    assert len(exp_results) == 14

    for eid in [f"E{i:02d}" for i in range(14)]:
        assert eid in exp_results, f"Missing experiment {eid} in sweep results"
        res = exp_results[eid]
        assert res.get("claim_eligible") is True, f"{eid} claim_eligible is not True"
        assert res.get("status") in ("REPRODUCED_AND_VERIFIED", "VERIFIED"), f"{eid} status invalid: {res.get('status')}"
        assert res.get("seal_verified") is True, f"{eid} seal_verified is not True"


def test_claim_ledger_verification() -> None:
    """Test that claim_to_evidence.csv is complete and free of NOT_RUN violations."""
    claim_csv = RELEASE_ROOT / "claim_to_evidence.csv"
    assert claim_csv.is_file(), f"Missing claim ledger: {claim_csv}"

    claim_audit = verify_claim_ledger(claim_csv)
    assert claim_audit["claim_ledger_valid"] is True
    assert claim_audit["violations_count"] == 0
    assert claim_audit["total_claims"] == 15
    assert claim_audit["claim_eligible_claims"] == 15


def test_release_manifest_integrity() -> None:
    """Test release_manifest.json bindings and experiment coverage."""
    manifest_path = RELEASE_ROOT / "release_manifest.json"
    assert manifest_path.is_file(), f"Missing release manifest: {manifest_path}"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "glhs-q2-r2-release-manifest.v1"
    assert manifest["release_id"] == "GLHS-Q2-R2-RELEASE-20260928-V1"
    assert manifest["audited_git_commit"] == AUDITED_GIT_COMMIT
    assert manifest["total_experiments"] == 14
    assert manifest["claim_eligible_experiments"] == 14
    assert manifest["overall_status"] == "UNIFIED_RELEASE_SEALED"

    for eid in [f"E{i:02d}" for i in range(14)]:
        assert eid in manifest["experiments"]
        assert manifest["experiments"][eid]["claim_eligible"] is True


def test_artifact_sha256_digests() -> None:
    """Test that every file recorded in artifact-sha256.json matches on-disk SHA256 digest."""
    artifact_json_path = RELEASE_ROOT / "artifact-sha256.json"
    assert artifact_json_path.is_file(), f"Missing artifact sha256 map: {artifact_json_path}"

    artifact_map = json.loads(artifact_json_path.read_text(encoding="utf-8"))
    assert len(artifact_map) > 0

    for rel_path, expected_sha in artifact_map.items():
        file_path = REPO_ROOT / rel_path
        assert file_path.is_file(), f"Artifact file missing: {rel_path}"
        actual_sha = sha256_file(file_path)
        assert actual_sha == expected_sha, f"SHA256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"


def test_full_reproduction_sweep() -> None:
    """Test full reproduction sweep output report."""
    sweep_report = reproduce_q2_r2(skip_git_check=True)
    assert sweep_report["overall_status"] == "UNIFIED_REPRODUCIBILITY_VERIFIED"
    assert sweep_report["network_isolation_active"] is True
    assert sweep_report["total_experiments_swept"] == 14
    assert sweep_report["claim_ledger_audit"]["claim_ledger_valid"] is True
