# Cross-Agent Dependency Request — Subagent A01 (API + contract) -> Subagent A07 (Tests + CI)

## Target Subagent
- **Target:** Subagent A07 (Tests + CI / merge queue and integration worker)
- **Path Lane:** `services/api/tests/;services/ml/tests/;apps/web/e2e/;.github/workflows/`
- **Requesting Agent:** Subagent A01 (API + contract)

## Request Details

### Background
Subagent A01 has implemented:
1. `contracts/agent-execution/agent-manifest.schema.json`: Canonical JSON Schema Draft 2020-12 for 10-subagent execution manifests.
2. `services/api/src/clara_api/schemas.py`: Pydantic validation models (`AgentManifest`, `AgentId`, `AgentManifestStatus`, `AgentTestRunItem`).
3. `contracts/agent-execution/test_agent_manifest_schema.py`: 50 comprehensive unit tests verifying allow, deny, malformed, normalization, and invariant requirements.

### Requested Action
To include `contracts/agent-execution/test_agent_manifest_schema.py` in the default CI pytest execution without crossing subagent write lanes:
1. In `services/api/tests/`, optionally add a test proxy or symlink `test_agent_manifest_schema.py` pointing to `contracts/agent-execution/test_agent_manifest_schema.py`.
2. Ensure CI workflow runs `python -m pytest contracts/agent-execution/test_agent_manifest_schema.py` alongside other contract test suites.

### Ownership Boundary Compliance
Because `services/api/tests/` is within Subagent A07's write lane, Subagent A01 has kept all test artifacts within `contracts/agent-execution/` and `artifacts/PH02/A01/`, strictly adhering to the multi-agent isolated worktree protocol.
