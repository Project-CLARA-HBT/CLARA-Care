# Deviations & Trade-Offs: Minimal Read-Set Token Baseline

## 1. Deviations from Full GLHS Representation

1. **Flattened Evidence Representation**: Instead of storing full structured evidence item manifests and DAG edges, the minimal token uses a compact SHA-256 commitment over sorted evidence IDs.
2. **Stateless Transport Token**: The token encapsulates all disclosure coordinates into a single transferable payload rather than requiring separate snapshot manifest resolution for every coordinate.
3. **No Incremental DAG Lineage**: The minimal token tracks direct lineage root binding but omits multi-hop intermediate adaptation branches present in GLHS full manifests.

## 2. Controlled Invariants

- **Schedule Parity**: Replays the identical 352 schedules and 9 families from E01 without modification.
- **Canonical Serialization**: Uses the exact same RFC 8785 canonical JSON serializer (`CANONICALIZATION_PROFILE`) as GLHS to eliminate serialization format as a confounder.
- **Isolated Evaluation Boundary**: Evaluation-only code loaded strictly under `evaluation/`, forbidden from production `services/`.
