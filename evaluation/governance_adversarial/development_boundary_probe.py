"""Operator-driven, non-headline synthetic RIVF boundary-path probe.

The supplied observer command must return only sanitized hashes for the
isolated PostgreSQL, Redis, and audit stores.  It is invoked after synthetic
identity setup and on completion of the tested request, so account creation is
not confused with request-side persistence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from evaluation.governance_adversarial.development_smoke import _identity, _request

_OBSERVER_FIELDS = ("postgres_sha256", "redis_sha256", "audit_sha256")


def _snapshot(command: list[str]) -> dict[str, str]:
    completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("govred_observer_json_invalid") from exc
    if not isinstance(value, dict) or set(value) != set(_OBSERVER_FIELDS):
        raise RuntimeError("govred_observer_shape_invalid")
    if any(
        not isinstance(value[field], str)
        or len(value[field]) != 64
        or any(character not in "0123456789abcdef" for character in value[field])
        for field in _OBSERVER_FIELDS
    ):
        raise RuntimeError("govred_observer_hash_invalid")
    return {field: value[field] for field in _OBSERVER_FIELDS}


def run(*, base_url: str, observer_command: list[str]) -> dict[str, object]:
    attacker_token, _ = _identity(base_url, "boundary-attacker")
    _, target_profile = _identity(base_url, "boundary-target")
    before = _snapshot(observer_command)
    status, response = _request(
        base_url,
        "/api/v1/lifemap/today",
        token=attacker_token,
        profile=target_profile,
    )
    after = _snapshot(observer_command)
    response_bytes = json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8")
    detail = response.get("detail")
    denied = status == 404 and isinstance(detail, dict) and detail.get("code") == "scope_forbidden"
    return {
        "schema_version": "govred-boundary-development-probe-v1",
        "status": "development_boundary_probe_not_headline",
        "family": "cross_subject_retrieval",
        "transport": "HTTP API -> scope resolver -> isolated PostgreSQL/Redis/audit observer",
        "http_status": status,
        "cross_subject_scope_denied": denied,
        "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
        "observer_before": before,
        "observer_after": after,
        "raw_response_persisted": False,
        "note": "One synthetic strict-system probe only; no research-arm comparison or headline outcome.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--observer-command", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    command = shlex.split(args.observer_command)
    if not command:
        parser.error("govred_observer_command_required")
    result = run(base_url=args.base_url, observer_command=command)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
