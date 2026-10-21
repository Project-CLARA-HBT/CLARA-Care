# Test and Smoke Report: PostgreSQL, Redis Compose & Mobile Network (PH01_A06)

## 1. Executive Summary & Verification Context

- **Subagent**: `A06`
- **Phase**: `PH01`
- **Role**: `Mobile Flutter`
- **Worktree**: `/dev/shm/clara_worktrees/PH01_A06`
- **Branch**: `phase/ph01-a06`
- **Frozen HEAD SHA**: `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
- **Audit Date**: 2026-10-21
- **Task**: PostgreSQL 16 + pgvector compose smoke, Redis cache service smoke, audit compose files (`deploy/docker/docker-compose*.yml`), and Mobile network configuration validation.
- **Status**: Complete with verified source anchors and clean container smoke execution.

---

## 2. Docker Compose Audit Findings

### 2.1 Compose Files Inspected
1. `deploy/docker/docker-compose.yml`:
   - Primary infrastructure compose file defining PostgreSQL 16 (`pgvector/pgvector:pg16`), Redis 7 (`redis:7-alpine`), Milvus (`milvusdb/milvus:v2.4.12`), Elasticsearch 8 (`elasticsearch:8.13.4`), and Neo4j 5 (`neo4j:5.22`).
   - Default logging configured with `json-file`, max-size 10MB, max-file 5 (`x-default-logging`).
   - Network: creates project network `clara-local_default` (aliased in dependent files as `clara-local` or `clara_local`).

2. `deploy/docker/docker-compose.app.yml`:
   - Application service tier (`api`, `ml`, `ocr`, `asr`, `searxng`, `web`, `lifemap-worker`, `evidence-monitor`).
   - Connects to external network `clara-local` (`name: clara-local_default`) to reach database and cache services.
   - Points to PostgreSQL via `DATABASE_URL` (`${DATABASE_URL}`) and Redis via `REDIS_URL` (`redis://redis:6379/0`).

3. `deploy/docker/docker-compose.deploy.yml`:
   - Production deployment compose file with pre-built immutable images (`${API_IMAGE}`, `${ML_IMAGE}`, `${ASR_IMAGE}`, `${WEB_IMAGE}`).
   - Contains database connection pool sizing (`DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=5`, `DB_POOL_TIMEOUT=30`, `DB_POOL_RECYCLE=1800`, `DB_POOL_PRE_PING=true`).
   - Enforces `DATABASE_FALLBACK_ENABLED=false` to prevent silent SQLite fallback in production.

4. `deploy/docker/docker-compose.govred-isolated.yml`:
   - Isolated GovRed RIVF experimental boundary environment with ephemeral container volumes and strict project-scoped network (`boundary`).

---

## 3. PostgreSQL 16 + pgvector Smoke Test Execution

### 3.1 Container Lifecycle & Healthcheck
- **Configuration**:
  - Image: `pgvector/pgvector:pg16`
  - Healthcheck command: `["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-clara} -d ${POSTGRES_DB:-clara}"]`
  - Healthcheck parameters: `interval: 10s`, `timeout: 5s`, `retries: 10`.
- **Command Executed**:
  ```bash
  POSTGRES_PORT=54329 REDIS_PORT=63799 docker compose -f deploy/docker/docker-compose.yml up -d postgres redis
  ```
- **Exit Code**: `0`
- **Result**: Container `clara-postgres` started successfully, completed `initdb`, and transitioned to `healthy` status in `docker ps`.

### 3.2 SQL Verification & Extension Functionality
- **Command Executed**:
  ```bash
  docker exec -i clara-postgres psql -U clara -d clara \
    -c "SELECT version();" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" \
    -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';" \
    -c "CREATE TABLE test_vector (id serial PRIMARY KEY, embedding vector(3)); INSERT INTO test_vector (embedding) VALUES ('[1,2,3]'), ('[4,5,6]'); SELECT id, embedding, embedding <-> '[1,2,3]' AS distance FROM test_vector ORDER BY distance; DROP TABLE test_vector;"
  ```
- **Exit Code**: `0`
- **Stdout Output**:
  ```text
                                                             version
  ------------------------------------------------------------------------------------------------------------------------------
   PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit
  (1 row)

  CREATE EXTENSION
   extversion
  ------------
   0.8.7
  (1 row)

  CREATE TABLE
  INSERT 0 2
   id | embedding |     distance
  ----+-----------+-------------------
    1 | [1,2,3]   |                 0
    2 | [4,5,6]   | 5.196152422706632
  (2 rows)

  DROP TABLE
  ```
- **Finding**: Verified PostgreSQL engine version is 16.15, `vector` extension version 0.8.7 installs cleanly, and L2 distance calculation `<->` executes correctly.

