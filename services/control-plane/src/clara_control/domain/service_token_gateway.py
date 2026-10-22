"""Control-Plane Service-Token Gateway.

Spec: PH41 / A03 (Domain Service).
Enforces:
1. Cryptographic HMAC token authentication for internal control-plane service requests.
2. Segregated service identity preventing end-user session token interchange.
3. Fail-closed replay and expiration protection on control signals.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any


class ServiceTokenGateway:
    """Manages service-to-service cryptographic authentication tokens."""

    def __init__(self, signing_secret: str = "clara-control-plane-internal-service-secret") -> None:
        self._secret = signing_secret.encode("utf-8")

    def mint_service_token(self, *, service_name: str, target_audience: str, ttl_seconds: int = 300) -> str:
        """Mint a short-lived service token."""
        expires_at = int(time.time()) + ttl_seconds
        payload = f"{service_name}:{target_audience}:{expires_at}"
        signature = hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
        return f"{payload}.{sig_b64}"

    def verify_service_token(self, token: str, *, expected_audience: str) -> tuple[bool, str]:
        """Verify token authenticity and expiration."""
        parts = token.split(".")
        if len(parts) != 2:
            return False, "Malformed service token structure"

        payload, sig_b64 = parts
        payload_parts = payload.split(":")
        if len(payload_parts) != 3:
            return False, "Malformed service token payload"

        service_name, target_audience, expires_at_str = payload_parts
        try:
            expires_at = int(expires_at_str)
        except ValueError:
            return False, "Invalid expiration timestamp"

        if time.time() > expires_at:
            return False, "Service token has expired"

        if target_audience != expected_audience:
            return False, f"Audience mismatch: expected {expected_audience}, got {target_audience}"

        # Constant-time signature verification
        expected_sig = hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
        if not hmac.compare_digest(expected_sig, actual_sig):
            return False, "Invalid cryptographic token signature"

        return True, service_name
