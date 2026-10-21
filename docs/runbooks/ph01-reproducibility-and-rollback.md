# Runbook: PH01 Platform Reproducibility and Emergency Rollback

**Phase:** PH01 — Toolchain Reproducibility & Dependency Supply-Chain
**Scope:** Multi-Tier Platform Build, Hermetic Toolchain Verification, and Incident Rollback Procedures
**Target Environments:** Local Development, CI Runners, Staging, and VPS Production
**Owner:** Subagent A10 (Adversarial Audit & Integration Proposals)
**Last Updated:** October 2026 (PH01 Baseline)

---

## 1. Executive Overview & Core Invariants

This runbook specifies the canonical, repeatable instructions for recreating, validating, and rolling back the CLARA Care platform across all runtime components.

### 1.1 Core Safety & Reproducibility Invariants (Locked)
1. **Zero-Mock Production Data:** No synthetic doctor appointments, fabricated patient metrics, or fake health statuses in production surfaces. If upstream services fail, client and administrative surfaces must render explicit, truthful error/degraded states.
2. **Deterministic Hermetic Locks:** Every dependency must be pinned with cryptographic hashes in version-controlled lockfiles (`services/api/uv.lock`, `services/ml/uv.lock`, `apps/web/package-lock.json`, `apps/mobile/pubspec.lock`). Direct unpinned `pip install` or `npm install` without lockfile enforcement is prohibited.
3. **Additive DB Migrations with Verified Reversibility:** Every Alembic migration must declare a non-empty `downgrade()` verified by `scripts/ops/check_migration_downgrade.py`. All table and foreign key constraints must be explicitly named to ensure clean execution on both SQLite and PostgreSQL.
4. **Deny-by-Default Public Boundaries:** Unauthenticated routes must exist in `INTENTIONAL_PUBLIC_ROUTES` (`services/api/src/clara_api/core/route_inventory.py`). Any unlisted route is blocked by default.
5. **Zero Hardcoded Secrets in Tracked Trees:** No private keys, bearer tokens, or provider API credentials may be committed in source, tests, documentation, or evaluation fixtures.

---

## 2. Platform Component Toolchain Matrix

| Component | Path | Pinned Runtime / Manager | Lockfile | Port | Health / Verification Command |
|---|---|---|---|---|---|
| **API Gateway** | `services/api` | Python `>=3.11` (3.12 verified) via `uv` | `services/api/uv.lock` | 8000 / 8100 | `curl -f http://localhost:8100/health` |
| **ML Service** | `services/ml` | Python `>=3.11` (3.12 verified) via `uv` | `services/ml/uv.lock` | 8010 / 8110 | `curl -f http://localhost:8110/health` |
| **Web Frontend** | `apps/web` | Node.js `20.x` (`.nvmrc`), npm `10.x` | `apps/web/package-lock.json` | 3000 | `curl -f http://localhost:3000/api/health` |
| **Mobile Client** | `apps/mobile` | Flutter `3.47+`, Dart `^3.9.0` | `apps/mobile/pubspec.lock` | — | `flutter test test/markdown_view_test.dart` |
| **Database** | Docker | PostgreSQL 16.15 + pgvector 0.8.7 | `pgvector/pgvector:pg16` | 5432 | `pg_isready -U clara -d clara` |
| **Cache & Bus** | Docker | Redis 7.4.8 standalone | `redis:7-alpine` | 6379 | `redis-cli ping` |
| **ASR Sidecar** | `services/asr` | Python 3.12, faster-whisper 1.2.1 | `services/asr/requirements.lock` | 8090 | `curl -f http://localhost:8090/health` |
| **OCR Sidecar** | `services/ocr` | Python 3.12, multimodal proxy | `services/ocr/Dockerfile` | 8080 | `curl -f http://localhost:8080/health` |

---

## 3. End-to-End Reproducibility Instructions

