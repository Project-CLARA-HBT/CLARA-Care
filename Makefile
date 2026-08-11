SHELL := /bin/bash
COMPOSE_FILE := deploy/docker/docker-compose.yml
APP_COMPOSE_FILE := deploy/docker/docker-compose.app.yml

.PHONY: help setup-env check-env docker-up docker-down docker-logs docker-ps docker-app-up docker-app-logs docker-app-ps dev-api dev-web dev-ml lint type-check test docs-check precommit-install scribe-rollout-plan scribe-rollback-plan eval-smoke eval-nightly eval-release eval-judge-report eval-structural-conformance eval-glhs-local-assurance eval-glhs-fullstack-postgres eval-glhs-contention-postgres eval-standards-comparator-validate eval-contract-clause-ablation eval-commitloop-local eval-commitloop-validate eval-commitloop-secret-scan eval-commitloop-freeze eval-commitloop-provider-probe eval-commitloop-phase-b

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
	@echo "  eval-structural-conformance  Run the non-clinical state-layer conformance protocol"
	@echo "  eval-glhs-local-assurance  Measure network-free GLHS replay/governance overhead"
	@echo "  eval-glhs-fullstack-postgres  Run the acknowledged empty-DB service-layer benchmark"
	@echo "  eval-glhs-contention-postgres  Measure profile-global true/false stale contention"
	@echo "  eval-standards-comparator-validate  Validate the frozen novelty-isolation comparator"
	@echo "  eval-contract-clause-ablation  Run and validate the frozen clause matrix"
	@echo "  eval-commitloop-local  Run the sealed two-subject CommitLoop fake-provider grid"
	@echo "  eval-commitloop-validate  Validate COMMITLOOP_RUN_DIR and its SHA-256 inventory"
	@echo "  eval-commitloop-secret-scan  Fail if tracked CommitLoop content contains credentials"
	@echo "  eval-commitloop-freeze  Seal a clean Phase-A run with local validation evidence"
	@echo "  eval-commitloop-provider-probe  Phase-B-only exact-model router probe"
	@echo "  eval-commitloop-phase-b  Run the freeze/probe-gated bounded synthetic benchmark"

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
		if [ -x services/api/.venv/bin/ruff ]; then services/api/.venv/bin/ruff check $$targets; \
		elif command -v ruff >/dev/null 2>&1; then ruff check $$targets; \
		else echo "No ruff runner available (need services/api/.venv or PATH)." >&2; exit 127; fi; \
	else \
		echo "No Python source directories found."; \
	fi

type-check:
	@if [ -d services/api/src ] || [ -d services/ml/src ]; then \
		if [ -x services/api/.venv/bin/mypy ]; then services/api/.venv/bin/mypy services/api/src services/ml/src --ignore-missing-imports; \
		elif command -v mypy >/dev/null 2>&1; then mypy services/api/src services/ml/src --ignore-missing-imports; \
		else echo "No mypy runner available (need services/api/.venv or PATH)." >&2; exit 127; fi; \
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

# This protocol is structural and synthetic by design. It never reads a patient
# record or auto-downloads credentialed MIMIC data.
eval-structural-conformance:
	@python3 -m evaluation.structural_conformance.run --output artifacts/structural-conformance/latest

eval-glhs-local-assurance:
	@test -n "$(GLHS_ASSURANCE_OUTPUT)" || (echo "GLHS_ASSURANCE_OUTPUT is required" >&2; exit 2)
	@PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.glhs_assurance.run --output "$(GLHS_ASSURANCE_OUTPUT)"

eval-glhs-fullstack-postgres:
	@test -n "$(DATABASE_URL)" && test -n "$(GLHS_FULLSTACK_OUTPUT)" && test -n "$(GLHS_POSTGRES_IMAGE_DIGEST)" || (echo "DATABASE_URL, GLHS_FULLSTACK_OUTPUT and GLHS_POSTGRES_IMAGE_DIGEST are required" >&2; exit 2)
	@test "$(ALLOW_GLHS_FULLSTACK_EMPTY_DATABASE)" = "true" || (echo "ALLOW_GLHS_FULLSTACK_EMPTY_DATABASE=true is required" >&2; exit 2)
	@DATABASE_URL="$(DATABASE_URL)" PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.fullstack_benchmark.run_postgresql --output "$(GLHS_FULLSTACK_OUTPUT)" --database-image-digest "$(GLHS_POSTGRES_IMAGE_DIGEST)" --acknowledge-isolated-empty-database
	@PYTHONPATH=. services/api/.venv/bin/python -m evaluation.fullstack_benchmark.validate_metrics --metrics "$(GLHS_FULLSTACK_OUTPUT)/fullstack_metrics.csv" --manifest "$(GLHS_FULLSTACK_OUTPUT)/fullstack_manifest.json"

