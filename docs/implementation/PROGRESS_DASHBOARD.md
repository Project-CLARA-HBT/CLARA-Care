# CLARA Care Multi-Agent Phase DAG Progress & Checkpoint Dashboard

## 1. Overview & Purpose

The CLARA Care Multi-Agent Phase DAG Progress & Checkpoint Dashboard (`scripts/ops/progress_dashboard.py`) provides authoritative, real-time observability over the execution state of the 101-phase roadmap defined in `CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK`.

It parses:
1. `machine/DAG_TOPOLOGICAL_ORDER.json`: Authoritative topological ordering of 101 phases (`PH00` through `PH100`).
2. `machine/PHASE_TASKS.json`: Phase definitions, dependencies, agent task specifications, and acceptance artifact schemas.
3. `artifacts/`: Integration manifests, agent deliverables, test reports, risk logs, and defect ledgers.
4. `/dev/shm/clara_worktrees/`: Active concurrent subagent worktrees (`PH<NN>_A<XX>`).

The dashboard visualizes:
- **Phase Completion Matrix**: Progress across topological waves, completed agents (0–10/10), and execution state (`COMPLETED`, `IN_PROGRESS`, `READY`, `BLOCKED`, `PENDING`).
- **Current Phase Spotlight**: Focused breakdown of the active wavefront, inspecting all 10 subagents (`A01`–`A10`), roles, deliverables, test results, and blocker status.
- **Defect Remediation Ledger**: Tracks baseline defects discovered during audits and reconciles them against verified remediations (e.g., `DEFECT-01`, `DEFECT-02`, `SEC-CRIT-01`).
- **Active Blocker Ledger**: Surfaces critical path impediments and unresolved blockers preventing downstream phases from activating.

---

## 2. Architecture & Design Principles

### 2.1 Multi-Candidate Source Discovery
The tool operates seamlessly across isolated git worktrees, host checkouts, and CI runners:
- Inspects `./machine/` or `<repo_root>/machine/` for DAG order and phase tasks.
- Falls back to `CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK/machine/` if present.
- Discovers live concurrent agent deliverables in `/dev/shm/clara_worktrees/` before integration merge.
- Supports explicit overrides via `--machine-dir`, `--dag-order`, `--phase-tasks`, `--artifacts-dir`, and `--worktrees-dir`.

### 2.2 DAG Wavefront State Model
Phases progress through deterministic states:
- `COMPLETED`: Integration manifest exists with `integration_status == "PASSED"`, or all 10 agents completed with deliverables.
- `IN_PROGRESS`: Phase dependencies are satisfied and one or more subagents have begun active execution or emitted deliverables.
- `READY`: All upstream dependencies are `COMPLETED`, ready for agent scheduling.
- `BLOCKED`: Any required prerequisite phase is `BLOCKED`, or an active agent in the phase has reported an unresolved blocker.
- `PENDING`: Waiting for upstream prerequisite phases to complete in topological order.

### 2.3 Hermetic Zero-Dependency Execution
Implemented purely with the Python standard library (`argparse`, `dataclasses`, `json`, `pathlib`, `shutil`, `re`, `datetime`). Runs without third-party package dependencies across Python `>= 3.11` environments.

---

## 3. Command-Line Usage

### 3.1 Standard Terminal Dashboard
```bash
python3 scripts/ops/progress_dashboard.py
```
Outputs an ANSI-colored, Unicode-bordered terminal dashboard sized dynamically to terminal dimensions.

### 3.2 Ascii & Non-Color Modes (CI / Scripting)
```bash
# Plain ASCII borders with no color codes
python3 scripts/ops/progress_dashboard.py --ascii --no-color
```

### 3.3 Phase Drill-Down
```bash
# Focus spotlight on a specific phase
python3 scripts/ops/progress_dashboard.py --phase PH01
```

### 3.4 Machine-Readable Formats
```bash
# Emit full JSON state for CI ingestion or metrics scraping
python3 scripts/ops/progress_dashboard.py --format json

# Emit GitHub-flavored Markdown for PR descriptions or release notes
python3 scripts/ops/progress_dashboard.py --format markdown
```

### 3.5 Complete 101-Phase Pipeline View
```bash
python3 scripts/ops/progress_dashboard.py --all-phases
```

### 3.6 Strict Exit Gate (CI Verification)
```bash
# Exits with return code 1 if active phase is BLOCKED or has unresolved blockers
python3 scripts/ops/progress_dashboard.py --strict-exit
```

---

## 4. Test Suite

Unit and integration tests are located in `scripts/ops/test_progress_dashboard.py`:
```bash
pytest scripts/ops/test_progress_dashboard.py
```
Covers:
- Data source resolution and path fallbacks.
- Live repository state and DAG topological order (101 phases).
- Defect reconciliation and historical blocker scoping.
- Terminal, Markdown, and JSON renderers.
- CLI arguments and exit codes.
- Synthetic DAG topologies with simulated blockers.
