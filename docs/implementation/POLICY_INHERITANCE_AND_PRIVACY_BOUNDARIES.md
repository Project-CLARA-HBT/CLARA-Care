# Administrative Policy Inheritance & Tenant Privacy Boundaries (PH43)

## Executive Summary
This research and operational specification establishes the formal model for policy inheritance, role binding delegation, and legal privacy boundaries across multi-tenant healthcare organizations in The CLARA Care.

## Policy Inheritance Hierarchy

The authorization model follows a strict hierarchical tree:

```text
[ Global Statutory Privacy Policy (Decree 13/2023/ND-CP) ]  <- Invariant Root (Non-Overridable)
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
[ Platform Governance Policy ]   [ Tenant Organization Policy ]
   • Account Lifecycle               • Workspace Quotas
   • MFA Enforcement                 • Staff Role Bindings
   • Ingress Key Rotation            • Retention Overrides (>= Statutory)
             │                           │
             └─────────────┬─────────────┘
                           ▼
              [ Active Role Evaluation ]
```

### Statutory Non-Overridable Invariants
1. **Consent Primacy:** No tenant or platform policy may process data without valid user consent.
2. **Right to Erasure (DSAR):** Patient data erasure requests must execute within 72 hours across all tenant workspaces.
3. **No Retaliation:** Withdrawal of optional research or sharing consent cannot alter access to core healthcare consultations.

## Tenant Isolation & Legal Boundaries
- Each B2B tenant organization (hospital, clinic, health network) represents an independent legal data controller or joint processor.
- Tenant administrators cannot grant themselves access to sibling tenant data.
- Platform administrators cannot access clinical patient records without explicit emergency break-glass procedures signed by clinical leadership.
