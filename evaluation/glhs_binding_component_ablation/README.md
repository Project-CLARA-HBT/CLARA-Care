# GLHS E01: Component-Wise Exact-Binding 2^3 Factorial Ablation

Evaluation-only scientific artifact for evaluating the necessity, sufficiency, and interactions of the 3 exact-binding dimensions:
1. `c_id` (Snapshot Identity)
2. `c_digest` (Snapshot & Manifest Content Digest)
3. `c_evidence` (Declared Evidence Membership)

## Factorial 2^3 Arms

| Arm | Identity ($c_{id}$) | Digest ($c_{digest}$) | Evidence ($c_{evidence}$) |
|---|:---:|:---:|:---:|
| **B000** | OFF | OFF | OFF |
| **B100** | ON | OFF | OFF |
| **B010** | OFF | ON | OFF |
| **B001** | OFF | OFF | ON |
| **B110** | ON | ON | OFF |
| **B101** | ON | OFF | ON |
| **B011** | OFF | ON | ON |
| **B111** | ON | ON | ON (Full Exact Binding) |

All 8 arms hold non-ablated governance invariants constant:
- State version & staleness check
- Current policy epoch & version check
- Current medical consent check
- Actor role, purpose, and task scope authorization
- Snapshot expiry lease check

## Schedule Families (352 Total Logical Schedules)

- **ID-SUB** (32 schedules): Snapshot ID substitution / mismatch.
- **DIGEST-MUT** (32 schedules): Snapshot digest corruption / payload tampering.
- **EVIDENCE-OUTSIDE** (32 schedules): Proposal cites un-disclosed evidence.
- **MIN-SET-SWAP** (32 schedules): Evidence subset swapped for un-disclosed subset.
- **CROSS-SNAPSHOT-SAME-VERSION** (32 schedules): Foreign snapshot reuse across patients/sessions.
- **COORD-SUB** (32 schedules): Governance coordinate substitution.
- **LINEAGE-ROOT-SUB** (32 schedules): Lineage root proposal substitution.
- **EXPIRY-CONTROL** (32 schedules): Expired snapshot lease (negative control).
- **CLEAN** (96 schedules): Legitimate proposals across 12 clinical contexts (positive controls).

Total: 352 schedules $\times$ 8 arms = 2,816 executions.

## Execution & Analysis

```bash
# SQLite smoke run (for unit/integration testing)
python3 evaluation/glhs_binding_component_ablation/postgres_runner.py --backend sqlite

# PostgreSQL isolated execution
export GLHS_BINDING_ABLATION_ISOLATED_RESEARCH=1
export GLHS_BINDING_ABLATION_DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/clara_isolated"
python3 evaluation/glhs_binding_component_ablation/postgres_runner.py --backend postgres

# Analyze & Seal
python3 evaluation/glhs_binding_component_ablation/analyze.py
python3 evaluation/glhs_binding_component_ablation/seal.py --run-id <RUN_ID>
```
