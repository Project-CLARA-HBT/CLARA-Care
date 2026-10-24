#!/usr/bin/env python3
"""Unit tests for audit_fhir_validator_conformance.py."""

from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path

import pytest
from audit_fhir_validator_conformance import FhirConformanceAuditor


@pytest.fixture
def repo_root() -> Path:
    """Returns the repository root path."""
    current = Path(__file__).resolve().parent.parent.parent
    return current


def test_auditor_runs_against_repo(repo_root: Path) -> None:
    auditor = FhirConformanceAuditor(repo_root)
    findings = auditor.audit_all()
    assert isinstance(findings, list)
    assert len(findings) == 0, f"Expected 0 findings against repo, got: {findings}"


def test_auditor_detects_missing_toolchain_lock() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        auditor = FhirConformanceAuditor(root)
        findings = auditor.audit_all(verify_fixtures=False)
        rule_ids = {f.rule_id for f in findings}
        assert "FHIR-TOOL-01" in rule_ids
        assert "FHIR-MOD-01" in rule_ids


def test_auditor_detects_toolchain_mismatch() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        lock_dir = root / "docs/interoperability"
        lock_dir.mkdir(parents=True)
        (lock_dir / "fhir-toolchain.lock.json").write_text(
            json.dumps(
                {
                    "validator": {
                        "version": "6.8.0",
                        "sha256": "bad_checksum_value_here",
                    }
                }
            )
        )

        auditor = FhirConformanceAuditor(root)
        findings = auditor.audit_all(verify_fixtures=False)
        rule_ids = {f.rule_id for f in findings}
        assert "FHIR-TOOL-02" in rule_ids
        assert "FHIR-TOOL-03" in rule_ids


def test_auditor_detects_relaxed_bounds() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        module_dir = root / "services/api/src/clara_api/lifemap"
        module_dir.mkdir(parents=True)
        (module_dir / "fhir_r4.py").write_text(
            textwrap.dedent(
                """
                MAX_BUNDLE_BYTES = 50_000_000
                MAX_ENTRIES = 5000
                MAX_DEPTH = 100
                MAX_STRING = 500_000
                FHIR_VALIDATOR_SHA256 = "0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6"
                """
            )
        )

        auditor = FhirConformanceAuditor(root)
        findings = auditor.audit_all(verify_fixtures=False)
        rule_ids = {f.rule_id for f in findings}
        assert "FHIR-BOUND-01" in rule_ids
        assert "FHIR-BOUND-02" in rule_ids
        assert "FHIR-BOUND-03" in rule_ids
        assert "FHIR-BOUND-04" in rule_ids


def test_auditor_detects_missing_dangerous_rejections() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        module_dir = root / "services/api/src/clara_api/lifemap"
        module_dir.mkdir(parents=True)
        (module_dir / "fhir_r4.py").write_text(
            textwrap.dedent(
                """
                MAX_BUNDLE_BYTES = 1_000_000
                MAX_ENTRIES = 500
                MAX_DEPTH = 20
                MAX_STRING = 20_000
                FHIR_VALIDATOR_SHA256 = "0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6"
                # No modifierExtension or contained checks here
                """
            )
        )

        auditor = FhirConformanceAuditor(root)
        findings = auditor.audit_all(verify_fixtures=False)
        rule_ids = {f.rule_id for f in findings}
        assert "FHIR-DANG-01" in rule_ids
        assert "FHIR-DANG-02" in rule_ids
        assert "FHIR-DANG-03" in rule_ids


def test_auditor_detects_missing_single_patient_and_anti_ssrf() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        module_dir = root / "services/api/src/clara_api/lifemap"
        module_dir.mkdir(parents=True)
        (module_dir / "fhir_r4.py").write_text(
            textwrap.dedent(
                """
                MAX_BUNDLE_BYTES = 1_000_000
                MAX_ENTRIES = 500
                MAX_DEPTH = 20
                MAX_STRING = 20_000
                FHIR_VALIDATOR_SHA256 = "0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6"
                # Omit single patient requirement and url reference check
                """
            )
        )

        auditor = FhirConformanceAuditor(root)
        findings = auditor.audit_all(verify_fixtures=False)
        rule_ids = {f.rule_id for f in findings}
        assert "FHIR-REF-01" in rule_ids
        assert "FHIR-REF-02" in rule_ids
        assert "FHIR-REF-03" in rule_ids


def test_auditor_detects_fixture_hash_drift() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        pkg_dir = root / "evaluation/fhir_conformance"
        fix_dir = pkg_dir / "fixtures"
        fix_dir.mkdir(parents=True)

        fixture_file = fix_dir / "test.json"
        fixture_file.write_text('{"foo": "bar"}')

        manifest_file = fix_dir / "manifest.json"
        manifest_file.write_text(
            json.dumps(
                {
                    "fixtures": [
                        {
                            "path": "fixtures/test.json",
                            "sha256": "expected_different_sha256_hash",
                        }
                    ]
                }
            )
        )

        auditor = FhirConformanceAuditor(root)
        findings = auditor.audit_all(verify_fixtures=True)
        rule_ids = {f.rule_id for f in findings}
        assert "FHIR-FIX-02" in rule_ids
