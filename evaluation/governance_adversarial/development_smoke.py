"""One synthetic HTTP boundary smoke probe, explicitly not a headline runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import urllib.error
import urllib.request
from pathlib import Path


def _request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    token: str | None = None,
    profile: str | None = None,
) -> tuple[int, dict]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if profile:
        headers["X-CLARA-Profile-Context"] = profile
    request = urllib.request.Request(
        base_url.rstrip("/") + path, data=payload, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(), exc.code
    parsed = json.loads(raw) if raw else {}
    return status, parsed


def _identity(base_url: str, label: str) -> tuple[str, str]:
    suffix = secrets.token_hex(8)
    email = f"rivf-{label}-{suffix}@example.com"
    password = f"Rivf{suffix}9"
    status, _ = _request(
        base_url,
        "/api/v1/auth/register",
        method="POST",
        body={
            "email": email,
            "password": password,
            "full_name": f"Synthetic {label}",
            "accepted_terms": True,
            "accepted_privacy": True,
            "accepted_medical_consent": True,
        },
    )
    if status != 200:
        raise RuntimeError(f"synthetic_registration_failed:{status}")
    status, login = _request(
        base_url, "/api/v1/auth/login", method="POST", body={"email": email, "password": password}
    )
    token = login.get("access_token") if status == 200 else None
    if not isinstance(token, str):
        raise TypeError("synthetic_login_failed")
    status, profiles = _request(base_url, "/api/v1/profiles", token=token)
    if status != 200 or not isinstance(profiles, list) or len(profiles) != 1:
        raise RuntimeError("synthetic_profile_provisioning_failed")
    profile_id = profiles[0].get("id")
    if not isinstance(profile_id, str):
        raise TypeError("synthetic_profile_identifier_missing")
    return token, profile_id


def run(base_url: str) -> dict[str, object]:
    attacker_token, _ = _identity(base_url, "attacker")
    _, target_profile = _identity(base_url, "target")
    # `/profiles/context` is only a UI recovery hint.  Lifemap resolves an
    # actual profile-scoped resource and fails closed for a foreign profile.
    status, response = _request(
        base_url, "/api/v1/lifemap/today", token=attacker_token, profile=target_profile
    )
    response_bytes = json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8")
    detail = response.get("detail")
    denied = status == 404 and isinstance(detail, dict) and detail.get("code") == "scope_forbidden"
    return {
        "schema_version": "govred-development-smoke-v2",
        "status": "development_smoke_not_headline",
        "family": "cross_subject_retrieval",
        "transport": "HTTP API -> authenticated Lifemap scope resolution -> isolated PostgreSQL/Redis",
        "http_status": status,
        "cross_subject_scope_denied": denied,
        "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
        "raw_response_persisted": False,
        "note": "One synthetic profile-scope probe only; not a frozen logical attack result.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
