# Risk Register: PH12-A02 LifeMap Temporal Projection Cache & Invalidation

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH12-A02-01** | Clinical Data Integrity / Stale Projections | If invalidation operations omit affected downstream projections after an event mutation, users/clinicians could view outdated or conflicting clinical timelines. | High | Medium | Multi-scoped invalidation (`all`, `projection_type`, `key_prefix`, `temporal_window`, `single_projection`) integrated with `LifeMapCacheInvalidationLedger`. Every invalidation marks caches invalid (`is_valid=False`, `status='invalidated'`) and records full causation metadata. | Controlled |
| **RR-PH12-A02-02** | Privacy / Cross-Profile Leakage | Inadequate profile or tenant partitioning in cache retrieval queries could result in cross-patient projection bleed. | Critical | Low | Strict composite uniqueness `uq_lifemap_temporal_cache_identity` on `(profile_id, projection_type, projection_key, state_version)`. All query functions mandate `profile_id` filter and assert `profile_id > 0`. Verified in dedicated multi-profile isolation tests. | Controlled |
| **RR-PH12-A02-03** | Concurrency / Version Collisions | High-frequency concurrent event insertions racing to assign the same `state_version` for a profile. | High | Medium | Monotonic `state_version` increment guarded by database-level unique constraint `uq_lifemap_profile_state_version`. Concurrent collisions fail closed at the database constraint boundary, allowing transaction retry. | Controlled |
| **RR-PH12-A02-04** | Performance / Cache Stampede & Bloat | Unbounded projection caching over wide date windows consuming table space without eviction. | Medium | Medium | Built-in TTL expiration (`expires_at`), status tracking (`status='expired'`), and explicit sweep primitive (`prune_expired_projections`). Inactive and expired projections fail cache lookup immediately. | Controlled |
| **RR-PH12-A02-05** | Deployability / Migration Irreversibility | Alembic migration 20260908_0070 failing on PostgreSQL/SQLite or lacking clean downgrade rollback. | High | Low | Verified non-empty `downgrade()` via `check_migration_downgrade.py --strict` (70/70 passing) and tested complete upgrade/downgrade/upgrade cycle on SQLite. Tables dropped in strict reverse foreign-key dependency order. | Controlled |

---

## Architectural & Safety Invariants Maintained

1. **Deterministic Monotonic State Versioning:** LifeMap profiles advance through strictly increasing integer state versions, providing an immutable watermark for timeline reconstruction and bitemporal queries.
2. **Tamper-Evident Invalidation Ledger:** Every cache invalidation is recorded in `lifemap_cache_invalidation_ledgers` with caller attribution (`triggered_by_user_id`), causation links (`source_event_id`, `source_revision_id`), scope, and idempotency protection.
3. **Canonical Payload Hashing:** All cached projection payloads store a SHA-256 canonical hash (RFC 8785 compatible) preventing silent content tampering or drift.
4. **Subagent Path Isolation:** All file creations and modifications strictly conform to lane `services/api/src/clara_api/db/; services/api/alembic/versions/; artifacts/PH12/A02/`.
