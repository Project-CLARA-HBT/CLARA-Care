# GovRed RIVF freeze and isolated execution

Status: **candidate preparation available; final execution NOT RUN**.

`prepare_freeze.py` creates only a candidate locked partition and a final-freeze
template. Neither artifact is frozen or executable. An independent reviewer must
approve the locked partition and statistics plan before changing either final
artifact to `frozen`; do not self-attest this review.

## Candidate artifacts

Run this on the isolated-stack operator host from the repository checkout. The
output directory is intentionally under ignored `artifacts/` and must contain no
credentials or raw responses.

```bash
RUN_ID=2026-08-17-rivf-freeze-candidate
export RUN_ID
PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.governance_adversarial.prepare_freeze --statistics-plan research/govred_rivf/statistics_plan.json --seed 20260817 --repetitions 30 --output-dir "artifacts/govred/${RUN_ID}/freeze"
PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m pytest -q evaluation/governance_adversarial/test_prepare_freeze.py evaluation/governance_adversarial/test_protocol.py
```

This produces 450 synthetic logical cases: 15 protocol families x 30 repetitions.
It is not a frozen manifest or RIVF result.

## Final freeze gate

The independent reviewer must retain the reviewed final statistics plan and
manifest outside this repository's tracked data, record their SHA-256 values,
set the manifest `status` to `frozen`, retain `partition: locked_test`, and set
`independent_curator_attestation: true`. The final plan must also have
`status: frozen`. The reviewer must verify that its SHA-256 equals
`final_statistics_plan_sha256` in the final manifest. Only then may the
following isolated execution commands be used.

## Remote isolated-stack commands

These commands intentionally reject `clara-app`, production, non-loopback API
ports, shared Docker networks, and non-`clara-rivf-` containers. Substitute a
fresh run ID and unused loopback port. Create the environment file outside the
repository; do not use the example values as secrets.

```bash
RUN_ID=2026-08-17-rivf-final-001
PROJECT=clara-rivf-20260817-final001
PORT=18121
ENV_FILE="$HOME/.config/clara-rivf/${RUN_ID}.env"
mkdir -p "$HOME/.config/clara-rivf"
umask 077
openssl rand -hex 32
```

Put the random values into `$ENV_FILE` with exactly these non-secret fields plus
the generated secrets:

```text
RIVF_RUN_ID=2026-08-17-rivf-final-001
RIVF_COMPOSE_PROJECT=clara-rivf-20260817-final001
RIVF_API_PORT=18121
RIVF_POSTGRES_USER=rivf
RIVF_POSTGRES_DB=govred_rivf
GOVRED_RESEARCH_ARM=GLHS_STRICT
```

Add `RIVF_POSTGRES_PASSWORD`, `RIVF_JWT_SECRET_KEY`, and
`RIVF_ML_INTERNAL_API_KEY` as distinct random values. Run each arm in a fresh
project and volume set; never change `GOVRED_RESEARCH_ARM` in a live project.

```bash
docker compose --env-file "$ENV_FILE" -f deploy/docker/docker-compose.govred-isolated.yml up --build --wait
docker compose --env-file "$ENV_FILE" -f deploy/docker/docker-compose.govred-isolated.yml ps
curl --fail --silent --show-error "http://127.0.0.1:${PORT}/health"
export CLARA_GOVRED_ISOLATED_RESEARCH=1 ENV=development GOVRED_RESEARCH_PROJECT="$PROJECT" GOVRED_RESEARCH_BASE_URL="http://127.0.0.1:${PORT}" GOVRED_POSTGRES_CONTAINER="${PROJECT}-postgres-1" GOVRED_REDIS_CONTAINER="${PROJECT}-redis-1" GOVRED_ARTIFACT_ROOT="$PWD/artifacts/govred/${RUN_ID}" GOVRED_IMPLEMENTATION_REVISION="$(git rev-parse HEAD)"
PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.governance_adversarial.execute --manifest /secure/govred-final-locked-manifest.json --adapter evaluation.governance_adversarial.isolated_boundary_adapter:adapter --output "artifacts/govred/${RUN_ID}/raw_results.csv" --artifact-root "artifacts/govred/${RUN_ID}"
PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.governance_adversarial.validate_results --manifest /secure/govred-final-locked-manifest.json --results "artifacts/govred/${RUN_ID}/raw_results.csv"
PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m evaluation.governance_adversarial.analyze --manifest /secure/govred-final-locked-manifest.json --results "artifacts/govred/${RUN_ID}/raw_results.csv" --output "artifacts/govred/${RUN_ID}/analysis.json"
docker compose --env-file "$ENV_FILE" -f deploy/docker/docker-compose.govred-isolated.yml down --volumes
```

Current adapter coverage is partial: it returns explicit `NOT_RUN` for
`cross_subject_retrieval`, `purpose_mismatch`, `policy_version_change`, and the
three prompt/disclosure stress families. It executes only supported synthetic
commit/cache schedules. `NOT_RUN` is excluded from denominators and prevents a
complete final RIVF comparison. Do not execute the final command sequence until
the independent reviewer accepts this coverage or the adapter is extended and
re-reviewed.
