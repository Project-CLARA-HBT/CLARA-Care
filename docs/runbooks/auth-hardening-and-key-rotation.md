# Runbook: Auth Hardening, Key Rotation & Zero-Downtime Session Recovery

**Status:** ACTIVE OPERATIONAL RUNBOOK · LOCKED TO CONTRACT SPEC
**Audience:** Platform Reliability Engineers, Security Officers, Operations Lead
**Scope:** `services/api` Authentication Subsystem, Redis Security Store, JWT Lifecycle, Secret Rotation
**Phase Verification Anchor:** PH03 / Subagent A10

---

## 1. Architectural Foundation & Guarantees

The CLARA-Care platform provides a safety-critical clinical assistant environment where continuous availability and strict identity verification must coexist. The authentication layer is architectured around three core pillars:

1. **Stateless JWT Claims with Multi-Key Verification (`services/api/src/clara_api/core/security.py:53`):**
   Candidate verification keys are ordered: current `JWT_SECRET_KEY` is tried first, followed by `JWT_SECRET_KEY_PREVIOUS` during an overlap window. Newly issued tokens are strictly signed with `JWT_SECRET_KEY`.
2. **Stateful Invalidation & Replay Defense via Redis (`services/api/src/clara_api/core/session_security.py:41`):**
   Refresh tokens are strictly single-use (`test_refresh_token_is_single_use`). When rotated, the old token ID (`jti`) is persisted as a SHA-256 digest in Redis. Attempting to refresh using an already rotated token triggers automated lockout of the session family. Access and refresh tokens revoked at logout are similarly denylisted for their remaining TTL.
3. **Defense-in-Depth Startup Validation (`services/api/src/clara_api/main.py:62`):**
   In `ENVIRONMENT=production`, the application immediately fails fast if `JWT_SECRET_KEY` or `JWT_SECRET_KEY_PREVIOUS` contains placeholder values, if `AUTH_COOKIE_SECURE` is false, or if `ML_INTERNAL_API_KEY` is unconfigured.

---

## 2. Zero-Downtime Secret Rotation Procedure

### 2.1 Rotation Lifecycle & Overlap Window Design

A naive secret rotation invalidates all existing JWT signatures simultaneously, triggering a disruptive mass logout for active patients, physicians, and background collectors. CLARA-Care implements an **Overlap Window Architecture**:

```
                       Timeline (T0 -> T1 -> T2)
  [T0: Baseline]       JWT_SECRET_KEY = Key_A
                       JWT_SECRET_KEY_PREVIOUS = ""
                       --------------------------------------------------------
  [T1: Rotation]       JWT_SECRET_KEY = Key_B           <-- New signings use Key_B
                       JWT_SECRET_KEY_PREVIOUS = Key_A  <-- Verification accepts Key_A & Key_B
                       --------------------------------------------------------
  [T2: Deprecation]    JWT_SECRET_KEY = Key_B
                       JWT_SECRET_KEY_PREVIOUS = ""     <-- Key_A fully retired
```

* **Window Duration Requirement:** The minimum overlap window must equal the active refresh token TTL (`REFRESH_TOKEN_EXPIRE_MINUTES`, default 43,200 minutes ≈ 30 days) to guarantee that zero legitimate client sessions are dropped.

### 2.2 Step-by-Step Execution Plan

#### Step 1: Pre-Rotation Readiness Inspection
Verify that the current instance is healthy and that no existing rotation window is active:
```bash
# Verify API readiness
curl -f -s http://localhost:8000/api/v1/health/readiness | jq .

# Inspect environment configuration
python3 -c "
from clara_api.core.config import get_settings
s = get_settings()
assert s.jwt_secret_key != '', 'Current key must be set'
print('Pre-rotation status: READY. Previous key configured:', bool(s.jwt_secret_key_previous))
"
```

#### Step 2: High-Entropy Key Generation
Generate the replacement secret using cryptographically secure random bytes:
```bash
# Generate 32-byte (256-bit) URL-safe token
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Generated entropy verified (length: ${#NEW_KEY})"
```

