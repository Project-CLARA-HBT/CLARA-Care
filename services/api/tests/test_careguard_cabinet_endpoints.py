from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login_without_consent(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    status_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    required_version = status_response.json()["required_version"]
    accept_response = client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": required_version, "accepted": True},
    )
    assert accept_response.status_code == 200
    return token


def test_cabinet_requires_consent_gate() -> None:
    token = _login_without_consent("consent-required@example.com")
    response = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 428
    assert "miễn trừ trách nhiệm y tế" in response.json()["detail"]


def test_cabinet_lifecycle() -> None:
    token = _login("cabinet-user@example.com")

    get_response = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    assert "items" in get_response.json()

    add_response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "drug_name": "Metformin",
            "dosage": "500mg",
            "quantity": 10,
            "source": "manual",
        },
    )
    assert add_response.status_code == 200
    item_id = add_response.json()["id"]

    patch_response = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "drug_name": "Warfarin",
            "dosage": "3mg",
            "quantity": 14,
            "note": "uống buổi tối",
        },
    )
    assert patch_response.status_code == 200
    patched_item = patch_response.json()
    assert patched_item["drug_name"] == "Warfarin"
    assert patched_item["normalized_name"] == "warfarin"
    assert patched_item["dosage"] == "3mg"
    assert patched_item["quantity"] == 14
    assert patched_item["note"] == "uống buổi tối"

    list_response = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert any(item["id"] == item_id for item in list_response.json()["items"])

    delete_response = client.delete(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True


def test_scan_and_import_detection() -> None:
    token = _login("scan-user@example.com")
    scan_response = client.post(
        "/api/v1/careguard/cabinet/scan-text",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Toa thuoc: Panadol 500mg, ibuprofen 200mg"},
    )
    assert scan_response.status_code == 200
    detections = scan_response.json()["detections"]
    assert len(detections) >= 1

    import_response = client.post(
        "/api/v1/careguard/cabinet/import-detections",
        headers={"Authorization": f"Bearer {token}"},
        json={"detections": detections},
    )
    assert import_response.status_code == 200
    assert import_response.json()["inserted"] >= 1


def test_scan_file_uses_tgc_ocr(monkeypatch) -> None:
    token = _login("scan-file-user@example.com")

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    captured: dict[str, object] = {}
    call_kinds: list[tuple[bool, bool]] = []

    def _fake_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        url = kwargs.get("url", args[0] if args else "")
        captured["url"] = url
        has_files = kwargs.get("files") is not None
        has_json = kwargs.get("json") is not None
        captured["has_files"] = has_files
        captured["has_json"] = has_json
        call_kinds.append((has_files, has_json))

        if has_files:
            return _FakeResponse(422, {"detail": "multipart not supported"})
        if has_json:
            return _FakeResponse(200, {"text": "Hoa don: Panadol 500mg, ibuprofen 200mg"})
        return _FakeResponse(500, {"detail": "unexpected request"})

    monkeypatch.setattr("clara_api.api.v1.endpoints.careguard.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/careguard/cabinet/scan-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("receipt.jpg", b"fake-image-data", "image/jpeg")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ocr_provider"] == "tgc-transhub"
    assert payload["ocr_endpoint"] == "/api/ocr"
    assert len(payload["detections"]) >= 1
    assert any(has_files for has_files, _ in call_kinds)
    assert any(has_json for _, has_json in call_kinds)


def test_auto_ddi_proxy_payload(monkeypatch) -> None:
    token = _login("ddi-user@example.com")
    client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_name": "Warfarin", "source": "manual"},
    )

    captured: dict[str, object] = {}

    def _fake_proxy(path: str, payload: dict[str, object]) -> dict[str, object]:
        captured["path"] = path
        captured["payload"] = payload
        return {
            "risk_tier": "high",
            "ddi_alerts": [{"title": "test"}],
            "recommendations": ["test"],
            "citations": [{"source": "RxNorm", "url": "https://rxnav.nlm.nih.gov/"}],
        }

    monkeypatch.setattr("clara_api.api.v1.endpoints.careguard.proxy_ml_post", _fake_proxy)

    response = client.post(
        "/api/v1/careguard/cabinet/auto-ddi-check",
        headers={"Authorization": f"Bearer {token}"},
        json={"allergies": ["penicillin"], "symptoms": [], "labs": {}},
    )
    assert response.status_code == 200
    assert captured["path"] == "/v1/careguard/analyze"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "medications" in payload
    assert payload["external_ddi_enabled"] is False
    body = response.json()
    assert "attribution" in body
    assert body["attribution"]["channel"] == "careguard"
    assert body["attribution"]["mode"] == "local_only"
    assert body["attribution"]["citation_count"] == 1
