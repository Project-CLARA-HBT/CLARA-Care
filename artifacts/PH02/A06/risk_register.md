# Risk Register — Subagent A06 (Mobile Flutter / Prompt & Context Pack Generator)

## 1. Overview & Risk Matrix

- **Subagent**: `A06`
- **Phase**: `PH02`
- **Role**: `Mobile Flutter`
- **Scope**: Agent prompt and bounded context pack generator (`scripts/ops/generate_agent_prompts.py`)
- **Base SHA**: `879dc5dcfcaae91b3626e28062043d934294478b`

| Risk ID | Title | Severity | Likelihood | Impact | Status |
|---|---|---|---|---|---|
| `RISK-PH02-A06-01` | Unpopulated Template Placeholders in Prompt | High | Low | High | Mitigated (Regex Guard) |
| `RISK-PH02-A06-02` | Cross-Agent Write Lane Overlap or Ambiguity | High | Low | Critical | Mitigated (Disjoint Checks) |
| `RISK-PH02-A06-03` | Stale or Mismatched Base SHA Propagation | Critical | Low | Critical | Mitigated (SHA Validation) |
| `RISK-PH02-A06-04` | Subagent Artifact Path Exclusion from Write Lane | Medium | Low | High | Mitigated (Auto-Inclusion) |
| `RISK-PH02-A06-05` | Host Worktree Filesystem Collisions | Low | Medium | Medium | Mitigated (Configurable Base) |

---

## 2. Risk Profiles & Compensating Controls

### RISK-PH02-A06-01: Unpopulated Template Placeholders in Prompt
- **Description**: If `templates/AGENT_TASK_PROMPT.md` contains unpopulated brackets (e.g., `[AGENT_ID]`, `[BASE_SHA]`, `[EXACT_WRITE_PATHS]`), a lower-tier coding model might hallucinate values or fail to identify its assigned boundaries.
- **Compensating Control**:
  - `populate_agent_prompt` runs a strict post-replacement regex check: `re.findall(r"\[[A-Z0-9_]{3,}\]", body)`.
  - If any matching pattern is found, a `ValueError` is raised immediately, halting execution and blocking generation.
  - Verified by unit test `test_generate_ph02_ten_agents` ensuring 0 bracket tokens remain.

### RISK-PH02-A06-02: Cross-Agent Write Lane Overlap or Ambiguity
- **Description**: Two subagents concurrently modifying overlapping file paths can cause merge conflicts, race conditions, or overwrites during sequential fan-in.
- **Compensating Control**:
  - `check_write_lane_isolation()` inspects the pairwise write paths across all 10 agents to detect identical paths or directory-nesting collisions.
  - Generates clear warnings in the bounded context pack (`write_lane_conflicts`).
  - Strict enforcement is integrated with `scripts/ci/check_agent_path_acl.py` (A05) to fail any PR modifying out-of-lane paths.

### RISK-PH02-A06-03: Stale or Mismatched Base SHA Propagation
- **Description**: If subagents are launched with an outdated or incorrect commit SHA, their changes will conflict with recently merged PRs, violating the pinned baseline guarantee.
- **Compensating Control**:
  - `resolve_base_sha()` enforces 40-character hexadecimal format checking (`^[0-9a-fA-F]{40}$`).
  - In absence of an explicit override, defaults to the verified frozen SHA `879dc5dcfcaae91b3626e28062043d934294478b` or queries `git rev-parse HEAD`.
  - The generated prompt explicitly mandates: *"Stop immediately if repo HEAD mismatches that SHA."*

### RISK-PH02-A06-04: Subagent Artifact Path Exclusion from Write Lane
- **Description**: An agent that produces required deliverables (`change_manifest.json`, `test_report.md`, `risk_register.md`) in `artifacts/{phase_id}/{agent_id}/` might have those writes rejected by the path ACL checker if not explicitly in its write lane.
- **Compensating Control**:
  - `derive_write_paths()` automatically injects `artifacts/{phase_id}/{agent_id}/` into the agent's owned write paths.
  - Deliverable acceptance artifacts are explicitly itemized in both `exact_write_paths` and the markdown task prompt.

### RISK-PH02-A06-05: Host Worktree Filesystem Collisions
- **Description**: Running on different workstations where `/dev/shm` is unavailable, non-standard, or has insufficient RAM could lead to failure.
- **Compensating Control**:
  - Default worktree directory `/dev/shm/clara_worktrees` is parameterized via `--worktree-base`.
  - Can be redirected to an arbitrary directory (e.g. `/tmp/clara_worktrees`) when running in resource-restricted or non-Linux environments.
