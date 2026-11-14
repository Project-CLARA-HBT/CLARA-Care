# PH13 / A07 — Risk Register

**Scope:** mobile permission/resync integration tests for Connected Health (`services/api/tests/`).

| ID | Risk | Severity | Likelihood | Impact | Mitigation | Status |
|----|------|----------|------------|--------|------------|--------|
| R-A07-01 | Tests rely on shared `/tmp/clara_api_ci.db` and may accumulate state across runs | Medium | Medium | Low | Each test provisions a unique user via `_unique_email` and scopes assertions to its own connector/profile; reruns are safe. Full suite is intended to run against a fresh DB in CI. | Accepted |
| R-A07-02 | CSRF assertions are conditional on `AUTH_CSRF_ENABLED`; a disabled-flag CI run silently skips three security checks | Medium | Low | Medium | Bearer-bypass case always runs; CI env keeps CSRF enabled by default (`AUTH_CSRF_ENABLED` defaults true). Flag guard documents the dependency rather than faking enforcement. | Mitigated |
| R-A07-03 | Assertions on exact error strings (`"CSRF validation failed"`, `"unconsented"`, `"scope mismatch"`) are brittle to wording changes | Low | Medium | Low | Strings are canonical security-invariant messages; any change should be deliberate and paired with test updates. | Accepted |
| R-A07-04 | Suite runtime (~8m) dominated by per-test unique-user provisioning and bcrypt hashing | Low | High | Low | Acceptable for an integration suite; can be partitioned in CI if wall-clock budget tightens. | Accepted |
| R-A07-05 | Tests depend on base-commit schema (`WearableObservation`, `WearableObservationVersion`, `WearableDailyAggregate`, `ConnectorImportBatch`, `ConnectorSyncCursor`, `ConnectorAuditEvent`, `LifeMapOutboxEvent`) | Medium | Low | Medium | All models exist at base SHA `bce92340`; schema changes in A02 must update this suite in the same change set. | Watched |
| R-A07-06 | SQLite datetime adapter deprecation warning could become an error on a future Python upgrade | Low | Low | Low | Third-party warning only; does not affect test outcomes. Track upstream SQLAlchemy fix. | Accepted |
| R-A07-07 | No coverage of concurrent batch submission races (true parallel idempotency) | Medium | Medium | Medium | Sequential replay/conflict covered; parallel race is out of scope for this lane and tracked for A08 replay simulations. | Open (deferred) |
| R-A07-08 | Mobile client (A06) contract not exercised — tests validate API semantics only | Low | Medium | Low | API is the boundary contract; mobile UI flows covered by A06. This suite is intentionally transport-level. | Accepted |

## Safety Invariant Verification

- **Consent gate:** unconsented and revoked-consent imports are asserted to fail closed (403/409).
- **RBAC:** routes resolve the authenticated owner via `owned_connector`; no bypass introduced.
- **CSRF:** cookie-auth mutations without a matching CSRF pair are asserted to return 403; Bearer path is asserted exempt only when a valid token is presented.
- **No-PII telemetry:** tests do not assert on PII-bearing telemetry; no new telemetry emitted by tests.
