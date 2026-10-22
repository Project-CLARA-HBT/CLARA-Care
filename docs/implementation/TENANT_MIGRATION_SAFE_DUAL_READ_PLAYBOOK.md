# Runbook: Tenant Migration & Safe Dual-Read Backfill Playbook (PH44)

## 1. Overview & Objective
Governs the zero-downtime data migration of legacy single-tenant medical records and workspaces into multi-tenant partitioned organizations using the **Dual-Read / Dual-Write Safe Cutover Pattern**.

## 2. Safe Cutover Phases

```text
Phase 1: Dual-Write
  • Writes update both legacy table and new tenant-partitioned table.
  • Reads continue from legacy table.

Phase 2: Backfill & Checksum Reconciliation
  • Historical records migrated with explicit tenant_id bindings.
  • Cryptographic checksums reconciled across legacy and tenant rows.

Phase 3: Dual-Read with Canary Divergence Assertion
  • Primary read from new tenant partition; shadow read from legacy table.
  • Mismatches log critical alert without interrupting user traffic.

Phase 4: Full Cutover & Deprecation
  • Reads and writes exclusively target tenant-partitioned tables.
  • Legacy columns marked deprecated via Alembic migration.
```

## 3. Backfill Execution Procedure
1. **Initialize Migration Lock:**
   ```bash
   python3 -m clara_api.ops.tenant_migration --init --tenant-id "tenant-hbt-central"
   ```
2. **Execute Chunked Batch Backfill (1,000 records/batch):**
   ```bash
   python3 -m clara_api.ops.tenant_migration --backfill --batch-size 1000
   ```
3. **Reconcile Checksums:**
   ```bash
   python3 -m clara_api.ops.tenant_migration --verify-checksums
   ```
   **Acceptance Invariant:** 100% digest match across all migrated patient entities.
