# PH02-A01 Risk Register

- **Phase:** PH02
- **Subagent:** A01 (API + contract)
- **Evaluation Target:** Agent Execution Manifest Contract & Validation Schemas
- **Date:** 2026-10-21

---

## Risk Assessment Matrix

| Risk ID | Severity | Likelihood | Impact Area | Description | Mitigation Strategy | Status |
|---|---|---|---|---|---|---|
| **RISK-PH02-A01-01** | Medium | Low | Interoperability | Drift between JSON Schema specification (`contracts/agent-execution/agent-manifest.schema.json`) and Pydantic model (`AgentManifest` in `schemas.py`). | Automated test `test_schema_required_fields_contain_exact_mandated_invariants` verifies parity across required fields, agent enums, status enums, and SHA patterns. | **MITIGATED** |
| **RISK-PH02-A01-02** | High | Medium | Compatibility | Legacy manifests in PH00 and PH01 used `frozen_head_sha` instead of `base_sha` and `files_created`/`files_modified` instead of `files_changed`. | `AgentManifest` model includes `AliasChoices("base_sha", "frozen_head_sha")` and model validator `aggregate_files_changed` to ensure seamless backwards-compatibility. | **MITIGATED** |
| **RISK-PH02-A01-03** | Critical | Low | Multi-Agent Safety | An agent modifying files outside assigned path lane could cause unresolvable merge conflicts during fan-in. | Schema requires `files_changed` and `path_lane` declaration; A05 (ownership and path ACL checker) and A07 (merge queue worker) validate write-lane adherence. | **MITIGATED** |
| **RISK-PH02-A01-04** | Critical | Medium | Recoverability | Subagent providing empty, unparseable, or non-actionable `rollback_steps` preventing clean disaster recovery. | Validation schema enforces `min_length=1` on `rollback_steps`, denys empty arrays/strings, and normalizes multi-line text into structured command sequences. | **MITIGATED** |
| **RISK-PH02-A01-05** | High | Low | CI / Orchestration | Subagent emitting non-standard status strings (e.g. `COMPLETED`, `IN_PROGRESS`, `DONE`) breaking merge queue state machine. | Strict literal enum `AgentManifestStatus = Literal["PASSED", "FAILED", "BLOCKED"]` fails closed on any unclassified status values. | **MITIGATED** |

---

## Detailed Risk Analyses

### RISK-PH02-A01-01: Contract Schema Parity
- **Hazard:** Tooling relying on standard JSON Schema (e.g. ajv, python jsonschema, web linters) and backend services relying on Pydantic v2 might diverge if fields are added to one without the other.
- **Remediation:** Centralized contract repository in `contracts/agent-execution/agent-manifest.schema.json` and mirrored Pydantic model in `services/api/src/clara_api/schemas.py`. Unit test suite runs contract invariant tests verifying parity.
- **Residual Risk:** Low.

### RISK-PH02-A01-02: Legacy Manifest Ingestion
- **Hazard:** Ingestion tooling auditing historical runs (PH00, PH01) fails with validation errors due to field naming discrepancies.
- **Remediation:** Evaluated both `artifacts/PH00/A01/change_manifest.json` and `artifacts/PH01/A01/change_manifest.json`. Handled field aliases and aggregated creation/modification lists.
- **Residual Risk:** Negligible.

### RISK-PH02-A01-03: Worktree Write-Lane Integrity
- **Hazard:** Concurrently executing low-capability subagents could modify files in peer lanes, leading to catastrophic overwrites or merge thrashing.
- **Remediation:** Subagent A01 writes strictly to authorized paths (`contracts/agent-execution/`, `services/api/src/clara_api/schemas.py`, `artifacts/PH02/A01/`).
- **Residual Risk:** Low.

### RISK-PH02-A01-04: Non-actionable Rollback Steps
- **Hazard:** In failure scenarios, missing or vague rollback documentation delays system recovery.
- **Remediation:** Validation schema strictly enforces non-empty rollback steps and requires exact shell/git commands.
- **Residual Risk:** Low.
