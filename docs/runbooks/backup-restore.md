# Runbook: Datastore backup, restore & restore-drill

Spec: `clara-platform-hardening` · Task 10.1 (author the backup/restore runbook
and schedule).

This runbook is the documented procedure for **backing up and restoring the
production datastores** of CLARA-Care, with a defined schedule and retention, a
rehearsed restore procedure that verifies a backup is actually restorable, and
the **pre-migration backup** that every database migration depends on
(Requirement 9.1, 9.2, 9.3; design §I). It covers the **Postgres primary**
(relational + pgvector), the **object-store** (MinIO behind Milvus), and the
**graph-store** (Neo4j), plus the rebuildable derived stores (Milvus, Elastic)
and the deliberately-not-backed-up ephemeral store (Redis).

This is **the procedure only**. Nothing in this document moves data by itself;
running a section performs a live backup or restore. Treat every restore step as
an operator action executed during a maintenance window with the rollback notes
in hand, against the target environment's secret-store-injected credentials
(never plaintext defaults — see `docs/runbooks/credential-rotation.md`).

The model is always: **snapshot a consistent backup → store it with a checksum →
enforce retention → periodically prove it restores into a throwaway target →
record the drill.** A backup that has never been restored is not a backup.

## Principles

- **Restore-verified, not just taken.** A backup counts only once a restore of it
  has succeeded into an isolated target and been verified (Requirement 9.2).
  Unverified backups are treated as absent.
- **Consistent snapshots.** Use each engine's native, transaction-consistent dump
  (`pg_dump`/`pg_dumpall` for Postgres, `neo4j-admin database dump` for Neo4j,
  `mc mirror` of the object store) rather than copying live data files.
- **No secret values, no PII in artifacts.** Backup filenames, logs, checksums,
  and this runbook carry metadata only — never credentials, never patient data
  in cleartext outside the encrypted backup blob. Credentials are sourced from
  the managed secret store at run time.
- **Encrypt at rest, off-host.** Backups contain PHR; they are encrypted and
  stored off the application host (a separate bucket/volume), with access scoped
  to operators.
- **Pre-migration backup is mandatory.** Every database migration is preceded by
  a fresh, verified Postgres backup and the migration must define a tested
  downgrade (Requirement 9.3); a failed migration rolls back to the prior image
  and, if needed, the prior backup (Requirement 9.5).

## Datastore inventory

What lives where, and the backup class. Service/volume names match the deploy
stack (`deploy/docker/docker-compose.yml`, `docker-compose.deploy.yml`).

| Datastore | Service / container | Volume(s) | Holds | Backup class |
| --- | --- | --- | --- | --- |
| **Postgres (primary)** | `postgres` / `clara-postgres` (`pgvector/pgvector:pg16`) | `postgres_data` | Users, sessions, consent logs, PHR, knowledge sources/docs, research jobs, workspace; pgvector embeddings. Alembic-managed schema. | **Primary — scheduled logical dump, point-in-time critical** |
| **Object-store (MinIO)** | `milvus-minio` / `clara-milvus-minio` | `milvus_minio` | Milvus segment/object data; any uploaded blobs routed to MinIO. | **Scheduled mirror** |
| **Graph-store (Neo4j)** | `neo4j` / `clara-neo4j` | `neo4j_data`, `neo4j_logs` | Knowledge-graph nodes/edges for GraphRAG. | **Scheduled dump** |
| Milvus (vector) | `milvus` / `clara-milvus` | `milvus_data`, `milvus_etcd` | Vector indexes/collections. Derived — rebuildable from Postgres + re-embed; MinIO backup covers its object segments. | Rebuildable (object-store backup is the durable copy) |
| Elasticsearch (lexical) | `elasticsearch` / `clara-elasticsearch` | `elastic_data` | BM25/lexical index. Derived — re-indexable from the corpus. | Rebuildable (snapshot optional) |
| Redis | `redis` / `clara-redis` | `redis_data` | Rate-limit counters, login guard, `jti` denylist, rotation markers — all ephemeral and TTL-bound. | **Not backed up by design** (loss is self-healing) |

