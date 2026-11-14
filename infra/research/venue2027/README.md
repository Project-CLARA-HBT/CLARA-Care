# CLARA research PostgreSQL 16 isolation environment

Task: `SH-postgres_isolation` (Phase P03, shared). This directory provisions a
**disposable, network-isolated PostgreSQL 16 cluster** for all CLARA-Care 2027
research studies. It is research infrastructure only — none of it belongs in
production paths.

## Isolation guarantees

1. **Dedicated network.** Compose project `clara-research-pg` with its own
   bridge network `pg_research_net`. No other compose project or container is
   attached to it.
2. **No host port.** The service publishes **no `ports:` mapping**. The cluster
   is reachable *only* from containers/processes attached to
   `pg_research_net`, by the hostname `pg_research`. This makes port
   collisions with host services impossible by construction (the host happens
   to have an unrelated listener on 55432 belonging to another project; this
   cluster never touches host ports at all).
3. **No production credentials.** Users are throwaway research accounts
   created by `initdb/001_init_roles.sql` (`research_app` is `NOSUPERUSER
   NOCREATEDB NOCREATEROLE NOREPLICATION`; `research_admin` owns the
   `research_test` schema). Never substitute production DSNs or secrets.
4. **Fixed research database.** `POSTGRES_DB=clara_research`. The guard
   `research/venue2027/_shared/tools/pg_guard.py` refuses anything else.
5. **Named volume, explicit teardown.** Data lives in named volume
   `pg_research_data`; it is destroyed by teardown (below).
6. **Fail-closed DSN guard.** Every research tool must call
   `pg_guard.assert_isolated_database_url(url)` before connecting.

### Localhost non-isolated databases are refused

`pg_guard` accepts exactly one DSN shape:

```
postgresql://research_app:<throwaway>@pg_research:5432/clara_research
```

Anything else is refused with a stable reason code: `postgresql://...@localhost/...`,
`127.0.0.1`, LAN/VPN addresses, `db.*`/`prod*`/`staging*`/`clara*` hosts
(`PROD_LIKE_HOST` / `NON_ISOLATED_HOST`), non-`clara_research` database names
(`NON_RESEARCH_DBNAME`), and non-postgres schemes such as SQLite or MySQL
(`NON_POSTGRES_SCHEME`). **A localhost (non-isolated) database is refused even
if its database name matches**, because isolation is provided by the dedicated
compose network, not by naming. Malformed input is refused (`UNPARSEABLE_URL`)
rather than guessed at.

## Usage

```bash
docker compose -f infra/research/venue2027/docker-compose.pg.yaml up -d
docker compose -f infra/research/venue2027/docker-compose.pg.yaml down -v
```

From a container on `pg_research_net` (e.g. a study runner attached with
`docker compose ... run --network pg_research_net` or an external
`networks:` entry), the DSN is:

```
postgresql://research_app:research-only-throwaway@pg_research:5432/clara_research
```

## Digest pinning policy

The compose file pins the image **by digest**, not by mutable tag:

```yaml
image: postgres@sha256:e62fbf9d3e2b49816a32c400ed2dba83e3b361e6833e624024309c35d334b412  # postgres:16.4-bookworm
```

Policy:

- The digest is recorded at first pull (2026-11-15) together with the tag and
  date in the compose file header comment.
- Upgrades are deliberate: pull the new minor, verify it is PostgreSQL 16,
  record **date + tag + digest** in the compose header, and re-run the
  integration test (`tests/test_pg_isolation.py`), which asserts
  `SHOW server_version` starts with `16` and writes the observed value to
  `research/venue2027/proof/logs/pg_server_version.log`.
- Never reference a floating tag (`postgres:16`, `postgres:latest`) in research
  compose files; runtime version is additionally recorded per run so evidence
  is never mixed-version.

## Teardown

```bash
docker compose -f infra/research/venue2027/docker-compose.pg.yaml down -v
```

`-v` removes the named volume `pg_research_data`, destroying all research
data. The integration test performs this teardown automatically in a `finally`
block. Without `-v` the volume persists between runs; only do that during
interactive debugging, and finish with `-v`.

## Tests

```bash
# Unit guard tests (no Docker required):
python3 -m pytest -q research/venue2027/_shared/tests/test_pg_guard.py

# Integration test (requires Docker + real PostgreSQL; skips with a clear
# reason if the daemon or image is unavailable):
python3 -m pytest -q infra/research/venue2027/tests/test_pg_isolation.py -rs
```

Per the independent-evidence protocol: claims about PostgreSQL concurrency or
version require a **real PostgreSQL** backend (this cluster). SQLite or any
in-memory substitute is not acceptable evidence and is refused by the guard.
