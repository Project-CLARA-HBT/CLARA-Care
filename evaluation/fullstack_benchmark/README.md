# Full-stack benchmark protocol

The PostgreSQL runner calls the API-owned GST/GLHS gateway in process. GLHS
intentionally exposes no arbitrary public GST endpoint, so the manifest
distinguishes this service-layer measurement from HTTP transport latency.

The runner accepts only an explicitly acknowledged, empty, non-default
PostgreSQL database and refuses an existing output path. It upgrades the empty
database through Alembic so append-only triggers and the production schema are
present. It records P50/P95/P99, throughput, SQL reads/writes, write
amplification, state/snapshot/governed-decision reconstruction, audit lookup,
invalidation/error rebuild, CPU, peak RSS, database settings, implementation
SHA, container-image digest and SHA-256 output inventory.

The v2 service-layer contract is intentionally **PARTIAL**. It records
`http_transport`, `source_revocation_propagation` and `concurrent_transition`
as coverage gaps rather than relabelling an error transition as source
revocation. Those paths require separate real-boundary execution.

```bash
DATABASE_URL='postgresql+psycopg://.../new_empty_database' \
python3 -m evaluation.fullstack_benchmark.run_postgresql \
  --output /secure/fullstack-run \
  --database-image-digest sha256:... \
  --acknowledge-isolated-empty-database
python3 -m evaluation.fullstack_benchmark.validate_metrics \
  --metrics /secure/fullstack-run/fullstack_metrics.csv \
  --manifest /secure/fullstack-run/fullstack_manifest.json
```

The database URL is never written to the artifact. Failed or partial attempts
must use a new empty database and output directory; no completed output is
overwritten.
