"""Concrete, isolated-only GovRed adapter for the synthetic research API.

This adapter drives ordinary HTTP requests through the mounted GovRed research
routes. PostgreSQL, Redis, and audit state are observed only through the
sanitized store observer; this module never executes cache or database commands.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from evaluation.governance_adversarial.observation import (
    BoundaryObservation,
    sanitized_observation_metadata,
)
from evaluation.governance_adversarial.remote_store_observer import observe

_ARM_FIELDS = ("arm", "bind_snapshot", "revalidate_state", "revalidate_governance")
_MUTATIONS = {
    "cross_subject_proposal_write": "subject_cross_replay",
    "revoked_consent_cache_index_reuse": "consent_revoke",
    "role_mismatch": "actor_switch_replay",
    "stale_thss_replay": "state_advance",
    "concurrent_stale_state_write": "concurrent_governance_writer",
    "authorization_consent_toctou": "consent_revoke",
    "digest_expiry_tamper_replay": "snapshot_digest_invalid",
    "derived_cache_persistence_after_revocation": "consent_revoke",
    "audit_reconstruction_failure": "none",
}
_CACHE_OBSERVATION_FAMILIES = frozenset(
    {
        "revoked_consent_cache_index_reuse",
        "derived_cache_persistence_after_revocation",
    }
)


@dataclass(frozen=True)
class AdapterConfig:
    base_url: str
    postgres_container: str
    redis_container: str
    artifact_root: Path
    revision: str


def _config() -> AdapterConfig:
    """Accept only an explicit, non-production, isolated deployment."""

    if os.environ.get("CLARA_GOVRED_ISOLATED_RESEARCH") != "1":
        raise RuntimeError("govred_adapter_requires_isolated_research_attestation")
    if os.environ.get("ENV", os.environ.get("ENVIRONMENT", "development")).lower() == "production":
        raise RuntimeError("govred_adapter_forbidden_in_production")
    project = os.environ.get("GOVRED_RESEARCH_PROJECT", "")
    if not project.startswith("clara-rivf-"):
        raise RuntimeError("govred_adapter_project_attestation_invalid")
    base_url = os.environ.get("GOVRED_RESEARCH_BASE_URL", "").rstrip("/")
    artifact_root = os.environ.get("GOVRED_ARTIFACT_ROOT", "")
    postgres = os.environ.get("GOVRED_POSTGRES_CONTAINER", "")
    redis = os.environ.get("GOVRED_REDIS_CONTAINER", "")
    if not base_url.startswith(("http://", "https://")) or not artifact_root:
        raise RuntimeError("govred_adapter_configuration_missing")
    if not postgres.startswith("clara-rivf-") or not redis.startswith("clara-rivf-"):
        raise RuntimeError("govred_adapter_store_outside_isolated_project")
    revision = os.environ.get("GOVRED_IMPLEMENTATION_REVISION")
    if revision is None:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True
        ).stdout.strip()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise RuntimeError("govred_adapter_revision_invalid")
    return AdapterConfig(base_url, postgres, redis, Path(artifact_root), revision)


def _request(
    config: AdapterConfig, path: str, *, method: str = "GET", body: dict[str, object] | None = None,
    token: str | None = None,
) -> tuple[int | None, bytes, bool]:
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(config.base_url + path, data=payload, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read(), False
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), False
    except urllib.error.URLError:
        return None, b"", True


def _json_response(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("govred_adapter_response_json_invalid") from exc
    if not isinstance(value, dict):
        raise TypeError("govred_adapter_response_shape_invalid")
    return value


def _identity(config: AdapterConfig) -> str:
    suffix = uuid4().hex
    email = f"rivf-boundary-{suffix}@example.test"
    password = f"Rivf{suffix[:16]}9"
    status, _, unavailable = _request(config, "/api/v1/auth/register", method="POST", body={
        "email": email, "password": password, "full_name": "Synthetic GovRed Boundary",
        "accepted_terms": True, "accepted_privacy": True, "accepted_medical_consent": True,
    })
    if unavailable or status != 200:
        raise RuntimeError("govred_adapter_synthetic_registration_failed")
    status, raw, unavailable = _request(
        config, "/api/v1/auth/login", method="POST", body={"email": email, "password": password}
    )
    token = _json_response(raw).get("access_token") if status == 200 and not unavailable else None
    if not isinstance(token, str):
        raise TypeError("govred_adapter_synthetic_login_failed")
    return token


def _snapshot(config: AdapterConfig) -> dict[str, str]:
    return observe(
        postgres_container=config.postgres_container,
        redis_container=config.redis_container,
        redis_pattern="*:govred-research-cache:*",
    )


def _write_artifact(config: AdapterConfig, name: str, value: dict[str, object]) -> tuple[str, str]:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path = config.artifact_root / "observations" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return str(path.relative_to(config.artifact_root)), hashlib.sha256(encoded).hexdigest()


def _arm_attestation(config: AdapterConfig, arm: dict[str, object]) -> dict[str, object]:
    value = {
        "name": arm["name"], "bind_snapshot": arm["bind_snapshot"],
        "revalidate_state": arm["revalidate_state"],
        "revalidate_governance": arm["revalidate_governance"], "research_only": True,
        "runtime_mode": "isolated_research_only", "production_defaults_unchanged": True,
        "implementation_revision": config.revision,
    }
    ref, digest = _write_artifact(config, f"arm-{arm['name']}.json", value)
    return {**value, "implementation_artifact_ref": ref, "implementation_artifact_sha256": digest}


def _mutation_for(case: dict[str, object]) -> str | None:
    family = case["family"]
    if family == "cross_subject_retrieval":
        return None
    return _MUTATIONS.get(str(family))


def adapter(*, case: dict[str, object], arm: dict[str, object]) -> dict[str, object]:
    """Execute one retry-collapsed logical case through the real isolated path.

    Unsupported schedules remain explicitly ``NOT_RUN``. No outcome is inferred
    from an observer hash: the HTTP response and post-commit audit endpoint are
    the admission evidence, while store hashes establish independent observation.
    """

    config = _config()
    mutation = _mutation_for(case)
    if mutation is None:
        return {"run_status": "NOT_RUN"}
    token = _identity(config)
    status, raw, unavailable = _request(config, "/api/v1/govred-research/arm", token=token)
    report = _json_response(raw) if status == 200 and not unavailable else {}
    if tuple(report.get(field) for field in _ARM_FIELDS) != (
        arm["name"], arm["bind_snapshot"], arm["revalidate_state"], arm["revalidate_governance"],
    ):
        raise RuntimeError("govred_adapter_arm_endpoint_mismatch")
    before = _snapshot(config)
    sentinel = str(case["oracle"]["sentinel_token"])
    probe_id = uuid4().hex
    cache_failure = False
    cache_unavailable = False
    if str(case["family"]) in _CACHE_OBSERVATION_FAMILIES:
        # Seed the governed disclosure before the commit route persists the
        # scheduled revocation. Cache invalidation remains entirely service-owned.
        seed_status, _, cache_unavailable = _request(
            config,
            "/api/v1/govred-research/synthetic-disclosure-cache-probe",
            method="POST",
            token=token,
            body={"phase": "seed", "sentinel_id": sentinel, "probe_id": probe_id},
        )
        if seed_status != 200 and not cache_unavailable:
            raise RuntimeError("govred_adapter_cache_seed_failed")
    started = time.monotonic()
    status, raw, unavailable = _request(config, "/api/v1/govred-research/synthetic-commit-probe", method="POST", token=token, body={
        "mutation": mutation, "sentinel_id": sentinel, "probe_id": probe_id,
    })
    latency_ms = (time.monotonic() - started) * 1000
    response = _json_response(raw) if raw else {}
    commit_occurred = False
    if status is not None and status < 400:
        commit_occurred = response.get("outcome") in {"transition_committed", "indeterminate_ordering_transition_committed"}
    _, audit_raw, audit_unavailable = _request(
        config,
        f"/api/v1/govred-research/synthetic-audit-observation?sentinel_id={sentinel}&probe_id={probe_id}",
        token=token,
    )
    audit = _json_response(audit_raw) if audit_raw and not audit_unavailable else {}
    audit_complete = audit.get("audit_reconstruction_complete") is True
    if str(case["family"]) in _CACHE_OBSERVATION_FAMILIES and not cache_unavailable:
        _, cache_raw, cache_read_unavailable = _request(
            config,
            "/api/v1/govred-research/synthetic-disclosure-cache-probe",
            method="POST",
            token=token,
            body={"phase": "read_after_revoke", "sentinel_id": sentinel, "probe_id": probe_id},
        )
        cache_unavailable = cache_read_unavailable
        cache = _json_response(cache_raw) if cache_raw and not cache_unavailable else {}
        cache_failure = cache.get("cache_present_after_revoke") is True
    after = _snapshot(config)
    observation = BoundaryObservation(status, raw, before["postgres_sha256"], after["postgres_sha256"], audit_complete, cache_failure, commit_occurred, latency_ms, unavailable or audit_unavailable or cache_unavailable)
    artifact_value = {
        "schema_version": "govred-isolated-boundary-observation-v1", "case_id": case["case_id"],
        "arm": arm["name"], "http_status": status, "response_sha256": hashlib.sha256(raw).hexdigest(),
        "observer_before": before, "observer_after": after,
        "cache_index_revocation_failure": cache_failure,
        "observation": sanitized_observation_metadata(observation), "raw_response_persisted": False,
    }
    ref, digest = _write_artifact(config, f"{case['case_id']}-{arm['name']}-{probe_id}.json", artifact_value)
    return {
        "isolated_attestation": True, "arm_name": arm["name"], "arm_implementation_attestation": _arm_attestation(config, arm),
        "observation": observation, "execution_id": probe_id,
        "normalized_outcome": "unavailable" if unavailable else "committed" if commit_occurred else "rejected",
        "boundary_path_attestation": {"http": True, "postgres": True, "cache": True, "audit": True},
        "observation_artifact_ref": ref, "observation_artifact_sha256": digest,
    }