> Credentials for every datastore are injected from the managed secret store at
> deploy time (`POSTGRES_PASSWORD`, `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`,
> `NEO4J_AUTH`). Read them from the store for a backup/restore run; do not paste
> them into shared shell history. See `docs/runbooks/credential-rotation.md`.

## Backup schedule & retention

Backups run on a fixed cadence via cron on the deploy host (mirroring the
existing `scripts/ops/install_env_backup_cron.sh` pattern) or the environment's
managed scheduler. All times are the host timezone; stagger jobs so they do not
overlap.

| Datastore | Frequency | Cron (suggested) | Retention | Off-host copy |
| --- | --- | --- | --- | --- |
| **Postgres (primary)** | Every 6 h + nightly full | `0 */6 * * *` (full nightly at `0 2 * * *`) | 7 daily, 4 weekly, 3 monthly | Yes (encrypted) |
| **Object-store (MinIO)** | Nightly | `0 3 * * *` | 7 daily, 4 weekly | Yes (encrypted) |
| **Graph-store (Neo4j)** | Nightly | `0 4 * * *` | 7 daily, 4 weekly | Yes (encrypted) |
| Elasticsearch (optional snapshot) | Weekly | `0 5 * * 0` | 2 weekly | Optional (re-indexable) |
| **Ad-hoc pre-migration** | On every migration deploy | n/a (CD step) | Until the migration is confirmed stable in production, min 7 days | Yes (encrypted) |

Retention is enforced by a sweep that deletes artifacts older than the policy
(reuse the `RETENTION_DAYS`-style sweep from `scripts/ops/run_retention_sweep.sh`
/ `scripts/ops/backup_env.sh`). Each artifact is written with a sibling
`.sha256` checksum; the sweep never deletes the most recent verified backup of
any store even if it ages past the window.

Backup artifacts and checksums are stored with mode `600`, owned by the ops
user, in an off-host encrypted location. They are **never** committed to git
(they contain PHR) — keep the backup directory in `.gitignore`, as the `.env`
backups already are.

## Backup procedures

Run from the deploy host (`/opt/clara-care`), reading credentials from the
secret-store-injected `.env`. Replace `<backup-dir>` with the off-host encrypted
target and `<ts>` with `date +%Y%m%dT%H%M%SZ`.

### Postgres (primary)

A logical dump is portable across patch versions and restores cleanly into an
empty database. Use the running container so no extra client install is needed.

```bash
# Consistent custom-format dump of the clara database
docker exec clara-postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  > "<backup-dir>/pg_clara_<ts>.dump"

# Roles/globals (so a clean restore has the right roles) — nightly full only
docker exec clara-postgres pg_dumpall -U "$POSTGRES_USER" --globals-only \
  > "<backup-dir>/pg_globals_<ts>.sql"

# Checksum for integrity verification on restore
sha256sum "<backup-dir>/pg_clara_<ts>.dump" > "<backup-dir>/pg_clara_<ts>.dump.sha256"
```

Notes: the dump includes the `alembic_version` table, so a restore lands at the
exact migration revision the backup was taken at — keep the Postgres backup and
the deployed image/migration revision correlated (see Pre-migration backup).
pgvector columns are dumped as ordinary data; ensure the `vector` extension
exists on the restore target (it does in `pgvector/pgvector:pg16`).

### Object-store (MinIO)

Mirror all buckets to the backup target with the MinIO client (`mc`). Configure
an alias from the store-held root credentials first.

```bash
mc alias set claraminio "http://127.0.0.1:${MINIO_PORT:-9000}" \
  "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mirror --overwrite --remove claraminio "<backup-dir>/minio_<ts>/"
( cd "<backup-dir>" && find "minio_<ts>" -type f -print0 \
    | sort -z | xargs -0 sha256sum > "minio_<ts>.sha256" )
```

### Graph-store (Neo4j)

Dump the database with `neo4j-admin`. The database can be dumped online in Neo4j
5.x; for a fully quiescent dump, stop writes first.

