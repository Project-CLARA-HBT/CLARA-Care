# FHIR Endpoint Security Architecture & Implementation Guide

- **Phase:** PH11 — FHIR R4 interoperability production profiles
- **Document ID:** `docs/implementation/FHIR_ENDPOINT_SECURITY_ARCHITECTURE.md`
- **Agent:** A09 (Docs + research evidence)
- **Status:** Approved Engineering Implementation Guide
- **Target Audience:** Backend API engineers, security reviewers, DevOps and interoperability integrators

---

## 1. System Overview & Component Topology

CLARA Care exposes FHIR R4 interoperability endpoints through the `services/api` FastAPI gateway. The gateway mediates all requests between external clients (consumer web/mobile apps, hospital EHR systems, researcher pipelines) and internal domain stores (LifeMap, PHR, Clinical Capture, and Flow Event Engine).

```text
                                  ┌────────────────────────────────┐
                                  │   External SMART/FHIR Client   │
                                  │ (Mobile / Web / EHR Partner)   │
                                  └───────────────┬────────────────┘
                                                  │ HTTPS / TLS 1.3
                                                  ▼
                                  ┌────────────────────────────────┐
                                  │    Reverse Proxy / Ingress     │
                                  │  • TLS Termination & HSTS      │
                                  │  • IP Rate Limiting            │
                                  │  • Strip Spoofed X-Tenant-ID   │
                                  └───────────────┬────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Gateway (services/api)                                                          │
│                                                                                         │
│  1. AuthContextMiddleware (services/api/src/clara_api/core/rbac.py:60)                  │
│     • _has_bearer_scheme(request)                                                       │
│     • extract_bearer_token(request)                                                     │
│     • decode_access_token(token) with key rotation                                      │
│                                                                                         │
│  2. Token Denylist Check (services/api/src/clara_api/core/rbac.py:41)                   │
│     • _reject_if_revoked(payload) ──► Query Redis Denylist (jti)                        │
│                                                                                         │
│  3. RBAC Dependency Gate (services/api/src/clara_api/core/rbac.py:138)                  │
│     • require_roles("normal", "doctor", "researcher", "admin")                          │
│                                                                                         │
│  4. Tenant Boundary Gate (services/api/src/clara_api/core/tenant.py)                    │
│     • Enforce tenant_id match between token and target resource                         │
│     • Enforce invariant: platform_root_cannot_read_phi                                  │
│                                                                                         │
│  5. ABAC Profile Scope Gate (services/api/src/clara_api/lifemap/profile_scope.py:86)    │
│     • resolve_profile_scope(db, token, requested_profile, action, purpose)              │
│     • Verify ownership (is_owner) or active FamilyAccessGrant                           │
│     • Filter allowed data classes (lifemap, medications, visits, profile)               │
│                                                                                         │
│  6. SMART Scope Evaluation                                                              │
│     • Verify requested FHIR resource and CRUDS verb against granted scopes              │
│                                                                                         │
│  7. Domain Service & Concurrency (LifeMap / PHR / Capture)                              │
│     • If-Match ETag optimistic concurrency check                                        │
│     • Size and entry bounds check (MAX_BUNDLE_BYTES=1MB, MAX_ENTRIES=500)               │
│                                                                                         │
│  8. Audit & Telemetry Pipeline                                                          │
│     • Emit FHIR AuditEvent & Provenance                                                 │
│     • Emit Zero-PHI OpenTelemetry metrics                                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Request Lifecycle & Middleware Pipeline

### 2.1 Step-by-Step Processing Flow

Every incoming HTTP request destined for a FHIR endpoint undergoes an eight-stage security pipeline:

1. **Ingress Filtering & Header Normalization:**
   - Ingress verifies TLS 1.3 negotiation.
   - External headers such as `X-Tenant-ID`, `X-User-Role`, or `X-Internal-Secret` from public interfaces are stripped to prevent identity spoofing.

2. **Scheme Disambiguation (`_has_bearer_scheme`):**
   - The gateway inspects the `Authorization` header.
   - If the header begins with `Bearer ` (case-insensitive per RFC 7235), `_has_bearer_scheme` returns `True`.
   - **Critical Security Invariant:** If a Bearer header is present, authentication is bound exclusively to the bearer token. If the token is invalid, expired, or malformed, the gateway raises HTTP 401. It **never** falls back to an ambient browser session cookie.

3. **Cryptographic Signature & Rotation Verification (`decode_access_token`):**
   - The token is verified against the primary secret key `jwt_secret_key`.
   - If verification fails and a previous key `jwt_secret_key_previous` is configured (during key rotation overlap windows), the previous key is tried.
   - Claims validated: `iss` must match `settings.jwt_issuer`, `typ` must equal `"access"`, and `exp` must be strictly in the future.

4. **Revocation & Anti-Replay Gate (`_reject_if_revoked`):**
   - The token's unique identifier `jti` is checked against Redis via `session_security.is_revoked(jti)`.
   - If the token was revoked (e.g., user logout, password reset, administrative revocation), HTTP 401 is raised immediately.

5. **Tenant Isolation Enforcement:**
   - The tenant identifier in the token (`tenant_id`) is matched against the target resource's tenant boundary.
   - Requests attempting cross-tenant access are aborted with HTTP 404 to prevent tenant enumeration.

6. **ABAC Profile Scope Gate (`resolve_profile_scope`):**
   - The requested profile is verified. If the actor is the owner (`profile.user_id == actor.id`), owner permissions apply.
   - If the actor is a delegate (clinician, caregiver), the database is queried for an active, unexpired `FamilyAccessGrant`.
   - The request's `purpose` (`self_care`, `self_download`, `clinician_handoff`, `care_coordination`) must match allowed purposes.

7. **SMART Scope Verification:**
   - Granted scopes in the token (e.g., `patient/Observation.rs`) are matched against the target FHIR resource type and HTTP action.

8. **Payload Validation & Execution:**
   - Import payloads are restricted to 1,000,000 bytes and 500 entries.
   - Mutations check `If-Match` ETags against the database version.

---

## 3. SMART Scope Evaluation Engine

The SMART scope evaluation logic validates that the token carries sufficient permissions for the requested operation.

### 3.1 Scope Syntax Parser & Matching Algorithm

```python
import re
from typing import Set

