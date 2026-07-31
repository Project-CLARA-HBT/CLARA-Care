from __future__ import annotations

from types import SimpleNamespace

from clara_ml.model_router.encoder_shadow import (
    public_encoder_shadow_metadata,
    run_encoder_slm_shadow,
)


class _Response:
    def __init__(self, payload: object, *, content: bytes = b"{}") -> None:
        self._payload = payload
        self.content = content
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _Client:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url: str, **kwargs: object) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self.response


def _settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "encoder_slm_shadow_enabled": True,
        "encoder_slm_shadow_url": "http://encoder.internal/v1/clinical-route",
        "encoder_slm_shadow_api_key": "test-only-secret",
        "encoder_slm_shadow_model_id": "vi-clinical-encoder-2026-07",
        "encoder_slm_shadow_timeout_ms": 700,
        "encoder_slm_shadow_max_input_chars": 1200,
        "model_registry_enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_encoder_shadow_is_disabled_without_network_call() -> None:
    result = run_encoder_slm_shadow(
        "Tôi bị đau đầu",
        settings=_settings(encoder_slm_shadow_enabled=False),
        client_factory=lambda **_: (_ for _ in ()).throw(AssertionError("network must not run")),
    )

    assert result.state == "disabled"
    assert public_encoder_shadow_metadata(result) == {
        "state": "disabled",
        "reason": "feature_flag_disabled",
    }


def test_encoder_shadow_redacts_and_bounds_input_and_publishes_categories_only() -> None:
    client = _Client(
        _Response(
            {
                "schema_version": "clara.encoder-slm-shadow.v1",
                "intent": "symptom_triage",
                "risk_level": "medium",
                "entity_categories": ["symptom", "medication"],
                "negated": False,
                "temporality": "current",
                "experiencer": "self_or_unspecified",
                "language": "vi",
            }
        )
    )
    result = run_encoder_slm_shadow(
        "Gọi cho tôi 0901234567, tôi đau đầu sau khi uống Panadol.",
        settings=_settings(encoder_slm_shadow_max_input_chars=80),
        client_factory=lambda **_: client,
    )

    assert result.state == "available"
    sent = client.calls[0]["json"]
    assert isinstance(sent, dict)
    assert "0901234567" not in str(sent)
    assert "[REDACTED_PHONE]" in str(sent)
    public = public_encoder_shadow_metadata(result)
    assert public["state"] == "available"
    assert "confidence" not in str(public)
    assert "Panadol" not in str(public)
    assert public["prediction"] == {
        "schema_version": "clara.encoder-slm-shadow.v1",
        "intent": "symptom_triage",
        "risk_level": "medium",
        "entity_categories": ["symptom", "medication"],
        "negated": False,
        "temporality": "current",
        "experiencer": "self_or_unspecified",
        "language": "vi",
    }


def test_encoder_shadow_rejects_extra_or_unbounded_response_fields() -> None:
    client = _Client(
        _Response(
            {
                "schema_version": "clara.encoder-slm-shadow.v1",
                "intent": "general_health_qa",
                "risk_level": "low",
                "entity_categories": [],
                "negated": False,
                "temporality": "unspecified",
                "experiencer": "self_or_unspecified",
                "language": "vi",
                "confidence": 0.99,
            }
        )
    )

    result = run_encoder_slm_shadow(
        "Xin chào",
        settings=_settings(),
        client_factory=lambda **_: client,
    )

    assert result.state == "invalid"
    assert result.reason == "response_contract_invalid"


def test_encoder_shadow_endpoint_failure_is_safe_unavailable() -> None:
    result = run_encoder_slm_shadow(
        "Tôi bị đau đầu",
        settings=_settings(encoder_slm_shadow_url="not-a-url"),
    )

    assert result.state == "unavailable"
    assert result.reason == "endpoint_invalid"
