"""Control-Plane Tenant Governor Domain Service.

Enforces tenant lifecycle rules, operational quota thresholds,
and workspace boundary enforcement.
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class TenantQuotaCheck:
    allowed: bool
    current_count: int
    max_allowed: int
    reason: str


class TenantGovernor:
    """Domain governor managing tenant limits and operational bounds."""

    @staticmethod
    def evaluate_workspace_creation(current_workspaces: int, max_workspaces: int) -> TenantQuotaCheck:
        if current_workspaces >= max_workspaces:
            return TenantQuotaCheck(
                allowed=False,
                current_count=current_workspaces,
                max_allowed=max_workspaces,
                reason="Tenant workspace quota exhausted",
            )
        return TenantQuotaCheck(
            allowed=True,
            current_count=current_workspaces,
            max_allowed=max_workspaces,
            reason="Quota available",
        )

    @staticmethod
    def evaluate_user_membership(current_users: int, max_users: int) -> TenantQuotaCheck:
        if current_users >= max_users:
            return TenantQuotaCheck(
                allowed=False,
                current_count=current_users,
                max_allowed=max_users,
                reason="Tenant user seat quota exhausted",
            )
        return TenantQuotaCheck(
            allowed=True,
            current_count=current_users,
            max_allowed=max_users,
            reason="Seats available",
        )
