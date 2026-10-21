# Risk Register: PH03_A02 Data Model, Session Invalidation & Migration Hardening

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH03-A02-01** | Domain Model Disambiguation | Developers confusing conversational chat sessions (`SessionModel`, table `sessions`) with HTTP/auth session tokens, causing incorrect foreign keys or queries. | Medium | Medium | Documented architectural boundaries in `models.py`: `SessionModel` represents dialogue trees (`queries.session_id`); stateful auth sessions and rotating refresh tokens are managed strictly by `AuthToken` (`auth_tokens`). | Controlled |
| **RR-PH03-A02-02** | Refresh Token Replay & Race Conditions | Concurrent requests presenting the same refresh token could lead to token duplication or desynchronization. | Critical | Low | Enforce single-use database semantics via `used_at`: `_consume_refresh_session_token()` atomically checks `used_at.is_(None)` and commits `used_at = now`. In addition, Redis `SessionSecurity` tracks rotated `jti`s and halts replayed tokens immediately with 401. | Controlled |
| **RR-PH03-A02-03** | Incomplete Logout / Token Invalidation | User logout leaves active refresh tokens in the database or active short-lived access JWTs valid until natural expiry. | High | Low | Multi-layer invalidation: `_revoke_refresh_sessions()` marks all active `refresh_jwt` rows as `used_at = now` in DB, while `SessionSecurity.revoke()` denylists access and refresh `jti` markers in Redis for their remaining TTL. | Controlled |
| **RR-PH03-A02-04** | Migration Downgrade & Batch Alter Table Invariants | Database migrations lacking non-empty `downgrade()` methods or failing under SQLite `batch_alter_table` due to unnamed constraints. | High | Low | Verified via `python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions --strict` (64/64 migrations valid) and dynamic SQLite schema round-trip (upgrade head -> downgrade -1 -> upgrade head). Parity between `Base.metadata` and migrations verified 100%. | Controlled |
| **RR-PH03-A02-05** | Token Table Bloat & Retention Sweep Hygiene | High login and refresh frequency bloating `auth_tokens` table over time with obsolete single-use tokens. | Medium | Low | Periodic retention sweep: `_cleanup_auth_tokens()` deletes expired tokens (`expires_at < now`) and consumed tokens older than 30 days (`used_at < now - 30d`). Covered by `ix_auth_tokens_created_at` index from migration `0048`. | Controlled |
| **RR-PH03-A02-06** | Cross-Endpoint Token Type Divergence | `you.py:revoke_other_sessions` querying `token_type == 'refresh'` while `auth.py` issues and revokes `token_type == 'refresh_jwt'`. | Medium | High | Issued cross-agent `DEPENDENCY_REQUEST.md` to Agent A01 to unify the filter expression to `AuthToken.token_type.in_(["refresh_jwt", "refresh"])`. | Controlled |

---

## Architectural Invariants Maintained

1. **Opaque Token Storage:** Plaintext tokens are NEVER stored in the database. All action tokens and refresh session tokens are stored as SHA-256 digests in `AuthToken.token_hash`.
2. **Single-Use Refresh Rotation:** Consuming a refresh token marks `used_at = now`, immediately preventing token reuse at the database persistence tier.
3. **Strict Migration Downgrade Integrity:** All 64 Alembic revisions strictly define non-empty `downgrade()` functions and pass automated verification.
4. **Zero-PII Token Tracking:** Neither `AuthToken` nor Redis `SessionSecurity` stores usernames, emails, or personal data; state is strictly keyed by user IDs and SHA-256 digests of opaque token identifiers.