```bash
docker exec clara-neo4j neo4j-admin database dump neo4j \
  --to-path=/backups
docker cp clara-neo4j:/backups/neo4j.dump "<backup-dir>/neo4j_<ts>.dump"
sha256sum "<backup-dir>/neo4j_<ts>.dump" > "<backup-dir>/neo4j_<ts>.dump.sha256"
```

(`NEO4J_AUTH` credentials are read from the store; `neo4j-admin database dump`
does not require them when run inside the container with filesystem access.)

### Verify every backup at creation

Immediately after each backup, verify its checksum and non-zero size before
recording it as a candidate. A checksum mismatch or empty artifact fails the
backup job (alert, do not silently retain a bad file):

```bash
sha256sum -c "<backup-dir>/pg_clara_<ts>.dump.sha256"
test -s "<backup-dir>/pg_clara_<ts>.dump" || echo "EMPTY BACKUP — FAIL"
```

## Restore procedures

Restore is destructive to the target. **Always restore into an isolated target
first** (a throwaway container or a standby environment), verify, and only then
promote. Read credentials from the secret store; never restore production into a
target still serving traffic without a maintenance window.

### Postgres (primary)

```bash
# 1. Verify the artifact before touching any target
sha256sum -c "<backup-dir>/pg_clara_<ts>.dump.sha256"

# 2. Restore into an empty target database (clean, single transaction)
docker exec -i clara-postgres-restore \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
  --no-owner --single-transaction < "<backup-dir>/pg_clara_<ts>.dump"

# 3. Confirm schema revision and row sanity
docker exec clara-postgres-restore \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT version_num FROM alembic_version;" \
  -c "SELECT count(*) FROM users;"
```

The restored `alembic_version` must match the migration revision expected for
the image being run. If the running image is **newer**, run `alembic upgrade
head` after the restore (forward-only). If the image is **older**, redeploy the
matching prior image rather than downgrading data (see Pre-migration backup &
rollback).

### Object-store (MinIO)

```bash
( cd "<backup-dir>" && sha256sum -c "minio_<ts>.sha256" )
mc mirror --overwrite "<backup-dir>/minio_<ts>/" claraminio
```

After restoring MinIO, restart `milvus` so it re-reads its object segments; if
Milvus collections are inconsistent, rebuild them from Postgres (re-embed) — the
object-store backup is the durable copy, the live Milvus index is derived.

### Graph-store (Neo4j)

Neo4j must be stopped to load a dump into an existing database.

```bash
( cd "<backup-dir>" && sha256sum -c "neo4j_<ts>.dump.sha256" )
docker cp "<backup-dir>/neo4j_<ts>.dump" clara-neo4j:/backups/neo4j.dump
docker exec clara-neo4j neo4j-admin database load neo4j \
  --from-path=/backups --overwrite-destination=true
docker restart clara-neo4j
```

### Derived stores (Milvus, Elasticsearch)

These are rebuildable and need no point-in-time restore: after Postgres + MinIO
are restored, re-embed/re-index from the restored corpus. Restore an Elastic
snapshot only if a full re-index is too slow for the recovery objective.

## Restore drill (rehearsed, scheduled)

A restore is only trustworthy if it is rehearsed. Run a **full restore drill at
least monthly** (and after any change to a backup procedure), into an isolated
target, and record the result. This is what satisfies "define and rehearse a
restore procedure that verifies a backup is actually restorable" (Requirement
9.2).

Drill checklist (Postgres is mandatory each drill; rotate MinIO/Neo4j across
drills or include all three):

- [ ] Pick the **most recent nightly** Postgres backup (not a hand-made one).
- [ ] Verify its `.sha256` checksum passes and the artifact is non-empty.
- [ ] Spin up an **isolated** target (`clara-postgres-restore` container / standby
      env) with no production traffic pointed at it.
- [ ] Restore the Postgres dump per the procedure above; restore MinIO and Neo4j
      into isolated targets when included in the drill.
- [ ] Verify integrity: `alembic_version` matches the expected revision; key
      tables have plausible row counts (`users`, `phr_profiles`,
      `knowledge_sources`, `research_jobs`); a sample PHR row reads back intact;
      a vector similarity query returns rows; a Neo4j sample query returns nodes.
