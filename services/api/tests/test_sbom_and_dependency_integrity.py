"""Unit tests for SBOM generation, dependency integrity audit, and CVE triage.

Spec: PH01 / A07 (Tests + CI)
Validates:
  1. CycloneDX 1.5 SBOM generation across Python, Node, and Flutter ecosystems.
  2. PURL generation, direct dependency detection, and cryptographic integrity hashes.
  3. Unpinned direct dependency detection and lockfile completeness.
  4. Accepted security findings parsing, required fields, and review dates.
  5. CLI execution and artifact output.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Add scripts/ops to path to import generate_sbom and check_dependency_integrity
REPO_ROOT = Path(__file__).resolve().parents[3]
OPS_DIR = REPO_ROOT / "scripts/ops"
if str(OPS_DIR) not in sys.path:
    sys.path.insert(0, str(OPS_DIR))

from check_dependency_integrity import (  # noqa: E402
    parse_accepted_findings,
    run_dependency_integrity_audit,
)
from generate_sbom import (  # noqa: E402
    SbomBuilder,
    is_constraint_pinned,
    make_purl,
)


def test_make_purl_ecosystems():
    """Verify standard Package URL (PURL) formatting across ecosystems."""
    assert make_purl("pypi", "FastAPI", "0.116.0") == "pkg:pypi/fastapi@0.116.0"
    assert make_purl("npm", "axios", "1.14.0") == "pkg:npm/axios@1.14.0"
    assert make_purl("npm", "@tanstack/react-virtual", "3.13.23") == "pkg:npm/%40tanstack/react-virtual@3.13.23"
    assert make_purl("pub", "http", "1.2.2") == "pkg:pub/http@1.2.2"
    assert make_purl("generic", "custom", "1.0") == "pkg:generic/custom@1.0"


def test_is_constraint_pinned():
    """Verify constraint classification as pinned exact vs range/unpinned."""
    # Pinned cases
    assert is_constraint_pinned("==1.18.4") is True
    assert is_constraint_pinned("18.3.1") is True
    assert is_constraint_pinned("15.5.22") is True
    assert is_constraint_pinned("0.1.0+1") is True

    # Unpinned cases
    assert is_constraint_pinned(">=1.13.2") is False
    assert is_constraint_pinned("^1.14.0") is False
    assert is_constraint_pinned("~2.1.0") is False
    assert is_constraint_pinned(">=3.3.0 <4.0.0") is False
    assert is_constraint_pinned("*") is False
    assert is_constraint_pinned("any") is False
    assert is_constraint_pinned("") is False


def test_sbom_builder_scan_and_cyclonedx():
    """Verify SBOM builder scans all three ecosystems and creates valid CycloneDX 1.5 JSON."""
    builder = SbomBuilder(REPO_ROOT)
    builder.scan_all()

    assert len(builder.components) >= 500, f"Expected >= 500 components, got {len(builder.components)}"

    # Ecosystem representation
    ecosystems = {c.ecosystem for c in builder.components}
    assert "pypi" in ecosystems
    assert "npm" in ecosystems
    assert "pub" in ecosystems

    # Verify key direct dependencies are captured
    names = {c.name for c in builder.components}
    assert "fastapi" in names
    assert "pydantic" in names
    assert "next" in names
    assert "react" in names
    assert "http" in names
    assert "flutter_secure_storage" in names

    # Generate CycloneDX JSON
    cdx = builder.to_cyclonedx()
    assert cdx["$schema"] == "http://cyclonedx.org/schema/bom-1.5.json"
    assert cdx["bomFormat"] == "CycloneDX"
    assert cdx["specVersion"] == "1.5"
    assert cdx["version"] == 1
    assert "serialNumber" in cdx
    assert cdx["serialNumber"].startswith("urn:uuid:")
    assert cdx["metadata"]["component"]["name"] == "CLARA-Care"
    assert len(cdx["components"]) == len(builder.components)
    assert len(cdx["dependencies"]) > 0

    # Validate first component shape
    sample = cdx["components"][0]
    assert "bom-ref" in sample
    assert "type" in sample
    assert "name" in sample
    assert "version" in sample
    assert "purl" in sample
    assert "scope" in sample
    assert "properties" in sample


def test_sbom_builder_manifest():
    """Verify CLARA supply chain manifest structure and lockfile checksums."""
    builder = SbomBuilder(REPO_ROOT)
    builder.scan_all()
    manifest = builder.to_manifest()

    assert manifest["schema_version"] == "1.0.0"
    summary = manifest["summary"]
    assert summary["total_components"] == len(builder.components)
    assert summary["ecosystems"]["pypi"] > 50
    assert summary["ecosystems"]["npm"] > 500
    assert summary["ecosystems"]["pub"] > 50
    assert summary["direct_dependencies_count"] > 0
    assert summary["unpinned_direct_count"] > 0

    # Check lockfile checksums
    checksums = manifest["lockfile_checksums"]
    assert "services/api/uv.lock" in checksums
    assert "services/ml/uv.lock" in checksums
    assert "apps/web/package-lock.json" in checksums
    assert "apps/mobile/pubspec.lock" in checksums
    for path, sha in checksums.items():
        assert len(sha) == 64, f"Invalid SHA-256 for {path}: {sha}"


def test_parse_accepted_findings_from_repo():
    """Verify docs/security/accepted-findings.md active table parsing."""
    accepted_path = REPO_ROOT / "docs/security/accepted-findings.md"
    records, errors = parse_accepted_findings(accepted_path)

    assert not errors, f"Unexpected validation errors: {errors}"
    assert len(records) >= 1, "Expected at least 1 active accepted finding"

    ecdsa_rec = next((r for r in records if "GHSA-wj6h-64fc-37mp" in r.advisory_id), None)
    assert ecdsa_rec is not None, "GHSA-wj6h-64fc-37mp not found in accepted findings"
    assert "ecdsa" in ecdsa_rec.package
    assert ecdsa_rec.severity == "HIGH"
    assert ecdsa_rec.disposition == "accepted"
    assert "Minerva timing" in ecdsa_rec.justification
    assert "HMAC" in ecdsa_rec.compensating_control
    assert ecdsa_rec.suppression_ref == "pip-audit --ignore-vuln GHSA-wj6h-64fc-37mp"


def test_parse_accepted_findings_malformed(tmp_path: Path):
    """Verify parse_accepted_findings rejects invalid tables and missing required fields."""
    bad_md = tmp_path / "bad-accepted-findings.md"
    bad_md.write_text(
        """# Accepted findings
