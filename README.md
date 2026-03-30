# CLARA P0 - Infra/DevOps Bootstrap

Tài liệu này mô tả phần hạ tầng/devops cho Phase 0 để đội API/Web/ML có thể phát triển song song và deploy web P0 trên domain.

## 1. Phạm vi P0 Infra

- Local infra stack bằng Docker Compose.
- App stack Docker gồm `web + api + ml`.
- CI trên Pull Request chạy `docs-check` + `ruff` + `mypy` + `pytest`.
- Make targets chuẩn cho dev flow.
- Pre-commit hooks để giữ quality gate trước khi push.

## 2. Thành phần Local Stack

File: `deploy/docker/docker-compose.yml`

- PostgreSQL 16
- Redis 7
- Milvus standalone (kèm etcd + minio)
- Elasticsearch 8
- Neo4j 5

## 3. Thành phần App Stack

File: `deploy/docker/docker-compose.app.yml`

- `web` (Next.js 14) chạy cổng nội bộ `127.0.0.1:3100`
- `api` (FastAPI) chạy cổng nội bộ `127.0.0.1:8100`
- `ml` (FastAPI + LangChain/LangGraph skeleton) chạy cổng nội bộ `127.0.0.1:8110`

Các cổng bind vào `127.0.0.1` để không ảnh hưởng project khác trên server.

## 4. Prerequisites

- Docker Engine + Docker Compose v2
- Python 3.11+
- `pip` (để cài `pre-commit`, `ruff`, `mypy`, `pytest` local)

## 5. Onboarding nhanh

```bash
cp .env.example .env
make check-env
make docker-up
make docker-ps
```

Dừng stack:

```bash
make docker-down
```

Chạy app stack:

```bash
make docker-app-up
make docker-app-ps
```

Dừng app stack:

```bash
make docker-app-down
```

## 6. Các lệnh Make chính

- `make dev-api`: chạy API local (khi đã có `services/api`).
- `make dev-web`: chạy web local (khi đã có `apps/web`).
- `make dev-ml`: chạy ML service local (khi đã có `services/ml`).
- `make docker-app-up`: build + chạy app stack.
- `make docker-app-logs`: xem logs app stack.
- `make lint`: `ruff check services scripts tests`.
- `make type-check`: `mypy services --ignore-missing-imports`.
- `make test`: `pytest -q`.
- `make docs-check`: kiểm tra link docs và tham chiếu `docs/...` bị gãy.
- `make docker-logs`: tail logs toàn bộ infra.

## 7. CI Quality Gate

Workflow chính: `.github/workflows/ci.yml` (GitHub Actions)

Trigger:

- Pull Request
- Manual (`workflow_dispatch`)

Các job chính:

1. `quality`: `docs-check` + `ruff` + `mypy`
2. `api-tests`: chỉ chạy khi thay đổi `services/api/**`
3. `ml-tests`: chỉ chạy khi thay đổi `services/ml/**`
4. `web-lint-build`: `npm ci` + `npm run lint` + `npm run build` trong `apps/web`
5. `security-audit`: `pip-audit` + `npm audit --omit=dev`
6. `docker-compose-smoke`: build nhanh `api/ml/web` từ `docker-compose.app.yml`
7. `container-scan`: quét image bằng Trivy (HIGH/CRITICAL)
8. `required-ci-gates`: gate tổng để branch protection chỉ cần yêu cầu 1 check bắt buộc

Chính sách blocking/advisory:

- `pull_request`: `security-audit` + `docker-compose-smoke` + `container-scan` chạy advisory.
- `push main`/`workflow_dispatch`: `security-audit` + `docker-compose-smoke` blocking qua `required-ci-gates`.
- `container-scan`: blocking khi có `CRITICAL`, còn `HIGH` được ghi warning + artifact để theo dõi remediation.

## 7.1 Release + CD

- Release workflow: `.github/workflows/release.yml`
  - Semver tag (`vX.Y.Z`)
  - Auto release notes
  - Build/push GHCR images theo tag + SHA
  - Upload image manifest artifact
- CD workflow: `.github/workflows/cd.yml`
  - Deploy staging (manual approve qua environment)
  - Smoke checks API/ML/Web
  - Promote production (manual approve + smoke)
  - Hỗ trợ rollback bằng tag cũ

Tài liệu chi tiết:

- `docs/devops/release-process.md`
- `docs/devops/cd-pipeline.md`
- `docs/devops/branch-protection.md`

## 8. Pre-commit

Cài hook:

```bash
pip install pre-commit
make precommit-install
```

Hook hiện có:

- `ruff-lint`
- `ruff-format`
- `mypy-services`
- `pytest-check` (pre-push)

## 9. Biến môi trường

Xem `.env.example` để cấu hình:

- Key API: `OPENAI_API_KEY`, `NCBI_API_KEY`, `WHO_ICD11_CLIENT_ID`, `WHO_ICD11_CLIENT_SECRET`
- Database URLs: `DATABASE_URL`, `REDIS_URL`, `ELASTICSEARCH_URL`, `NEO4J_URI`
- Consent gate: `MEDICAL_DISCLAIMER_VERSION`
- Port override cho Compose nếu máy local bị trùng cổng.

## 10. Deploy Nginx cho domain

File mẫu Nginx: `deploy/nginx/clara.thiennn.icu.conf`

- `/` -> `127.0.0.1:3100` (web)
- `/api/` -> `127.0.0.1:8100` (api)
- `/ml/` -> `127.0.0.1:8110` (ml)
