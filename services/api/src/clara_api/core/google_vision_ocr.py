"""Google Cloud Vision OCR integration using REST API with service account JWT auth."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

_VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/cloud-vision"

_cached_token: dict[str, Any] = {"access_token": "", "expires_at": 0.0}


def _build_jwt(service_account: dict[str, str]) -> str:
    """Build a signed JWT for Google OAuth2 service account auth."""
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": service_account["client_email"],
        "scope": _SCOPE,
        "aud": _TOKEN_URI,
        "iat": now,
        "exp": now + 3600,
    }

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    private_key = serialization.load_pem_private_key(
        service_account["private_key"].encode(), password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())  # type: ignore[union-attr]
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"


def _get_access_token(service_account: dict[str, str]) -> str:
    """Get or refresh an OAuth2 access token for the service account."""
    global _cached_token
    if _cached_token["access_token"] and time.time() < _cached_token["expires_at"] - 60:
        return _cached_token["access_token"]

    jwt_token = _build_jwt(service_account)
    # Bounded outbound timeout (Requirement 10.3): the OAuth token exchange uses
    # an explicit, conservative timeout so a hung upstream cannot stall the OCR
    # path indefinitely. Single attempt — no retry loop, so calls are bounded.
    response = httpx.post(
        _TOKEN_URI,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt_token,
        },
        timeout=15.0,
    )
    response.raise_for_status()
    token_data = response.json()
    _cached_token = {
        "access_token": token_data["access_token"],
        "expires_at": time.time() + token_data.get("expires_in", 3600),
    }
    return _cached_token["access_token"]


def detect_text(
    image_bytes: bytes,
    service_account_json: str,
    *,
    language_hints: list[str] | None = None,
    timeout_seconds: float = 30.0,
) -> str:
    """
    Call Google Cloud Vision API to detect text in an image.

    Returns the extracted full text annotation, or empty string on failure.
    """
    service_account = json.loads(service_account_json)
    access_token = _get_access_token(service_account)

    image_content = base64.b64encode(image_bytes).decode("utf-8")

    request_body: dict[str, Any] = {
        "requests": [
            {
                "image": {"content": image_content},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION", "maxResults": 1}],
            }
        ]
    }
    if language_hints:
        request_body["requests"][0]["imageContext"] = {
            "languageHints": language_hints
        }

    # Bounded outbound timeout (Requirement 10.3): the Vision annotate call uses
    # an explicit timeout (default 30s, caller-overridable) so OCR cannot block
    # indefinitely on a slow upstream. Single attempt — bounded, no retry loop.
    response = httpx.post(
        _VISION_API_URL,
        json=request_body,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()

    responses = data.get("responses", [])
    if not responses:
        return ""

    first_response = responses[0]
    if "error" in first_response:
        raise RuntimeError(
            f"Vision API error: {first_response['error'].get('message', 'unknown')}"
        )

    full_annotation = first_response.get("fullTextAnnotation", {})
    return full_annotation.get("text", "").strip()
