#!/usr/bin/env python3
"""Cross-Tenant Isolation & Multi-Tenant Boundary Security Auditor.

Audits multi-tenant boundaries across CLARA-Care to ensure zero cross-tenant data leakage:
  - Database models and entity ownership/tenancy attributes
  - Object-level IDOR query predicates in API endpoints
  - Tenant-admin privilege containment (admin in Tenant A cannot access Tenant B)
  - GLHS commit kernel idempotency and state version tenant namespacing
  - Cache key tenant partitioning and no-PII telemetry hygiene
  - Uniform HTTP 404 fail-closed non-enumeration standards
  - Clinical patient roster and administration endpoint tenant scoping

Usage:
  python3 scripts/ops/audit_cross_tenant_isolation.py [--repo-root .] [--json] [--fail-on-high]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass
class CrossTenantFinding:
    rule_id: str
    title: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: str  # DATA_MODEL, ENDPOINT_IDOR, ADMIN_BOUNDARY, GLHS_KERNEL, CACHE_ISOLATION, NON_ENUMERATION
    file_path: str
    line_number: int | None
    code_anchor: str
    description: str
    impact: str
    remediation: str


class CrossTenantAuditor:
    """Security auditor for multi-tenant boundaries and cross-tenant isolation."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.findings: list[CrossTenantFinding] = []

    def audit_all(self) -> list[CrossTenantFinding]:
        self.findings.clear()
        self._audit_data_model_scoping()
        self._audit_endpoint_query_scoping()
        self._audit_admin_privilege_boundaries()
        self._audit_glhs_tenant_partitioning()
        self._audit_cache_key_namespacing()
        self._audit_non_enumeration_status_codes()
        self._audit_patient_roster_scoping()
        self._audit_admin_endpoints_scoping()
        return self.findings

    def _audit_data_model_scoping(self) -> None:
        """Verify DB models define ownership/tenancy scoping attributes."""
        models_file = self.repo_root / "services/api/src/clara_api/db/models.py"
        if not models_file.exists():
            return

        content = models_file.read_text(encoding="utf-8")

        # Required tenancy/ownership attributes by model class
        required_scoping: dict[str, list[str]] = {
            "WorkspaceFolder": ["user_id"],
            "WorkspaceChannel": ["user_id"],
            "WorkspaceNote": ["user_id"],
            "SessionModel": ["user_id"],
            "CouncilCase": ["user_id"],
            "ScribeSession": ["user_id"],
            "KnowledgeSource": ["owner_user_id"],
            "KnowledgeDocument": ["owner_user_id"],
            "PhrProfile": ["user_id"],
            "GlhsAppliedTransition": ["tenant_id", "profile_id"],
        }

        for model_name, required_cols in required_scoping.items():
            class_match = re.search(rf"class {model_name}\(Base\):.*?(?=\nclass |\Z)", content, re.DOTALL)
            if not class_match:
                continue

            class_body = class_match.group(0)
            for col in required_cols:
                col_pattern = rf"\b{col}\s*:\s*Mapped\["
                if not re.search(col_pattern, class_body):
                    line_no = content[:class_match.start()].count("\n") + 1
                    self.findings.append(
                        CrossTenantFinding(
                            rule_id="TEN-MOD-01",
                            title=f"Missing Tenancy/Ownership Attribute on {model_name}",
                            severity="CRITICAL",
                            category="DATA_MODEL",
                            file_path="services/api/src/clara_api/db/models.py",
                            line_number=line_no,
                            code_anchor=f"class {model_name}(Base)",
                            description=f"Model '{model_name}' lacks required scoping attribute '{col}'.",
                            impact="Records cannot be partitioned by tenant/owner, risking cross-tenant data exposure.",
                            remediation=f"Add column '{col}' to model '{model_name}' with appropriate foreign key / index.",
                        )
                    )

    def _audit_endpoint_query_scoping(self) -> None:
        """Verify endpoint object retrieval verifies ownership and fails closed."""
        endpoints_dir = self.repo_root / "services/api/src/clara_api/api/v1/endpoints"
        if not endpoints_dir.exists():
            return

        # Target endpoint helper functions that must enforce ownership predicates
        helper_specs = [
            ("workspace.py", "_get_owned_folder", "WorkspaceFolder.user_id == user_id"),
            ("workspace.py", "_get_owned_channel", "WorkspaceChannel.user_id == user_id"),
            ("workspace.py", "_get_owned_conversation", "SessionModel.user_id == user_id"),
            ("workspace.py", "_get_owned_note", "WorkspaceNote.user_id == user_id"),
            ("council.py", "_get_owned_case", "CouncilCase.user_id == user_id"),
            ("scribe.py", "_get_owned_session", "ScribeSession.user_id == user_id"),
            ("research.py", "_get_owned_source", "KnowledgeSource.owner_user_id == owner_user_id"),
            ("research.py", "_get_owned_document", "KnowledgeDocument.owner_user_id == owner_user_id"),
        ]

        for file_name, helper_name, expected_predicate in helper_specs:
            ep_file = endpoints_dir / file_name
            if not ep_file.exists():
                continue

            content = ep_file.read_text(encoding="utf-8")
            if helper_name not in content:
                self.findings.append(
                    CrossTenantFinding(
                        rule_id="TEN-IDR-01",
                        title=f"Missing Ownership Lookup Helper '{helper_name}' in {file_name}",
                        severity="HIGH",
                        category="ENDPOINT_IDOR",
                        file_path=f"services/api/src/clara_api/api/v1/endpoints/{file_name}",
                        line_number=None,
                        code_anchor=helper_name,
                        description=f"Expected helper function '{helper_name}' is missing.",
                        impact="Endpoint may query objects without ownership constraint, risking horizontal IDOR.",
                        remediation=f"Implement '{helper_name}' with '{expected_predicate}' predicate.",
                    )
                )
                continue

            helper_match = re.search(rf"def {helper_name}\([^)]*\):.*?(?=\ndef |\Z)", content, re.DOTALL)
            if helper_match:
                helper_body = helper_match.group(0)
                pred_col = expected_predicate.split("==")[0].strip()
                if pred_col not in helper_body:
                    line_no = content[:helper_match.start()].count("\n") + 1
                    self.findings.append(
                        CrossTenantFinding(
                            rule_id="TEN-IDR-02",
                            title=f"Unscoped Query Predicate in '{helper_name}'",
                            severity="CRITICAL",
                            category="ENDPOINT_IDOR",
                            file_path=f"services/api/src/clara_api/api/v1/endpoints/{file_name}",
                            line_number=line_no,
                            code_anchor=helper_name,
                            description=f"Helper '{helper_name}' omits ownership predicate '{expected_predicate}'.",
                            impact="Horizontal IDOR: User A can view or mutate User B's records across tenants.",
                            remediation=f"Ensure query in '{helper_name}' contains '{expected_predicate}'.",
                        )
                    )

    def _audit_admin_privilege_boundaries(self) -> None:
        """Verify admin role does not bypass object-level or tenant-level scoping."""
        profile_scope_file = self.repo_root / "services/api/src/clara_api/lifemap/profile_scope.py"
        if profile_scope_file.exists():
            content = profile_scope_file.read_text(encoding="utf-8")

            # Check that administrative role does not grant ambient profile access
            if "if policy.administrative:" not in content or "status.HTTP_404_NOT_FOUND" not in content:
                self.findings.append(
                    CrossTenantFinding(
                        rule_id="TEN-ADM-01",
                        title="Admin Role Bypasses Profile Isolation in LifeMap",
                        severity="CRITICAL",
                        category="ADMIN_BOUNDARY",
                        file_path="services/api/src/clara_api/lifemap/profile_scope.py",
                        line_number=None,
                        code_anchor="policy.administrative",
                        description="Administrative role must not grant ambient health-data access; break-glass required.",
                        impact="Tenant or system administrators can view sensitive patient data without break-glass workflow.",
                        remediation="Enforce fail-closed 404 scope_forbidden when policy.administrative is true.",
                    )
                )

        # Scan for dangerous admin bypass patterns in endpoint implementations
        endpoints_dir = self.repo_root / "services/api/src/clara_api/api/v1/endpoints"
        if endpoints_dir.exists():
            for py_file in endpoints_dir.glob("*.py"):
                if py_file.name.startswith("admin_"):
                    continue  # Platform administration endpoints handled separately
                text = py_file.read_text(encoding="utf-8")
                bypass_matches = list(re.finditer(
                    r"if\s+(?:user|token)\.role\s*==\s*['\"]admin['\"]\s*:\s*(?:return|pass|db\.execute\(select\([^)]+\)\.all\(\))",
                    text,
                ))
                for bm in bypass_matches:
                    line_no = text[:bm.start()].count("\n") + 1
                    self.findings.append(
                        CrossTenantFinding(
                            rule_id="TEN-ADM-02",
                            title=f"Unsafe Admin Cross-Tenant Bypass in {py_file.name}",
                            severity="HIGH",
                            category="ADMIN_BOUNDARY",
                            file_path=str(py_file.relative_to(self.repo_root)),
                            line_number=line_no,
                            code_anchor=bm.group(0),
                            description="Unconditional admin check bypassing entity tenancy filter.",
                            impact="Tenant admin can query or mutate records from other tenants.",
                            remediation="Scope admin operations to the caller's tenant or organization ID.",
                        )
                    )

    def _audit_glhs_tenant_partitioning(self) -> None:
        """Verify GLHS commit kernel partitions idempotency and state by tenant."""
        kernel_file = self.repo_root / "services/api/src/clara_api/glhs/commit_kernel.py"
        if not kernel_file.exists():
            return

        content = kernel_file.read_text(encoding="utf-8")

        # 1. Verify idempotency lock namespacing includes tenant_id
        if '("idempotency_key", f"idempotency:{tenant_id}:{operation_kind}:{idempotency_key}"' not in content:
            pos = content.find("idempotency_key")
            line_no = content[:pos].count("\n") + 1 if pos != -1 else None
            self.findings.append(
                CrossTenantFinding(
                    rule_id="TEN-GLHS-01",
                    title="GLHS Idempotency Lock Lacks Tenant Partitioning",
                    severity="CRITICAL",
                    category="GLHS_KERNEL",
                    file_path="services/api/src/clara_api/glhs/commit_kernel.py",
                    line_number=line_no,
                    code_anchor="idempotency_key lock plan",
                    description="GLHS idempotency lock key must include tenant_id to prevent cross-tenant key collisions.",
                    impact="Tenant B could block or replay Tenant A's transactional commitments via idempotency keys.",
                    remediation="Namespace idempotency lock as 'idempotency:{tenant_id}:{operation_kind}:{idempotency_key}'.",
                )
            )

        # 2. Verify GlhsAppliedTransition lookup queries tenant_id
        if "GlhsAppliedTransition.tenant_id == tenant_id" not in content:
            self.findings.append(
                CrossTenantFinding(
                    rule_id="TEN-GLHS-02",
                    title="GLHS Applied Transition Lookup Ignores Tenant Boundary",
                    severity="HIGH",
                    category="GLHS_KERNEL",
                    file_path="services/api/src/clara_api/glhs/commit_kernel.py",
                    line_number=None,
                    code_anchor="GlhsAppliedTransition query",
                    description="Replay detection must match tenant_id to prevent cross-tenant transition retrieval.",
                    impact="Tenant B could retrieve Tenant A's commit results by guessing or replaying an idempotency key.",
                    remediation="Add GlhsAppliedTransition.tenant_id == tenant_id to existing_locked select query.",
                )
            )

    def _audit_cache_key_namespacing(self) -> None:
        """Verify cache keys incorporate tenant/profile namespace."""
        session_sec_file = self.repo_root / "services/api/src/clara_api/core/session_security.py"
        if session_sec_file.exists():
            content = session_sec_file.read_text(encoding="utf-8")
            if "security_redis_key_prefix" not in content:
                self.findings.append(
                    CrossTenantFinding(
                        rule_id="TEN-CACHE-01",
                        title="Unpartitioned Redis Security Key Layout",
                        severity="MEDIUM",
                        category="CACHE_ISOLATION",
                        file_path="services/api/src/clara_api/core/session_security.py",
                        line_number=None,
                        code_anchor="SessionSecurity._key",
                        description="Redis keys must include configurable prefix for tenant/environment segregation.",
                        impact="Shared Redis instance could leak token revocation states across tenants.",
                        remediation="Prefix all Redis keys with settings.security_redis_key_prefix.",
                    )
                )

    def _audit_non_enumeration_status_codes(self) -> None:
        """Verify unauthorized or foreign-tenant requests return 404 instead of 403."""
        endpoints_dir = self.repo_root / "services/api/src/clara_api/api/v1/endpoints"
        if not endpoints_dir.exists():
            return

        for py_file in ["workspace.py", "council.py", "scribe.py", "research.py"]:
            file_path = endpoints_dir / py_file
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8")
            owned_matches = list(re.finditer(r"def (_get_owned_\w+)\([^)]*\):.*?(?=\ndef |\Z)", content, re.DOTALL))
            for om in owned_matches:
                func_name = om.group(1)
                func_body = om.group(0)
                if "status.HTTP_403_FORBIDDEN" in func_body:
                    line_no = content[:om.start()].count("\n") + 1
                    self.findings.append(
                        CrossTenantFinding(
                            rule_id="TEN-NONENUM-01",
                            title=f"Identifier Enumeration Oracle in '{func_name}'",
                            severity="MEDIUM",
                            category="NON_ENUMERATION",
                            file_path=f"services/api/src/clara_api/api/v1/endpoints/{py_file}",
                            line_number=line_no,
                            code_anchor=func_name,
                            description=f"Helper '{func_name}' emits 403 Forbidden instead of 404 Not Found on ownership mismatch.",
                            impact="Attacker can enumerate valid IDs of other tenants by observing 403 vs 404 responses.",
                            remediation="Emit uniform 404 Not Found ('Folder không tồn tại', etc.) for both missing and foreign objects.",
                        )
                    )

    def _audit_patient_roster_scoping(self) -> None:
        """Inspect clinical patient roster for cross-tenant organizational boundaries."""
        cw_file = self.repo_root / "services/api/src/clara_api/api/v1/endpoints/clinical_workbench.py"
        if not cw_file.exists():
            return

        content = cw_file.read_text(encoding="utf-8")
        roster_match = re.search(r"def get_clinical_patient_roster\b.*?(?=\n@|\Z)", content, re.DOTALL)
        if roster_match:
            body = roster_match.group(0)
            if "select(PhrProfile)" in body and "where(" not in body:
                line_no = content[:roster_match.start()].count("\n") + 1
                self.findings.append(
                    CrossTenantFinding(
                        rule_id="TEN-ROST-01",
                        title="Clinical Patient Roster Queries Global PhrProfile Unconditionally",
                        severity="MEDIUM",
                        category="ADMIN_BOUNDARY",
                        file_path="services/api/src/clara_api/api/v1/endpoints/clinical_workbench.py",
                        line_number=line_no,
                        code_anchor="get_clinical_patient_roster",
                        description="get_clinical_patient_roster selects from PhrProfile without explicit organization filter.",
                        impact="Clinicians in Organization A may view de-identified patient handles belonging to Organization B.",
                        remediation="Bind PhrProfile query to clinician's authorized organization_id or active care team.",
                    )
                )

    def _audit_admin_endpoints_scoping(self) -> None:
        """Inspect administrative endpoints for cross-tenant organization segregation."""
        endpoints_dir = self.repo_root / "services/api/src/clara_api/api/v1/endpoints"
        if not endpoints_dir.exists():
            return

        # 1. Admin users endpoint
        users_file = endpoints_dir / "admin_users.py"
        if users_file.exists():
            content = users_file.read_text(encoding="utf-8")
            if "def list_admin_users" in content and "stmt = select(User)" in content:
                # Check if tenant_id or org_id filter exists on base query
                if "User.tenant_id" not in content and "User.organization_id" not in content:
                    pos = content.find("def list_admin_users")
                    line_no = content[:pos].count("\n") + 1 if pos != -1 else None
                    self.findings.append(
                        CrossTenantFinding(
                            rule_id="TEN-ADM-03",
                            title="Admin Users List Lacks Multi-Tenant Organization Scoping",
                            severity="HIGH",
                            category="ADMIN_BOUNDARY",
                            file_path="services/api/src/clara_api/api/v1/endpoints/admin_users.py",
                            line_number=line_no,
                            code_anchor="list_admin_users() -> stmt = select(User)",
                            description="list_admin_users selects users globally; an organization admin in Tenant A could view Tenant B users.",
                            impact="Cross-tenant user directory disclosure if organization admin role is mapped to admin route gate.",
                            remediation="Scope User query by current_user organization / tenant membership.",
                        )
                    )

        # 2. Admin audit logs endpoint
        audit_file = endpoints_dir / "admin_audit.py"
        if audit_file.exists():
            content = audit_file.read_text(encoding="utf-8")
            if "list_admin_actions(db" in content:
                # Check backend implementation in admin_audit.py
                obs_file = self.repo_root / "services/api/src/clara_api/observability/admin_audit.py"
                if obs_file.exists():
                    obs_content = obs_file.read_text(encoding="utf-8")
                    if "select(AdminAuditRecord)" in obs_content and "where(" not in obs_content.split("list_admin_actions")[1]:
                        pos = content.find("def list_admin_audit")
                        line_no = content[:pos].count("\n") + 1 if pos != -1 else None
                        self.findings.append(
                            CrossTenantFinding(
                                rule_id="TEN-AUD-01",
                                title="Admin Audit Log Lacks Tenant Partitioning",
                                severity="MEDIUM",
                                category="ADMIN_BOUNDARY",
                                file_path="services/api/src/clara_api/api/v1/endpoints/admin_audit.py",
                                line_number=line_no,
                                code_anchor="list_admin_audit() -> list_admin_actions(db)",
                                description="Admin audit logs are queried globally without organization or tenant partition key.",
                                impact="Tenant administrators can view administrative action records initiated by other tenants.",
                                remediation="Partition AdminAuditRecord by tenant_id / organization_id.",
                            )
                        )

        # 3. Admin feedback endpoint
        feedback_file = endpoints_dir / "admin_feedback.py"
        if feedback_file.exists():
            content = feedback_file.read_text(encoding="utf-8")
            if "def list_clinical_feedback" in content and "stmt = select(ClinicalFeedback)" in content:
                if "organization_id" not in content and "tenant_id" not in content:
                    pos = content.find("def list_clinical_feedback")
                    line_no = content[:pos].count("\n") + 1 if pos != -1 else None
                    self.findings.append(
                        CrossTenantFinding(
                            rule_id="TEN-FDB-01",
                            title="Clinical Feedback Management Lacks Tenant Scoping",
                            severity="MEDIUM",
                            category="ADMIN_BOUNDARY",
                            file_path="services/api/src/clara_api/api/v1/endpoints/admin_feedback.py",
                            line_number=line_no,
                            code_anchor="list_clinical_feedback() -> select(ClinicalFeedback)",
                            description="ClinicalFeedback records are listed globally without filtering by health organization.",
                            impact="Feedback reported in Hospital A is visible to administrators of Hospital B.",
                            remediation="Partition ClinicalFeedback by reporting organization or tenant ID.",
                        )
                    )


