#!/usr/bin/env python3
"""Dependency integrity, unpinned dependency audit, and CVE triage verification.

Spec: PH01 / A07 (Tests + CI)
Audits:
  1. Direct dependency pinning across Python, Node, Flutter, and Dockerfile.
  2. Lockfile completeness and cryptographic hash integrity.
  3. Security advisory registry completeness and review freshness in
     docs/security/accepted-findings.md.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from generate_sbom import SbomBuilder

REQUIRED_ACCEPTED_FINDINGS_HEADERS = [
    "advisory id",
    "package / ecosystem",
    "surface",
    "severity",
    "disposition",
    "justification",
    "compensating control",
    "owner",
    "accepted on",
    "review date",
    "revisit condition",
    "suppression ref",
]


@dataclass
class UnpinnedDependency:
    surface: str
    ecosystem: str
    package: str
    declared_constraint: str
    resolved_version: str
    severity: str  # "HIGH", "MEDIUM", "LOW"
    recommendation: str


@dataclass
class AcceptedFindingRecord:
    advisory_id: str
    package: str
    surface: str
    severity: str
    disposition: str
    justification: str
    compensating_control: str
    owner: str
    accepted_on: str
    review_date: str
    revisit_condition: str
    suppression_ref: str
    is_expired: bool = False
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class IntegrityReport:
    generated_at: str
    repo_root: str
    total_components_checked: int
    direct_dependencies_count: int
    unpinned_count: int
    unpinned_dependencies: list[UnpinnedDependency] = field(default_factory=list)
    missing_lockfiles: list[str] = field(default_factory=list)
    lockfile_hash_coverage: dict[str, Any] = field(default_factory=dict)
    accepted_findings: list[AcceptedFindingRecord] = field(default_factory=list)
    expired_findings_count: int = 0
    findings_validation_errors: list[str] = field(default_factory=list)
    passed: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_accepted_findings(accepted_findings_path: Path, reference_date: datetime.date | None = None) -> tuple[list[AcceptedFindingRecord], list[str]]:
    """Parse and validate the active accepted findings table from accepted-findings.md."""
    if reference_date is None:
        reference_date = datetime.date.today()

    if not accepted_findings_path.is_file():
        return [], [f"Accepted findings register not found at {accepted_findings_path}"]

    content = accepted_findings_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    active_section = False
    table_lines: list[str] = []
    global_errors: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Active accepted / ignored findings"):
            active_section = True
            continue
        if active_section:
            if stripped.startswith("## ") and not stripped.startswith("## Active"):
                break
            if stripped.startswith("### ") or stripped.startswith("```"):
                break
            if stripped.startswith("|"):
                table_lines.append(stripped)

    if not table_lines:
        return [], ["No active findings table found under '## Active accepted / ignored findings'"]

    # Header row
    raw_header = [col.strip().lower() for col in table_lines[0].strip("|").split("|")]
    for expected in REQUIRED_ACCEPTED_FINDINGS_HEADERS:
        matched = any(expected in h for h in raw_header)
        if not matched:
            global_errors.append(f"Missing required column in accepted findings table: '{expected}'")

    records: list[AcceptedFindingRecord] = []
    # Skip header and separator row (| --- | --- | ...)
    for row_idx, row_str in enumerate(table_lines[2:], start=3):
        cells = [c.strip() for c in row_str.strip("|").split("|")]
        if not cells or len(cells) < len(REQUIRED_ACCEPTED_FINDINGS_HEADERS):
            continue
        advisory_id = cells[0]
        if advisory_id in ("_none yet_", "—", "", "-"):
            continue

        package_str = cells[1] if len(cells) > 1 else ""
        surface = cells[2] if len(cells) > 2 else ""
        severity = cells[3] if len(cells) > 3 else ""
        disposition = cells[4] if len(cells) > 4 else ""
        justification = cells[5] if len(cells) > 5 else ""
        compensating_control = cells[6] if len(cells) > 6 else ""
        owner = cells[7] if len(cells) > 7 else ""
        accepted_on = cells[8] if len(cells) > 8 else ""
        review_date_str = cells[9] if len(cells) > 9 else ""
        revisit_condition = cells[10] if len(cells) > 10 else ""
        suppression_ref = cells[11] if len(cells) > 11 else ""

        rec_errors: list[str] = []
        if not justification or justification == "—":
            rec_errors.append(f"Row {row_idx} ({advisory_id}): Missing justification")
        if not compensating_control or compensating_control == "—":
            rec_errors.append(f"Row {row_idx} ({advisory_id}): Missing compensating control")
        if not review_date_str or review_date_str == "—":
            rec_errors.append(f"Row {row_idx} ({advisory_id}): Missing review date")

        is_expired = False
        if review_date_str and review_date_str != "—":
            try:
                rev_date = datetime.date.fromisoformat(review_date_str)
                if rev_date < reference_date:
                    is_expired = True
            except ValueError:
                rec_errors.append(f"Row {row_idx} ({advisory_id}): Invalid ISO review date: {review_date_str}")

        record = AcceptedFindingRecord(
            advisory_id=advisory_id,
            package=package_str,
            surface=surface,
            severity=severity,
            disposition=disposition,
            justification=justification,
            compensating_control=compensating_control,
            owner=owner,
            accepted_on=accepted_on,
            review_date=review_date_str,
            revisit_condition=revisit_condition,
            suppression_ref=suppression_ref,
            is_expired=is_expired,
            validation_errors=rec_errors,
        )
        records.append(record)

    return records, global_errors


def run_dependency_integrity_audit(
    repo_root: Path,
    fail_unpinned: bool = False,
    fail_expired_findings: bool = False,
    reference_date: datetime.date | None = None,
) -> IntegrityReport:
    """Run full repository audit across Python, Node, Flutter."""
    builder = SbomBuilder(repo_root)
    builder.scan_all()

    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    report = IntegrityReport(
        generated_at=now_iso,
        repo_root=str(repo_root.resolve()),
        total_components_checked=len(builder.components),
        direct_dependencies_count=sum(1 for c in builder.components if c.direct),
        unpinned_count=0,
        missing_lockfiles=builder.missing_lockfiles,
    )

    # 1. Audit unpinned dependencies
    for c in builder.components:
        if c.direct and not c.pinned:
            # Assess severity and recommendation
            sev = "MEDIUM"
            rec = f"Pin {c.name} in {c.surface} to exact version '=={c.version}'"
            if c.surface == "services/ocr":
                sev = "HIGH"
                rec = "Replace unpinned 'RUN pip install ...' in Dockerfile with a versioned pyproject.toml or requirements.lock"
            elif c.scope == "required" and c.ecosystem == "npm":
                sev = "MEDIUM"
                rec = f"Pin {c.name} in apps/web/package.json to exact semver '{c.version}' without '^' prefix"
            elif c.scope == "required" and c.ecosystem == "pub":
                sev = "MEDIUM"
                rec = f"Pin {c.name} in apps/mobile/pubspec.yaml to exact version '{c.version}' without '^' prefix"

            dep = UnpinnedDependency(
                surface=c.surface,
                ecosystem=c.ecosystem,
                package=c.name,
                declared_constraint=c.constraint,
                resolved_version=c.version,
                severity=sev,
                recommendation=rec,
            )
            report.unpinned_dependencies.append(dep)

    report.unpinned_count = len(report.unpinned_dependencies)

    # 2. Check lockfile cryptographic hash integrity
    hashed_pkgs = sum(1 for c in builder.components if c.integrity_hash)
    report.lockfile_hash_coverage = {
        "components_with_cryptographic_hashes": hashed_pkgs,
        "total_components": len(builder.components),
        "hash_coverage_percentage": round(100.0 * hashed_pkgs / max(1, len(builder.components)), 2),
    }

    if report.missing_lockfiles:
        for m in report.missing_lockfiles:
            report.warnings.append(f"Surface lacks hermetic lockfile: {m}")

    # 3. Check accepted findings register
    accepted_path = repo_root / "docs/security/accepted-findings.md"
    findings, f_errors = parse_accepted_findings(accepted_path, reference_date=reference_date)
    report.accepted_findings = findings
    report.findings_validation_errors = f_errors

    expired_count = 0
    for f in findings:
        if f.is_expired:
            expired_count += 1
            report.warnings.append(
                f"Accepted finding {f.advisory_id} ({f.package}) review date expired on {f.review_date}"
            )
        if f.validation_errors:
            report.errors.extend(f.validation_errors)

    report.expired_findings_count = expired_count

    if f_errors:
        report.errors.extend(f_errors)

    if fail_unpinned and report.unpinned_count > 0:
        report.errors.append(f"Strict pinning check failed: found {report.unpinned_count} unpinned direct dependencies")

    if fail_expired_findings and expired_count > 0:
        report.errors.append(f"Strict review check failed: found {expired_count} expired accepted findings")

    if report.errors:
        report.passed = False

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=str(Path.cwd()),
        help="Path to repository root",
    )
    parser.add_argument(
        "--report-file",
        default=None,
        help="Optional path to write audit report (JSON format)",
    )
    parser.add_argument(
        "--fail-unpinned",
        action="store_true",
        help="Fail with exit code 1 if unpinned direct dependencies are found",
    )
    parser.add_argument(
        "--fail-expired-findings",
        action="store_true",
        help="Fail with exit code 1 if any accepted findings in docs/security/accepted-findings.md have expired",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode (fails on unpinned deps and expired findings)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    fail_unpinned = args.fail_unpinned or args.strict
    fail_expired = args.fail_expired_findings or args.strict

    report = run_dependency_integrity_audit(
        repo_root=repo_root,
        fail_unpinned=fail_unpinned,
        fail_expired_findings=fail_expired,
    )

    print("=" * 70)
    print("CLARA DEPENDENCY INTEGRITY & CVE TRIAGE AUDIT")
    print("=" * 70)
    print(f"Components checked:          {report.total_components_checked}")
    print(f"Direct dependencies:         {report.direct_dependencies_count}")
    print(f"Unpinned direct:             {report.unpinned_count}")
    print(f"Lockfile hash coverage:      {report.lockfile_hash_coverage.get('hash_coverage_percentage')}%")
    print(f"Active accepted findings:    {len(report.accepted_findings)}")
    print(f"Expired accepted findings:   {report.expired_findings_count}")
    print("-" * 70)

    if report.unpinned_dependencies:
        print("[UNPINNED DIRECT DEPENDENCIES SUMMARY]")
        for u in report.unpinned_dependencies[:10]:
            print(f"  - [{u.severity}] {u.surface} -> {u.package} ({u.declared_constraint}) resolved: {u.resolved_version}")
        if len(report.unpinned_dependencies) > 10:
            print(f"  ... and {len(report.unpinned_dependencies) - 10} more unpinned dependencies")
        print("-" * 70)

    if report.warnings:
        print("[WARNINGS]")
        for w in report.warnings:
            print(f"  [WARN] {w}")
        print("-" * 70)

    if report.errors:
        print("[ERRORS]", file=sys.stderr)
        for e in report.errors:
            print(f"  [FAIL] {e}", file=sys.stderr)
        print("-" * 70, file=sys.stderr)

    status_str = "PASS" if report.passed else "FAIL"
    print(f"OVERALL INTEGRITY STATUS: {status_str}")
    print("=" * 70)

    if args.report_file:
        out_p = Path(args.report_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        report_dict = asdict(report)
        out_p.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
        print(f"[AUDIT] Wrote report to {out_p}")

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
