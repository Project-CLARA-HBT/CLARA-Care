# PH02 Demonstration Scenarios

## Scenario 1: Multi-Agent Progress Dashboard & Recovery Tooling (Happy Path)
Run the progress dashboard to inspect roadmap state, DAG readiness, and defect resolution:
```bash
python3 scripts/ops/progress_dashboard.py
```
**Expected Output:**
```text
CLARA Care — Multi-Agent Roadmap Dashboard
Total Phases: 101 | Completed: PH00, PH01, PH02 | Ready: PH03, PH04
DAG Status: VALID (Acyclic, 101 nodes, topological order verified)
```

## Scenario 2: Path ACL Violation Interception (Negative Path)
Run the path ACL checker against an agent attempting to write to an unauthorized directory:
```bash
python3 scripts/ci/check_agent_path_acl.py --agent-id A05 --phase-id PH02 --files services/api/src/clara_api/main.py
```
**Expected Output:**
```text
[ACL VIOLATION] Agent A05 touched file outside designated lane: services/api/src/clara_api/main.py
Exit code: 1
```
This confirms that cross-lane unauthorized code modifications fail closed and are halted before reaching the merge queue.
