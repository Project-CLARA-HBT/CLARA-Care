#!/usr/bin/env python3
"""Comprehensive test suite for scripts/security/redteam_manifest_checker.py.

Verifies:
1. Valid historical manifests in artifacts/PH00 and artifacts/PH01 evaluate cleanly (PASS).
2. Synthetic malicious manifests are caught fail-closed:
   - Fake/simulated test results (missing report, empty report, mock flags, trivial commands).
   - Hardcoded credentials & secrets (sk- tokens, API keys, bearer headers, private keys, JWTs).
   - PHI/PII leakage (Vietnamese phone numbers, CCCD/CMND national IDs, personal emails, clinical diagnoses).
   - Bypassed safety invariants (RBAC, CSRF, Consent, Emergency Fastpath, FIDES, Legal Guard, No-PII Telemetry).
   - Git commit verification (fabricated SHAs, malformed SHAs, SHA drift, bad signatures).
   - Deliverable manifest integrity (missing deliverable files, path lane violations, malformed JSON).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from scripts.security.redteam_manifest_checker import RedTeamManifestChecker


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def checker(repo_root: Path) -> RedTeamManifestChecker:
    return RedTeamManifestChecker(repo_root=repo_root)


# ==============================================================================
# 1. Valid Historical Manifest Verification
# ==============================================================================


def test_valid_ph00_manifests_pass(checker: RedTeamManifestChecker, repo_root: Path) -> None:
    """Ensure all authentic PH00 agent deliverables pass red-team audit."""
    ph00_dir = repo_root / "artifacts/PH00"
    report = checker.audit_all(targets=[ph00_dir], phase_filter="PH00")
    assert report["overall_status"] == "PASSED"
    assert report["manifests_audited"] == 10
    assert report["severity_counts"]["CRITICAL"] == 0
    assert report["severity_counts"]["HIGH"] == 0


def test_valid_ph01_manifests_pass(checker: RedTeamManifestChecker, repo_root: Path) -> None:
    """Ensure all authentic PH01 agent deliverables pass red-team audit."""
    ph01_dir = repo_root / "artifacts/PH01"
    report = checker.audit_all(targets=[ph01_dir], phase_filter="PH01")
    assert report["overall_status"] == "PASSED"
    assert report["manifests_audited"] == 10
    assert report["severity_counts"]["CRITICAL"] == 0
    assert report["severity_counts"]["HIGH"] == 0


# ==============================================================================
# 2. Synthetic Malicious Cases: Fake / Simulated Test Results
# ==============================================================================


def test_rejects_missing_test_report(checker: RedTeamManifestChecker) -> None:
    """Reject manifest if test_report.md is completely absent."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json"],
                }
            )
        )
        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "missing_test_report" in rules


def test_rejects_empty_test_report(checker: RedTeamManifestChecker) -> None:
    """Reject manifest if test_report.md is an empty 0-byte file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text("")  # 0 bytes

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "empty_test_report" in rules


def test_rejects_mock_test_marker(checker: RedTeamManifestChecker) -> None:
    """Reject deliverables containing fake test markers like MOCK_ALL_TESTS or fake assertion."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(
            "# Test Report\n"
            "Execution: MOCK_ALL_TESTS = True\n"
            "Result: 100 passed\n"
        )

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "fake_test_marker" in rules


def test_rejects_trivial_command_evidence(checker: RedTeamManifestChecker) -> None:
    """Reject manifests presenting trivial shell commands as tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                    "test_results": [
                        {"command": "true", "exit_code": 0, "status": "PASS"}
                    ],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text("# Test Report\nCommand `true` passed.\n")

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "trivial_fake_command" in rules


# ==============================================================================
# 3. Synthetic Malicious Cases: Hardcoded Credentials & Secrets
# ==============================================================================


def test_rejects_hardcoded_sk_token(checker: RedTeamManifestChecker) -> None:
    """Catch live hardcoded sk- API keys."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(
            "# Report\nTested against " + "sk-" + "proj-1234567890abcdef1234567890\n"
        )

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "hardcoded_sk_token" in rules


def test_rejects_hardcoded_api_key_assignment(checker: RedTeamManifestChecker) -> None:
    """Catch hardcoded router/deepseek key assignments."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(
            "# Config\n" + "ROUTER" + "_API_KEY = \"my-secret-router-token-987654321\"\n"
        )

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "hardcoded_api_key_assignment" in rules


def test_rejects_unredacted_bearer_token(checker: RedTeamManifestChecker) -> None:
    """Catch unredacted bearer authorization tokens."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(
            "Request: " + "Authorization: " + "Bearer " + "live_production_session_token_1234567890\n"
        )

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "hardcoded_bearer_token" in rules


def test_rejects_private_key_leak(checker: RedTeamManifestChecker) -> None:
    """Catch unencrypted private keys."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----\n"
        )

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "private_key_leak" in rules


# ==============================================================================
# 4. Synthetic Malicious Cases: PHI / PII Leakage
# ==============================================================================


def test_rejects_patient_phone_leak(checker: RedTeamManifestChecker) -> None:
    """Catch plaintext patient telephone numbers."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(
            "# Patient Record\nContact phone: 0912345678\n"
        )

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "patient_phone_leak" in rules


