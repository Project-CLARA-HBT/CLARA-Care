from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_control_tower_config_requires_doctor_role() -> None:
    token = _login("alice@research.clara")
    response = client.get(
        "/api/v1/system/control-tower/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_control_tower_config_get_and_put() -> None:
    token = _login("dr@doctor.clara")

    get_response = client.get(
        "/api/v1/system/control-tower/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    payload = get_response.json()
    assert "rag_sources" in payload
    assert "rag_flow" in payload
    assert "careguard_runtime" in payload
    assert "rule_verification_enabled" in payload["rag_flow"]
    assert "nli_model_enabled" in payload["rag_flow"]
    assert "rag_reranker_enabled" in payload["rag_flow"]
    assert "rag_nli_enabled" in payload["rag_flow"]
    assert "rag_graphrag_enabled" in payload["rag_flow"]
    assert "llm_provider" in payload["rag_flow"]
    assert "llm_base_url" in payload["rag_flow"]
    assert "llm_model" in payload["rag_flow"]
    assert "llm_api_key" in payload["rag_flow"]

    payload["rag_flow"]["deepseek_fallback_enabled"] = True
    payload["rag_flow"]["rule_verification_enabled"] = False
    payload["rag_flow"]["llm_provider"] = "hitechcloud_gpt53_codex_high"
    payload["rag_flow"]["llm_base_url"] = "https://platform.hitechcloud.one/v1"
    payload["rag_flow"]["llm_model"] = "gpt-5.3-codex-high"
    payload["rag_flow"]["llm_api_key"] = "masked-test-key"
    put_response = client.put(
        "/api/v1/system/control-tower/config",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert put_response.status_code == 200
    updated = put_response.json()
    assert updated["rag_flow"]["deepseek_fallback_enabled"] is True
    assert updated["rag_flow"]["rule_verification_enabled"] is False
    assert updated["rag_flow"]["llm_provider"] == "hitechcloud_gpt53_codex_high"
    assert updated["rag_flow"]["llm_base_url"] == "https://platform.hitechcloud.one/v1"
    assert updated["rag_flow"]["llm_model"] == "gpt-5.3-codex-high"
    assert updated["rag_flow"]["llm_api_key"] == "masked-test-key"


def test_control_tower_config_put_maps_legacy_verification_enabled() -> None:
    token = _login("dr@doctor.clara")

    get_response = client.get(
        "/api/v1/system/control-tower/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    payload = get_response.json()
    payload["rag_flow"].pop("rule_verification_enabled", None)
    payload["rag_flow"]["verification_enabled"] = False

    put_response = client.put(
        "/api/v1/system/control-tower/config",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert put_response.status_code == 200
    updated = put_response.json()
    assert updated["rag_flow"]["rule_verification_enabled"] is False
    assert "verification_enabled" not in updated["rag_flow"]


def test_careguard_runtime_toggle_get_and_put() -> None:
    token = _login("dr@doctor.clara")

    get_response = client.get(
        "/api/v1/system/careguard/runtime",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    payload = get_response.json()
    assert "external_ddi_enabled" in payload

    put_response = client.put(
        "/api/v1/system/careguard/runtime",
        headers={"Authorization": f"Bearer {token}"},
        json={"external_ddi_enabled": True},
    )
    assert put_response.status_code == 200
    updated = put_response.json()
    assert updated["external_ddi_enabled"] is True
