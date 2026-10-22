# Multi-Tenant Bleed, Malicious Organization Owner & Link Sharing Threat Model (PH44)

## Executive Summary
This threat specification analyzes vulnerabilities surrounding B2B tenant organization lifecycle, link sharing, cross-tenant bleed, and malicious organization administrator actions.

## Threat Vectors & Countermeasures

### 1. Cross-Tenant Data Bleed via Shared Database Queries
- **Threat Vector:** An attacker queries patient records without an explicit `tenant_id` filter, returning records from peer healthcare facilities.
- **Countermeasure:**
  - `RowScopedQueryAdapter` strictly prepends `WHERE tenant_id = :tenant_id` on all data plane clinical queries.
  - Omission of tenant context raises `TenantContextMissingError`.
  - Stale or mismatched tenant identifiers trigger `CrossTenantAccessViolation`.

### 2. Malicious Organization Owner Privilege Escalation
- **Threat Vector:** A rogue clinic administrator attempts to grant themselves `platform_admin` privileges or suspend peer clinics.
- **Countermeasure:**
  - The control plane enforces strict role boundaries: `tenant_admin` can only assign roles within the `tenant:*` scope.
  - Attempting to invoke `platform:*` actions fails closed with `DENY_BY_DEFAULT` (HTTP 403).
  - Destructive actions (`tenant:workspaces:delete`) require an active MFA step-up session (`step_up_level == "PRIVILEGED"`).

### 3. Invitation Link Interception & Public Sharing
- **Threat Vector:** A staff member posts an onboarding invitation link publicly or on an unencrypted communication channel.
- **Countermeasure:**
  - Invitation tokens bind to the recipient's explicit email address (`email` claim in token payload).
  - Redemption verifies that the authenticated user's email exactly matches the invitation payload.
  - Tokens expire after 24 hours (`ttl_seconds <= 86400`) and are invalidated upon first use.

## Threat Evaluation Matrix

| Threat ID | Threat Vector | Likelihood | Impact | Primary Defense | Residual Risk |
|---|---|---|---|---|---|
| TM-ORG-01 | Cross-tenant data bleed in clinical search | Low | Critical | `RowScopedQueryAdapter` mandatory filtering | None |
| TM-ORG-02 | Rogue clinic admin suspending peer clinic | Low | High | Tenant boundary enforcement in `ControlPolicyEvaluator` | None |
| TM-ORG-03 | Replaying leaked invitation link | Medium | High | Email binding + 24h expiration + single-use mark | Negligible |
| TM-ORG-04 | Deleted tenant data retained in live pool | Low | High | `ON DELETE CASCADE` + 72h permanent cryptographic wipe | Negligible |
