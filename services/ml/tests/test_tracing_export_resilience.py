"""Export-failure resilience for the optional OTEL tracer (task 6.2, Req 6.5).

Requirement 6.5: *If the trace exporter is unavailable or errors, THEN
CLARA_ML SHALL continue to serve the request and SHALL NOT propagate the export
failure into the response.*

These tests drive the tracing wrapper with a deliberately hostile fake tracer
whose span operations (attribute recording and close/flush/export on span exit)
all raise. They assert that:

* ``request_span`` / ``SpanHandle.stage`` still run the wrapped user code and
  return its result, swallowing every tracing failure;
* a genuine *user* exception still propagates (we only swallow tracing-machinery
  failures, never the caller's error), even when span close also raises;
* exporter/provider construction failures in ``init_tracing`` degrade to a
  no-op tracer rather than crashing startup.
"""

from __future__ import annotations

import pytest

from clara_ml.observability import tracing
from clara_ml.observability.tracing import Tracer, request_span


class _ExplodingSpan:
    """A span whose every operation raises (simulates a broken exporter)."""

    def set_attribute(self, key: str, value: object) -> None:
        raise RuntimeError(f"exporter attribute boom: {key}={value}")


class _ExplodingSpanCM:
    """Context manager whose ``__exit__`` raises (simulates export-on-flush)."""

    def __enter__(self) -> _ExplodingSpan:
        return _ExplodingSpan()

    def __exit__(self, *exc: object) -> bool:
        raise RuntimeError("exporter flush/export boom")


class _ExplodingTracer:
    """Fake OTEL tracer that hands out spans which fail on use and on close."""

    def start_as_current_span(self, name: str) -> _ExplodingSpanCM:
        _ = name
        return _ExplodingSpanCM()


class _Settings:
    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class _ExplodingProvider:
    """Provider whose force_flush and shutdown both raise (export-on-teardown)."""

    def __init__(self) -> None:
        self.flush_called = False
        self.shutdown_called = False

    def force_flush(self) -> None:
        self.flush_called = True
        raise RuntimeError("force_flush export boom")

    def shutdown(self) -> None:
        self.shutdown_called = True
        raise RuntimeError("shutdown export boom")


def test_request_span_returns_result_when_export_fails() -> None:
    tracer = Tracer(_ExplodingTracer())
    assert tracer.enabled is True

    order: list[str] = []
    with tracer.request_span("request", {"stage": "answer"}) as span:
        # Attribute recording hits the exploding span -> must be swallowed.
        span.set_attribute("status", "ok")
        with span.stage("retrieve", {"source_count": 3}) as child:
            child.set_attribute("status", "ok")
            order.append("inner")
        order.append("outer")

    # User code ran fully and the (failing) span close did not leak out.
    assert order == ["inner", "outer"]


def test_wrapped_result_is_returned_through_failing_tracer() -> None:
    tracer = Tracer(_ExplodingTracer())

    def traced_unit_of_work() -> int:
        with tracer.request_span("request", {"stage": "answer"}) as span:
            with span.stage("synthesize") as child:
                child.set_attribute("status", "ok")
            return 42

    assert traced_unit_of_work() == 42


def test_module_level_request_span_swallows_export_failure() -> None:
    tracer = Tracer(_ExplodingTracer())
    with request_span(tracer, "request", {"role": "doctor"}) as span:
        with span.stage("verify", {"verdict": "supported"}):
            pass
    # Reaching here without raising is the assertion.


def test_user_exception_propagates_even_when_export_fails() -> None:
    tracer = Tracer(_ExplodingTracer())
    with pytest.raises(ValueError, match="user error"):
        with tracer.request_span("request") as span:
            span.set_attribute("status", "ok")
            raise ValueError("user error")


def test_init_tracing_construction_failure_degrades_to_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a: object, **_k: object) -> object:
        raise RuntimeError("exporter construction boom")

    monkeypatch.setattr(tracing, "_OTEL_AVAILABLE", True, raising=False)
    monkeypatch.setattr(tracing, "OTLPSpanExporter", _boom, raising=False)

    tracer = tracing.init_tracing(
        _Settings(otel_export_enabled=True, otel_export_endpoint="http://collector")
    )
    assert tracer.enabled is False
    # The degraded tracer is still fully usable as a no-op.
    with tracer.request_span("request") as span:
        span.set_attribute("status", "ok")


def test_init_tracing_noop_when_disabled_or_unconfigured() -> None:
    assert (
        tracing.init_tracing(
            _Settings(otel_export_enabled=False, otel_export_endpoint="http://x")
        ).enabled
        is False
    )
    assert (
        tracing.init_tracing(
            _Settings(otel_export_enabled=True, otel_export_endpoint="")
        ).enabled
        is False
    )


def test_shutdown_swallows_force_flush_and_shutdown_failures() -> None:
    provider = _ExplodingProvider()
    tracer = Tracer(_ExplodingTracer(), provider=provider)

    # A teardown whose flush AND shutdown both raise must not propagate, and
    # must still attempt the shutdown after the flush fails (Req 6.5).
    tracer.shutdown()

    assert provider.flush_called is True
    assert provider.shutdown_called is True


def test_shutdown_is_noop_without_a_provider() -> None:
    # No provider configured (the disabled/unconfigured no-op path) -> nothing
    # to flush or shut down, and certainly nothing to raise.
    Tracer(_ExplodingTracer()).shutdown()
    Tracer().shutdown()
