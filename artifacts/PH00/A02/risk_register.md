# Risk Register: PH00_A02 Data Model + Migration Inventory

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-A02-01** | Migration Lineage | Forked or multiple heads in Alembic migration directory creating non-deterministic schema migrations in staging/production. | Critical | Low | Verified strict linear chain: 64 sequential migrations from root `20260324_0001` to head `20260826_0064`. Verified zero branches. | Controlled |
| **RR-A02-02** | Rollback Feasibility | Migration modules defining empty/no-op `downgrade()` functions leading to irreversible schema drift on deployment failure. | High | Low | Enforced via `scripts/ops/check_migration_downgrade.py --strict`. All 64 migrations have substantive, non-empty downgrade operations. | Controlled |
| **RR-A02-03** | Connection Pool Exhaustion | Concurrency spikes or worker thread leakage exhausting DB pool connections under heavy API/ML traffic. | High | Medium | Explicit QueuePool settings: `db_pool_size=20`, `db_max_overflow=30`, `db_pool_timeout=30`, `db_pool_recycle=1800` (30m) and `db_pool_pre_ping=True` preventing stale pooled connections. NullPool applied in Alembic runner to prevent migration connection leaks. | Controlled |
| **RR-A02-04** | Accidental Production Fallback | Failure of primary PostgreSQL causing silent fallback to a local SQLite database, resulting in data desynchronization and loss of multi-tenant durability. | Critical | Low | Hard guard in `services/api/src/clara_api/db/session.py:79-85`: in production (`environment in {"prod", "production"}`), fallback is strictly prohibited unless `DATABASE_FALLBACK_ENABLED=true` is explicitly configured. | Controlled |
| **RR-A02-05** | Transaction Leakage & Dirty Reads | Sessions auto-committing partially formed mutations or leaking uncommitted state across HTTP requests. | High | Low | `SessionLocal` defined with `autoflush=False, autocommit=False`. Sessions managed in dependency generator `get_db()` with guaranteed `finally: db.close()`. | Controlled |
| **RR-A02-06** | Concurrency Anomaly (TOCTOU) | Race conditions in GLHS clinical commitment and LifeMap state transitions under concurrent doctor/patient updates. | High | Low | Row-level locking (`FOR UPDATE` / `FOR SHARE`), dynamic partition locks in GLHS commitment gateway, and version checking (`GlhsStateVersion`, `GlhsEntityVersionPartition`). Validated in E04/E05 empirical benchmarks. | Controlled |
| **RR-A02-07** | Data Retention & DSAR Index Degradation | Background compliance retention sweeps causing full table scans and lock contention on high-volume tables. | Medium | Low | Migration `20260801_0048_retention_sweep_indexes` indexed timestamp cutoffs across clinical tables specifically for compliance retention queries. | Controlled |

---

## Invariant Summary

1. **Additive DB Migrations:** All schema alterations maintain backward compatibility; schema deprecation uses dual-read before cutover.
2. **Strict Downgrade Contract:** Every migration must cleanly reverse its actions without leaving orphaned foreign keys or corrupted constraints.
3. **Owner & Profile Isolation:** Models enforce foreign key cascade / set null rules with tenant and profile boundaries.
