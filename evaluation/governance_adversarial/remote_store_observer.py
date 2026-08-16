"""Emit sanitized hashes from one explicitly named isolated Docker project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess


def _capture(command: list[str]) -> bytes:
    return subprocess.run(command, check=True, capture_output=True).stdout


def _require_isolated_research_project(*, postgres_container: str, redis_container: str) -> None:
    """Refuse to inspect stores unless the caller attests an isolated RIVF deployment."""
    if os.environ.get("CLARA_GOVRED_ISOLATED_RESEARCH") != "1":
        raise RuntimeError("govred_remote_observer_requires_isolated_research_attestation")
    if not all(container.startswith("clara-rivf-") for container in (postgres_container, redis_container)):
        raise RuntimeError("govred_remote_observer_container_outside_isolated_project")


def observe(*, postgres_container: str, redis_container: str, redis_pattern: str) -> dict[str, str]:
    _require_isolated_research_project(
        postgres_container=postgres_container,
        redis_container=redis_container,
    )
    # Hash selected governance-store state without emitting row values or keys.
    postgres_query = (
        "SELECT 'phr_profiles=' || count(*) FROM phr_profiles "
        "UNION ALL SELECT 'phr_audit=' || count(*) FROM phr_audit "
        "UNION ALL SELECT 'lifemap_events=' || count(*) FROM lifemap_events "
        "UNION ALL SELECT 'glhs_assertions=' || count(*) FROM glhs_assertions "
        "UNION ALL SELECT 'glhs_transitions=' || count(*) FROM glhs_transitions "
        "UNION ALL SELECT 'glhs_snapshot_manifests=' || count(*) FROM glhs_snapshot_manifests "
        "UNION ALL SELECT 'glhs_commitment_proposals=' || count(*) FROM glhs_clinical_commitment_proposals "
        "UNION ALL SELECT 'glhs_commitment_versions=' || count(*) FROM glhs_clinical_commitment_versions "
        "UNION ALL SELECT 'glhs_commitment_transitions=' || count(*) FROM glhs_clinical_commitment_transitions "
        "ORDER BY 1"
    )
    postgres = _capture(
        [
            "docker", "exec", postgres_container, "sh", "-c",
            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c '
            + json.dumps(postgres_query),
        ]
    )
    audit = _capture(
        [
            "docker", "exec", postgres_container, "sh", "-c",
            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c '
            + json.dumps(
                "SELECT action, entity, entity_id, profile_id, actor_user_id, scope "
                "FROM phr_audit ORDER BY id"
            ),
        ]
    )
    redis = _capture(
        ["docker", "exec", redis_container, "redis-cli", "--scan", "--pattern", redis_pattern]
    )
    canonical_redis = b"\n".join(sorted(redis.splitlines()))
    return {
        "postgres_sha256": hashlib.sha256(postgres).hexdigest(),
        "redis_sha256": hashlib.sha256(canonical_redis).hexdigest(),
        "audit_sha256": hashlib.sha256(audit).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres-container", required=True)
    parser.add_argument("--redis-container", required=True)
    parser.add_argument("--redis-pattern", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            observe(
                postgres_container=args.postgres_container,
                redis_container=args.redis_container,
                redis_pattern=args.redis_pattern,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
