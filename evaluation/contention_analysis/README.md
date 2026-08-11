# PostgreSQL contention analysis

This experiment runs the production profile-global GLHS transition path at
concurrency 1, 2, 4, 8 and 16. Each race uses a newly seeded synthetic profile.
The same-dependency workload classifies losing version checks as true stale;
the unrelated-slot workload classifies them as false stale because the
intervening transition is outside each proposal's declared `semantic_key`,
which this experiment preregisters as the dependency operationalization.

The study is descriptive and partial. It does not retry rejected attempts and
does not implement resource-partition or dependency-hybrid alternatives,
consent/policy races, or a mixed read/snapshot/write workload. These omissions
remain explicit manifest gaps; the runner never changes production versioning.

Like the full-stack runner, it requires an acknowledged empty non-default
PostgreSQL database, migrates it through Alembic, refuses output reuse and
writes raw attempts, recomputable summaries, environment/estimand metadata and
SHA-256 checksums. No provider or external network call is made by the study.

```bash
DATABASE_URL='postgresql+psycopg://.../new_empty_database' \
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.contention_analysis.run_postgresql \
  --output /new/contention-run \
  --database-image-digest sha256:... \
  --acknowledge-isolated-empty-database

PYTHONPATH=. services/api/.venv/bin/python \
  -m evaluation.contention_analysis.validate --run-dir /new/contention-run
```
