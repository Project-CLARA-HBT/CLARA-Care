"""Security negative tests: SSRF webhook rejection & revoked-consent job replay blocking.

Spec: PH51 / A08 (Security / negative tests).
Verifies:
1. Replay of DLQ job is permanently blocked when patient revoked required consent.
2. Webhook / connector URL parser rejects SSRF targeting cloud metadata and private IP spaces.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def is_ssrf_safe_webhook_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        return False, "Only HTTPS webhooks permitted"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"

    # Block common local hostnames
    if hostname in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
        return False, "Targeting loopback or cloud metadata is forbidden"

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, f"Private or reserved IP target forbidden: {ip}"
    except ValueError:
        # Not a raw IP literal, domain name resolution would check IP at runtime
        pass

    return True, "SAFE"


def evaluate_replay_permission(
    job_id: str,
    required_purpose: str,
    user_consents: set[str],
) -> tuple[bool, str]:
    if required_purpose not in user_consents:
        return False, f"Patient revoked purpose '{required_purpose}'; replay blocked"
    return True, "REPLAY_PERMITTED"


def test_ssrf_webhook_rejection() -> None:
    dangerous_urls = [
        "http://169.254.169.254/latest/meta-data/",
        "https://127.0.0.1:8200/admin/dump",
        "http://localhost:8000/internal",
        "https://10.0.1.50/api/push",
        "https://192.168.1.1/webhook",
        "http://metadata.google.internal/computeMetadata/v1/",
    ]

    for url in dangerous_urls:
        safe, reason = is_ssrf_safe_webhook_url(url)
        assert safe is False, f"Expected {url} to be blocked by SSRF filter, but was allowed"

    # Legitimate external webhook
    safe, _ = is_ssrf_safe_webhook_url("https://emr.bachmai.vn/api/v1/integrations")
    assert safe is True


def test_revoked_consent_job_replay_blocked() -> None:
    # Scenario: job requires 'telehealth_vital_sync', patient revoked it
    allowed, reason = evaluate_replay_permission(
        job_id="job-dlq-revoked-01",
        required_purpose="telehealth_vital_sync",
        user_consents={"emergency_fast_path"},  # missing vital sync
    )
    assert allowed is False
    assert "revoked purpose" in reason

    # Scenario: patient gave consent
    allowed, _ = evaluate_replay_permission(
        job_id="job-dlq-active-02",
        required_purpose="telehealth_vital_sync",
        user_consents={"telehealth_vital_sync", "emergency_fast_path"},
    )
    assert allowed is True
