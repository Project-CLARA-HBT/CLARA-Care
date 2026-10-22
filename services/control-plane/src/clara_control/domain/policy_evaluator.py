"""Control-Plane Policy Evaluation Service (RBAC & ABAC).

Spec: PH43 / A03 (Domain Service).
Enforces:
1. Deny-by-default evaluation for all administrative actions.
2. Tenant scoping: tenant_admin can only manage resources within authorized tenant_id.
3. Privilege elevation: destructive actions mandate step_up_level == "PRIVILEGED".
4. Zero implicit access: platform_admin cannot access patient clinical PHI records.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Literal

PolicyDecision = Literal["ALLOW", "DENY"]


@dataclasses.dataclass(frozen=True)
class PolicyEvaluationResult:
    decision: PolicyDecision
    reason: str
    action: str
    target_tenant_id: str | None


DESTRUCTIVE_ACTIONS = {
    "platform:tenants:suspend",
    "platform:tenants:delete",
    "platform:keys:rotate",
    "tenant:workspaces:delete",
}


class ControlPolicyEvaluator:
    """Evaluates administrative permissions against RBAC roles, tenant bindings, and MFA step-up state."""

    @staticmethod
    def evaluate(
        *,
        admin_role: str,  # "platform_admin", "tenant_admin", "auditor"
        action: str,
        target_tenant_id: str | None = None,
        authorized_tenant_ids: list[str] | None = None,
        step_up_level: str = "STANDARD",
    ) -> PolicyEvaluationResult:
        # 1. Reject any attempt to query clinical PHI through control plane
        if "phi:" in action or "clinical:patient" in action:
            return PolicyEvaluationResult(
                decision="DENY",
                reason="INVARIANT_VIOLATION: Control plane has zero authority over clinical patient PHI",
                action=action,
                target_tenant_id=target_tenant_id,
            )

        # 2. Destructive actions require PRIVILEGED step-up
        if action in DESTRUCTIVE_ACTIONS and step_up_level != "PRIVILEGED":
            return PolicyEvaluationResult(
                decision="DENY",
                reason="MFA_STEP_UP_REQUIRED: Action requires active PRIVILEGED session level",
                action=action,
                target_tenant_id=target_tenant_id,
            )

        # 3. Platform Admin Scope
        if admin_role == "platform_admin":
            if action.startswith("platform:"):
                return PolicyEvaluationResult(
                    decision="ALLOW",
                    reason="Authorized under platform administrator role",
                    action=action,
                    target_tenant_id=target_tenant_id,
                )
            if action.startswith("tenant:"):
                # Platform admin can inspect tenant governance metadata
                return PolicyEvaluationResult(
                    decision="ALLOW",
                    reason="Platform admin permitted tenant oversight",
                    action=action,
                    target_tenant_id=target_tenant_id,
                )

        # 4. Tenant Admin Scope
        if admin_role == "tenant_admin":
            if not target_tenant_id:
                return PolicyEvaluationResult(
                    decision="DENY",
                    reason="TENANT_SCOPE_REQUIRED: Action requires explicit tenant identifier",
                    action=action,
                    target_tenant_id=target_tenant_id,
                )
            if not authorized_tenant_ids or target_tenant_id not in authorized_tenant_ids:
                return PolicyEvaluationResult(
                    decision="DENY",
                    reason="CROSS_TENANT_FORBIDDEN: User lacks role binding for specified tenant",
                    action=action,
                    target_tenant_id=target_tenant_id,
                )
            if action.startswith("tenant:"):
                return PolicyEvaluationResult(
                    decision="ALLOW",
                    reason="Authorized under tenant role binding",
                    action=action,
                    target_tenant_id=target_tenant_id,
                )

        # 5. Auditor Scope (read-only)
        if admin_role == "auditor":
            if ":read" in action or action.endswith(":summary") or action.endswith(":health"):
                return PolicyEvaluationResult(
                    decision="ALLOW",
                    reason="Auditor read-only authorization granted",
                    action=action,
                    target_tenant_id=target_tenant_id,
                )

        return PolicyEvaluationResult(
            decision="DENY",
            reason="DENY_BY_DEFAULT: No matching authorization policy allows this action",
            action=action,
            target_tenant_id=target_tenant_id,
        )