eval-glhs-contention-postgres:
	@test -n "$(DATABASE_URL)" && test -n "$(GLHS_CONTENTION_OUTPUT)" && test -n "$(GLHS_POSTGRES_IMAGE_DIGEST)" || (echo "DATABASE_URL, GLHS_CONTENTION_OUTPUT and GLHS_POSTGRES_IMAGE_DIGEST are required" >&2; exit 2)
	@test "$(ALLOW_GLHS_CONTENTION_EMPTY_DATABASE)" = "true" || (echo "ALLOW_GLHS_CONTENTION_EMPTY_DATABASE=true is required" >&2; exit 2)
	@DATABASE_URL="$(DATABASE_URL)" PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.contention_analysis.run_postgresql --output "$(GLHS_CONTENTION_OUTPUT)" --database-image-digest "$(GLHS_POSTGRES_IMAGE_DIGEST)" --acknowledge-isolated-empty-database
	@PYTHONPATH=. services/api/.venv/bin/python -m evaluation.contention_analysis.validate --run-dir "$(GLHS_CONTENTION_OUTPUT)"

eval-standards-comparator-validate:
	@PYTHONPATH=. services/api/.venv/bin/python -m evaluation.comparator_studies.standards_composed_baseline.validate_manifest

eval-contract-clause-ablation:
	@test -n "$(CONTRACT_ABLATION_OUTPUT)" || (echo "CONTRACT_ABLATION_OUTPUT is required" >&2; exit 2)
	@PYTHONPATH=. services/api/.venv/bin/python -m evaluation.contract_clause_ablation.validate
	@PYTHONPATH=. services/api/.venv/bin/python -m evaluation.contract_clause_ablation.run --output "$(CONTRACT_ABLATION_OUTPUT)"
	@PYTHONPATH=. services/api/.venv/bin/python -m evaluation.contract_clause_ablation.validate --output "$(CONTRACT_ABLATION_OUTPUT)"

eval-commitloop-local:
	@PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.commitloop.cli local-fixture --output artifacts/commitloop/local-phase-a

eval-commitloop-validate:
	@test -n "$(COMMITLOOP_RUN_DIR)" || (echo "COMMITLOOP_RUN_DIR is required" >&2; exit 2)
	@PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.commitloop.cli validate --run-dir "$(COMMITLOOP_RUN_DIR)"

eval-commitloop-secret-scan:
	@PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.commitloop.secret_scan --repo-root . --path evaluation/commitloop --path protocols/commitloop --path services/api/src/clara_api/glhs --path services/api/tests/test_commitloop_gateway.py --path services/api/tests/test_commitloop_predicate_dsl.py --path services/api/tests/test_commitloop_reconciliation.py --path services/api/tests/test_commitment_policies.py

eval-commitloop-freeze:
	@test -n "$(COMMITLOOP_RUN_DIR)" && test -n "$(COMMITLOOP_VALIDATION_EVIDENCE)" || (echo "COMMITLOOP_RUN_DIR and COMMITLOOP_VALIDATION_EVIDENCE are required" >&2; exit 2)
	@PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.commitloop.freeze --run-dir "$(COMMITLOOP_RUN_DIR)" --validation-evidence "$(COMMITLOOP_VALIDATION_EVIDENCE)"

eval-commitloop-provider-probe:
	@test -n "$(COMMITLOOP_FREEZE)" && test -n "$(COMMITLOOP_PROBE_OUTPUT)" || (echo "COMMITLOOP_FREEZE and COMMITLOOP_PROBE_OUTPUT are required" >&2; exit 2)
	@PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.commitloop.provider_probe --freeze "$(COMMITLOOP_FREEZE)" --output "$(COMMITLOOP_PROBE_OUTPUT)"

eval-commitloop-phase-b:
	@test -n "$(COMMITLOOP_FREEZE)" && test -n "$(COMMITLOOP_PROBE)" && test -n "$(COMMITLOOP_PHASE_B_OUTPUT)" && test -n "$(COMMITLOOP_BUNDLE_DIR)" && test -n "$(COMMITLOOP_FHIR_VERSION)" && test -n "$(COMMITLOOP_VALID_CUTOFF)" && test -n "$(COMMITLOOP_KNOWN_CUTOFF)" || (echo "COMMITLOOP_FREEZE, COMMITLOOP_PROBE, COMMITLOOP_PHASE_B_OUTPUT, COMMITLOOP_BUNDLE_DIR, COMMITLOOP_FHIR_VERSION, COMMITLOOP_VALID_CUTOFF and COMMITLOOP_KNOWN_CUTOFF are required" >&2; exit 2)
	@PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.commitloop.run_benchmark --freeze "$(COMMITLOOP_FREEZE)" --probe "$(COMMITLOOP_PROBE)" --output "$(COMMITLOOP_PHASE_B_OUTPUT)" --bundle-dir "$(COMMITLOOP_BUNDLE_DIR)" --fhir-version "$(COMMITLOOP_FHIR_VERSION)" --valid-cutoff "$(COMMITLOOP_VALID_CUTOFF)" --known-cutoff "$(COMMITLOOP_KNOWN_CUTOFF)"

precommit-install:
	pre-commit install