---

## 4. Redis Cache Service Smoke Test Execution

### 4.1 Container Lifecycle & Healthcheck
- **Configuration**:
  - Image: `redis:7-alpine`
  - Command: `["redis-server", "--appendonly", "yes"]`
  - Healthcheck command: `["CMD", "redis-cli", "ping"]`
  - Healthcheck parameters: `interval: 10s`, `timeout: 3s`, `retries: 10`.
- **Exit Code**: `0`
- **Result**: Container `clara-redis` started successfully and transitioned to `healthy` status immediately.

### 4.2 Cache Command & AOF Verification
- **Command Executed**:
  ```bash
  docker exec -i clara-redis redis-cli ping && \
  docker exec -i clara-redis redis-cli info server | grep -E 'redis_version|redis_mode|os' && \
  docker exec -i clara-redis redis-cli set clara:test:key "clara_smoke_test_value" ex 60 && \
  docker exec -i clara-redis redis-cli get clara:test:key && \
  docker exec -i clara-redis redis-cli del clara:test:key && \
  docker exec -i clara-redis redis-cli config get appendonly
  ```
- **Exit Code**: `0`
- **Stdout Output**:
  ```text
  PONG
  redis_version:7.4.8
  redis_mode:standalone
  os:Linux 6.17.0-20-generic x86_64
  OK
  clara_smoke_test_value
  1
  appendonly
  yes
  ```
- **Finding**: Redis 7.4.8 standalone server responds to `PING` with `PONG`, correctly sets and gets TTL-keyed data, and persists with `appendonly yes`.

### 4.3 Network Port Reachability
- Host-to-container reachability probe via Python socket connection to ports `127.0.0.1:54329` and `127.0.0.1:63799`:
  - Postgres port 54329: `reachable` (Exit 0)
  - Redis port 63799: `reachable` (Exit 0)
- Clean container teardown performed via `docker compose down -v` without leaving orphan containers or dangling volumes.

---

## 5. Mobile Target Settings & Network Endpoints

### 5.1 Endpoint Resolution Matrix
- **Production Base URL**:
  - `https://theclaracare.com` (proxied by Nginx at `deploy/nginx/clara.thiennn.icu.conf` to API port 8100).
- **Development Base URL**:
  - Compiled in via `--dart-define=CLARA_API_BASE_URL=...` (`apps/mobile/lib/main.dart:16-19`).
  - Defaults to `http://localhost:8100` in debug mode.
  - Android Emulator loopback: `http://10.0.2.2:8100`.
  - iOS Simulator loopback: `http://127.0.0.1:8100`.
  - Android Physical Device: `adb reverse tcp:8100 tcp:8100` routing to workstation host.

### 5.2 Android Cleartext Traffic Hardening
- Android 9+ (API Level 28+) disables cleartext HTTP traffic by default. When developers run debug builds pointing to `http://localhost:8100` or `http://10.0.2.2:8100`, Android blocks HTTP socket creation unless explicit cleartext traffic is enabled.
- **Audit & Remediation**:
  - `apps/mobile/android/app/src/main/AndroidManifest.xml` (release manifest): strictly HTTPS-only (no cleartext attribute).
  - `apps/mobile/android/app/src/debug/AndroidManifest.xml` (debug-only overlay): updated to include `<application android:usesCleartextTraffic="true"/>`.
  - Result: Debug builds can communicate with local development API without impacting production release builds, which remain strictly HTTPS-only.

### 5.3 Consumer Terminology Contract
- **Command**: `npm run consumer-terminology:check` in `apps/web`
- **Exit Code**: `0`
- **Output**: `consumer terminology contract passed: 19 keys, 2026-07-30.v1.`
- Mobile projection `apps/mobile/lib/core/consumer_terminology.generated.dart` is in 100% sync with contract `contracts/consumer-terminology/consumer-terminology.v1.json`.

---

## 6. Deliverable Verification Checklist

- [x] Repo HEAD verified equal to `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
- [x] Inspected docker-compose configurations (`deploy/docker/docker-compose*.yml`)
- [x] Successfully smoke-tested PostgreSQL 16 + pgvector container definition
- [x] Successfully smoke-tested Redis 7 cache service with AOF persistence
- [x] Audited Mobile network configuration, endpoints, and target platform settings
- [x] Applied safe debug-only cleartext configuration in `apps/mobile/android/app/src/debug/AndroidManifest.xml`
- [x] Wrote `change_manifest.json`, `test_report.md`, `risk_register.md`, and `rollback.md` in `artifacts/PH01/A06/`
- [x] Verified zero secrets, zero PHI, and clean git diff