### 3.1 Workspace Initialization & Clean Clone
```bash
# 1. Clone repository and checkout pinned baseline commit
git clone https://github.com/theclaracare/clara-care.git /workspace/clara-care
cd /workspace/clara-care
git checkout 2aa9016a57b49b53f1a433d076e1028a6ec45f64

# 2. Verify git cleanliness and HEAD commit
git rev-parse HEAD  # Expected: 2aa9016a57b49b53f1a433d076e1028a6ec45f64
git status -s       # Expected: empty output
```

### 3.2 Infrastructure Services (PostgreSQL & Redis)
```bash
# Start containerized database and cache dependencies
docker compose -f deploy/docker/docker-compose.yml up -d postgres redis

# Verify PostgreSQL is ready and pgvector is active
docker exec -it clara-postgres pg_isready -U clara -d clara
docker exec -it clara-postgres psql -U clara -d clara -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"

# Verify Redis is ready
docker exec -it clara-redis redis-cli ping  # Expected: PONG
```

### 3.3 Python Services (`services/api` and `services/ml`)
```bash
# 1. Setup API virtual environment with uv
cd /workspace/clara-care/services/api
uv sync --frozen --extra dev --no-editable

# 2. Run Alembic migrations to head
uv run alembic upgrade head

# 3. Verify migration downgrade and re-upgrade
uv run alembic downgrade -1
uv run alembic upgrade head

# 4. Setup ML service
cd /workspace/clara-care/services/ml
uv sync --frozen --extra dev --no-editable
```

### 3.4 Web Application (`apps/web`)
```bash
cd /workspace/clara-care/apps/web

# 1. Enforce Node 20 runtime
nvm use || nvm install 20

# 2. Hermetic clean installation from package-lock.json
npm ci

# 3. Verify consumer terminology and route contracts
npm run consumer-terminology:check
npm run route-matrix:check
npm run bundle:check
```

### 3.5 Automated Toolchain & Quality Gate Sweep
Run the PH01 CI gate script to assert AST bytecode integrity, migration downgrades, and supply-chain lockfile purity in a single non-destructive pass:
```bash
cd /workspace/clara-care
python3 scripts/ci/ph01_reproducibility_gate.py
```

---

## 4. Emergency Rollback Runbook

### 4.1 Incident Classification & Immediate Action

| Severity | Definition | Response Time | Rollback Strategy |
|---|---|---|---|
| **P0 (Critical)** | Data corruption, crash loop on boot, security/credential exposure, medical hallucination/bypass. | Immediate (<5 min) | Fast kill-switch flag disable, migration reversal, or full git reset. |
| **P1 (High)** | Route inventory test failure, external provider timeout, degraded background sync, unpinned package warning. | <30 min | Revert offending commit, pin dependency, deploy hotfix patch. |
| **P2 (Medium)** | Non-blocking telemetry warning, documentation link drift, local toolchain cache issue. | Next release | Track in risk register; remediate in subsequent phase. |

---

### 4.2 Rollback Procedure 1: Fast Kill-Switch Flag Disablement (Zero Downtime)
All new platform capabilities and security features are gated behind default-off `HARDENING_*` flags. If an issue is observed in staging or production:

1. Update `.env` or deployment environment secrets:
   ```bash
   HARDENING_REFRESH_ROTATION_ENABLED=false
   HARDENING_TOKEN_DENYLIST_ENABLED=false
   HARDENING_LOGIN_FAIL_CLOSED=false
   HARDENING_RATE_LIMIT_FAIL_CLOSED=false
   HARDENING_REQUEST_BODY_LIMIT_ENABLED=false
   HARDENING_READINESS_PROBE_ENABLED=false
   HARDENING_CIRCUIT_BREAKER_ENABLED=false
   ```
2. Restart API and ML services without redeploying code:
   ```bash
   docker compose -f deploy/docker/docker-compose.deploy.yml restart api ml
   ```
3. Confirm services return to nominal unhardened baseline behavior.

