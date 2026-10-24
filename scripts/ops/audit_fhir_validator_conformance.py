#!/usr/bin/env python3
"""FHIR R4 Validator Conformance & Security Boundary Auditor.

Audits the HL7 FHIR R4 interoperability layer across CLARA-Care:
  - Pinned toolchain lock integrity and checksum alignment (v6.9.12)
  - Security invariant limits (MAX_BUNDLE_BYTES, MAX_ENTRIES, MAX_DEPTH, MAX_STRING)
  - Rejection of dangerous constructs (modifierExtension, contained, implicitRules)
  - Single-patient boundary and intra-bundle reference isolation
  - Anti-SSRF external URL reference rejection
  - Endpoint feature flag gating, consent verification, and idempotency digests
  - Untrusted capture staging quarantine (import_candidates filtering)
  - Fail-closed IPS release gate (HTTP 409)
  - Conformance test fixture manifest verification and hash stability

Usage:
  python3 scripts/ops/audit_fhir_validator_conformance.py [--repo-root .] [--json] [--fail-on-high] [--verify-fixtures]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass
class ConformanceFinding:
    rule_id: str
    title: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: str  # TOOLCHAIN, INVARIANTS, REFERENCE_ISOLATION, ENDPOINT_GATE, FIXTURE_STABILITY
    file_path: str
    line_number: int | None
    code_anchor: str
    description: str
    impact: str
    remediation: str


class FhirConformanceAuditor:
    """Automated security and conformance auditor for FHIR R4 interoperability."""

    EXPECTED_TOOLCHAIN_VERSION = "6.9.12"
    EXPECTED_TOOLCHAIN_SHA256 = (
        "0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6"
    )
    EXPECTED_MAX_BUNDLE_BYTES = 1_000_000
    EXPECTED_MAX_ENTRIES = 500
    EXPECTED_MAX_DEPTH = 20
    EXPECTED_MAX_STRING = 20_000

    EXPECTED_RESOURCE_TYPES = frozenset(
        {
            "Patient",
            "Observation",
            "AllergyIntolerance",
            "Condition",
            "MedicationStatement",
            "MedicationRequest",
            "CarePlan",
            "Goal",
            "Task",
            "QuestionnaireResponse",
            "DocumentReference",
            "Provenance",
            "Consent",
            "AuditEvent",
            "Composition",
        }
    )

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.findings: list[ConformanceFinding] = []

    def audit_all(self, verify_fixtures: bool = True) -> list[ConformanceFinding]:
        self.findings.clear()
        self._audit_toolchain_lock()
        self._audit_fhir_r4_module_invariants()
        self._audit_dangerous_construct_rejections()
        self._audit_reference_isolation_and_single_patient()
        self._audit_endpoint_security_and_flags()
        self._audit_untrusted_staging_and_quarantine()
        if verify_fixtures:
            self._audit_fixture_manifest_and_hashes()
        return self.findings

    def _audit_toolchain_lock(self) -> None:
        """Verify the toolchain lock file exists and has pinned coordinates."""
        lock_file = self.repo_root / "docs/interoperability/fhir-toolchain.lock.json"
        if not lock_file.exists():
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-TOOL-01",
                    title="Missing FHIR toolchain lock file",
                    severity="CRITICAL",
                    category="TOOLCHAIN",
                    file_path=str(lock_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="docs/interoperability/fhir-toolchain.lock.json",
                    description="The canonical toolchain lock file does not exist.",
                    impact="Cannot verify cryptographic integrity of the official HL7 validator CLI.",
                    remediation="Restore docs/interoperability/fhir-toolchain.lock.json with pinned SHA-256.",
                )
            )
            return

        try:
            lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            validator = lock_data.get("validator", {})
            version = str(validator.get("version", ""))
            sha256 = str(validator.get("sha256", ""))

            if version != self.EXPECTED_TOOLCHAIN_VERSION:
                self.findings.append(
                    ConformanceFinding(
                        rule_id="FHIR-TOOL-02",
                        title="Validator CLI version mismatch in lock file",
                        severity="HIGH",
                        category="TOOLCHAIN",
                        file_path=str(lock_file.relative_to(self.repo_root)),
                        line_number=10,
                        code_anchor=f"version: {version}",
                        description=f"Expected validator CLI version {self.EXPECTED_TOOLCHAIN_VERSION}, found {version}.",
                        impact="Potential behavioral divergence from tested conformance baseline.",
                        remediation=f"Pin validator version to {self.EXPECTED_TOOLCHAIN_VERSION}.",
                    )
                )

            if sha256 != self.EXPECTED_TOOLCHAIN_SHA256:
                self.findings.append(
                    ConformanceFinding(
                        rule_id="FHIR-TOOL-03",
                        title="Validator CLI SHA-256 mismatch in lock file",
                        severity="CRITICAL",
                        category="TOOLCHAIN",
                        file_path=str(lock_file.relative_to(self.repo_root)),
                        line_number=13,
                        code_anchor=f"sha256: {sha256}",
                        description="Validator CLI SHA-256 does not match canonical release digest.",
                        impact="Risk of compromised or tampered validation binary execution.",
                        remediation=f"Restore canonical SHA-256 {self.EXPECTED_TOOLCHAIN_SHA256}.",
                    )
                )
        except Exception as e:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-TOOL-04",
                    title="Failed to parse FHIR toolchain lock file",
                    severity="HIGH",
                    category="TOOLCHAIN",
                    file_path=str(lock_file.relative_to(self.repo_root)),
                    line_number=1,
                    code_anchor="json.loads",
                    description=f"Parse error: {e}",
                    impact="Invalid JSON in lock file breaks toolchain verification.",
                    remediation="Fix syntax error in fhir-toolchain.lock.json.",
                )
            )

    def _audit_fhir_r4_module_invariants(self) -> None:
        """Audit fhir_r4.py for bounded limits and resource type sets."""
        module_file = self.repo_root / "services/api/src/clara_api/lifemap/fhir_r4.py"
        if not module_file.exists():
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-MOD-01",
                    title="Missing core FHIR R4 projection module",
                    severity="CRITICAL",
                    category="INVARIANTS",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="services/api/src/clara_api/lifemap/fhir_r4.py",
                    description="Core fhir_r4.py module is absent from the repository.",
                    impact="FHIR R4 capabilities cannot function.",
                    remediation="Restore services/api/src/clara_api/lifemap/fhir_r4.py.",
                )
            )
            return

        content = module_file.read_text(encoding="utf-8")

        # Check bounds constants
        checks = [
            ("MAX_BUNDLE_BYTES", self.EXPECTED_MAX_BUNDLE_BYTES, "FHIR-BOUND-01", "Payload size limit"),
            ("MAX_ENTRIES", self.EXPECTED_MAX_ENTRIES, "FHIR-BOUND-02", "Entry count limit"),
            ("MAX_DEPTH", self.EXPECTED_MAX_DEPTH, "FHIR-BOUND-03", "AST depth limit"),
            ("MAX_STRING", self.EXPECTED_MAX_STRING, "FHIR-BOUND-04", "String length limit"),
        ]

        for const_name, expected_val, rule_id, label in checks:
            match = re.search(rf"^\s*{const_name}\s*=\s*([0-9_]+)", content, re.MULTILINE)
            if not match:
                self.findings.append(
                    ConformanceFinding(
                        rule_id=rule_id,
                        title=f"Missing {label} ({const_name})",
                        severity="HIGH",
                        category="INVARIANTS",
                        file_path=str(module_file.relative_to(self.repo_root)),
                        line_number=None,
                        code_anchor=const_name,
                        description=f"Constant {const_name} is missing from fhir_r4.py.",
                        impact="Unbounded resource parsing leaves server vulnerable to DoS.",
                        remediation=f"Define {const_name} = {expected_val} in fhir_r4.py.",
                    )
                )
            else:
                raw_val = int(match.group(1).replace("_", ""))
                if raw_val > expected_val:
                    self.findings.append(
                        ConformanceFinding(
                            rule_id=rule_id,
                            title=f"Relaxed {label} ({const_name})",
                            severity="HIGH",
                            category="INVARIANTS",
                            file_path=str(module_file.relative_to(self.repo_root)),
                            line_number=None,
                            code_anchor=f"{const_name} = {raw_val}",
                            description=f"{const_name} set to {raw_val}, exceeding safety threshold {expected_val}.",
                            impact="Increased attack surface for memory exhaustion and DoS.",
                            remediation=f"Constrain {const_name} <= {expected_val}.",
                        )
                    )

        # Check toolchain pin match in python module
        match_sha = re.search(r'FHIR_VALIDATOR_SHA256\s*=\s*\(\s*["\']([a-f0-9]+)["\']\s*\)', content)
        if not match_sha:
            match_sha = re.search(r'FHIR_VALIDATOR_SHA256\s*=\s*["\']([a-f0-9]+)["\']', content)

        if match_sha and match_sha.group(1) != self.EXPECTED_TOOLCHAIN_SHA256:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-TOOL-05",
                    title="In-code validator SHA-256 does not match lock",
                    severity="CRITICAL",
                    category="TOOLCHAIN",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor=match_sha.group(0),
                    description="FHIR_VALIDATOR_SHA256 in fhir_r4.py diverges from locked checksum.",
                    impact="Discrepancy between code constants and lock file creates release confusion.",
                    remediation=f"Synchronize FHIR_VALIDATOR_SHA256 with {self.EXPECTED_TOOLCHAIN_SHA256}.",
                )
            )

    def _audit_dangerous_construct_rejections(self) -> None:
        """Verify fail-closed rejection of modifierExtension, contained, and implicitRules."""
        module_file = self.repo_root / "services/api/src/clara_api/lifemap/fhir_r4.py"
        if not module_file.exists():
            return

        content = module_file.read_text(encoding="utf-8")

        has_rejection_logic = (
            "unsafe_modifier_or_contained" in content
            or "modifier_extension_forbidden" in content
        )

        if "modifierExtension" not in content or not has_rejection_logic:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-DANG-01",
                    title="Missing strict modifierExtension rejection",
                    severity="CRITICAL",
                    category="INVARIANTS",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="modifierExtension",
                    description="validate_bundle does not fail closed on modifierExtension.",
                    impact="Allowing modifierExtension can invert clinical meaning (e.g. negated allergy).",
                    remediation="Reject any resource possessing modifierExtension with HTTP 422.",
                )
            )

        if '"contained"' not in content or not has_rejection_logic:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-DANG-02",
                    title="Missing strict contained resource rejection",
                    severity="HIGH",
                    category="INVARIANTS",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="contained",
                    description="validate_bundle does not reject contained sub-resources.",
                    impact="Contained resources bypass top-level entry counts and reference resolution.",
                    remediation="Reject any resource containing 'contained' with HTTP 422.",
                )
            )

        if "implicitRules" not in content or not has_rejection_logic:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-DANG-03",
                    title="Missing implicitRules rejection",
                    severity="HIGH",
                    category="INVARIANTS",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="implicitRules",
                    description="validate_bundle does not reject resources with custom implicitRules.",
                    impact="Custom processing rules could violate base FHIR R4 semantic expectations.",
                    remediation="Reject any resource specifying implicitRules with HTTP 422.",
                )
            )

    def _audit_reference_isolation_and_single_patient(self) -> None:
        """Verify single-patient requirement and anti-SSRF relative reference rules."""
        module_file = self.repo_root / "services/api/src/clara_api/lifemap/fhir_r4.py"
        if not module_file.exists():
            return

        content = module_file.read_text(encoding="utf-8")

        if "exactly_one_patient_required" not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-REF-01",
                    title="Missing single-patient invariant check",
                    severity="CRITICAL",
                    category="REFERENCE_ISOLATION",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="exactly_one_patient_required",
                    description="Bundle validator does not enforce exactly one Patient per bundle.",
                    impact="Multi-patient bundles cause cross-subject clinical data contamination.",
                    remediation="Ensure len(patient_entries) == 1 is strictly enforced.",
                )
            )

        if "external_reference_forbidden" not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-REF-02",
                    title="Missing external URL reference rejection (Anti-SSRF)",
                    severity="CRITICAL",
                    category="REFERENCE_ISOLATION",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="external_reference_forbidden",
                    description="Validator does not reject absolute external URL references.",
                    impact="Vulnerability to SSRF, DNS exfiltration, or external resource spoofing.",
                    remediation="Forbid references starting with http://, https://, //, or containing _history.",
                )
            )

        if "dangling_reference" not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-REF-03",
                    title="Missing intra-bundle reference closure check",
                    severity="HIGH",
                    category="REFERENCE_ISOLATION",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="dangling_reference",
                    description="Validator does not ensure all internal references resolve inside the bundle.",
                    impact="Dangling references cause orphaned clinical data or runtime null errors.",
                    remediation="Validate that all Reference.reference values match an existing bundle entry.",
                )
            )

    def _audit_endpoint_security_and_flags(self) -> None:
        """Verify endpoints gate behind feature flags, verify consent, and check idempotency."""
        endpoints_file = self.repo_root / "services/api/src/clara_api/api/v1/endpoints/lifemap.py"
        if not endpoints_file.exists():
            return

        content = endpoints_file.read_text(encoding="utf-8")

        # Check export feature flag
        if "lifemap_fhir_export_enabled" not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-END-01",
                    title="Export endpoint missing feature flag check",
                    severity="CRITICAL",
                    category="ENDPOINT_GATE",
                    file_path=str(endpoints_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="lifemap_fhir_export_enabled",
                    description="export_fhir_r4_summary does not check settings.lifemap_fhir_export_enabled.",
                    impact="Export surface exposed without administrator feature enablement.",
                    remediation="Add check for settings.lifemap_fhir_export_enabled defaulting to false.",
                )
            )

        # Check import feature flag
        if "lifemap_fhir_import_enabled" not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-END-02",
                    title="Import endpoint missing feature flag check",
                    severity="CRITICAL",
                    category="ENDPOINT_GATE",
                    file_path=str(endpoints_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="lifemap_fhir_import_enabled",
                    description="import_fhir_r4 does not check settings.lifemap_fhir_import_enabled.",
                    impact="Untrusted ingestion endpoint active without explicit operator enablement.",
                    remediation="Add check for settings.lifemap_fhir_import_enabled defaulting to false.",
                )
            )

        # Check export consent check
        if "ensure_medical_disclaimer_consent" not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-END-03",
                    title="Export endpoint missing consent check",
                    severity="HIGH",
                    category="ENDPOINT_GATE",
                    file_path=str(endpoints_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="ensure_medical_disclaimer_consent",
                    description="export_fhir_r4_summary does not verify affirmative medical consent.",
                    impact="Violates PDPD Article 17 and core medical disclaimer invariant.",
                    remediation="Ensure ensure_medical_disclaimer_consent is called prior to export.",
                )
            )

        # Check Cache-Control: no-store
        if '"Cache-Control": "no-store"' not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-END-04",
                    title="Export response missing Cache-Control: no-store",
                    severity="HIGH",
                    category="ENDPOINT_GATE",
                    file_path=str(endpoints_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor='"Cache-Control": "no-store"',
                    description="FHIR export response lacks strict no-store cache control header.",
                    impact="Sensitive PHI could be cached in intermediate proxies or browser history.",
                    remediation='Set "Cache-Control": "no-store" in export Response headers.',
                )
            )

        # Check import idempotency key & digest
        if "bundle_digest" not in content or "Idempotency-Key" not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-END-05",
                    title="Import endpoint missing cryptographic idempotency digest",
                    severity="HIGH",
                    category="ENDPOINT_GATE",
                    file_path=str(endpoints_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="bundle_digest",
                    description="Import endpoint does not bind Idempotency-Key to raw bundle SHA-256 digest.",
                    impact="Vulnerable to duplicate draft injection and replay desynchronization.",
                    remediation="Compute hashlib.sha256(raw).hexdigest() and pass as idempotency payload.",
                )
            )

        # Check IPS fail-closed gate
        if "ips_conformance_not_approved" not in content:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-END-06",
                    title="IPS export endpoint does not fail closed",
                    severity="HIGH",
                    category="ENDPOINT_GATE",
                    file_path=str(endpoints_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="ips_conformance_not_approved",
                    description="export_ips does not fail closed with HTTP 409.",
                    impact="Could falsely advertise IPS conformance without regulatory and terminology clearance.",
                    remediation="Raise HTTPException 409 with ips_conformance_not_approved.",
                )
            )

    def _audit_untrusted_staging_and_quarantine(self) -> None:
        """Verify imported resources never auto-confirm health truth."""
        module_file = self.repo_root / "services/api/src/clara_api/lifemap/fhir_r4.py"
        if not module_file.exists():
            return

        content = module_file.read_text(encoding="utf-8")

        # import_candidates must filter out metadata resources
        filtered_types = ["Provenance", "Consent", "AuditEvent", "Composition"]
        missing_filters = [t for t in filtered_types if f'"{t}"' not in content or "import_candidates" not in content]
        if missing_filters:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-QUAR-01",
                    title="Metadata resources not filtered from clinical candidates",
                    severity="HIGH",
                    category="INVARIANTS",
                    file_path=str(module_file.relative_to(self.repo_root)),
                    line_number=None,
                    code_anchor="import_candidates",
                    description=f"import_candidates does not exclude {missing_filters} from capture queue.",
                    impact="Non-clinical metadata resources could pollute clinical capture inbox.",
                    remediation="Ensure Provenance, Consent, AuditEvent, Composition are omitted from candidates.",
                )
            )

    def _audit_fixture_manifest_and_hashes(self) -> None:
        """Verify fixture manifest integrity and SHA-256 preservation."""
        manifest_path = self.repo_root / "evaluation/fhir_conformance/fixtures/manifest.json"
        if not manifest_path.exists():
            return

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            fixtures = data.get("fixtures", [])
            package_dir = manifest_path.parent.parent

            for fix in fixtures:
                rel_path = fix.get("path")
                expected_sha = fix.get("sha256")
                if not rel_path or not expected_sha:
                    continue
                file_path = package_dir / rel_path
                if not file_path.exists():
                    self.findings.append(
                        ConformanceFinding(
                            rule_id="FHIR-FIX-01",
                            title=f"Missing fixture file: {rel_path}",
                            severity="HIGH",
                            category="FIXTURE_STABILITY",
                            file_path=str(manifest_path.relative_to(self.repo_root)),
                            line_number=None,
                            code_anchor=rel_path,
                            description=f"Declared fixture {rel_path} does not exist on disk.",
                            impact="Breaks conformance suite execution.",
                            remediation="Restore missing fixture file.",
                        )
                    )
                    continue

                actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
                if actual_sha != expected_sha:
                    self.findings.append(
                        ConformanceFinding(
                            rule_id="FHIR-FIX-02",
                            title=f"Fixture hash drift: {rel_path}",
                            severity="HIGH",
                            category="FIXTURE_STABILITY",
                            file_path=str(file_path.relative_to(self.repo_root)),
                            line_number=None,
                            code_anchor=f"expected {expected_sha[:8]} got {actual_sha[:8]}",
                            description=f"Fixture content has drifted from declared manifest hash.",
                            impact="Invalidates sealed conformance baselines.",
                            remediation="Restore unmodified fixture or update manifest via freeze script.",
                        )
                    )
        except Exception as e:
            self.findings.append(
                ConformanceFinding(
                    rule_id="FHIR-FIX-03",
                    title="Failed to evaluate fixture manifest",
                    severity="MEDIUM",
                    category="FIXTURE_STABILITY",
                    file_path=str(manifest_path.relative_to(self.repo_root)),
                    line_number=1,
                    code_anchor="json.loads",
                    description=f"Manifest evaluation error: {e}",
                    impact="Fixture verification skipped.",
                    remediation="Fix syntax error in fixtures/manifest.json.",
                )
            )


def format_text_report(findings: list[ConformanceFinding]) -> str:
    lines = [
        "=" * 80,
        "FHIR R4 VALIDATOR CONFORMANCE & SECURITY BOUNDARY AUDIT REPORT",
        "=" * 80,
        f"Total Findings Detected: {len(findings)}",
    ]

    severity_counts: dict[str, int] = {}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    lines.append("Severity Breakdown:")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        if sev in severity_counts:
            lines.append(f"  - {sev}: {severity_counts[sev]}")

    if not findings:
        lines.append("\n[PASS] All FHIR R4 security boundaries and conformance invariants verified.")
        lines.append("       Official validator pins, bounded gates, single-patient rules, and")
        lines.append("       anti-SSRF protections strictly comply with specification.")
        return "\n".join(lines)

    lines.append("\nDetailed Findings:")
    for f in findings:
        lines.extend([
            "-" * 80,
            f"[{f.severity}] {f.rule_id}: {f.title}",
            f"Category   : {f.category}",
            f"Location   : {f.file_path}:{f.line_number or 'N/A'}",
            f"Anchor     : {f.code_anchor}",
            f"Description: {f.description}",
            f"Impact     : {f.impact}",
            f"Remediation: {f.remediation}",
        ])

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit FHIR R4 validator conformance and security boundaries.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root path (default: current working directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings in JSON format",
    )
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Exit with non-zero status if CRITICAL or HIGH findings exist",
    )
    parser.add_argument(
        "--verify-fixtures",
        action="store_true",
        default=True,
        help="Verify fixture file existence and SHA-256 stability",
    )

    args = parser.parse_args(argv)

    auditor = FhirConformanceAuditor(args.repo_root)
    findings = auditor.audit_all(verify_fixtures=args.verify_fixtures)

    if args.json:
        payload = {
            "findings_count": len(findings),
            "findings": [asdict(f) for f in findings],
            "passed": len(findings) == 0,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(format_text_report(findings))

    if args.fail_on_high:
        has_high_or_crit = any(f.severity in ("CRITICAL", "HIGH") for f in findings)
        return 1 if has_high_or_crit else 0

    return 0 if len(findings) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
