# E10 Full-Stack Performance Characterization Summary

- **Repetitions (N):** 100 per operation class
- **Claim Eligible:** `True`
- **Sample Size Sufficient (N >= 100):** `True`
- **HTTP Transport Measured:** `True`
- **Architecture Path:** `client>fastapi_http>auth_rbac_csrf>glhs_validation_thss>postgresql_commit>response_audit_outbox`
- **Total DB Reads:** 15455
- **Total DB Writes:** 1512
- **Peak RSS Memory:** 4136.66 MB

## Latency & Resource Breakdown

| Operation | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (tps) | Reads | Writes | Write Amp | CPU % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `transition` | 150.98 | 157.99 | 170.07 | 6.4 | 8201 | 1400 | 14.00 | 64.4% |
| `reconstruction` | 24.89 | 28.59 | 30.61 | 39.5 | 1300 | 0 | 0.00 | 73.6% |
| `snapshot_compile` | 29.12 | 60.35 | 549.82 | 21.4 | 1300 | 100 | 1.00 | 46.1% |
| `governed_decision_reconstruction` | 24.87 | 27.24 | 29.57 | 37.9 | 1300 | 0 | 0.00 | 73.9% |
| `audit_lookup` | 24.27 | 25.70 | 27.12 | 41.2 | 1300 | 0 | 0.00 | 73.2% |
| `invalidation_rebuild` | 18.05 | 19.62 | 21.75 | 52.4 | 1054 | 12 | 0.12 | 73.7% |
| `enter_in_error_rebuild` | 18.38 | 19.20 | 19.34 | 54.6 | 1000 | 0 | 0.00 | 73.0% |