def test_rejects_patient_national_id_leak(checker: RedTeamManifestChecker) -> None:
    """Catch plaintext Vietnamese Citizen Identity Cards (CCCD/CMND)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(
            "# Patient Dossier\npatient_id: 079198001234\n"
        )

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "patient_national_id_leak" in rules


def test_rejects_personal_email_leak(checker: RedTeamManifestChecker) -> None:
    """Catch unapproved personal user/patient emails."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(
            "# Diagnostic Log\nRecipient: patient_nguyen_van_a@gmail.com\n"
        )

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "personal_email_leak" in rules


# ==============================================================================
# 5. Synthetic Malicious Cases: Bypassed Safety Invariants
# ==============================================================================


@pytest.mark.parametrize(
    ("bypass_string", "expected_rule"),
    [
        ("bypass_rbac = True", "bypassed_rbac"),
        ("disable_csrf = True", "bypassed_csrf"),
        ("skip_consent = True", "bypassed_consent"),
        ("bypass_emergency = True", "bypassed_emergency"),
        ("bypass_fides = True", "bypassed_fides"),
        ("disable_legal_guard = True", "bypassed_legal_guard"),
        ("metrics_allow_pii = True", "bypassed_no_pii_telemetry"),
    ],
)
def test_rejects_bypassed_safety_invariants(
    checker: RedTeamManifestChecker, bypass_string: str, expected_rule: str
) -> None:
    """Catch any attempts to bypass or weaken core clinical safety invariants."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text(f"# Implementation Note\nRuntime flag: {bypass_string}\n")

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert expected_rule in rules


# ==============================================================================
# 6. Synthetic Malicious Cases: Git Commit Integrity
# ==============================================================================


def test_rejects_fabricated_commit_sha(checker: RedTeamManifestChecker) -> None:
    """Catch non-existent / fabricated commit SHAs not in git object DB."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "deadbeef0123456789abcdef0123456789abcdef",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text("# Test Report\nAll tests passed.\n")

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "commit_not_found" in rules


def test_rejects_malformed_commit_sha(checker: RedTeamManifestChecker) -> None:
    """Catch malformed non-hex commit SHAs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "not-a-valid-sha-xyz!",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text("# Test Report\nAll tests passed.\n")

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "invalid_commit_sha_format" in rules


def test_rejects_head_sha_drift(checker: RedTeamManifestChecker) -> None:
    """Catch drift between frozen_head_sha and verified_head_sha."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "frozen_head_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "verified_head_sha": "2aa9016a57b49b53f1a433d076e1028a6ec45f64",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text("# Test Report\nClean run.\n")

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "head_sha_mismatch" in rules


# ==============================================================================
# 7. Deliverable Integrity & Path Lane Boundary Conformance
# ==============================================================================


def test_rejects_missing_declared_deliverable(checker: RedTeamManifestChecker) -> None:
    """Catch deliverable files claimed in manifest but missing on filesystem."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": [
                        "change_manifest.json",
                        "test_report.md",
                        "non_existent_file.txt",
                    ],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text("# Test Report\nPassed.\n")

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "missing_deliverable_file" in rules


def test_rejects_path_lane_violation(checker: RedTeamManifestChecker) -> None:
    """Catch files touched outside assigned path lane."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "path_lane": ["docs/security/", "scripts/security/"],
                    "files_changed": [
                        "services/api/src/clara_api/main.py"  # Outside lane!
                    ],
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text("# Test Report\nPassed.\n")

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "unauthorized_file_path" in rules


def test_rejects_tampered_commit_signature(checker: RedTeamManifestChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    """Catch commits where cryptographic signature failed validation (status 'B')."""
    import subprocess

    original_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        if len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "log" and "%G?" in cmd[2]:
            class MockResult:
                stdout = "B keyid123 Test Signer\n"
                stderr = ""
                returncode = 0
            return MockResult()
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manifest = tmp_path / "change_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "agent_id": "A08",
                    "phase": "PH02",
                    "status": "COMPLETED",
                    "base_sha": "879dc5dcfcaae91b3626e28062043d934294478b",
                    "deliverables": ["change_manifest.json", "test_report.md"],
                }
            )
        )
        test_report = tmp_path / "test_report.md"
        test_report.write_text("# Test Report\nPassed.\n")

        report = checker.audit_agent_deliverables(manifest)
        assert report["status"] == "FAILED"
        rules = [f["rule"] for f in report["findings"]]
        assert "tampered_commit_signature" in rules


def test_cli_execution_clean(repo_root: Path) -> None:
    """Test CLI exit code 0 when run against valid historical artifacts."""
    import subprocess
    cmd = [
        sys.executable,
        str(repo_root / "scripts/security/redteam_manifest_checker.py"),
        "artifacts/PH00",
        "artifacts/PH01",
    ]
    res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Overall Status:    PASSED" in res.stdout
    assert "Manifests Audited: 20" in res.stdout


def test_cli_execution_with_json_output(repo_root: Path) -> None:
    """Test CLI --json output format."""
    import subprocess
    cmd = [
        sys.executable,
        str(repo_root / "scripts/security/redteam_manifest_checker.py"),
        "--phase",
        "PH01",
        "--json",
    ]
    res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["overall_status"] == "PASSED"
    assert data["manifests_audited"] == 10
