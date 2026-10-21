# Risk Register: PH01_A02 Data Model & Migration Supply-Chain

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH01-A02-01** | Database Dialect Divergence (DEFECT-02) | Unnamed constraints in Alembic migrations pass on Postgres but crash on SQLite batch alter table operations (`ValueError: Constraint must have a name`), breaking CI and local developer flows. | Critical | High | Explicitly declare constraint names via `batch.create_foreign_key("fk_social_comments_parent_id", ...)` and reverse via `batch.drop_constraint("fk_social_comments_parent_id", type_="foreignkey")`. Validated with SQLite memory and file roundtrip. | Controlled |
| **RR-PH01-A02-02** | Dependency Supply-Chain Drift | Discrepancies between `services/api/pyproject.toml` and `services/api/uv.lock` leading to non-reproducible test runs and deployment discrepancies. | High | Low | Verified complete lock coverage: all 17 runtime and 5 development dependencies are resolved, version-bounded, and pinned in `uv.lock`. CI uses `uv sync --frozen`. | Controlled |
| **RR-PH01-A02-03** | Known Security Vulnerabilities (CVEs) | Vulnerable JWT or multipart parser libraries introducing DoS or algorithm confusion vectors. | Critical | Low | Enforced minimum dependency floors in `pyproject.toml`: `python-jose[cryptography]>=3.4.0` (clears CVE-2024-33664/33663; locked at 3.5.0) and `python-multipart>=0.0.18` (clears CVE-2024-53981; locked at 0.0.22). | Controlled |
| **RR-PH01-A02-04** | Irreversible Migration Drift | Migration downgrade failures leaving database schema in an irrecoverable state during deployment rollbacks. | High | Low | Enforced via `scripts/ops/check_migration_downgrade.py --strict` (scanned 64 migrations, 64 non-empty downgrades) and live downgrade execution (0064 -> 0061 and re-upgrade to head). | Controlled |
| **RR-PH01-A02-05** | Test Concurrency Contention | Multiple concurrent subagents running tests against shared `/tmp` SQLite databases causing file locking delays or IO thrashing. | Medium | Medium | Test executions isolated using ramdisk (`/dev/shm`) and unique database URLs per process, preventing cross-worktree lock contention. | Controlled |

---

## Architectural Invariants Maintained

1. **Deterministic Dependency Locking:** All backend Python dependencies are strictly locked in `services/api/uv.lock` and audited against `pyproject.toml`.
2. **Dialect Agnostic Schema Alterations:** Table alterations executed via Alembic batch mode must provide explicit constraint identifiers to support both SQLite and PostgreSQL without failure.
3. **Strict Downgrade Verification:** No migration may be merged or deployed without a functional, non-empty `downgrade()` implementation verified under `--strict` mode.
