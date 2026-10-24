# SMART-on-FHIR OAuth2 / OIDC Scopes and Endpoint Security Architecture

- **Phase:** PH11 — FHIR R4 interoperability production profiles
- **Document ID:** `docs/interoperability/FHIR_SMART_AUTH_SCOPES_AND_ENDPOINT_SECURITY.md`
- **Agent:** A09 (Docs + research evidence)
- **Status:** Approved Architecture Specification
- **Security Baseline:** SMART App Launch Framework (v1.0.0 & v2.2.0), HL7 FHIR Release 4 (v4.0.1), RFC 6749, RFC 7636 (PKCE), RFC 7519 (JWT), RFC 7523 (JWT Profile for Client Authentication), OpenID Connect Core 1.0

---

## 1. Executive Summary & Security Baseline

This specification defines the authorization, authentication, and endpoint security architecture for HL7 FHIR R4 RESTful interoperability across the CLARA Care health AI platform.

CLARA Care operates as a Vietnamese, safety-first Medical AI Assistant — **a clinical assistant, not a doctor replacement**. All interoperability endpoints strictly preserve core safety invariants:
1. **RBAC & ABAC Gatekeeping:** `require_roles(...)` and `resolve_profile_scope(...)` enforce granular multi-tenant role and profile isolation.
2. **Patient Consent Gate:** Versioned medical consent precedes any access to or export of protected health information (PHI).
3. **Emergency Fast-Path:** Acute symptom presentation immediately halts background or export processing and triggers triage escalation.
4. **Prescribing Hard-Guard:** Machine learning models and self-declared consumer workflows are prohibited from generating clinician medication orders (`MedicationRequest`) or diagnostic conclusions.
5. **Bearer Scheme Isolation:** Explicit Bearer tokens are strictly parsed without silent fallback to browser cookie sessions; malformed or revoked Bearer tokens fail immediately with HTTP 401.
6. **No-PII Telemetry:** Telemetry metrics, distributed tracing spans, and system logs exclude PII and PHI (names, emails, prompts, clinical summaries, drug lists).

---

## 2. SMART-on-FHIR Scope Specification

CLARA Care implements both SMART-on-FHIR v1 scope strings and SMART-on-FHIR v2 granular syntax, enabling least-privilege delegation across consumer applications, clinician portals, and machine-to-machine integrations.

### 2.1 Scope Taxonomy & Syntax

SMART v2 scope grammar follows:

```text
<context> / <resource-type> . <cruds-permissions> [ ? <parameter-filter> ]
```

- **`<context>`**:
  - `patient`: Scope is restricted strictly to the in-context patient profile authorized during the SMART launch flow.
  - `user`: Scope is restricted to records the authenticated user is authorized to access across multiple patients (applicable to clinicians).
  - `system`: Scope is restricted to backend services acting autonomously without an active user context (system-to-system EHR integration via RFC 7523).
- **`<resource-type>`**: A supported FHIR R4 resource name (e.g., `Patient`, `Observation`, `Condition`, `MedicationStatement`, `AllergyIntolerance`, `DocumentReference`, `Binary`, `Consent`, `Provenance`, `AuditEvent`, `QuestionnaireResponse`, `CarePlan`, `Goal`) or wildcard `*`.
- **`<cruds-permissions>`**: One or more permission verbs:
  - `c`: Create new resource.
  - `r`: Read specific resource by ID or version.
  - `u`: Update existing resource (requires optimistic concurrency).
  - `d`: Delete/archive resource (prohibited for consumers on immutable health records).
  - `s`: Search resources of the given type.
  - Wildcard `*`: Equivalent to `cruds` (subject to role constraints).

### 2.2 SMART-on-FHIR Supported Scopes Matrix

