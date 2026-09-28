# E10 Full-Stack Performance Characterization Summary

- **Repetitions (N):** 100 per operation class
- **Claim Eligible:** `True`
- **Sample Size Sufficient (N >= 100):** `True`
- **HTTP Transport Measured:** `True`
- **Architecture Path:** `client>fastapi_http>auth_rbac_csrf>glhs_validation_thss>postgresql_commit>response_audit_outbox`
- **Total DB Reads:** 12242
- **Total DB Writes:** 1815
- **Peak RSS Memory:** 2116.97 MB

## Latency & Resource Breakdown

| Operation | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (tps) | Reads | Writes | Write Amp | CPU % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `transition` | 99.13 | 113.31 | 166.94 | 9.6 | 6201 | 1700 | 17.00 | 70.1% |
| `reconstruction` | 13.26 | 13.87 | 14.82 | 75.2 | 1100 | 0 | 0.00 | 101.3% |
| `snapshot_compile` | 27.37 | 32.44 | 35.52 | 37.0 | 1100 | 100 | 1.00 | 63.7% |
| `governed_decision_reconstruction` | 13.60 | 14.22 | 14.60 | 66.9 | 1100 | 0 | 0.00 | 101.2% |
| `audit_lookup` | 13.83 | 14.44 | 14.82 | 72.2 | 1100 | 0 | 0.00 | 101.3% |
| `invalidation_rebuild` | 10.81 | 11.77 | 13.41 | 86.5 | 841 | 15 | 0.15 | 99.8% |
| `enter_in_error_rebuild` | 10.69 | 11.54 | 11.76 | 92.8 | 800 | 0 | 0.00 | 101.3% |
