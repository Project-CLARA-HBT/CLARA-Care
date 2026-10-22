# Control Plane Network Segmentation & SSO Threat Model (PH41)

## Architecture Overview
The CLARA Care separates administrative control-plane governance from clinical data-plane processing through rigorous network segmentation, host-only SSO cookies, and zero-PHI database segregation.

## Threat Analysis & Countermeasures

### 1. Cross-Origin Session Hijacking & Subdomain Cookie Forgery
- **Threat Vector:** An attacker exploiting an XSS in a consumer web page attempts to forge or read administrative session cookies.
- **Countermeasure:** 
  - Administrative session cookies employ the `__Host-` prefix: `__Host-clara_admin_session`.
  - RFC 6265bis guarantees that `__Host-` cookies cannot be read, set, or overwritten by parent domains or sibling subdomains.
  - Enforces `SameSite=Strict`, `HttpOnly`, and `Secure` attributes unconditionally.

### 2. Network Segmentation Architecture
- **Data Plane (Ports 3000 / 8000 / 8010):**
  - Web client (`apps/web`) communicates with API Gateway (`services/api`) on port 8000.
  - API Gateway queries ML inference (`services/ml`) on internal port 8010 via `X-ML-Internal-Key`.
  - Database access restricted to clinical database (`DATABASE_URL`).
- **Control Plane (Ports 3100 / 8200):**
  - Admin client (`apps/admin`) communicates exclusively with Control Plane Gateway on port 8200.
  - Database access restricted to control database (`DATABASE_CONTROL_URL`).
  - **Invariant:** Control Plane has zero direct connection or network route to clinical database tables.

### 3. Inter-Plane Telemetry RPC Bridge
- When the Control Plane requires operational health metrics from the API Gateway:
  - It issues an authenticated HTTP request to `GET /system/telemetry/metrics` carrying `X-Control-Service-Token`.
  - The API Gateway validates the HMAC signature and timestamp (300s TTL).
  - Telemetry response is certified `zero_phi_certified=true`, emitting only system resource counters (CPU, RAM, Pool).

## Threat Matrix

| Threat ID | Description | Severity | Likelihood | Mitigation | Residual Risk |
|---|---|---|---|---|---|
| TM-CP-01 | Patient token presented to Admin API | Critical | Medium | Control plane validates dedicated admin user model; rejects patient JWTs | None |
| TM-CP-02 | Admin cookie leaked to consumer subdomains | High | Low | `__Host-` cookie prefix prevents domain inheritance | Negligible |
| TM-CP-03 | Control plane compromised to exfiltrate PHI | Critical | Low | Zero database network routing to clinical DB; RPC adapter emits no PHI | Negligible |
| TM-CP-04 | Replay of internal service tokens | High | Low | 300-second TTL + monotonic timestamp check | Low |