| Scope Identifier | Target Persona | Permitted Operations | Safety & Regulatory Constraints |
|---|---|---|---|
| `launch` | Third-party EHR app | Resolve launch context from EHR session | Requires valid EHR session token; non-transferable |
| `launch/patient` | Mobile & Consumer apps | Select or bind patient context at authorization | Resolved against authenticated user's own profile or active Family grant |
| `openid` | All clients | Identity federation | Issues OIDC `id_token` asserting verified subject |
| `profile` | All clients | Basic profile claims | Emits non-PHI subject claims (`name`, `preferred_username`) |
| `fhirUser` | All clients | FHIR user identity URI | Emits URL to `Patient/{id}` or `Practitioner/{id}` |
| `patient/*.read` / `patient/*.rs` | Consumer / Family | Read and search all allowed clinical resources for target patient | Gated by medical consent; confined to caller's `ProfileScope` |
| `patient/Patient.rs` | Consumer / Family | Demographics read and search | Name, birth date, gender; administrative attributes only |
| `patient/Observation.rs` | Consumer / Family | Vitals and lab measurements | Confirmed measurements only; raw unverified capture drafts excluded |
| `patient/Condition.rs` | Consumer / Family | Active and historical health conditions | Standardized ICD-10 or verified self-reported conditions |
| `patient/MedicationStatement.rs` | Consumer / Family | Self-declared and confirmed medication courses | Emitted with clear self-reported attribution; not clinician orders |
| `patient/AllergyIntolerance.rs` | Consumer / Family | Recorded substance allergies and adverse reactions | Critical safety data; includes criticality and verification status |
| `patient/DocumentReference.rs` | Consumer / Family | Clinical documentation metadata | Points to encrypted, authenticated attachments |
| `patient/Binary.rs` | Consumer / Family | Document payloads and exported PDF/CCDA summaries | Validated MIME types only (`application/pdf`, `text/xml`) |
| `patient/*.write` / `patient/*.c` | Consumer / Capture | Submit external records into Universal Capture review | Untrusted external drafts only (`untrusted_external_draft`); never direct health truth |
| `user/*.read` / `user/*.rs` | Clinician (`doctor`) | Read clinical data for patients with active clinical relationship | Gated by patient consent, care-team grant, or emergency encounter override |
| `user/MedicationRequest.c` | Clinician (`doctor`) | Create verified clinician medication order | Strictly restricted to `doctor` role; requires clinical verification |
| `system/*.read` / `system/*.rs` | B2B / EHR Partner | Read cohort or cross-patient records for approved clinical purpose | Authenticated via mTLS + RFC 7523 JWT assertion; tenant isolated |
| `offline_access` | Native mobile apps | Mint refresh tokens for background synchronization | Requires refresh token rotation and replay prevention (`jti` tracking) |

### 2.3 Prohibited Scopes & Clinical Safeguards
- **`patient/MedicationRequest.write` / `patient/MedicationRequest.c`**: Strictly prohibited. End users and AI agents cannot create clinician prescription orders. Self-reported medications are projected exclusively as `MedicationStatement`.
- **`system/*.*` without Tenant Isolation**: Strictly prohibited. System tokens are unconditionally scoped to a single `tenant_id`. Cross-tenant system access is rejected at gateway admission.
- **`patient/*.d` (Consumer Delete)**: Strictly prohibited on immutable clinical lineage. Patients may withdraw consent or request erasure under DSAR protocols, but cannot arbitrarily delete historical audit trails or clinical observations.

---

## 3. RBAC & ABAC Access Policy Mapping

CLARA Care combines Role-Based Access Control (RBAC) with Attribute-Based Access Control (ABAC) to enforce multi-layered defense-in-depth.

```text
[ Client Request ]
       │
       ▼
┌──────────────────────────────────────────────┐
│ 1. Gateway RBAC Gate (require_roles)         │
│    • Validate JWT Bearer token               │
│    • Check actor role (normal/doctor/admin)   │
│    • Reject revoked tokens (Redis denylist)  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ 2. Tenant Boundary Gate (TenantScope)        │
│    • Verify tenant_id in token               │
│    • Platform root cannot read PHI           │
│    • Cross-tenant isolation                  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ 3. ABAC Profile Scope Gate                   │
│    (resolve_profile_scope)                   │
│    • Resolve requested profile               │
│    • Check account ownership (is_owner)      │
│    • Or verify active FamilyAccessGrant      │
│    • Verify Purpose of Use                   │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ 4. SMART Scope Filter                        │
│    • Verify requested resource in scope      │
│    • Verify requested CRUD action in scope   │
│    • Restrict fields based on data classes   │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
             [ Authorized Data Access ]
```

### 3.1 Role Hierarchy & Capabilities

1. **Consumer (`normal` role):**
   - Default identity for registered patients and family members.
   - Authorized Scopes: `openid`, `profile`, `email`, `fhirUser`, `launch/patient`, `patient/*.read`, `patient/*.c`, `offline_access`.
   - Access Boundary: Strictly limited to the user's own profile (`profile.user_id == actor.id`) or profiles with an active, unexpired `FamilyAccessGrant`.
   - Anti-IDOR Defense: Requesting a profile ID outside ownership or grant yields HTTP 404 (`scope_forbidden`) to prevent profile enumeration.

