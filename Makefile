SHELL := /bin/zsh
COMPOSE_FILE := deploy/docker/docker-compose.yml
APP_COMPOSE_FILE := deploy/docker/docker-compose.app.yml

.PHONY: help setup-env check-env docker-up docker-down docker-logs docker-ps docker-app-up docker-app-down docker-app-logs docker-app-ps dev-api dev-web dev-ml lint type-check test precommit-install

help:
	@echo "CLARA P0 Make targets"
	@echo "  setup-env         Create .env from .env.example if missing"
	@echo "  check-env         Validate local toolchain (.env, docker, docker compose)"
	@echo "  docker-up         Start local infra stack"
	@echo "  docker-down       Stop local infra stack"
	@echo "  docker-logs       Tail infra logs"
	@echo "  docker-ps         Show infra service status"
	@echo "  docker-app-up     Start CLARA app stack (web/api/ml)"
	@echo "  docker-app-down   Stop CLARA app stack"
	@echo "  docker-app-logs   Tail app stack logs"
	@echo "  docker-app-ps     Show app stack status"
	@echo "  dev-api           Run API dev server (services/api)"
	@echo "  dev-web           Run web dev server (apps/web)"
	@echo "  dev-ml            Run ML dev service (services/ml)"
	@echo "  lint              Run ruff"
	@echo "  type-check        Run mypy"
	@echo "  test              Run pytest"
	@echo "  precommit-install Install git pre-commit hooks"

setup-env:
	@test -f .env || cp .env.example .env
	@echo "[ok] .env is ready"

check-env:
	@bash scripts/setup/check-env.sh

docker-up: setup-env
	docker compose --env-file .env -f $(COMPOSE_FILE) up -d

docker-down:
	docker compose --env-file .env -f $(COMPOSE_FILE) down

docker-logs:
	docker compose --env-file .env -f $(COMPOSE_FILE) logs -f --tail=200

docker-ps:
	docker compose --env-file .env -f $(COMPOSE_FILE) ps

docker-app-up: setup-env
	docker compose --env-file .env -f $(APP_COMPOSE_FILE) up -d --build

docker-app-down:
	docker compose --env-file .env -f $(APP_COMPOSE_FILE) down

docker-app-logs:
	docker compose --env-file .env -f $(APP_COMPOSE_FILE) logs -f --tail=200

docker-app-ps:
	docker compose --env-file .env -f $(APP_COMPOSE_FILE) ps

dev-api:
	@if [ ! -d services/api ]; then \
		echo "services/api chưa tồn tại"; \
		exit 1; \
	fi
	cd services/api && uvicorn clara_api.main:app --app-dir src --host 0.0.0.0 --port $${API_PORT:-8000} --reload

dev-web:
	@if [ ! -d apps/web ]; then \
		echo "apps/web chưa tồn tại"; \
		exit 1; \
	fi
	cd apps/web && npm run dev

dev-ml:
	@if [ ! -d services/ml ]; then \
		echo "services/ml chưa tồn tại"; \
		exit 1; \
	fi
	cd services/ml && uvicorn clara_ml.main:app --app-dir src --host 0.0.0.0 --port $${ML_PORT:-8010} --reload

lint:
	@targets=""; \
	for d in services/api/src services/api/tests services/ml/src services/ml/tests scripts; do \
		if [ -d "$$d" ]; then targets="$$targets $$d"; fi; \
	done; \
	if [ -n "$$targets" ]; then \
		ruff check $$targets; \
	else \
		echo "No Python source directories found."; \
	fi

type-check:
	@if [ -d services/api/src ] || [ -d services/ml/src ]; then \
		mypy services/api/src services/ml/src --ignore-missing-imports; \
	else \
		echo "No type-check targets found."; \
	fi

test:
	@targets=""; \
	for d in services/api/tests services/ml/tests; do \
		if [ -d "$$d" ]; then targets="$$targets $$d"; fi; \
	done; \
	if [ -n "$$targets" ]; then \
		pytest -q $$targets; \
	else \
		echo "No test directories found."; \
	fi

precommit-install:
	pre-commit install
