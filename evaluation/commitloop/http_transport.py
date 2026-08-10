"""Minimal HTTPS JSON transport, used only by the Phase-B provider command."""

from __future__ import annotations

import json
import urllib.request
from typing import Any


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
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read())
        if not isinstance(value, dict):
            raise TypeError("provider_response_not_object")
        return value
