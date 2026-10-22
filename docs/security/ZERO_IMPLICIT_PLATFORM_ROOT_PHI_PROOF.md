# Zero Implicit Platform-Root PHI Permission Proof & Threat Model (PH43)

## Executive Summary
This security proof demonstrates that administrative platform-root credentials possess **zero implicit authority** over electronic health records (EHR), clinical notes, prescriptions, or patient identifying information (PHI).

## Formal Invariant Proof

### Invariant 1: Physical Database Segregation
- The Control Plane runs on isolated port 8200 and connects exclusively to `DATABASE_CONTROL_URL`.
- The database connection pool for the control plane possesses credentials only for control tables:
  ```sql
  control_tenants, control_admin_users, control_admin_sessions,
  control_audit_logs, control_role_bindings, control_feature_flags
  ```
- **Proof:** Even if an administrative SQL injection or root compromised account is achieved, the database user has zero grant permissions or schema existence on the data plane tables (`phr_records`, `lifemap_events`, `medicine_cabinets`, `users`).

### Invariant 2: Deny-by-Default Control Plane Policy Engine
- `ControlPolicyEvaluator.evaluate()` checks every requested action against an explicit allowlist.
- Invariant check:
  ```python
  if "phi:" in action or "clinical:patient" in action:
      return PolicyEvaluationResult(decision="DENY", reason="INVARIANT_VIOLATION")
  ```
- **Proof:** There is no code path or role (including `platform_admin`) that maps to a clinical read action.

### Invariant 3: Tenant Boundary Scoping (ABAC)
- All tenant operations require `target_tenant_id` to be explicitly bound in the user's `ControlRoleBinding` records.
- Cross-tenant requests unconditionally return `CROSS_TENANT_FORBIDDEN` (HTTP 403).

## Threat Matrix

| Attack Scenario | Attacker Capability | Target Asset | Defense Mechanism | Verdict |
|---|---|---|---|---|
| Platform root tries to read patient dossier | Valid platform_admin JWT | Patient PHR Record | Database disconnection + policy engine denial | BLOCKED |
| Compromised tenant admin queries peer clinic | Valid tenant_admin session | Peer Tenant Workspaces | `target_tenant_id not in authorized_tenants` | BLOCKED |
| SQL injection on control API | SQL injection exploit | Clinical DB tables | Physical DB host/instance separation | BLOCKED |
