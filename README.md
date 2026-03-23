# CLARA P0 - Infra/DevOps Bootstrap

Tài liệu này mô tả phần hạ tầng/devops cho Phase 0 để đội API/Web/ML có thể phát triển song song và deploy web P0 trên domain.

## 1. Phạm vi P0 Infra

- Local infra stack bằng Docker Compose.
- App stack Docker gồm `web + api + ml`.
- CI trên Pull Request chạy `ruff` + `mypy` + `pytest`.
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
- `make docker-logs`: tail logs toàn bộ infra.

## 7. CI Quality Gate

Workflow: `.github/workflows/ci.yml`

Trigger:

- Pull Request
- Manual (`workflow_dispatch`)

Các bước:

1. Setup Python 3.11
2. Install tooling (`ruff`, `mypy`, `pytest`)
3. Run `ruff`
4. Run `mypy`
5. Run `pytest`

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
- Port override cho Compose nếu máy local bị trùng cổng.

## 10. Deploy Nginx cho domain

File mẫu Nginx: `deploy/nginx/clara.thiennn.icu.conf`

- `/` -> `127.0.0.1:3100` (web)
- `/api/` -> `127.0.0.1:8100` (api)
- `/ml/` -> `127.0.0.1:8110` (ml)
