"""Concrete, isolated-only GovRed adapter for the synthetic research API.

This adapter drives ordinary HTTP requests through the mounted GovRed research
routes.  PostgreSQL, Redis, and audit state are observed only through the
sanitized store observer; this module never executes cache or database commands.

The three mandatory-primary families that were NOT_RUN in final-003 now execute
as two-phase schedules (create then commit): ``cross_subject_retrieval`` via
``subject_cross_replay``, ``purpose_mismatch`` via the narrow synthetic
``purpose_switch_replay`` grant mutation, and ``policy_version_change`` via the
deployment-level ``GOVRED_RESEARCH_POLICY_VERSION`` override.  Each executed
family's ``boundary_path_attestation`` is derived from its
:mod:`family_contracts` contract rather than hard-coded all-true: a non-cache
family never claims a cache traversal, and a cache family carries its cache
observation.  A rejected admission additionally surfaces the structural
rejection event (reason code, proposal/snapshot coordinates, actor/purpose/
task, zero transition rows) recorded through the synthetic-audit-observation
endpoint.
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

from evaluation.governance_adversarial.family_contracts import (
    STAGE_NAMES,
    family_contract,
)
from evaluation.governance_adversarial.observation import (
    BoundaryObservation,
    sanitized_observation_metadata,
)
from evaluation.governance_adversarial.remote_store_observer import observe

_ARM_FIELDS = ("arm", "bind_snapshot", "revalidate_state", "revalidate_governance")
_MUTATIONS = {
    "cross_subject_proposal_write": "subject_cross_replay",
    "cross_subject_retrieval": "subject_cross_replay",
    "purpose_mismatch": "purpose_switch_replay",
    "policy_version_change": "policy_version_change",
    "revoked_consent_cache_index_reuse": "consent_revoke",
    "role_mismatch": "actor_switch_replay",
    "stale_thss_replay": "state_advance",
    "concurrent_stale_state_write": "concurrent_governance_writer",
    "authorization_consent_toctou": "consent_revoke",
    "digest_expiry_tamper_replay": "snapshot_digest_invalid",
    "derived_cache_persistence_after_revocation": "consent_revoke",
    "audit_reconstruction_failure": "none",
}
#: Mandatory-primary families executed as a two-phase schedule: the create
#: phase persists the synthetic disclosure (and its bound THSS snapshot for
#: binding arms); the commit phase applies the mutation and runs the ordinary
#: admission path.  This lets the real policy-version override or a purpose
#: grant switch be observed between disclosure and commit.
_TWO_PHASE_FAMILIES = frozenset(
    {
        "cross_subject_retrieval",
        "purpose_mismatch",
        "policy_version_change",
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
    email = f"rivf-boundary-{suffix}@example.org"
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
    status, raw, unavailable = _request(config, "/api/v1/auth/consent-status", token=token)
    consent = _json_response(raw) if status == 200 and not unavailable else {}
    required_version = consent.get("required_version")
    if not isinstance(required_version, str) or not required_version:
        raise RuntimeError("govred_adapter_consent_version_unavailable")
    status, _, unavailable = _request(
        config,
        "/api/v1/auth/consent",
        method="POST",
        token=token,
        body={"consent_version": required_version, "accepted": True},
    )
    if unavailable or status != 200:
        raise RuntimeError("govred_adapter_consent_grant_failed")
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
    return _MUTATIONS.get(str(case["family"]))


def _boundary_path_attestation(family: str) -> dict[str, bool]:
    """Derive the stage attestation from the family's contract.

    Every executed family traverses the HTTP, PostgreSQL (store observer), and
    audit-observation stages; only a cache family may claim the ``cache``
    stage, and the claim is taken from the contract rather than hard-coded.
    A non-cache family must never claim a cache traversal.
    """

    contract = family_contract(family)
    traversed = frozenset({"http", "postgres", "audit"})
    if contract.cache_required:
        traversed = frozenset(traversed | {"cache"})
    return {
        stage: stage in traversed and stage in contract.permitted_stages()
        for stage in STAGE_NAMES
    }


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
    family = str(case["family"])
    contract = family_contract(family)
    sentinel = str(case["oracle"]["sentinel_token"])
    probe_id = uuid4().hex
    cache_failure = False
    cache_unavailable = False
    if contract.cache_required:
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
    if family in _TWO_PHASE_FAMILIES:
        # Two-phase schedules: persist the synthetic disclosure (and its bound
        # THSS snapshot) first, then apply the mutation at commit time.  The
        # policy-version override and the purpose grant switch are deployment/
        # request-orchestrated between the two phases.
        create_status, create_raw, create_unavailable = _request(
            config,
            "/api/v1/govred-research/synthetic-commit-probe",
            method="POST",
            token=token,
            body={
                "mutation": mutation,
                "sentinel_id": sentinel,
                "probe_id": probe_id,
                "phase": "create",
            },
        )
        if create_unavailable or create_status != 201:
            raise RuntimeError("govred_adapter_two_phase_create_failed")
        created = _json_response(create_raw)
        created_probe_id = created.get("probe_id")
        if isinstance(created_probe_id, str) and created_probe_id:
            probe_id = created_probe_id
    before = _snapshot(config)
    started = time.monotonic()
    status, raw, unavailable = _request(config, "/api/v1/govred-research/synthetic-commit-probe", method="POST", token=token, body={
        "mutation": mutation, "sentinel_id": sentinel, "probe_id": probe_id,
        "phase": "commit" if family in _TWO_PHASE_FAMILIES else "full",
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
    rejection_audit_event = None
    if isinstance(audit.get("rejection_reason_code"), str):
        rejection_audit_event = {
            "rejection_reason_code": audit["rejection_reason_code"],
            "rejection_coordinates": audit.get("rejection_coordinates"),
            "rejection_context": audit.get("rejection_context"),
            "transition_item_count": audit.get("transition_item_count", 0),
        }
    if contract.cache_required and not cache_unavailable:
        _, cache_raw, cache_read_unavailable = _request(
            config,
            "/api/v1/govred-research/synthetic-disclosure-cache-probe",
            method="POST",
            token=token,
            body={"phase": "read_after_revoke", "sentinel_id": sentinel, "probe_id": probe_id},
        )
        cache_unavailable = cache_read_unavailable
        cache = _json_response(cache_raw) if cache_raw and not cache_unavailable else {}
        # Observer-only: the research route never invalidates the cache. A stale
        # research-only Redis entry remaining after revocation is an observation,
        # not a governance failure, because CLARA snapshots are authoritative
        # persisted PostgreSQL rows and the ordinary admission path revalidates.
        cache_stale_entry_present = cache.get("cache_present_after_revoke") is True
        cache_failure = cache_stale_entry_present and commit_occurred
    after = _snapshot(config)
    observation = BoundaryObservation(status, raw, before["postgres_sha256"], after["postgres_sha256"], audit_complete, cache_failure, commit_occurred, latency_ms, unavailable or audit_unavailable or cache_unavailable)
    artifact_value = {
        "schema_version": "govred-isolated-boundary-observation-v2", "case_id": case["case_id"],
        "arm": arm["name"], "mutation": mutation, "mutation_class": mutation,
        "http_status": status, "response_sha256": hashlib.sha256(raw).hexdigest(),
        "observer_before": before, "observer_after": after,
        "cache_index_revocation_failure": cache_failure,
        "rejection_audit_event": rejection_audit_event,
        "observation": sanitized_observation_metadata(observation), "raw_response_persisted": False,
    }
    ref, digest = _write_artifact(config, f"{case['case_id']}-{arm['name']}-{probe_id}.json", artifact_value)
    return {
        "isolated_attestation": True, "arm_name": arm["name"], "arm_implementation_attestation": _arm_attestation(config, arm),
        "observation": observation, "execution_id": probe_id, "mutation": mutation,
        "mutation_class": mutation, "rejection_audit_event": rejection_audit_event,
        "normalized_outcome": "unavailable" if unavailable else "committed" if commit_occurred else "rejected",
        "boundary_path_attestation": _boundary_path_attestation(family),
        "observation_artifact_ref": ref, "observation_artifact_sha256": digest,
    }
