#!/usr/bin/env bash
set -euo pipefail
: "${1:?supply a new output directory}"
cd "$(git rev-parse --show-toplevel)"
# A private parent restricts access to the trust-authenticated Unix socket.
scratch=$(mktemp -d)
mkdir "$scratch/socket"
export STUDY_IMAGE=postgres@sha256:e62fbf9d3e2b49816a32c400ed2dba83e3b361e6833e624024309c35d334b412
container=$(docker run -d --network none -v "$scratch/socket:/var/run/postgresql" \
    -e POSTGRES_HOST_AUTH_METHOD=trust "$STUDY_IMAGE" -c listen_addresses='')
trap 'docker stop -t 10 "$container" >/dev/null || true; docker rm -fv "$container" >/dev/null; rm -rf "$scratch"' EXIT
export PGHOST="$scratch/socket" PGUSER=postgres PGPORT=5432 PGCONNECT_TIMEOUT=3
# Wait for the final postgres PID 1, past the temporary initialization server.
for _ in {1..120}; do
    if docker exec "$container" sh -c 'test "$(cat /proc/1/comm)" = postgres && pg_isready -q'; then
        break
    fi
    sleep 0.25
done
python -m research.venue2027.dsn.process_study.study "$1"
