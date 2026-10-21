# Risk Register & Mitigation Strategy: Phase Progress Dashboard (PH02 / A09)

## 1. Overview & Risk Landscape

The Phase Progress Dashboard (`scripts/ops/progress_dashboard.py`) is a critical diagnostic and gating tool for orchestrating 10 concurrent subagents across 101 development phases.

This register identifies risks associated with data source availability, concurrent file access, schema drift, and terminal rendering across diverse environments.

---

## 2. Risk Matrix

| Risk ID | Severity | Likelihood | Risk Description | Compensating Control / Mitigation | Status |
|---|---|---|---|---|---|
| **RSK-PH02-01** | MEDIUM | LOW | Missing `machine/` directory in isolated worktree context | Implemented multi-candidate path locator: searches CWD, repo root, parent directories, and `CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK/machine/`. Also supports `--machine-dir`, `--dag-order`, and `--phase-tasks` CLI flags. | **MITIGATED** |
| **RSK-PH02-02** | LOW | MEDIUM | Race condition when reading in-flight subagent artifacts | Files are read using standard read-only semantics with explicit `try...except` blocks and empty-file guards. Partial writes are gracefully treated as in-progress rather than raising fatal parse exceptions. | **MITIGATED** |
| **RSK-PH02-03** | LOW | LOW | Broken pipe error when piping dashboard output to `head` or `less` | Explicitly caught `BrokenPipeError` in CLI execution handler and flush/close stderr cleanly with exit code 0. | **MITIGATED** |
| **RSK-PH02-04** | LOW | LOW | Terminal width clipping or border distortion on narrow screens | Dynamic width detection via `shutil.get_terminal_size()`, defensive string padding with ANSI escape sequence filtering, and fallback `--ascii` rendering mode. | **MITIGATED** |
| **RSK-PH02-05** | MEDIUM | LOW | Schema drift between integer phase dependencies (e.g., `0`) and phase IDs (`"PH00"`) | Implemented two-pass dependency resolution that transparently maps integer indices to canonical phase IDs (`PH{:02d}`). | **MITIGATED** |
| **RSK-PH02-06** | HIGH | LOW | Unresolved historical blockers showing as active blockers | Scoped active blocker ledger strictly to non-completed phases (`status != 'COMPLETED'`), preventing resolved PH00 blockers from blocking PH02. | **MITIGATED** |
| **RSK-PH02-07** | LOW | LOW | PII / PHI leakage in diagnostic output | Script strictly ingests phase IDs, defect codes, and agent task strings. Zero patient, telemetry, or user data is processed. | **MITIGATED** |

---

## 3. Residual Risk Assessment

Residual risk after mitigations is **NEGLIGIBLE**. All operations are read-only, non-destructive, and resilient to incomplete or concurrent agent artifacts.