---

### 4.3 Rollback Procedure 2: Database Migration Downgrade
If a newly applied Alembic migration causes schema lock contention or query failure:

1. Identify current database revision:
   ```bash
   cd services/api
   uv run alembic current
   ```
2. Revert exactly one revision:
   ```bash
   uv run alembic downgrade -1
   ```
3. If rolling back specific revision `20260824_0062` (DEFECT-02 fix):
   ```bash
   uv run alembic downgrade 20260824_0061
   ```
4. Verify database health:
   ```bash
   python3 -c "from clara_api.db.session import engine; from sqlalchemy import text; engine.connect().execute(text('SELECT 1'))"
   ```

---

### 4.4 Rollback Procedure 3: Git Branch & Artifact Abort
If an agent branch or worktree produces invalid artifacts or breaks test suites:

1. Discard uncommitted changes:
   ```bash
   git reset --hard HEAD
   git clean -fd
   ```
2. Revert worktree branch to the frozen base commit:
   ```bash
   git reset --hard 2aa9016a57b49b53f1a433d076e1028a6ec45f64
   ```
3. Remove generated artifacts directory if necessary:
   ```bash
   rm -rf artifacts/PH01/A10/
   ```

---

### 4.5 Rollback Procedure 4: Credential Exposure Quarantine (SEC-CRIT-01 Protocol)
If a credential or API key is detected in source code or commits:

1. **Containment:** Immediately revoke the exposed token at the provider or router console (`router.theclaracare.com`).
2. **Sanitization:** Remove the credential literal from the source file. Replace with environment variable resolution:
   ```python
   API_KEY = os.environ.get("CLARA_ROUTER_API_KEY", "")
   ```
3. **Redaction in Docs/Specs:** Replace literal tokens with `<REDACTED_API_KEY>`.
4. **Verification:** Execute the secret scanner:
   ```bash
   python3 -m evaluation.commitloop.secret_scan --repo-root .
   ```
   Must return `secret_scan_passed` with exit code 0.

---

### 4.6 Rollback Procedure 5: Public Route Inventory Remediation (DEFECT-01 Protocol)
If `test_route_inventory_public_boundaries.py` fails with unclassified public routes:

1. Inspect unclassified routes:
   ```bash
   python3 -c "from clara_api.main import app; from clara_api.core.route_inventory import unclassified_public_routes; print(unclassified_public_routes(app))"
   ```
2. If the endpoint is an intentional public capability (e.g., OAuth/SSO callback):
   - Add `(METHOD, PATH)` to `INTENTIONAL_PUBLIC_ROUTES` in `services/api/src/clara_api/core/route_inventory.py`.
3. If the endpoint is an accidental unauthenticated exposure:
   - Add `require_roles(...)` or `get_current_user` dependency to the endpoint route declaration in `services/api/src/clara_api/api/`.
4. Re-run boundary test to verify green exit:
   ```bash
   CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara_test.db" pytest services/api/tests/test_route_inventory_public_boundaries.py
   ```

---

## 5. Verification Checklist Before Marking Phase Complete

- [ ] Repository HEAD SHA equals pinned base (`2aa9016a57b49b53f1a433d076e1028a6ec45f64`).
- [ ] `python3 scripts/ci/ph01_reproducibility_gate.py` passes with exit code 0.
- [ ] `python3 -m evaluation.commitloop.secret_scan --repo-root .` passes (SEC-CRIT-01 remediated).
- [ ] `test_route_inventory_public_boundaries.py` passes (DEFECT-01 remediated).
- [ ] `check_migration_downgrade.py` passes on 64 Alembic revisions (DEFECT-02 remediated).
- [ ] No unpinned, wildcard, or malicious package sources in `uv.lock`, `package-lock.json`, or `pubspec.lock`.
- [ ] Deliverables `change_manifest.json`, `test_report.md`, and `risk_register.md` committed to branch `phase/ph01-a10`.