- [ ] Verify the app boots against the restored DB: the production migration
      guard (`phr/migration_guard.py`) passes and `GET /health/ready` reports
      `ready` (Requirement 9.4).
- [ ] Record the drill in the log below: date, operator, backup timestamp
      restored, time-to-restore, and pass/fail.
- [ ] Tear down the isolated target; confirm no drill artifact leaked PHR to an
      unencrypted or shared location.

Track the **recovery objectives** the drill must meet:

| Objective | Target |
| --- | --- |
| RPO (max data loss) | ≤ 6 h for Postgres (matches the 6-hourly cadence) |
| RTO (max time to restore) | ≤ 2 h for the primary path (Postgres + app boot) |

If a drill misses RPO/RTO or fails verification, that is a hard finding: fix the
backup/restore path before the next migration deploy.

## Pre-migration backup & rollback

Every database migration deploy is gated on a fresh, verified backup and a
present downgrade (Requirement 9.3; companion CD work in Task 10.2):

1. **Backup first.** Before `alembic upgrade head` runs in the deploy, take and
   verify a Postgres backup (the ad-hoc pre-migration class above). Record the
   backup timestamp alongside the target migration revision.
2. **Downgrade present.** The migration module to be deployed must define a
   `downgrade()` (the CD check enforces this); the existing migration guard
   continues to require the production schema to be migration-managed, never
   created by the `create_all` fallback (Requirement 9.4).
3. **Smoke after migrate.** Run the post-deploy smoke checks (`/health`,
   `/health/ready`, a read path).
4. **Rollback on failure** (Requirement 9.5):
   - **Prefer image rollback.** Redeploy the prior image; if the migration is
     backward-compatible, the data is untouched.
   - **Schema rollback.** If the migration changed schema incompatibly, run the
     tested `alembic downgrade <prior-revision>`.
   - **Data rollback (last resort).** If a migration corrupted data, restore the
     **pre-migration Postgres backup** taken in step 1 into the target and
     redeploy the matching prior image. Restore MinIO/Neo4j from their nightly
     backups only if the migration touched them.

## Rollback (of a restore itself)

A restore is destructive. If a restore into a *production* target goes wrong:

- Because restores are done into an **isolated** target first and promoted only
  after verification, the normal mitigation is to discard the bad target and
  re-restore — production was never overwritten.
- If production was restored in place and the result is wrong, restore the
  **previous** verified backup (one cadence older) following the same procedure;
  this is why retention keeps multiple generations.
- Redis needs no rollback — its state is ephemeral and TTL-bound and rebuilds
  itself after a restart.

## Restore-drill log

Record each drill here (or in the environment's ops audit). No secret values, no
PHR — metadata only. This is the record that satisfies "rehearsed and verified
restore" (Requirement 9.2).

| Date | Datastore(s) | Backup timestamp restored | Operator | Time-to-restore | RPO/RTO met? | Result |
| --- | --- | --- | --- | --- | --- | --- |
| _pending_ | Postgres | _first scheduled drill_ | _ops_ | _—_ | _—_ | _pending — run the first drill after backups are scheduled_ |

## Notes

- This runbook documents the procedure; it does not back up or restore anything
  by itself. Run each section deliberately, with credentials read from the
  managed secret store and the rollback notes to hand.
- Scheduling the cron jobs (and the retention sweep), and adding the CD
  pre-migrate backup + downgrade check, are companion tasks (10.2); this runbook
  assumes those run the procedures defined here.
- Redis is intentionally **not** backed up: it holds only ephemeral, TTL-bound
  security state (rate-limit counters, login guard, `jti` denylist, rotation
  markers) that self-heals on restart.
- Milvus and Elasticsearch are derived stores — the durable copies are the
  Postgres dump (source rows/embeddings) and the MinIO mirror (Milvus segments);
  rebuild the indexes rather than relying on a point-in-time index restore.
- Keep backup artifacts encrypted, off-host, mode `600`, and out of git — they
  contain PHR. The backup directory must be in `.gitignore`, like the existing
  `.env` backups.