2. **Clinician (`doctor` role):**
   - Verified medical practitioners and hospital clinical staff.
   - Authorized Scopes: All consumer scopes plus `user/*.read`, `user/*.rs`, `user/MedicationRequest.c`, `user/MedicationStatement.*`.
   - Access Boundary: Requires active patient consent, care-team assignment, or documented clinical encounter handoff.

3. **Researcher (`researcher` role):**
   - Academic and clinical trial research personnel.
   - Authorized Scopes: `system/*.read` restricted to designated research study cohorts.
   - PHI Redaction: FHIR exports for researchers undergo deterministic pseudonymization, k-anonymity checks, and direct identifier redaction.

4. **Platform Administrator (`admin` role):**
   - Infrastructure, tenant configuration, and security operators.
   - Core Platform Invariant: **`platform_root_cannot_read_phi: true`**.
   - Administrators possess privileges to manage tenant metadata, rotate cryptographic keys, and review non-PHI audit journals (`platform:tenants:*`, `platform:keys:rotate`), but are cryptographically and logically barred from accessing patient FHIR resources.

### 3.2 Purpose of Use Confinement

Every FHIR export and query must supply an authorized clinical purpose:
- `self_care`: Direct personal health monitoring by the patient.
- `self_download`: Patient data portability export (e.g., LifeMap JSON/PDF export).
- `clinician_handoff`: Sharing summary data with a healthcare provider during consultation.
- `care_coordination`: Inter-professional exchange within an authorized care network.

Requests specifying an unrecognized or unapproved purpose fail closed with HTTP 422:
```json
{
  "code": "unsupported_export_purpose",
  "detail": "Purpose of use must be one of: self_care, self_download, clinician_handoff, care_coordination"
}
```

---

## 4. Endpoint Security Architecture

### 4.1 SMART Configuration Discovery Endpoint

In conformance with the SMART App Launch specification, the FHIR authorization server publishes metadata at `/.well-known/smart-configuration` and `/api/v1/fhir/.well-known/smart-configuration`.

#### Discovery Response Schema (`GET /.well-known/smart-configuration`):
```json
{
  "authorization_endpoint": "https://theclaracare.com/api/v1/auth/smart/authorize",
  "token_endpoint": "https://theclaracare.com/api/v1/auth/smart/token",
  "introspection_endpoint": "https://theclaracare.com/api/v1/auth/smart/introspect",
  "revocation_endpoint": "https://theclaracare.com/api/v1/auth/smart/revoke",
  "jwks_uri": "https://theclaracare.com/api/v1/auth/jwks.json",
  "capabilities": [
    "launch-standalone",
    "launch-ehr",
    "client-public",
    "client-confidential-symmetric",
    "client-confidential-asymmetric",
    "sso-openid-connect",
    "context-standalone-patient",
    "context-ehr-patient",
    "permission-patient",
    "permission-user",
    "permission-system",
    "permission-v2"
  ],
  "scopes_supported": [
    "openid",
    "profile",
    "email",
    "fhirUser",
    "launch",
    "launch/patient",
    "offline_access",
    "patient/*.read",
    "patient/*.rs",
    "patient/Patient.rs",
    "patient/Observation.rs",
    "patient/Condition.rs",
    "patient/MedicationStatement.rs",
    "patient/AllergyIntolerance.rs",
    "patient/DocumentReference.rs",
    "patient/Binary.rs",
    "patient/*.c",
    "user/*.read",
    "user/*.rs",
    "user/MedicationRequest.c",
    "system/*.read",
    "system/*.rs"
  ],
  "response_types_supported": [
    "code"
  ],
  "token_endpoint_auth_methods_supported": [
    "none",
    "client_secret_basic",
    "client_secret_post",
    "private_key_jwt"
  ],
  "token_endpoint_auth_signing_alg_values_supported": [
    "RS384",
    "ES384"
  ],
  "code_challenge_methods_supported": [
    "S256"
  ]
}
```

### 4.2 FHIR CapabilityStatement Security Conformance

The FHIR `CapabilityStatement` (`GET /api/v1/fhir/metadata`) declares security conformance under `rest.security`:

