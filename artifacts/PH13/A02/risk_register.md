# PH13 A02 Risk Register: OAuth Callback/Refresh Secure Store & Lease Locking

## Risk Inventory

| Risk ID | Severity | Category | Description | Mitigation Strategy | State |
|---|---|---|---|---|---|
| **RSK-PH13-A02-001** | High | Cryptographic Exposure | Plaintext OAuth access/refresh tokens leaked via logs, memory dumps, or direct database access | AES-256-GCM authenticated encryption enforced at data layer with 12-byte cryptographic random nonces; plaintext tokens are never written to database columns. | MITIGATED |
| **RSK-PH13-A02-002** | High | Ciphertext Cross-Profile Splicing | Ciphertext encrypted for Profile A / Tenant X copied and decrypted in Profile B / Tenant Y context | Additional Authenticated Data (AAD) binds every encryption operation to `tenant_id`, `profile_id`, and `connector_id`. Decryption with mismatched context triggers `InvalidTag` and aborts. | MITIGATED |
| **RSK-PH13-A02-003** | Critical | Refresh Token Replay / Theft | Intercepted refresh token used by an adversary after legitimate client has rotated it | RFC 6819 Refresh Token Rotation enforced. Re-presentation of any previously rotated token triggers immediate cascade revocation of the entire token family, transitions account to `needs_reauth`, and logs reuse violation. | MITIGATED |
| **RSK-PH13-A02-004** | Medium | Concurrent Refresh Stampede | Multiple workers or background tasks simultaneously attempting to refresh a single-use token, invalidating each other | Distributed lease lock (`ConnectorLeaseLock`) provides mutual exclusion per connector/resource. Only the lease holder can execute the refresh sequence. | MITIGATED |
| **RSK-PH13-A02-005** | Medium | Worker Crash / Deadlock | Worker crashes while holding a lease lock on token refresh, blocking subsequent background synchronizations | Leases have strict TTL expiration (`expires_at`). Expired leases are automatically reclaimed by healthy workers with incremented fencing tokens. | MITIGATED |
| **RSK-PH13-A02-006** | Medium | Delayed Zombie Worker Writes | A stalled worker awakens after its lease has expired and attempts to commit stale tokens or sync records | Monotonically increasing fencing tokens are issued upon lease takeover, allowing downstream verifiers to reject out-of-order writes. | MITIGATED |
| **RSK-PH13-A02-007** | Low | Migration Schema Rollback Failure | Failure during Alembic upgrade leaves unrecoverable schema state in staging/production | Migration `20260909_0071` provides an explicit, non-empty `downgrade()` function dropping tables and indexes in proper dependency order; validated via strict downgrade checker. | MITIGATED |

## Residual Risk Assessment

No critical or high unmitigated risks remain. Cryptographic keys default to environment variable `OAUTH_TOKEN_ENCRYPTION_KEY` with deterministic fallback in staging/test environments.
