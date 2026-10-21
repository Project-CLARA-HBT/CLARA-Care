# Developer Local Bootstrap and Toolchain Guide

## 1. Purpose and Scope

This document describes the developer local setup workflow, toolchain requirements, and offline research verification procedures for the CLARA Care platform.

The primary bootstrap orchestrator is `scripts/ops/bootstrap_dev.sh`, which provides non-destructive environment inspection, prerequisite checking, dependency synchronization, and hermetic research runner validation.

---

## 2. Toolchain Prerequisites

CLARA enforces strict toolchain parity across local development and continuous integration environments:

| Tool | Required Version | Purpose | Specification Source |
|---|---|---|---|
| **Python** | `>= 3.11` (Target: `3.12`) | Backend API and ML services | `services/api/pyproject.toml`, `services/ml/pyproject.toml` |
| **Node.js** | `>= 20.0.0 < 21.0.0` | Web application (Next.js 15) | `.nvmrc`, `apps/web/package.json` |
| **npm** | `>= 10.0.0` | Web package manager | `apps/web/package.json` |
| **uv** | Fast resolver (`>= 0.4`) | Python dependency and venv management | `AGENTS.md` |
| **pre-commit** | Git hook framework | Quality gates (ruff, mypy, pytest) | `.pre-commit-config.yaml` |
| **Docker** | Optional / Local Services | PostgreSQL and Redis container compose | `deploy/docker/docker-compose.yml` |

---

## 3. Bootstrap Script Usage (`scripts/ops/bootstrap_dev.sh`)

The script `scripts/ops/bootstrap_dev.sh` is located in `scripts/ops/` and is executable. It operates non-destructively: it never overwrites existing `.env` files or removes user files.

### 3.1 Preflight Inspection Mode (`--check`)

To inspect system readiness without modifying any files or installing packages:

```bash
bash scripts/ops/bootstrap_dev.sh --check
```

The script evaluates:
1. **Core Toolchains:**
   - Detects `python3` and validates major/minor version (requires `>= 3.11`, target `3.12`).
   - Detects `node` and enforces Node 20 (`>= 20.0.0 < 21.0.0`).
   - Detects `uv` executable in PATH or user directories (`~/.local/bin`, `~/.cargo/bin`).
   - Detects `git` and verifies repository/worktree context.
   - Detects `pre-commit` CLI and checks if `.git/hooks/pre-commit` is active.
2. **Workspace Configuration:**
   - Verifies whether `.env` exists.
   - Verifies Docker daemon status.
   - Checks presence of service virtual environments (`services/api/.venv`, `services/ml/.venv`).
   - Checks presence of web packages (`apps/web/node_modules`).
3. **Research Runners:**
   - Verifies availability of prospective reproduction scripts (`reproduce_e01.py`, `reproduce_e07.py`, `reproduce_q3_r3.py`, `reproduce_q4_r4.py`).

**Exit codes:**
- `0`: All core toolchains satisfied (advisories may guide optional workspace items).
- `1`: Prerequisite check failed (missing uv, incompatible Python version, or non-Node 20).
- `2`: Invalid argument.

---

### 3.2 Automated Setup Modes

For local onboarding, `bootstrap_dev.sh` provides subcommands:

```bash
# Safely initialize .env from .env.example (never overwrites existing .env)
bash scripts/ops/bootstrap_dev.sh --setup-env

# Synchronize Python virtual environments for services/api and services/ml via uv
bash scripts/ops/bootstrap_dev.sh --sync-python

# Install Next.js web application dependencies via npm ci
bash scripts/ops/bootstrap_dev.sh --sync-web

# Install git pre-commit hooks
bash scripts/ops/bootstrap_dev.sh --install-hooks

# Run all non-destructive setup tasks and verify final readiness
bash scripts/ops/bootstrap_dev.sh --all
```

---

## 4. Hermetic Offline Research Reproduction Runners

Research evidence bundles in the CLARA repository (such as GLHS R3 and R4 prospective protocols) are cryptographically sealed and must reproduce deterministically without network access.

### 4.1 Running Hermetic Verification

Verify reproduction runners via `bootstrap_dev.sh`:

```bash
bash scripts/ops/bootstrap_dev.sh --verify-research
```

Or run standalone runners directly:

```bash
# E01: 2^4 binding component ablation offline seal verification
python3 reproduce_e01.py

# E07: RFC 8785 Canonical JSON cross-runtime determinism
python3 reproduce_e07.py

# GLHS R3 prospective reproducibility sweep (E00–E14)
python3 reproduce_q3_r3.py --skip-git-check

# GLHS R4 prospective reproducibility sweep (E15–E21)
python3 reproduce_q4_r4.py --skip-git-check
```

### 4.2 Network Isolation Invariant

Every reproduction runner activates `disable_network()` fail-closed enforcement at initialization:
- Prohibits all TCP/UDP socket creation (`socket.socket`).
- Prohibits external DNS resolution (`socket.getaddrinfo`, `socket.gethostbyname`).
- Raises `NetworkAccessProhibitedError` immediately upon any network attempt.
- Operates entirely on frozen local artifacts and immutable checksums (`checksums.sha256`).

---

## 5. Pre-Commit Hooks and Code Quality Standards

Code quality is enforced before commits and pushes via `.pre-commit-config.yaml`:
- **Commit stage:** Runs `ruff` (linting with `--fix`), `ruff-format` (code formatting), and `mypy` (type checking).
- **Push stage:** Runs `pytest-check` across `services/api/tests` and `services/ml/tests`.

To install or reinstall hooks:
```bash
make precommit-install
# Or:
pre-commit install
```
