"""Standalone LifeMap worker liveness and readiness contracts."""

import json
from threading import Event
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from clara_api.lifemap.worker import _start_health_server


def test_worker_health_server_distinguishes_liveness_and_readiness() -> None:
    ready = Event()
    server = _start_health_server(ready, 0)
    port = server.server_address[1]
    try:
        with urlopen(f"http://127.0.0.1:{port}/health/live", timeout=2) as response:
            assert response.status == 200

        with pytest.raises(HTTPError) as unavailable:
            urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=2)
        assert unavailable.value.code == 503

        ready.set()
        with urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=2) as response:
            assert response.status == 200
            payload = json.load(response)
            assert set(payload["metrics"]) == {
                "outcomes",
                "cycles",
                "cycle_p95_ms",
            }

        with pytest.raises(HTTPError) as missing:
            urlopen(f"http://127.0.0.1:{port}/unknown", timeout=2)
        assert missing.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