# Regex pattern for SMART v1 and v2 scopes
SMART_SCOPE_PATTERN = re.compile(
    r"^(?P<context>patient|user|system)/"
    r"(?P<resource>[A-Za-z*]+)\."
    r"(?P<perms>[cruds*]+)"
    r"(?:\?(?P<params>.*))?$"
)

# HTTP Method to SMART permission mapping
HTTP_METHOD_PERMS = {
    "GET": {"r", "s"},
    "HEAD": {"r", "s"},
    "POST": {"c"},
    "PUT": {"u"},
    "PATCH": {"u"},
    "DELETE": {"d"},
}

def is_smart_scope_authorized(
    granted_scopes: set[str],
    context: str,
    resource_type: str,
    http_method: str,
) -> bool:
    """Evaluates whether granted SMART scopes permit the requested FHIR operation."""
    required_perms = HTTP_METHOD_PERMS.get(http_method.upper(), set())
    if not required_perms:
        return False

    for scope in granted_scopes:
        # Check classic v1 read/write scopes
        if scope in {f"{context}/*.read", f"{context}/*.*"} and required_perms.issubset({"r", "s"}):
            return True
        if scope in {f"{context}/*.write", f"{context}/*.*"} and not required_perms.issubset({"r", "s"}):
            return True

        match = SMART_SCOPE_PATTERN.match(scope)
        if not match:
            continue

        s_context = match.group("context")
        s_resource = match.group("resource")
        s_perms = match.group("perms")

        # Context match (patient, user, or system)
        if s_context != context:
            continue

        # Resource match (exact resource name or wildcard *)
        if s_resource != "*" and s_resource != resource_type:
            continue

        # Permission match
        if s_perms == "*":
            return True

        granted_perm_set = set(s_perms)
        if required_perms.issubset(granted_perm_set):
            return True

    return False
