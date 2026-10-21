# Risk Register: PH03_A03 Object-Level Profile Scope & IDOR Prevention

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH03-A03-01** | Insecure Direct Object Reference (IDOR) | User A crafts an API request passing User B's profile ID (`public_id` or integer `id`), accessing User B's medical records. | Critical | Low | Gated by `resolve_profile_scope` and `require_profile_scope`: any profile requested must be owned by the caller or covered by a live `FamilyAccessGrant`. Violations return `404 scope_forbidden`. | Controlled |
| **RR-PH03-A03-02** | Profile Enumeration Oracle | An attacker probes profile IDs, discerning valid from invalid accounts based on response differences (e.g. 403 vs 404). | High | Low | Uniform 404 response: unauthorized profile access returns status `404` with detail `{"code": "scope_forbidden", "message": "Profile not found"}`, identical in status code and schema to non-existent profiles. | Controlled |
| **RR-PH03-A03-03** | Administrative Health-Data Bypass | Admin accounts bypass route-level RBAC (`token.role == "admin"` in `require_roles`) and read patient health records directly. | Critical | Low | Role decoupling: Administrative role is explicitly rejected in `profile_scope.py` (lines 152-169, 291-309). Admin access to health records requires a separate audited break-glass workflow; direct attempts return 404 and log an audit denial. | Controlled |
| **RR-PH03-A03-04** | Capability Scope Creep in Family Grants | A caregiver granted `view` on `lifemap` attempts to execute mutations (`create`, `correct`) or access other data classes (`medications`, `allergies`). | High | Low | Purpose and class binding: `resolve_profile_scope` checks `action in actions` and `data_class in classes` against the active grant. Ungranted actions or data classes are denied with 404. | Controlled |
| **RR-PH03-A03-05** | Stale / Revoked Grant Linger | A previously granted access continues to work after expiration or revocation. | High | Low | Instant query filtering: `FamilyAccessGrant` query strictly checks `status == "active"`, `revoked_at.is_(None)`, `starts_at <= now`, and `expires_at > now` on every single request. | Controlled |
| **RR-PH03-A03-06** | Mismatched Owner Scope in Internal Adapters | An internal GLHS adapter constructs an `owner` scope with mismatched user and profile objects. | High | Low | Invariant lock: `ProfileScope.__post_init__` raises `ValueError` if `actor_role == "owner"` and `profile.user_id != actor.id`. Similarly, `owner_profile_scope` validates `profile.user_id == actor.id`. | Controlled |

---

## Architectural Invariants Maintained

1. **Client Selection is Only a Hint:** `requested_profile` or `X-CLARA-Profile-Context` is NEVER trusted as authorization; it must resolve through database ownership or an active purpose-bound grant.
2. **Enumeration Resistance:** Unauthorized access to a profile is indistinguishable from a non-existent profile (uniform HTTP 404).
3. **No Role-Based Health Data Privilege:** `admin` or `doctor` roles do NOT grant health profile read/write capabilities without an explicit grant or break-glass authorization.
4. **Grant Immutability on Revocation:** Revoking a grant immediately denies subsequent requests at the database query boundary.
5. **Zero-PII Access Logging:** Denied access attempts log audit events (`FamilyAccessLog`) without exposing sensitive patient details.
