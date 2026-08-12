"""Minimal HTTPS JSON transport, used only by the Phase-B provider command."""

from __future__ import annotations

import json
import urllib.request
from typing import Any
from urllib.error import HTTPError


class ProviderHttpError(OSError):
    """Sanitized HTTP failure used by the evaluator retry policy.

    The response body may contain router diagnostics and must never be written
    to a benchmark artifact.  Preserve only the status code.
    """

    def __init__(self, status_code: int) -> None:
        super().__init__(f"provider_http_{status_code}")
        self.status_code = status_code


class UrllibJsonTransport:
    def __call__(
        self, path: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            path,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                value = json.loads(response.read())
        except HTTPError as exc:
            raise ProviderHttpError(int(exc.code)) from exc
        if not isinstance(value, dict):
            raise TypeError("provider_response_not_object")
        return value
