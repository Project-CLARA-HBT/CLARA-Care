# Risk Register: Phase PH02 — Agent A03 (Domain + GLHS Services)

**Phase:** PH02  
**Agent:** A03  
**Role:** Domain + GLHS services  
**Worktree:** `/dev/shm/clara_worktrees/PH02_A03`  
**Branch:** `phase/ph02-a03`  
**Frozen Ground-Truth HEAD SHA:** `879dc5dcfcaae91b3626e28062043d934294478b`  
**Task:** Ten task-scoped worktree paths & path governance; audit and formalize path lane allocations for all 10 agent roles across domain modules (glhs, lifemap, phr, compliance, core); verify that no two roles have overlapping write paths in PHASE_TASKS.json.  
**Evaluation Date:** 2026-10-21  

---

## 1. Governance & Boundary Risk Overview

Phase PH02 establishes the 10-subagent parallel worktree topology, path lane enforcement, and isolation invariants. For Agent A03 (Domain + GLHS services), maintaining airtight boundary separation and path governance is safety-critical to protect clinical domain logic:
1. **Parallel Execution Collision Risk:** Uncoordinated writes across subagents to the same directories or shared entry files causing merge conflicts and race conditions.
2. **Domain Encapsulation Violation:** Subagents attempting modifications to core domain models (`glhs/`, `lifemap/`, `phr/`, `compliance/`, `core/`) outside the designated domain role.
3. **Cross-Service Architectural Coupling:** Bypassing HTTP/gRPC boundaries through direct Python imports between `services/api` and `services/ml`.
4. **Specification Drift in Future Phases:** Cross-phase lane overlap discovered in later phases of `PHASE_TASKS.json` where control-plane paths or broad directory wildcards overlap between agents.

---

## 2. Identified Risks and Gaps Matrix

| Risk ID | Severity | Category | Component | Description & Forensic Evidence | Blast Radius & Potential Impact | Mitigation / Remediation Proposal |
|---|---|---|---|---|---|---|
| **RSK-PH02-A03-001** | Low (P3) | Specification / Future Phases | `PHASE_TASKS.json` (Phases PH40–PH70) | In phases PH40 through PH70, Agent A07 path lane includes `services/control-plane/tests/` while Agent A08 includes `services/control-plane/tests/security/`. Prefix containment creates potential write contention if both agents touch security test files. | If subagents run in parallel during those future phases without file-level locks, concurrent edits to security tests could cause merge conflicts. | When entering Phase PH40, refine A07's lane to exclude `services/control-plane/tests/security/` or serialize test additions. In Phase PH02, zero collisions exist. |
| **RSK-PH02-A03-002** | Medium (P2) | Specification / Future Phases | `PHASE_TASKS.json` (Phases PH40–PH70) | In phases PH40–PH70, Agent A04 path lane contains broad prefix `services/api/src/clara_api/`, which contains domain directories. | Overlaps with A03's domain path allocations if both agents were to edit domain modules concurrently in phases 40–70. | Restrict Agent A04 in those phases to ML proxy and gateway paths (e.g. `services/api/src/clara_api/api/v1/endpoints/ml_*.py`) rather than the broad root of `clara_api/`. |
| **RSK-PH02-A03-003** | Low (P3) | Test Suite / Working Directory | `services/api/tests/test_glhs_canonical_json.py` | Line 302 runs a subprocess with `os.path.abspath('services/api/src')`. When invoked with `cd services/api && pytest ...`, the path resolves relative to `services/api`, failing to locate `clara_api`. | Isolated execution from inside `services/api` fails `test_cross_process_determinism`, while root-level execution passes. | Remediate in a dedicated test fix task (Agent A07) by using `Path(__file__).resolve().parents[3]` to dynamically determine the repository root. |
| **RSK-PH02-A03-004** | Low (P3) | Test Suite / Flakiness | `services/api/tests/test_glhs_canonical_json.py` | Hypothesis health check `HealthCheck.too_slow` triggered under heavy CPU load during `test_property_determinism` (generating nested JSON inputs took >1.9s). | Potential flakiness in automated CI environments under high parallelism or resource contention. | Add `@settings(suppress_health_check=[HealthCheck.too_slow])` to `test_property_determinism` in `test_glhs_canonical_json.py`. |
| **RSK-PH02-A03-005** | High (P1) (Locked) | Domain Isolation / Zero ML Imports | Domain modules (`glhs`, `lifemap`, `phr`, `compliance`, `core`) | Direct in-process imports of `clara_ml` would break independent deployment, hermetic packaging, and container boundaries between API and ML runtimes. | AST scan in `test_domain_path_boundaries.py` confirmed 0 direct `clara_ml` imports in all 44 domain source files. | Automated AST boundary test continuously gates pull requests in CI, preventing any accidental imports. |

---

## 3. Defense-in-Depth & Architectural Safeguards

1. **Deterministic Path Governance Engine (`core/path_governance.py`):**
   Provides automated path normalization, trailing-slash enforcement, and prefix containment detection across any two paths, guaranteeing that directory lanes cannot overlap.
2. **Access Control Checker (`is_path_allowed_for_agent`):**
   Can be plugged into Git pre-commit hooks, CI checks, or worktree synchronization scripts to block any commit modifying files outside an agent's allocated path lane or inside another agent's artifact directory.
3. **AST-Level Zero-Coupling Verifier:**
   Automated Python AST traversal validates that all domain modules (`glhs`, `lifemap`, `phr`, `compliance`, `core`) communicate with `clara_ml` strictly via HTTP/gRPC interfaces rather than in-process imports.
4. **Isolated Worktree Discipline:**
   Every subagent operates in an isolated worktree under `/dev/shm/clara_worktrees/PH02_A0*` and writes deliverables exclusively to its own `artifacts/PH02/A0*/` directory.