```

### 3.2 Granular Resource Rules

- **`MedicationRequest` Restriction:**
  - `MedicationRequest` creation is strictly gated: only tokens with `role == "doctor"` and possessing `user/MedicationRequest.c` are authorized.
  - Consumer tokens requesting `patient/MedicationRequest.*` receive HTTP 403 (`insufficient_scope`).
- **`Observation` Filtering:**
  - Queries for `Observation` only return confirmed records unless the client explicitly passes `include_unconfirmed=true` AND possesses clinical verification scopes (`user/*.rs`).

---

## 4. Anti-IDOR & Fails-Closed Confinement Pattern

To prevent Insecure Direct Object Reference (IDOR) attacks and resource enumeration:

1. **Uniform Fails-Closed 404 Response:**
   ```python
   def enforce_profile_boundary(scope: ProfileScope, target_profile_id: str) -> None:
       """Uniformly raises HTTP 404 on boundary violations to prevent resource discovery."""
       if scope.profile.public_id != target_profile_id:
           # Do NOT return 403 Forbidden: returning 403 confirms target_profile_id exists
           raise HTTPException(
               status_code=404,
               detail={"code": "scope_forbidden", "message": "Resource not found or outside authorized scope"}
           )
   ```

2. **Tenant ID Isolation:**
   - Database queries include `WHERE tenant_id = :tenant_id` at the lowest query layer.
   - Multi-tenant data models utilize composite primary keys `(tenant_id, id)` and PostgreSQL Row-Level Security (RLS) policies.

---

## 5. Concurrency Control & TOCTOU Safeguards

Time-of-Check to Time-of-Use (TOCTOU) race conditions are prevented through Optimistic Concurrency Control (OCC):

```python
def update_fhir_resource(
    db: Session,
    resource_id: str,
    incoming_payload: dict,
    if_match_header: str | None,
) -> dict:
    record = db.query(ResourceModel).filter_by(id=resource_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Resource not found")

    expected_etag = f'W/"{record.version_id}"'
    if not if_match_header or if_match_header.strip() != expected_etag:
        raise HTTPException(
            status_code=412,
            detail={
                "code": "concurrency_conflict",
                "message": f"Resource version mismatch. Current version: {record.version_id}"
            }
        )

    # Perform update and increment version
    record.version_id += 1
    record.payload = incoming_payload
    db.commit()
    return record.payload
```

---

## 6. Denial-of-Service (DoS) & Resource Safeguards

1. **Payload Size Restrictions:**
   - Maximum FHIR Bundle payload size is enforced at 1,000,000 bytes (`MAX_BUNDLE_BYTES`).
   - Payloads exceeding 1 MB are rejected with HTTP 413 (`Payload Too Large`).
2. **Entry Count & Nesting Limits:**
   - Bundles are limited to 500 entries (`MAX_ENTRIES`).
   - JSON nesting depth is limited to 20 levels (`MAX_DEPTH`) to prevent stack-overflow deserialization attacks.
   - Individual strings are capped at 20,000 characters (`MAX_STRING`).
3. **Rate Limiting:**
   - Public / Consumer endpoints: 60 requests/minute per authenticated user.
   - Machine-to-machine / System endpoints: 300 requests/minute per client ID.
   - Excess requests receive HTTP 429 (`Too Many Requests`) with a `Retry-After` header.

---

## 7. Audit Logging & Telemetry Implementation

### 7.1 FHIR AuditEvent Emission

Every FHIR export or clinical modification emits an immutable `AuditEvent`:

```json
{
  "resourceType": "AuditEvent",
  "id": "audit-8a3f912c-4b5e-4c8d-91a3-ef0218734a1b",
  "type": {
    "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
    "code": "rest",
    "display": "RESTful Operation"
  },
  "action": "R",
  "recorded": "2026-10-24T12:00:00Z",
  "outcome": "0",
  "agent": [
    {
      "type": {
        "coding": [
          {
            "system": "https://theclaracare.com/fhir/actor-role",
            "code": "owner"
          }
        ]
      },
      "who": {
        "identifier": {
          "system": "https://theclaracare.com/fhir/users",
          "value": "usr_94b8e210a4"
        }
      },
      "requestor": true
    }
  ],
  "source": {
    "observer": {
      "display": "clara-api"
    }
  },
  "entity": [
    {
      "what": {
        "reference": "https://theclaracare.com/fhir/Patient/pat_71a09ef2"
      },
      "type": {
        "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
        "code": "1",
        "display": "Person"
      }
    }
  ]
}
```

### 7.2 Zero-PII Telemetry Compliance

Telemetry metrics record operational performance without capturing sensitive clinical or identity attributes:

```python
from prometheus_client import Counter, Histogram

FHIR_REQUESTS_TOTAL = Counter(
    "clara_fhir_requests_total",
    "Total FHIR API operations processed",
    ["tenant_id", "endpoint", "resource_type", "http_status"],
)

FHIR_AUTH_FAILURES = Counter(
    "clara_fhir_auth_failures_total",
    "Total FHIR authentication and authorization failures",
    ["tenant_id", "failure_reason", "http_status"],
)

FHIR_DURATION_SECONDS = Histogram(
    "clara_fhir_request_duration_seconds",
    "Duration of FHIR API request processing in seconds",
    ["tenant_id", "endpoint", "resource_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
```

No patient names, emails, medical conditions, medication names, or prompt texts are registered as metric labels.
