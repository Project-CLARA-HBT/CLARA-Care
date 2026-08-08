SHELL := /bin/bash
COMPOSE_FILE := deploy/docker/docker-compose.yml
APP_COMPOSE_FILE := deploy/docker/docker-compose.app.yml

.PHONY: help setup-env check-env docker-up docker-down docker-logs docker-ps docker-app-up docker-app-down docker-app-logs docker-app-ps dev-api dev-web dev-ml lint type-check test docs-check precommit-install scribe-rollout-plan scribe-rollback-plan eval-smoke eval-nightly eval-release eval-judge-report eval-glhs-q3 eval-glhs-q2 eval-glhs-q2-model-integrate

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
	@echo "  docs-check        Validate docs links and docs path references"
	@echo "  precommit-install Install git pre-commit hooks"
	@echo "  scribe-rollout-plan  Print the Clara Scribe staged flag-enablement plan (DRY-RUN, no .env edits, no deploy)"
	@echo "  scribe-rollback-plan Print the Clara Scribe rollback-all plan (DRY-RUN, no .env edits, no deploy)"
	@echo "  eval-smoke        Validate CLARA-Eval VN fixtures and emit PR evidence artifacts"
	@echo "  eval-nightly      Emit nightly CLARA-Eval VN evidence artifacts (live metrics require approved dependencies)"
	@echo "  eval-release      Run release-locked CLARA-Eval VN gate (fails closed without approved live evidence)"
	@echo "  eval-judge-report Generate artifacts/judge-report with honest measurement status"
	@echo "  eval-glhs-q3      Run the non-clinical GLHS structural comparison"
	@echo "  eval-glhs-q2      Run the frozen 400-case GLHS Q2 structural protocol"
	@echo "  eval-glhs-q2-model-integrate  Validate and summarise a completed frozen model arm"

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
	@if [ -x services/api/.venv/bin/uvicorn ]; then \
		services/api/.venv/bin/uvicorn clara_api.main:app --app-dir services/api/src --host 0.0.0.0 --port $${API_PORT:-8000} --reload; \
	elif command -v uv >/dev/null 2>&1; then \
		uv run --directory services/api uvicorn clara_api.main:app --app-dir services/api/src --host 0.0.0.0 --port $${API_PORT:-8000} --reload; \
	else \
		echo "Cần services/api/.venv hoặc uv." >&2; exit 127; \
	fi

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
	@if [ -x services/ml/.venv/bin/uvicorn ]; then \
		services/ml/.venv/bin/uvicorn clara_ml.main:app --app-dir services/ml/src --host 0.0.0.0 --port $${ML_PORT:-8110} --reload; \
	elif command -v uv >/dev/null 2>&1; then \
		uv run --directory services/ml uvicorn clara_ml.main:app --app-dir services/ml/src --host 0.0.0.0 --port $${ML_PORT:-8110} --reload; \
	else \
		echo "Cần services/ml/.venv hoặc uv." >&2; exit 127; \
	fi

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
	@status=0; \
	for d in services/api services/ml; do \
		if [ ! -d "$$d/tests" ]; then continue; fi; \
		if [ -x "$$d/.venv/bin/python" ]; then \
			(cd "$$d" && .venv/bin/python -m pytest -q) || status=$$?; \
		elif command -v uv >/dev/null 2>&1; then \
			(cd "$$d" && uv run pytest -q) || status=$$?; \
		else \
			echo "No Python runner available for $$d (need $$d/.venv or uv)." >&2; \
			status=127; \
		fi; \
	done; \
	exit $$status

docs-check:
	@bash scripts/docs/check-docs-links.sh

# Clara Scribe Enterprise staged rollout — DRY-RUN ONLY (task 10.3).
# These targets only PRINT the plan + run a read-only disk pre-check; they never
# edit .env and never redeploy. To actually apply a stage an operator runs the
# script directly with APPLY=true (see the runbook), which is intentionally NOT
# wrapped in a Make target to avoid accidental production changes.
#   docs/hackathon/scribe-enterprise-staged-rollout-runbook-2026-04-20.md
scribe-rollout-plan:
	@APPLY=false bash scripts/deploy/scribe_staged_rollout.sh plan

scribe-rollback-plan:
	@APPLY=false bash scripts/deploy/scribe_staged_rollout.sh rollback-all

# CLARA-Eval VN uses checksum-locked, privacy-safe fixtures in PR smoke.  The
# report runner never manufactures clinical metrics from those fixtures.
eval-smoke:
	@python3 -m evaluation.clara_eval.run --config evaluation/configs/smoke.yaml --output artifacts/clara-eval-vn/smoke

eval-nightly:
	@python3 -m evaluation.clara_eval.run --config evaluation/configs/nightly.yaml --output artifacts/clara-eval-vn/nightly

eval-release:
	@python3 -m evaluation.clara_eval.run --config evaluation/configs/release.yaml --output artifacts/clara-eval-vn/release

eval-judge-report:
	@python3 -m evaluation.clara_eval.run --config evaluation/configs/judge_demo.yaml --output artifacts/judge-report

# GLHS Q3 is structural and synthetic by design. It never reads a patient
# record or auto-downloads credentialed MIMIC data.
eval-glhs-q3:
	@python3 -m evaluation.glhs_q3.run --output artifacts/glhs-q3/latest

# Q2 freezes policy/relevance/oracle/holdout artifacts before comparator
# execution. It is structural conformance only, never clinical validation.
eval-glhs-q2:
	@python3 -m evaluation.glhs_q2.run --output artifacts/glhs-q2/latest

# The model arm is executed against an explicitly configured ML endpoint by an
# operator.  This target deliberately only accepts a completed raw artifact and
# fails closed for partial grids; it does not retry with another model.
eval-glhs-q2-model-integrate:
	@test -n "$(MODEL_ARM_SOURCE)" || (echo "MODEL_ARM_SOURCE is required" >&2; exit 2)
	@python3 -m evaluation.glhs_q2.integrate_model_arm --source "$(MODEL_ARM_SOURCE)" --output "$(or $(MODEL_ARM_OUTPUT),artifacts/glhs-q2/model-arm-latest)"

precommit-install:
	pre-commit install
