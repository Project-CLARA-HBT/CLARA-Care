from __future__ import annotations

import pytest
from fastapi import HTTPException

from clara_api.api.v1.endpoints import careguard


def test_drugbank_status_returns_ready_required_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readiness = {
        "state": "ready",
        "version": "drugbank-test",
        "pair_count": 12,
        "manifest_matches_index": True,
        "required": True,
    }
    monkeypatch.setattr(
        careguard,
        "proxy_ml_get",
        lambda *_args, **_kwargs: {"drugbank": readiness},
    )

    assert careguard.drugbank_status(token=object()) == readiness


def test_drugbank_status_returns_typed_503_when_required_source_is_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readiness = {
        "state": "degraded",
        "version": "drugbank-stale",
        "pair_count": 12,
        "manifest_matches_index": False,
        "required": True,
    }
    monkeypatch.setattr(
        careguard,
        "proxy_ml_get",
        lambda *_args, **_kwargs: {"drugbank": readiness},
    )

    with pytest.raises(HTTPException) as raised:
        careguard.drugbank_status(token=object())

    assert raised.value.status_code == 503
    assert raised.value.detail == {
        "code": "drugbank_required_unavailable",
        "readiness": readiness,
    }


def test_unavailable_ddi_attribution_does_not_claim_fallback_sources() -> None:
    payload = {
        "ddi_alerts": [],
        "ddi_status": {
            "state": "unavailable",
            "conclusion_available": False,
            "required_source": "drugbank",
            "reason": "drugbank_unavailable",
        },
        "metadata": {
            "fallback_used": True,
            "source_used": [],
            "source_errors": {"drugbank": ["required_source_unavailable"]},
        },
    }

    attributed = careguard._attach_careguard_attribution(
        payload,
        external_ddi_enabled=True,
    )

    assert attributed["attribution"]["mode"] == "unavailable"
    assert attributed["attribution"]["sources"] == []
    assert attributed["attribution"]["source_used"] == []
    assert attributed["attribution"]["fallback_used"] is True