## Active accepted / ignored findings
| Advisory ID | Package / ecosystem | Surface | Severity | Disposition | Justification | Compensating control | Owner | Accepted on | Review date | Revisit condition | Suppression ref |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GHSA-test-1234 | badpkg | api | HIGH | accepted | — | — | @owner | 2026-01-01 | not-a-date | revisit | ignore |
""",
        encoding="utf-8",
    )
    records, errors = parse_accepted_findings(bad_md)
    assert len(records) == 1
    assert len(records[0].validation_errors) >= 3  # missing justification, missing control, invalid date


def test_run_dependency_integrity_audit():
    """Verify dependency integrity audit execution, unpinned reporting, and hash coverage."""
    report = run_dependency_integrity_audit(REPO_ROOT, fail_unpinned=False, fail_expired_findings=False)

    assert report.total_components_checked >= 500
    assert report.direct_dependencies_count > 0
    assert report.unpinned_count > 0
    assert report.lockfile_hash_coverage["hash_coverage_percentage"] > 90.0
    assert len(report.accepted_findings) >= 1
    assert report.passed is True  # Non-strict passes with warnings

    # Missing lockfile warnings for ASR and OCR
    assert any("services/asr" in m for m in report.missing_lockfiles)
    assert any("services/ocr" in m for m in report.missing_lockfiles)


def test_run_dependency_integrity_audit_fail_strict():
    """Verify strict mode fails when unpinned direct dependencies exist."""
    report = run_dependency_integrity_audit(REPO_ROOT, fail_unpinned=True, fail_expired_findings=False)
    assert report.passed is False
    assert any("Strict pinning check failed" in e for e in report.errors)


def test_cli_generate_sbom_invocation(tmp_path: Path):
    """Verify generate_sbom.py runs via subprocess CLI and writes expected files."""
    out_dir = tmp_path / "sbom_test_out"
    cmd = [
        sys.executable,
        str(OPS_DIR / "generate_sbom.py"),
        "--repo-root",
        str(REPO_ROOT),
        "--output-dir",
        str(out_dir),
        "--summary",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"generate_sbom CLI failed: {res.stderr}"
    assert "CLARA SUPPLY-CHAIN SBOM SUMMARY" in res.stdout

    cdx_file = out_dir / "sbom.cyclonedx.json"
    manifest_file = out_dir / "sbom_manifest.json"
    assert cdx_file.is_file()
    assert manifest_file.is_file()

    with open(cdx_file) as f:
        cdx = json.load(f)
    assert cdx["bomFormat"] == "CycloneDX"

    with open(manifest_file) as f:
        man = json.load(f)
    assert man["schema_version"] == "1.0.0"


def test_cli_check_dependency_integrity_invocation(tmp_path: Path):
    """Verify check_dependency_integrity.py runs via subprocess CLI and writes report."""
    report_file = tmp_path / "integrity_report.json"
    cmd = [
        sys.executable,
        str(OPS_DIR / "check_dependency_integrity.py"),
        "--repo-root",
        str(REPO_ROOT),
        "--report-file",
        str(report_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"check_dependency_integrity CLI failed: {res.stderr}"
    assert "CLARA DEPENDENCY INTEGRITY & CVE TRIAGE AUDIT" in res.stdout
    assert report_file.is_file()

    with open(report_file) as f:
        rep = json.load(f)
    assert rep["passed"] is True
    assert rep["total_components_checked"] >= 500
