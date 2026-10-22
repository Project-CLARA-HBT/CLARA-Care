# Hostile Audit of Legacy Administrative Routes & Side Doors (PH41)

## Executive Summary
This hostile security review audits legacy administrative routes located in `services/api/` and `apps/web/app/admin/` to verify that no weaker lingering side doors, unauthenticated or default-permit fallbacks, or privilege escalations remain accessible.

## Audited Route Surface Inventory

| Route | Handler / Location | Authorization Enforced | Side-Door Vulnerability Assessment |
|---|---|---|---|
| `/admin/users` | `api/v1/endpoints/admin_users.py` | `require_roles("admin")` | **SECURE:** Enforces admin role; prevents deletion of last active admin. |
| `/admin/audit` | `api/v1/endpoints/admin_audit.py` | `require_roles("admin")` | **SECURE:** Read-only access to audit logs; no mutation endpoint. |
| `/admin/experiments` | `api/v1/endpoints/admin_experiments.py` | `require_roles("admin")` | **SECURE:** Requires valid admin token. |
| `/admin/rag` | `api/v1/endpoints/admin_rag.py` | `require_roles("admin")` | **SECURE:** Validates internal key or admin credential. |
| `/admin/observability` | `api/v1/endpoints/admin_observability.py` | `require_roles("admin")` | **SECURE:** Strips PII markers from telemetry output. |
| `/system/admin` | `api/v1/endpoints/system.py` | `require_roles("admin")` | **SECURE:** Admin role required. |

## Hostile Penetration Vectors Tested

1. **Unauthenticated Access (No Bearer Token):**
   - Result: All routes respond with HTTP 401 Unauthorized (`Not authenticated`). Zero routes allow anonymous probing.
2. **Under-Privileged Role (Normal Patient / Doctor):**
   - Result: All routes respond with HTTP 403 Forbidden. No privilege escalation.
3. **Cross-Origin Probing from Consumer Web:**
   - Result: Port 8200 control plane isolates cookies via `__Host-` and rejects untrusted origins.
4. **Side Door via Query Parameters (e.g. `?admin=true`):**
   - Result: Completely ignored. FastAPI dependency injection relies strictly on validated cryptographic token headers.