```json
{
  "service": [
    {
      "coding": [
        {
          "system": "http://hl7.org/fhir/restful-security-service",
          "code": "SMART-on-FHIR",
          "display": "SMART-on-FHIR"
        }
      ],
      "text": "OAuth2 with SMART-on-FHIR profiles and PKCE S256"
    }
  ],
  "extension": [
    {
      "url": "http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris",
      "extension": [
        {
          "url": "authorize",
          "valueUri": "https://theclaracare.com/api/v1/auth/smart/authorize"
        },
        {
          "url": "token",
          "valueUri": "https://theclaracare.com/api/v1/auth/smart/token"
        },
        {
          "url": "revoke",
          "valueUri": "https://theclaracare.com/api/v1/auth/smart/revoke"
        },
        {
          "url": "introspect",
          "valueUri": "https://theclaracare.com/api/v1/auth/smart/introspect"
        }
      ]
    }
  ],
  "description": "All FHIR endpoints require OAuth 2.0 Bearer tokens with SMART scopes. TLS 1.3 is enforced."
}
```

### 4.3 Bearer Token Handling & Anti-CSRF Invariants

1. **Strict Scheme Disambiguation (`_has_bearer_scheme`):**
   - Authentication scheme detection follows RFC 7235.
   - If an `Authorization: Bearer <token>` header is present, the request is handled strictly as Bearer authenticated.
   - If the token is invalid, expired, malformed, or revoked, the gateway returns HTTP 401 immediately.
   - Under no circumstances is a failing Bearer request silently downgraded to a browser cookie session.

2. **Revocation & Denylist Check (`_reject_if_revoked`):**
   - Access tokens contain a cryptographic identifier claim (`jti`).
   - Token revocation (upon logout, credential change, or session invalidation) places the `jti` in a distributed Redis security store with TTL matching the remaining token lifetime.
   - `get_current_token` verifies that `session_security.is_revoked(jti)` is false before granting endpoint access.

3. **CSRF Boundary Invariant:**
   - State-modifying requests (`POST`, `PUT`, `DELETE`, `PATCH`) utilizing cookie authentication must supply a cryptographically valid `X-CSRF-Token`.
   - Explicit Bearer token requests are exempt from CSRF checks because browsers do not attach custom `Authorization` headers across cross-origin requests without pre-flight CORS consent.

### 4.4 Transport Security & Cryptographic Controls

- **Transport Layer Security (TLS):** TLS 1.3 is mandatory on all external FHIR endpoints. TLS 1.2 is permitted only with approved forward-secrecy cipher suites (`ECDHE-RSA-AES256-GCM-SHA384`, `ECDHE-ECDSA-AES256-GCM-SHA384`). Plain HTTP is rejected with immediate HSTS redirect.
- **Mutual TLS (mTLS):** Required for all system-level B2B integrations (`system/*.read`). System clients must present client certificates signed by an authorized enterprise CA.
- **PKCE Enforcement:** Authorization code flow requires RFC 7636 Proof Key for Code Exchange (PKCE) with `code_challenge_method=S256`. Plain `code_challenge_method=plain` is rejected.
- **Client Assertion (RFC 7523):** Confidential clients authenticate to the token endpoint using asymmetric private keys (`private_key_jwt`) with RS384 or ES384 algorithms. Symmetric client secrets are deprecated for external integrations.

### 4.5 Anti-IDOR & Information Disclosure Defenses

- **Anti-Enumeration via Fails-Closed 404:**
  - When a caller requests a FHIR patient resource or export for an ID outside their authorized scope, the server returns HTTP 404 (`Not Found`) with a generic error code (`scope_forbidden`).
  - Returning HTTP 403 would disclose that the resource ID exists. Returning 404 prevents identifier enumeration attacks.
- **Zero-PHI Error Payloads:**
  - Diagnostic error details (e.g., `OperationOutcome.issue.diagnostics`) never expose patient names, internal primary keys, SQL traces, or medical terminology details.
  - Upstream error messages are sanitized before transmission.

### 4.6 Concurrency & TOCTOU Defenses

- **Optimistic Concurrency Control (OCC):**
  - All mutating FHIR operations (`PUT`, `DELETE`) require an `If-Match` header containing the resource's current version ID (`ETag: W/"<version>"`).
  - If the database version exceeds the provided `If-Match` version, the server aborts the mutation with HTTP 412 (`Precondition Failed`), preventing lost updates and race conditions.
- **Provenance Sealing:**
  - Every clinical mutation generates an immutable `Provenance` resource recording the actor, target resource version, cryptographic timestamp, and authorization scope.

---

## 5. Standardized Error Responses

All FHIR endpoints emit structured `OperationOutcome` or JSON error payloads adhering to standard HTTP status codes:

