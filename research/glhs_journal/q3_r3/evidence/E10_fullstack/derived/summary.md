# E10 Full-Stack Performance Characterization Summary

- **Repetitions (N):** 100 per operation class
- **Claim Eligible:** `True`
- **Sample Size Sufficient (N >= 100):** `True`
- **HTTP Transport Measured:** `True`
- **Architecture Path:** `client>fastapi_http>auth_rbac_csrf>glhs_validation_thss>postgresql_commit>response_audit_outbox`
- **Total DB Reads:** 15455
- **Total DB Writes:** 1512
- **Peak RSS Memory:** 2796.60 MB

## Latency & Resource Breakdown

| Operation | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (tps) | Reads | Writes | Write Amp | CPU % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `transition` | 139.89 | 150.82 | 220.97 | 6.9 | 8201 | 1400 | 14.00 | 64.1% |
| `reconstruction` | 23.29 | 25.54 | 27.12 | 42.7 | 1300 | 0 | 0.00 | 74.1% |
| `snapshot_compile` | 28.00 | 29.95 | 31.98 | 35.7 | 1300 | 100 | 1.00 | 72.5% |
| `governed_decision_reconstruction` | 24.46 | 25.61 | 28.96 | 38.5 | 1300 | 0 | 0.00 | 73.5% |
| `audit_lookup` | 24.56 | 25.59 | 26.52 | 40.6 | 1300 | 0 | 0.00 | 71.0% |
| `invalidation_rebuild` | 18.53 | 19.20 | 19.60 | 50.5 | 1054 | 12 | 0.12 | 71.3% |
| `enter_in_error_rebuild` | 18.49 | 19.04 | 19.43 | 54.1 | 1000 | 0 | 0.00 | 73.0% |