#### Step 3: Transition to Overlap Window
In your secret store (AWS Secrets Manager, Vault, or GitHub Secrets / `DEPLOY_ENV_FILE`):
1. Copy existing `JWT_SECRET_KEY` to `JWT_SECRET_KEY_PREVIOUS`.
2. Set `JWT_SECRET_KEY` to `$NEW_KEY`.
3. Trigger rolling deployment of `services/api`.

During this phase:
- Incoming requests bearing tokens signed under the old key match `_signing_keys()` index 1 and succeed.
- Newly minted access and refresh tokens are signed with the new key (`_signing_keys()` index 0).

#### Step 4: Verification of Dual-Acceptance
Execute automated verification asserting that both old and new signatures pass verification:
```bash
python3 scripts/ci/ph03_quality_gate.py --verify-rotation
```

#### Step 5: Close Overlap Window
After the configured refresh token TTL has elapsed:
1. Clear `JWT_SECRET_KEY_PREVIOUS=""` in the secret store.
2. Trigger rolling restart of `services/api`.
3. Assert that tokens signed under the retired key are now rejected (`401 Unauthorized`).

---

## 3. Coordinated Service Key Rotations

### 3.1 ML Internal API Key (`ML_INTERNAL_API_KEY`)
The internal API key authenticates high-privilege gateway communication between `services/api` and `services/ml` via the `X-ML-Internal-Key` header.
- **Dependency Order:** `services/ml` must accept the new key prior to `services/api` dispatching it.
- **Procedure:**
  1. Generate new key in secret store.
  2. Deploy `services/ml` with updated secret.
  3. Deploy `services/api` with updated secret.
  4. Verify inter-service synthesis route returns `200 OK`.

### 3.2 Datastore & Cache Credentials
- **PostgreSQL (`DATABASE_URL`, `POSTGRES_PASSWORD`):**
  Execute `ALTER ROLE clara WITH PASSWORD '<new_secret>';` on primary database, update secret store, and restart API cluster. `pool_pre_ping` validates connection vitality.
- **Redis Security Store (`REDIS_URL`):**
  Update Redis auth credentials with zero downtime via `AUTH` password rotation, preserving session revocation lists.

---

## 4. Emergency Revocation & Incident Response Runbook

### Scenario A: Compromised Master Signing Key
When `JWT_SECRET_KEY` is known to have been leaked:
1. **Immediate Invalidation:** Do **NOT** use the overlap window. Immediately set `JWT_SECRET_KEY` to a fresh random secret and set `JWT_SECRET_KEY_PREVIOUS=""`.
2. **Flush Active Sessions:** If malicious tokens were minted, flush the Redis revocation store or increment platform-wide session epoch:
   ```bash
   # Emergency restart of API gateway forcing immediate mass re-login
   docker compose restart api
   ```
3. **Audit Trail Inspection:** Query `/api/v1/admin/audit/logs` for suspicious admin provisioning or unauthorized role escalation during the compromise window.

### Scenario B: Distributed Brute-Force or Credential Stuffing
If `LoginGuard` alerts on high 429 lockout rates:
1. Confirm Redis connectivity: `redis-cli ping`.
2. Check top attacking IPs via rate limiter metrics:
   ```bash
   python3 -c "from clara_api.core.login_guard import login_guard; print('Active lockout keys:', len(login_guard._states))"
   ```
3. Enforce perimeter IP throttling via Nginx/Cloudflare WAF.

---

## 5. Verification Commands & Acceptance Checklist

| Step | Command | Expected Output |
|---|---|---|
| Base Integrity | `git rev-parse HEAD` | `3b1072b98350b978b83b7ecec5c35228415759a3` |
| Downgrade Completeness | `python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions` | `OK: every migration defines a downgrade()` |
| AST Bytecode Safety | `python3 -m compileall -q services/api/src scripts/ci/` | Exit Code 0 |
| Rotation Logic | `python3 scripts/ci/ph03_quality_gate.py` | `PH03 QUALITY GATE VERDICT: PASSED` |