| HTTP Status | Error Code | Description | Example Detail |
|---|---|---|---|
| `401 Unauthorized` | `unauthorized` | Missing, expired, malformed, or revoked Bearer token | `{"code": "unauthorized", "message": "Token không hợp lệ hoặc đã hết hạn"}` |
| `403 Forbidden` | `insufficient_scope` | Token valid but lacks necessary SMART scope for operation | `{"code": "insufficient_scope", "detail": "Scope 'patient/Patient.rs' does not permit 'Observation' read"}` |
| `404 Not Found` | `scope_forbidden` | Profile outside ownership, nonexistent, or cross-tenant | `{"code": "scope_forbidden", "detail": "Resource not found or outside authorized scope"}` |
| `412 Precondition Failed` | `concurrency_conflict` | `If-Match` ETag version mismatch during mutation | `{"code": "concurrency_conflict", "detail": "Target resource has been modified by another transaction"}` |
| `422 Unprocessable` | `unsupported_export_purpose` | Unrecognized clinical export purpose | `{"code": "unsupported_export_purpose", "detail": "Unsupported clinical export purpose"}` |
| `429 Too Many Requests` | `rate_limit_exceeded` | Client has exceeded quota | `{"code": "rate_limit_exceeded", "detail": "Rate limit exceeded; retry after 60s"}` |

---

## 6. Audit & Telemetry Invariants

All SMART authorization events, token issuances, and FHIR resource operations emit structured events to the security audit store:
1. **AuditEvent Resource Mapping:** Export and query operations generate FHIR `AuditEvent` records documenting actor ID, tenant ID, action, outcome, and timestamp.
2. **Zero-PII Telemetry:** OpenTelemetry meters and Prometheus counters record metrics (`clara_fhir_requests_total`, `clara_fhir_auth_failures_total`, `clara_fhir_scope_denials_total`) labeled strictly with `tenant_id`, `http_status`, `resource_type`, and `scope_family`. User email, patient name, queries, and medication identifiers are strictly excluded.

---

## 7. Traceability Matrix & Verified Source Anchors

| Component / Function | Source Anchor | Role in FHIR Security Architecture |
|---|---|---|
| `_has_bearer_scheme` | `services/api/src/clara_api/core/rbac.py:15` | Case-insensitive Bearer scheme parser; prevents cookie fallback |
| `extract_bearer_token` | `services/api/src/clara_api/core/rbac.py:31` | Explicit Bearer credential extraction |
| `_reject_if_revoked` | `services/api/src/clara_api/core/rbac.py:41` | Consults Redis `jti` denylist for revoked access tokens |
| `AuthContextMiddleware` | `services/api/src/clara_api/core/rbac.py:60` | Request lifecycle token decode and state attachment |
| `has_valid_explicit_bearer_token` | `services/api/src/clara_api/core/rbac.py:92` | CSRF exemption boundary verification |
| `require_roles` | `services/api/src/clara_api/core/rbac.py:138` | Role-based dependency checking (`normal`, `doctor`, `admin`) |
| `TokenPayload` | `services/api/src/clara_api/core/security.py:11` | Cryptographic JWT claims contract (`sub`, `role`, `jti`, `exp`) |
| `decode_access_token` | `services/api/src/clara_api/core/security.py:89` | Signature and issuer validation with rotation key overlap |
| `ProfileScope` | `services/api/src/clara_api/lifemap/profile_scope.py:23` | Server-authorized patient profile access scope |
| `resolve_profile_scope` | `services/api/src/clara_api/lifemap/profile_scope.py:86` | ABAC evaluation against ownership and FamilyAccessGrant |
| `_fhir_scope` | `services/api/src/clara_api/api/v1/endpoints/lifemap.py:2726` | Purpose-of-use gate and profile scope resolution |
| `_fhir_snapshot` | `services/api/src/clara_api/api/v1/endpoints/lifemap.py:2751` | Data class filtering (`lifemap`, `medications`, `visits`) |
| `export_fhir_r4_summary` | `services/api/src/clara_api/api/v1/endpoints/lifemap.py:2881` | FHIR R4 Bundle export with consent and audit logging |
| `fhir_conformance_statement` | `services/api/src/clara_api/api/v1/endpoints/lifemap.py:2940` | FHIR R4 boundary declaration (`fhir-r4-summary-not-ips`) |
| `import_fhir_r4_as_capture_drafts`| `services/api/src/clara_api/api/v1/endpoints/lifemap.py:3012`| Untrusted FHIR import boundary (`untrusted_external_draft`) |
