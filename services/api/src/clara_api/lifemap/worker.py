"""Standalone LifeMap background worker entry point."""

from __future__ import annotations

import json
import logging
import signal
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from time import perf_counter
from urllib.request import urlopen
from uuid import uuid4

from clara_api.core.config import get_settings
from clara_api.db.session import SessionLocal
from clara_api.lifemap.capture_worker import drain_capture_jobs
from clara_api.lifemap.outbox_metrics import get_lifemap_outbox_metrics
from clara_api.lifemap.outbox_relay import drain_lifemap_outbox

logger = logging.getLogger("clara_api.lifemap.worker")


def _start_health_server(ready: Event, port: int) -> ThreadingHTTPServer:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
            if self.path == "/health/live":
                code = HTTPStatus.OK
            elif self.path == "/health/ready":
                code = HTTPStatus.OK if ready.is_set() else HTTPStatus.SERVICE_UNAVAILABLE
            else:
                code = HTTPStatus.NOT_FOUND
            payload = json.dumps(
                {
                    "status": "ok" if code == HTTPStatus.OK else "unavailable",
                    "metrics": get_lifemap_outbox_metrics().snapshot(),
                },
                separators=(",", ":"),
            ).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), HealthHandler)
    Thread(target=server.serve_forever, name="lifemap-worker-health", daemon=True).start()
    return server


def run_worker(stop: Event | None = None, *, health_port: int | None = None) -> None:
    """Run bounded outbox cycles until SIGINT/SIGTERM or a supplied stop event."""

    settings = get_settings()
    stop_event = stop or Event()
    ready = Event()
    worker_id = uuid4().hex
    server = _start_health_server(ready, health_port or settings.lifemap_worker_health_port)

    def _stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    if stop is None:
        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

    logger.info("lifemap.worker.started", extra={"worker_id": worker_id})
    try:
        while not stop_event.is_set():
            started = perf_counter()
            with SessionLocal() as db:
                drain_lifemap_outbox(
                    db,
                    batch_size=settings.lifemap_outbox_relay_batch_size,
                    worker_id=worker_id,
                    lease_seconds=settings.lifemap_outbox_lease_seconds,
                    base_backoff_seconds=settings.lifemap_outbox_backoff_seconds,
                )
                if settings.lifemap_capture_enabled:
                    drain_capture_jobs(
                        db,
                        worker_id=worker_id,
                        batch_size=min(settings.lifemap_outbox_relay_batch_size, 20),
                    )
            get_lifemap_outbox_metrics().record_cycle(
                (perf_counter() - started) * 1000
            )
            ready.set()
            stop_event.wait(settings.lifemap_outbox_relay_interval_seconds)
    finally:
        ready.clear()
        server.shutdown()
        server.server_close()
        logger.info("lifemap.worker.stopped", extra={"worker_id": worker_id})


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if "--healthcheck" in sys.argv:
        port = get_settings().lifemap_worker_health_port
        with urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=5) as response:
            if response.status != HTTPStatus.OK:
                raise SystemExit(1)
        return
    run_worker()


if __name__ == "__main__":
    main()