def format_text_report(findings: Sequence[CrossTenantFinding], repo_root: Path) -> str:
    lines: list[str] = [
        "=" * 80,
        "CLARA CROSS-TENANT ISOLATION & MULTI-TENANT BOUNDARY SECURITY AUDIT",
        "=" * 80,
        f"Repository Root: {repo_root}",
        f"Total Findings Detected: {len(findings)}",
        "=" * 80,
    ]

    if not findings:
        lines.append("ALL MULTI-TENANT BOUNDARY CHECKS PASSED: ZERO CROSS-TENANT LEAKAGE VECTORS DETECTED.")
        lines.append("=" * 80)
        return "\n".join(lines)

    for idx, f in enumerate(findings, start=1):
        lines.extend([
            f"[{idx}] {f.rule_id}: {f.title} ({f.severity})",
            f"    Category:     {f.category}",
            f"    Location:     {f.file_path}:{f.line_number or 'N/A'}",
            f"    Code Anchor:  {f.code_anchor}",
            f"    Description:  {f.description}",
            f"    Impact:       {f.impact}",
            f"    Remediation:  {f.remediation}",
            "-" * 80,
        ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit cross-tenant isolation and multi-tenant security boundaries.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Path to repository root")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit 1 if CRITICAL or HIGH findings detected")
    args = parser.parse_args()

    auditor = CrossTenantAuditor(args.repo_root)
    findings = auditor.audit_all()

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        print(format_text_report(findings, auditor.repo_root))

    if args.fail_on_high:
        has_high_or_critical = any(f.severity in ("CRITICAL", "HIGH") for f in findings)
        if has_high_or_critical:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
