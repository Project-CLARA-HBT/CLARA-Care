# Adversarial Audit: Legacy Column Equivalence vs Governed Organization Model (PH44)

## Executive Summary
This hostile adversarial audit refutes the assumption that appending an unstructured `tenant_id` string column to database tables constitutes an adequate multi-tenant security architecture.

## Comparison: Flat Column vs Governed Organization Model

| Evaluation Dimension | Legacy Flat `tenant_id` Column | Governed Organization Model (`PH44`) | Security Assessment |
|---|---|---|---|
| **Identity Validation** | Free-text string, no FK | Foreign key to `control_tenants.id` with slug format rules | **VULNERABLE (Legacy):** Allows arbitrary typo-tenants and SQL injection tokens. |
| **Lifecycle State** | No status; always implicitly active | Explicit `status`: `ONBOARDING`, `ACTIVE`, `SUSPENDED` | **VULNERABLE (Legacy):** Cannot suspend compromised organization without table-wide lock. |
| **Membership & Role Binding** | Inferred from token subject | Explicit `control_role_bindings` with JSON permission scopes | **VULNERABLE (Legacy):** Subject to token role confusion attacks. |
| **Invitation Security** | Unsigned or static links | Cryptographically signed, email-bound, single-use tokens | **VULNERABLE (Legacy):** Reusable invite links lead to staff enumeration. |
| **Quota Enforcement** | None (unbounded growth) | Strict `max_workspaces` and `max_users` ceiling checks | **VULNERABLE (Legacy):** Resource exhaustion and multi-tenant noisy neighbor DoS. |

## Hostile Findings
1. **Unbounded Growth Attack:** Creating 10,000 workspaces under a flat `tenant_id` was previously permitted. Under PH44, `TenantGovernor` halts creation when `max_workspaces` is reached.
2. **Suspension Bypass Test:** Modifying local client storage to inject `X-CLARA-Organization-Id` for a suspended tenant fails closed; `TenantContext` raises `TenantSuspendedError` immediately upon query construction.
